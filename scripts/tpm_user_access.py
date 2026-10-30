#!/usr/bin/env python3
"""Optional, explicit per-user TPM access; never sends commands to the TPM."""

import argparse
import fcntl
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

DEVICE = Path('/dev/tpmrm0')
RULE = Path('/etc/udev/rules.d/72-chatgpt-tpm-user-access.rules')
STATE = Path('/var/lib/chatgpt-tpm-user-access')


def rule_text(uid, legacy=False):
    no_mask = '' if legacy else '-n '
    return ('# Explicit local-user access to the TPM resource-manager device.\n'
            '# Does not grant access to the raw /dev/tpm0 device.\n'
            'ACTION=="add|change", SUBSYSTEM=="tpmrm", KERNEL=="tpmrm0", '
            f'RUN+="/usr/bin/setfacl {no_mask}-m u:{uid}:rw /dev/%k"\n')


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def check_udev():
    version = run('/usr/bin/udevadm', '--version').strip().split()[0]
    if not version.isdigit() or int(version) < 254:
        raise RuntimeError('This optional tool requires udevadm 254 or newer for rule verification.')


def probe(account):
    code = ('import os; fd=os.open("/dev/tpmrm0",os.O_RDWR|os.O_NONBLOCK); '
            'os.close(fd)')
    kwargs = {}
    if os.geteuid() == 0:
        kwargs = {'user': account.pw_uid, 'group': account.pw_gid,
                  'extra_groups': os.getgrouplist(account.pw_name, account.pw_gid)}
    elif os.geteuid() != account.pw_uid:
        raise RuntimeError('Run the non-root check as the selected user.')
    result = subprocess.run(['/usr/bin/python3', '-I', '-c', code],
                            capture_output=True, text=True, **kwargs)
    errors = result.stderr.strip().splitlines()
    return {'open_succeeded': result.returncode == 0,
            'error': (errors[-1] if errors else 'Device open failed.') if result.returncode else None}


def write_atomic(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.chatgpt-tpm-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        Path(name).unlink(missing_ok=True)


def user_entry(acl, uid):
    match = re.search(rf'^user:{uid}:([rwx-]{{3}})(?:\s|$)', acl, re.M)
    return match.group(1) if match else None


def check_mask(acl):
    # Keep the shared ACL mask unchanged: do not widen other entries' access.
    match = re.search(r'^mask::([rwx-]{3})(?:\s|$)', acl, re.M)
    if match is None:
        match = re.search(r'^group::([rwx-]{3})(?:\s|$)', acl, re.M)
    if match is None or not match.group(1).startswith('rw'):
        raise RuntimeError('The existing ACL mask/group lacks read/write access; '
                           'an administrator must review this device policy manually.')


def restore_entry(uid, original_entry):
    if original_entry is None:
        acl = run('/usr/bin/getfacl', '-n', '-c', str(DEVICE))
        if user_entry(acl, uid) is not None:
            run('/usr/bin/setfacl', '-n', '-x', f'u:{uid}', str(DEVICE))
    else:
        run('/usr/bin/setfacl', '-n', '-m', f'u:{uid}:{original_entry}', str(DEVICE))


def repair(account, restore=False):
    if os.geteuid() != 0:
        raise RuntimeError('System administrator authentication is required.')
    check_udev()
    if STATE.is_symlink():
        raise RuntimeError('Unexpected state directory link.')
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o077:
        raise RuntimeError('Unexpected state directory permissions.')
    for name in ['lock', 'state.json', 'original-acl.txt']:
        path = STATE / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError('Unexpected state file type.')
    with (STATE / 'lock').open('a') as lock:
        os.chmod(STATE / 'lock', 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        return repair_locked(account, restore)


def repair_locked(account, restore):
    record_path = STATE / 'state.json'
    record = json.loads(record_path.read_text()) if record_path.exists() else None
    if record and (record['uid'] != account.pw_uid or record['device'] != str(DEVICE)):
        raise RuntimeError('A different local user or device already owns this access rule.')
    expected = rule_text(account.pw_uid)
    allowed = [expected, rule_text(account.pw_uid, legacy=True)] if record else []
    if RULE.is_symlink() or (RULE.exists() and RULE.read_text() not in allowed):
        raise RuntimeError('An unrelated rule already exists; no changes made.')
    if restore:
        if record is None:
            return {'status': 'nothing_to_restore'}
        RULE.unlink(missing_ok=True)
        run('/usr/bin/udevadm', 'control', '--reload-rules')
        restore_entry(account.pw_uid, record['original_user_entry'])
        record['enabled'] = False
        write_atomic(record_path, json.dumps(record, indent=2) + '\n', 0o600)
        return {'status': 'restored'}

    acl = run('/usr/bin/getfacl', '-n', '-p', str(DEVICE))
    check_mask(acl)
    if record is None:
        record = {'uid': account.pw_uid, 'user': account.pw_name,
                  'device': str(DEVICE), 'original_user_entry': user_entry(acl, account.pw_uid)}
        write_atomic(STATE / 'original-acl.txt', acl, 0o600)
    record['enabled'] = False
    write_atomic(record_path, json.dumps(record, indent=2) + '\n', 0o600)
    try:
        write_atomic(RULE, expected, 0o644)
        run('/usr/bin/udevadm', 'verify', str(RULE))
        run('/usr/bin/udevadm', 'control', '--reload-rules')
        run('/usr/bin/setfacl', '-n', '-m', f'u:{account.pw_uid}:rw', str(DEVICE))
        sys_path = run('/usr/bin/udevadm', 'info', '--query=path', '--name=' + str(DEVICE)).strip()
        if not sys_path.startswith('/devices/') or '..' in sys_path.split('/'):
            raise RuntimeError('Unexpected device path from udevadm.')
        run('/usr/bin/udevadm', 'trigger', '--action=change', '/sys' + sys_path)
        run('/usr/bin/udevadm', 'settle', '--timeout=10')
        result = probe(account)
        if not result['open_succeeded']:
            raise RuntimeError('The selected user still cannot open the TPM device: ' + str(result['error']))
        record['enabled'] = True
        write_atomic(record_path, json.dumps(record, indent=2) + '\n', 0o600)
        return {'status': 'applied', 'device': str(DEVICE), 'uid': account.pw_uid,
                'persistent_rule': str(RULE), 'device_open_verified': True}
    except Exception:
        RULE.unlink(missing_ok=True)
        run('/usr/bin/udevadm', 'control', '--reload-rules')
        restore_entry(account.pw_uid, record['original_user_entry'])
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True, help='Explicit non-root local account name')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--restore', action='store_true')
    modes.add_argument('--preview-rule', type=Path, metavar='FILE.rules')
    args = parser.parse_args()
    account = pwd.getpwnam(args.user)
    if account.pw_uid == 0:
        raise RuntimeError('Select a non-root local user.')
    if args.preview_rule:
        check_udev()
        args.preview_rule.write_text(rule_text(account.pw_uid))
        print(run('/usr/bin/udevadm', 'verify', str(args.preview_rule)), end='')
        return
    if DEVICE.is_symlink() or not DEVICE.exists() or not stat.S_ISCHR(DEVICE.stat().st_mode):
        raise RuntimeError('The expected TPM resource-manager character device is unavailable.')
    if args.check:
        result = {'device': str(DEVICE), 'uid': account.pw_uid, **probe(account)}
    else:
        result = repair(account, restore=args.restore)
    print(json.dumps(result, indent=2))
    if args.check and not result['open_succeeded']:
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
