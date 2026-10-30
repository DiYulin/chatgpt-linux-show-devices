import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('repair', Path(__file__).resolve().parents[1] / 'src/repair.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def make_archive(path, version='26.1101.1', variable='d', getter='zn', visible='U',
                 linked=True, duplicate=False, damaged=False):
    text = ('function Settings(){let ' + variable + '=' + getter + '(`782640499`),'
            + visible + '=!' + variable + ';return x({showControlOtherDevices:'
            + (visible if linked else 'unrelated') + ',title:"Control other devices"});}')
    if duplicate:
        text += 'let another=gate(`782640499`);'
    asset_name = 'webview/assets/remote-connections-settings-' + version + '.js'
    # Use the same hashed asset name shape as the real application.
    asset_name = asset_name.replace(version, version.replace('.', '_'))
    files = {
        'package.json': json.dumps({'name': 'openai-codex-electron', 'version': version}).encode(),
        asset_name: text.encode(),
        'unrelated.js': b'const unchanged = "not part of the connection UI";',
    }
    header = {'files': {}}
    offset = 0
    for name, data in files.items():
        node = header
        for part in name.split('/')[:-1]:
            node = node['files'].setdefault(part, {'files': {}})
        digest = hashlib.sha256(data).hexdigest()
        node['files'][name.split('/')[-1]] = {
            'size': len(data), 'offset': str(offset),
            'integrity': {'algorithm': 'SHA256', 'hash': digest, 'blockSize': 4194304, 'blocks': [digest]},
        }
        offset += len(data)
    if damaged:
        repair.node(header, asset_name)['integrity']['hash'] = '0' * 64
    raw = json.dumps(header, separators=(',', ':')).encode()
    padded_length = (len(raw) + 3) // 4 * 4
    prefix = struct.pack('<4I', 4, 8 + padded_length, 4 + padded_length, len(raw))
    path.write_bytes(prefix + raw + b'\0' * (padded_length - len(raw)) + b''.join(files.values()))
    return path.read_bytes(), asset_name


class RepairTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'app.asar'
        self.helper = repair.Repair(self.source, self.root / 'state', self.root / 'legacy', require_root=False)

    def tearDown(self):
        self.temp.cleanup()

    def test_patch_idempotence_integrity_and_exact_restore(self):
        original, asset_name = make_archive(self.source)
        before_header, _, _ = repair.archive(self.source)
        self.assertEqual(self.helper.ensure()['status'], 'patched')
        first_patch = self.source.read_bytes()
        self.assertNotEqual(first_patch, original)
        self.assertEqual(len(first_patch), len(original))
        self.assertTrue(self.helper.status()['enabled'])
        self.assertEqual(self.helper.ensure()['status'], 'already_enabled')
        self.assertEqual(self.source.read_bytes(), first_patch)
        header, _, base = repair.archive(self.source)
        data = repair.content(self.source, header, base, asset_name)
        self.assertIn(repair.MARKER, data)
        self.assertEqual(repair.node(header, asset_name)['integrity']['hash'], hashlib.sha256(data).hexdigest())
        self.assertEqual(repair.content(self.source, header, base, 'unrelated.js'),
                         b'const unchanged = "not part of the connection UI";')
        repair.node(header, asset_name)['integrity'] = repair.node(before_header, asset_name)['integrity']
        self.assertEqual(header, before_header)
        self.assertEqual(self.helper.restore()['status'], 'restored')
        self.assertEqual(self.source.read_bytes(), original)

    def test_update_with_changed_asset_and_variables_is_repaired(self):
        for index in range(4):
            original, _ = make_archive(self.source, version=f'26.110{index}.1',
                                       variable='flag', getter='g', visible='show')
            self.assertEqual(self.helper.ensure()['status'], 'patched')
            state = json.loads((self.root / 'state/state.json').read_text())
            self.assertEqual(Path(state['backup']).read_bytes(), original)
            self.assertLessEqual(len(list((self.root / 'state/backups').glob('*.asar'))), 2)
        self.assertEqual(self.helper.restore()['status'], 'restored')
        self.assertEqual(self.source.read_bytes(), original)

    def test_changed_ui_relationship_is_not_modified(self):
        original, _ = make_archive(self.source, linked=False)
        with self.assertRaises(repair.Unsupported):
            self.helper.ensure()
        self.assertEqual(self.source.read_bytes(), original)

    def test_ambiguous_gate_is_not_modified(self):
        original, _ = make_archive(self.source, duplicate=True)
        with self.assertRaises(repair.Unsupported):
            self.helper.ensure()
        self.assertEqual(self.source.read_bytes(), original)

    def test_corrupt_integrity_is_not_modified(self):
        original, _ = make_archive(self.source, damaged=True)
        with self.assertRaises(repair.Unsupported):
            self.helper.ensure()
        self.assertEqual(self.source.read_bytes(), original)

    def test_restore_never_overwrites_a_newer_app(self):
        make_archive(self.source)
        self.helper.ensure()
        newer, _ = make_archive(self.source, version='27.101.1', linked=False)
        self.assertEqual(self.helper.restore()['status'], 'newer_app_left_untouched')
        self.assertEqual(self.source.read_bytes(), newer)

    def test_symbolic_link_is_not_followed(self):
        actual = self.root / 'actual.asar'
        original, _ = make_archive(actual)
        self.source.symlink_to(actual)
        with self.assertRaises(repair.Unsupported):
            self.helper.ensure()
        self.assertEqual(actual.read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
