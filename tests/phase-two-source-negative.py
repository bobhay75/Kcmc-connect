#!/usr/bin/env python3
"""Reject undeclared collaboration/payroll source changes before old proofs run."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from phase_two_source_layer import FIXTURE, PhaseTwoLayer, PREFIX, ROOT
from workflow_source_layer import FIXTURE as FIRST_FIXTURE, Layer
from visual_source_layer import FIXTURE as VISUAL_FIXTURE
from manual_clock_source_layer import FIXTURE as MANUAL_FIXTURE, EDITORIAL_FIXTURE
from health_actions_source_layer import FIXTURE as HEALTH_FIXTURE
from welcome_home_source_layer import FIXTURE as WELCOME_FIXTURE, BRAND_FIXTURE, FUNCTION_FIXTURE
from workflow_followup_source_layer import FIXTURE as FOLLOWUP_FIXTURE


class ExactPhaseTwoSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-phase-two-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        shutil.copytree(ROOT / PREFIX, self.app)
        for name in [EDITORIAL_FIXTURE, FUNCTION_FIXTURE, BRAND_FIXTURE, WELCOME_FIXTURE, FIXTURE, FIRST_FIXTURE, VISUAL_FIXTURE, MANUAL_FIXTURE, HEALTH_FIXTURE, FOLLOWUP_FIXTURE]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return PhaseTwoLayer(self.root, ROOT)

    def test_untracked_public_route_cannot_hide_outside_historical_git_scope(self):
        (self.app / 'owner-bypass.php').write_text('<?php echo "undeclared";')
        with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
            self.verify()

    def test_public_homepage_is_protected_outside_collaboration_payroll_scope(self):
        path = self.app / 'index.php'
        path.write_bytes(path.read_bytes() + b'\n<!-- undeclared homepage banner -->\n')
        with self.assertRaisesRegex(AssertionError, 'Only exact Tony functional bytes permitted: index.php'):
            self.verify()

    def test_undeclared_owner_authorization_edit_cannot_hide_in_reviewed_403_markup(self):
        path = self.app / 'lib/operations-owner.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared authorization edit\n')
        with self.assertRaisesRegex(AssertionError, 'lib/operations-owner.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_undeclared_task_permission_edit_is_rejected(self):
        path = self.app / 'lib/team-workspace.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared task permission edit\n')
        with self.assertRaisesRegex(AssertionError, 'lib/team-workspace.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_undeclared_payroll_recipient_edit_is_rejected(self):
        path = self.app / 'lib/payroll.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared recipient edit\n')
        with self.assertRaisesRegex(AssertionError, 'lib/payroll.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_missing_new_owner_payroll_setup_route_is_rejected(self):
        (self.app / 'admin/payroll-setup.php').unlink()
        with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
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
