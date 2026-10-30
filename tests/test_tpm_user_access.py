"""Use ACLs on temporary files; never access TPM hardware or system rules."""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'tpm_user_access', Path(__file__).resolve().parents[1] / 'scripts/tpm_user_access.py')
tpm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpm)


@unittest.skipUnless(shutil.which('getfacl') and shutil.which('setfacl'), 'ACL tools are required')
class TpmAccessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.device = self.root / 'device'
        self.device.touch(mode=0o660)
        self.device.chmod(0o660)
        self.rule = self.root / 'rules/72-chatgpt-tpm-user-access.rules'
        self.rule.parent.mkdir()
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.account = types.SimpleNamespace(pw_uid=12345, pw_name='test-controller', pw_gid=os.getgid())
        self.commands = []
        self.patches = [patch.object(tpm, 'DEVICE', self.device), patch.object(tpm, 'RULE', self.rule),
                        patch.object(tpm, 'STATE', self.state), patch.object(tpm, 'run', self.fake_run),
                        patch.object(tpm, 'probe', return_value={'open_succeeded': True, 'error': None})]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temporary.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)

    def fake_run(self, *args):
        self.commands.append(args)
        if args[0] == '/usr/bin/udevadm':
            if args[1] == '--version':
                return '255\n'
            if args[1] == 'info':
                return '/devices/virtual/tpmrm/tpmrm0\n'
            return ''
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout

    def acl(self):
        return subprocess.run(['/usr/bin/getfacl', '-n', '-c', str(self.device)],
                              check=True, capture_output=True, text=True).stdout

    def set_acl(self, value):
        subprocess.run(['/usr/bin/setfacl', '-m', value, str(self.device)], check=True)

    def record(self):
        return json.loads((self.state / 'state.json').read_text())

    def test_apply_repeat_and_restore_preserve_another_user(self):
        self.set_acl('u:12346:r--')
        before = self.acl()
        self.assertEqual(tpm.repair_locked(self.account, False)['status'], 'applied')
        self.assertEqual(tpm.user_entry(self.acl(), 12345), 'rw-')
        self.assertEqual(tpm.user_entry(self.acl(), 12346), 'r--')
        self.assertIn('mask::rw-', self.acl())
        self.assertEqual(self.rule.read_text(), tpm.rule_text(12345))
        self.assertEqual((self.state / 'original-acl.txt').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.state / 'state.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.rule.stat().st_mode & 0o777, 0o644)
        self.assertEqual(tpm.repair_locked(self.account, False)['status'], 'applied')
        self.assertIsNone(self.record()['original_user_entry'])
        self.assertEqual(tpm.repair_locked(self.account, True)['status'], 'restored')
        self.assertEqual(self.acl(), before)
        self.assertFalse(self.rule.exists())
        self.assertFalse(self.record()['enabled'])
        self.assertIn(('/usr/bin/udevadm', 'trigger', '--action=change',
                       '/sys/devices/virtual/tpmrm/tpmrm0'), self.commands)

    def test_restore_keeps_original_selected_user_entry(self):
        self.set_acl('u:12345:r--,u:12346:r--')
        before = self.acl()
        tpm.repair_locked(self.account, False)
        self.assertEqual(self.record()['original_user_entry'], 'r--')
        tpm.repair_locked(self.account, True)
        self.assertEqual(self.acl(), before)

    def test_failed_device_probe_removes_rule_and_restores_entry(self):
        self.set_acl('u:12345:r--,u:12346:r--')
        before = self.acl()
        with patch.object(tpm, 'probe', return_value={'open_succeeded': False, 'error': 'denied'}):
            with self.assertRaisesRegex(RuntimeError, 'still cannot open'):
                tpm.repair_locked(self.account, False)
        self.assertFalse(self.rule.exists())
        self.assertEqual(self.acl(), before)
        self.assertFalse(self.record()['enabled'])

    def test_restricted_mask_is_left_untouched(self):
        self.set_acl('u:12346:rw-,m::r--')
        before = self.acl()
        with self.assertRaisesRegex(RuntimeError, 'mask/group'):
            tpm.repair_locked(self.account, False)
        self.assertEqual(self.acl(), before)
        self.assertFalse(self.rule.exists())
        self.assertFalse((self.state / 'state.json').exists())

    def test_existing_unmanaged_rule_is_left_untouched(self):
        self.rule.write_text('an administrator owns this rule\n')
        before = self.acl()
        with self.assertRaisesRegex(RuntimeError, 'unrelated rule'):
            tpm.repair_locked(self.account, False)
        self.assertEqual(self.rule.read_text(), 'an administrator owns this rule\n')
        self.assertEqual(self.acl(), before)

    def test_different_user_cannot_take_over_saved_rule(self):
        tpm.repair_locked(self.account, False)
        before = self.rule.read_text(), self.acl()
        other = types.SimpleNamespace(pw_uid=12346)
        with self.assertRaisesRegex(RuntimeError, 'different local user'):
            tpm.repair_locked(other, False)
        self.assertEqual((self.rule.read_text(), self.acl()), before)

    def test_old_managed_rule_is_upgraded_with_original_restore_data(self):
        tpm.repair_locked(self.account, False)
        self.rule.write_text(tpm.rule_text(12345, legacy=True))
        tpm.repair_locked(self.account, False)
        self.assertEqual(self.rule.read_text(), tpm.rule_text(12345))
        self.assertIsNone(self.record()['original_user_entry'])

    def test_state_symlink_and_old_udev_are_refused(self):
        self.state.rmdir()
        self.state.symlink_to(self.root / 'missing')
        with patch.object(tpm.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'directory link'):
                tpm.repair(self.account)
            with patch.object(tpm, 'run', return_value='249\n'):
                with self.assertRaisesRegex(RuntimeError, '254 or newer'):
                    tpm.repair(self.account)
        self.assertFalse(self.rule.exists())
        self.assertFalse((self.root / 'missing').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
