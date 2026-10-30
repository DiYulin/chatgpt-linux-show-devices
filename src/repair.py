#!/usr/bin/python3
"""Maintain the requested UI-only change after Debian package updates."""

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path

SOURCE = Path('/usr/lib/chatgpt/resources/app.asar')
STATE_DIR = Path('/var/lib/chatgpt-show-other-devices')
LEGACY_BACKUP = SOURCE.with_name('app.asar.before-devices-unhide-26.1027.30824')
LEGACY_ORIGINAL = '51b2f5e45e42b9123f067c697c4cf53fac35b4af9c46aa3c716f13922bcf9e1b'
LEGACY_PATCHED = '131c71b5eb5539f0176f466beebc28658356bbc28e8239a75a5a2c939ac95233'
GATE = '782640499'
MARKER = b'!1/*show-ui*/'
IDENTIFIER = rb'[A-Za-z_$][A-Za-z0-9_$]*'
ASSIGNMENT = re.compile(rb'(?<![A-Za-z0-9_$])(' + IDENTIFIER + rb')=(' + IDENTIFIER + rb'\(`782640499`\))')


class Unsupported(RuntimeError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def archive(path):
    with path.open('rb') as stream:
        prefix = stream.read(16)
        if len(prefix) != 16:
            raise Unsupported('The archive header is incomplete.')
        size, pickle_size, _, json_size = struct.unpack('<4I', prefix)
        if size != 4 or not 0 < json_size < 32 * 1024 * 1024 or json_size + 8 > pickle_size:
            raise Unsupported('The archive header format changed.')
        raw = stream.read(json_size)
    return json.loads(raw), raw, 8 + pickle_size


def node(header, path):
    result = header
    for name in path.split('/'):
        result = result['files'][name]
    return result


def entries(header, prefix=''):
    for name, entry in header.get('files', {}).items():
        path = prefix + name
        if 'files' in entry:
            yield from entries(entry, path + '/')
        else:
            yield path, entry


def content(path, header, base, name):
    entry = node(header, name)
    if entry.get('unpacked') or entry.get('link') or entry['size'] > 16 * 1024 * 1024:
        raise Unsupported('The target asset layout changed.')
    with path.open('rb') as stream:
        stream.seek(base + int(entry['offset']))
        result = stream.read(entry['size'])
    if len(result) != entry['size']:
        raise Unsupported('The target asset is truncated.')
    return result


def read_json(path, default=None):
    if not path.exists():
        return default
    if path.is_symlink():
        raise Unsupported('Unexpected state symbolic link.')
    return json.loads(path.read_text())


def atomic_json(path, data):
    fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def sync_directory(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Repair:
    def __init__(self, source=SOURCE, state_dir=STATE_DIR, legacy_backup=LEGACY_BACKUP,
                 require_root=True):
        self.source = Path(source)
        self.state_dir = Path(state_dir)
        self.backups = self.state_dir / 'backups'
        self.legacy_backup = Path(legacy_backup)
        self.require_root = require_root

    @contextlib.contextmanager
    def locked(self):
        if self.require_root and os.geteuid() != 0:
            raise RuntimeError('Administrator privileges are required.')
        for path in [self.state_dir, self.backups]:
            if path.is_symlink():
                raise Unsupported('Unexpected state directory symbolic link.')
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
            if self.require_root and (path.stat().st_uid != 0 or path.stat().st_mode & 0o022):
                raise Unsupported('State directory permissions are unsafe.')
        lock = self.state_dir / 'repair.lock'
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'r+') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def validate_source(self):
        if self.source.is_symlink() or not self.source.is_file():
            raise Unsupported('The installed app archive is missing or is a symbolic link.')
        metadata = self.source.stat()
        if self.require_root and (metadata.st_uid != 0 or metadata.st_mode & 0o022):
            raise Unsupported('Unexpected app archive ownership or permissions.')

    def record_result(self, result):
        result = dict(result, checked_at=now())
        atomic_json(self.state_dir / 'last-result.json', result)
        return result

    def backup(self, original, version, expected_hash):
        safe_version = re.sub(r'[^A-Za-z0-9_.+-]', '_', version)
        destination = self.backups / (safe_version + '-' + expected_hash[:16] + '.asar')
        if destination.exists():
            if destination.is_symlink() or sha256(destination) != expected_hash:
                raise Unsupported('The existing original backup does not match.')
            return destination
        try:
            os.link(original, destination)
        except OSError:
            shutil.copy2(original, destination)
        if sha256(destination) != expected_hash:
            destination.unlink(missing_ok=True)
            raise Unsupported('Original backup verification failed.')
        return destination

    def save_state(self, state):
        atomic_json(self.state_dir / 'state.json', dict(state, installed_at=now()))
        # Keep the current original plus one previous original. Only our own backups are eligible.
        current = Path(state['backup'])
        others = sorted((p for p in self.backups.glob('*.asar') if p != current),
                        key=lambda p: p.stat().st_ctime_ns, reverse=True)
        for stale in others[1:]:
            stale.unlink()

    def ensure(self):
        with self.locked():
            if not self.source.exists():
                return self.record_result({'status': 'app_not_installed'})
            self.validate_source()
            original_hash = sha256(self.source)
            state = read_json(self.state_dir / 'state.json', {})
            if original_hash == state.get('patched_sha256'):
                return self.record_result({'status': 'already_enabled', 'version': state['version']})
            header, raw_header, base = archive(self.source)
            package = json.loads(content(self.source, header, base, 'package.json'))
            if package.get('name') != 'openai-codex-electron' or not isinstance(package.get('version'), str):
                raise Unsupported('The application identity changed.')
            version = package['version']
            if original_hash == LEGACY_PATCHED:
                if (self.legacy_backup.is_symlink() or not self.legacy_backup.is_file()
                        or sha256(self.legacy_backup) != LEGACY_ORIGINAL):
                    raise Unsupported('The earlier verified original backup is unavailable.')
                backup = self.backup(self.legacy_backup, version, LEGACY_ORIGINAL)
                self.save_state({'version': version, 'original_sha256': LEGACY_ORIGINAL,
                                 'patched_sha256': LEGACY_PATCHED, 'backup': str(backup),
                                 'kind': 'adopted_existing_patch'})
                return self.record_result({'status': 'adopted_existing_patch', 'version': version})
            candidates = [(name, entry) for name, entry in entries(header)
                          if re.fullmatch(r'webview/assets/remote-connections-settings-[A-Za-z0-9_-]+\.js', name)]
            if len(candidates) != 1:
                raise Unsupported('The connection settings asset layout changed; the app was left untouched.')
            asset_name, entry = candidates[0]
            asset = content(self.source, header, base, asset_name)
            matches = list(ASSIGNMENT.finditer(asset))
            if len(matches) != 1:
                raise Unsupported('The known UI-only gate expression changed; the app was left untouched.')
            match = matches[0]
            gate_variable = match.group(1)
            visibility = list(re.finditer(rb'(?<![A-Za-z0-9_$])(' + IDENTIFIER
                                          + rb')=!' + re.escape(gate_variable) + rb'(?=[,;])', asset))
            if len(visibility) != 1:
                raise Unsupported('The UI visibility relationship changed; the app was left untouched.')
            visible_variable = visibility[0].group(1)
            if not re.search(rb'showControlOtherDevices:' + re.escape(visible_variable)
                             + rb'(?=[,}])', asset):
                raise Unsupported('The gate is no longer linked only to this UI entry; the app was left untouched.')
            if b'Control other devices' not in asset:
                raise Unsupported('The expected connection UI content is missing.')
            expression = match.group(2)
            if len(expression) < len(MARKER):
                raise Unsupported('The replacement expression would change archive offsets.')
            replacement = MARKER.ljust(len(expression), b' ')
            patched_asset = asset[:match.start(2)] + replacement + asset[match.end(2):]
            old_hash = hashlib.sha256(asset).hexdigest()
            new_hash = hashlib.sha256(patched_asset).hexdigest()
            integrity = entry.get('integrity', {})
            if (integrity.get('algorithm') != 'SHA256' or integrity.get('hash') != old_hash
                    or integrity.get('blocks') != [old_hash]
                    or len(asset) > integrity.get('blockSize', 0)
                    or raw_header.count(old_hash.encode()) != 2):
                raise Unsupported('The target file integrity layout changed; the app was left untouched.')
            patched_header = raw_header.replace(old_hash.encode(), new_hash.encode())
            decoded = json.loads(patched_header)
            node(decoded, asset_name)['integrity'] = integrity
            if decoded != header or len(patched_asset) != len(asset):
                raise Unsupported('The proposed patch would change unrelated archive metadata.')
            metadata = self.source.stat()
            fd, temporary_name = tempfile.mkstemp(prefix='.chatgpt-show-devices-', dir=self.source.parent)
            os.close(fd)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(self.source, temporary)
                with temporary.open('r+b') as stream:
                    stream.seek(16)
                    stream.write(patched_header)
                    stream.seek(base + int(entry['offset']))
                    stream.write(patched_asset)
                    stream.flush()
                    os.fsync(stream.fileno())
                if self.require_root:
                    os.chown(temporary, metadata.st_uid, metadata.st_gid)
                test_header, _, test_base = archive(temporary)
                if content(temporary, test_header, test_base, asset_name) != patched_asset:
                    raise Unsupported('Patched archive verification failed.')
                if temporary.stat().st_size != metadata.st_size or sha256(self.source) != original_hash:
                    raise Unsupported('The app changed during preparation; no changes made.')
                patched_hash = sha256(temporary)
                backup = self.backup(self.source, version, original_hash)
                new_state = {'version': version, 'original_sha256': original_hash,
                             'patched_sha256': patched_hash, 'backup': str(backup),
                             'asset': asset_name, 'kind': 'guarded_ui_patch'}
                # Save recovery metadata before the atomic replacement to survive interruption.
                self.save_state(new_state)
                os.replace(temporary, self.source)
                sync_directory(self.source.parent)
                return self.record_result({'status': 'patched', 'version': version,
                                           'restart_required': True})
            finally:
                temporary.unlink(missing_ok=True)

    def restore(self):
        with self.locked():
            state = read_json(self.state_dir / 'state.json', {})
            if not state or not self.source.exists():
                return self.record_result({'status': 'nothing_to_restore'})
            self.validate_source()
            current = sha256(self.source)
            if current == state.get('original_sha256'):
                return self.record_result({'status': 'already_original'})
            if current != state.get('patched_sha256'):
                return self.record_result({'status': 'newer_app_left_untouched'})
            backup = Path(state['backup'])
            if backup.parent != self.backups or backup.is_symlink() or sha256(backup) != state['original_sha256']:
                raise Unsupported('The verified backup is missing or invalid.')
            fd, name = tempfile.mkstemp(prefix='.chatgpt-restore-devices-', dir=self.source.parent)
            os.close(fd)
            temporary = Path(name)
            try:
                shutil.copy2(backup, temporary)
                if sha256(temporary) != state['original_sha256']:
                    raise Unsupported('Restored archive verification failed.')
                with temporary.open('rb') as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary, self.source)
                sync_directory(self.source.parent)
                return self.record_result({'status': 'restored', 'restart_required': True})
            finally:
                temporary.unlink(missing_ok=True)

    def status(self):
        state = read_json(self.state_dir / 'state.json', {})
        result = read_json(self.state_dir / 'last-result.json', {})
        current = sha256(self.source) if self.source.is_file() else None
        return {'enabled': bool(current and current == state.get('patched_sha256')),
                'version': state.get('version'), 'backup': state.get('backup'),
                'last_result': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--ensure', action='store_true')
    modes.add_argument('--restore', action='store_true')
    modes.add_argument('--status', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    repair = Repair()
    try:
        result = repair.ensure() if args.ensure else repair.restore() if args.restore else repair.status()
    except Exception as error:
        result = {'status': 'skipped', 'reason': str(error), 'checked_at': now()}
        if os.geteuid() == 0:
            try:
                with repair.locked():
                    repair.record_result(result)
            except Exception:
                pass
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 1
    if not args.quiet or result.get('status') in ['patched', 'adopted_existing_patch', 'restored']:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
