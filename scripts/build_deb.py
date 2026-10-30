#!/usr/bin/env python3
"""Build the companion package using only Python's standard library and dpkg-deb."""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}', version):
        raise SystemExit('VERSION must contain a numeric major.minor.patch version.')
    if not shutil.which('dpkg-deb'):
        raise SystemExit('dpkg-deb is required to build the Debian package.')
    output.mkdir(parents=True, exist_ok=True)
    package = output / f'chatgpt-show-other-devices_{version}_all.deb'
    with tempfile.TemporaryDirectory(prefix='show-devices-build-') as temporary:
        stage = Path(temporary) / 'package'
        stage.mkdir()
        mapping = {
            'src/repair.py': ('usr/lib/chatgpt-show-other-devices/repair.py', 0o644),
            'packaging/cli.sh': ('usr/bin/chatgpt-show-other-devices', 0o755),
            'LICENSE': ('usr/share/doc/chatgpt-show-other-devices/copyright', 0o644),
            'README.md': ('usr/share/doc/chatgpt-show-other-devices/README.md', 0o644),
        }
        for source, (destination, mode) in mapping.items():
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, target)
            target.chmod(mode)
        control = stage / 'DEBIAN'
        control.mkdir()
        (control / 'control').write_text((ROOT / 'packaging/debian/control.in').read_text().format(version=version))
        (control / 'control').chmod(0o644)
        for name in ['triggers', 'postinst', 'prerm', 'postrm']:
            target = control / name
            shutil.copyfile(ROOT / 'packaging/debian' / name, target)
            target.chmod(0o644 if name == 'triggers' else 0o755)
            if name != 'triggers':
                subprocess.run(['/bin/sh', '-n', str(target)], check=True)
        for path in [stage, *stage.rglob('*')]:
            if path.is_dir():
                path.chmod(0o755)
        environment = dict(os.environ)
        # A fixed default makes source builds repeatable; release builders may override it.
        environment.setdefault('SOURCE_DATE_EPOCH', '0')
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(stage), str(package)],
                       check=True, env=environment)
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {package.name}\n')
    print(package)
    print(digest)
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().output_dir.resolve())
