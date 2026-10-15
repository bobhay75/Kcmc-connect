#!/usr/bin/env python3
"""Reject undeclared collaboration/payroll source changes before old proofs run."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from phase_two_source_layer import FIXTURE, PhaseTwoLayer, PREFIX, ROOT
from workflow_source_layer import FIXTURE as FIRST_FIXTURE, Layer


class ExactPhaseTwoSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-phase-two-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        shutil.copytree(ROOT / PREFIX, self.app)
        for name in [FIXTURE, FIRST_FIXTURE]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return PhaseTwoLayer(self.root, ROOT)

    def test_untracked_public_route_cannot_hide_outside_historical_git_scope(self):
        (self.app / 'owner-bypass.php').write_text('<?php echo "undeclared";')
        with self.assertRaisesRegex(AssertionError, 'exact phase-one baseline plus reviewed phase-two files'):
            self.verify()

    def test_public_homepage_is_protected_outside_collaboration_payroll_scope(self):
        path = self.app / 'index.php'
        path.write_bytes(path.read_bytes() + b'\n<!-- undeclared homepage banner -->\n')
        with self.assertRaisesRegex(AssertionError, 'outside the reviewed phase-two delta'):
            self.verify()

    def test_undeclared_owner_authorization_edit_cannot_hide_in_reviewed_403_markup(self):
        path = self.app / 'lib/operations-owner.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared authorization edit\n')
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed phase-two target bytes'):
            self.verify()

    def test_undeclared_task_permission_edit_is_rejected(self):
        path = self.app / 'lib/team-workspace.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared task permission edit\n')
        with self.assertRaisesRegex(AssertionError, 'exact reviewed new phase-two file'):
            self.verify()

    def test_undeclared_payroll_recipient_edit_is_rejected(self):
        path = self.app / 'lib/payroll.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared recipient edit\n')
        with self.assertRaisesRegex(AssertionError, 'exact reviewed new phase-two file'):
            self.verify()

    def test_missing_new_owner_payroll_setup_route_is_rejected(self):
        (self.app / 'admin/payroll-setup.php').unlink()
        with self.assertRaisesRegex(AssertionError, 'exact phase-one baseline plus reviewed phase-two files'):
            self.verify()

    def test_second_fixture_cannot_be_silently_rewritten(self):
        path = self.root / FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable phase-two fixture'):
            self.verify()

    def test_both_historical_outputs_are_exact_and_leave_current_source_unchanged(self):
        before = {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.app.rglob('*') if p.is_file()}
        layer = Layer(self.root, ROOT)
        phase_one = Path(self.directory.name) / 'phase-one'
        historical = Path(self.directory.name) / 'historical'
        layer.phase_two.copy_phase_one(phase_one)
        layer.copy_baseline(historical)
        self.assertTrue((phase_one / 'admin/home.php').is_file())
        self.assertFalse((phase_one / 'lib/payroll.php').exists())
        self.assertFalse((phase_one / 'member/work.php').exists())
        self.assertFalse((historical / 'admin/home.php').exists())
        self.assertNotIn(b'Send update', (phase_one / 'member/notifications.php').read_bytes())
        self.assertIn(b'Send update', (historical / 'member/notifications.php').read_bytes())
        self.assertEqual(before, {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in self.app.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(AssertionError, 'must not already exist'):
            layer.phase_two.copy_phase_one(phase_one)


if __name__ == '__main__':
    unittest.main(verbosity=2)
