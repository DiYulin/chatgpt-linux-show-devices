#!/usr/bin/env python3
"""Check package payload ownership, permissions, and trigger wiring without installing it."""

import argparse
import io
import subprocess
import tarfile
from pathlib import Path


def members(package, option):
    data = subprocess.check_output(['dpkg-deb', option, str(package)])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        result = {}
        for entry in archive.getmembers():
            if entry.uid != 0 or entry.gid != 0:
                raise SystemExit(f'Non-root package owner: {entry.name}')
            if entry.mode & 0o022:
                raise SystemExit(f'Writable package entry: {entry.name}')
            if not (entry.isfile() or entry.isdir()):
                raise SystemExit(f'Unexpected link or special entry: {entry.name}')
            if entry.isfile():
                result[entry.name.removeprefix('./')] = archive.extractfile(entry).read()
        return result


def verify(package):
    payload = members(package, '--fsys-tarfile')
    expected = {
        'usr/bin/chatgpt-show-other-devices',
        'usr/lib/chatgpt-show-other-devices/repair.py',
        'usr/share/doc/chatgpt-show-other-devices/README.md',
        'usr/share/doc/chatgpt-show-other-devices/copyright',
    }
    if set(payload) != expected:
        raise SystemExit('Unexpected package payload: ' + repr(set(payload) ^ expected))
    control = members(package, '--ctrl-tarfile')
    if control['triggers'].strip() != b'interest-noawait /usr/lib/chatgpt/resources/app.asar':
        raise SystemExit('Unexpected file trigger.')
    if b'--ensure --quiet' not in control['postinst'] or b'--restore --quiet' not in control['prerm']:
        raise SystemExit('Package lifecycle wiring is incomplete.')
    compile(payload['usr/lib/chatgpt-show-other-devices/repair.py'], 'repair.py', 'exec')
    print('Package payload, permissions, Python syntax, and lifecycle hooks verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    verify(parser.parse_args().package)
