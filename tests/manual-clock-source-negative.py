#!/usr/bin/env python3
"""Reject any unreviewed time-clock, authorization, payroll or mount changes."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from manual_clock_source_layer import (
    BASE, BASE_APP_TREE, FIXTURE, MODIFIED, PREFIX, ROOT, VISUAL_FIXTURE,
    ManualClockLayer, app_tree_oid, blob,
)
from visual_source_layer import NEW_FILES as VISUAL_NEW_FILES, VisualLayer
from health_actions_source_layer import FIXTURE as HEALTH_FIXTURE


class ExactManualClockSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-manual-clock-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        shutil.copytree(ROOT / PREFIX, self.app)
        for name in [FIXTURE, VISUAL_FIXTURE, HEALTH_FIXTURE]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return ManualClockLayer(self.root, ROOT)

    def replace(self, name, old, new, count=1):
        path = self.app / name
        raw = path.read_bytes()
        self.assertGreaterEqual(raw.count(old), count, 'Mutation must change a real source anchor')
        path.write_bytes(raw.replace(old, new, count))

    def test_disabled_review_library_gate_cannot_be_replaced_with_success(self):
        self.replace('lib/timeclock.php',
                     b"throw new RuntimeException('Time cards do not need submission or approval. Recorded time is available directly.');",
                     b'return [];')
        with self.assertRaisesRegex(AssertionError, 'lib/timeclock.php: only exact reviewed manual-clock target bytes'):
            self.verify()

    def test_employee_clock_cannot_gain_an_unreviewed_approval_action(self):
        self.replace('member/timeclock.php', b'>Clock In</button>',
                     b'>Clock In</button><button name="action" value="approve">Approve</button>')
        with self.assertRaisesRegex(AssertionError, 'member/timeclock.php: only exact reviewed manual-clock target bytes'):
            self.verify()

    def test_csv_reviewer_gate_cannot_be_removed(self):
        self.replace('admin/timecards-export.php', b'kcmc_require_payroll_reviewer();',
                     b'/* reviewer gate removed */')
        with self.assertRaisesRegex(AssertionError, 'admin/timecards-export.php: only exact reviewed manual-clock target bytes'):
            self.verify()

    def test_admin_approval_rejection_cannot_be_disabled(self):
        self.replace('admin/timecards.php', b"['submit_period', 'approve', 'return']", b"['unused_action']")
        with self.assertRaisesRegex(AssertionError, 'admin/timecards.php: only exact reviewed manual-clock target bytes'):
            self.verify()

    def test_print_route_cannot_be_silently_restored_to_approved_only(self):
        path = self.app / 'admin/timecards-print.php'
        path.write_bytes(path.read_bytes() + b'\n<!-- unreviewed approved-only print gate -->\n')
        with self.assertRaisesRegex(AssertionError, 'admin/timecards-print.php: only exact reviewed manual-clock target bytes'):
            self.verify()

    def test_bootstrap_role_escalation_is_outside_the_reviewed_delta(self):
        self.replace('lib/bootstrap.php', b"return (string)($user['role'] ?? 'member');",
                     b"return 'pastor_admin';")
        with self.assertRaisesRegex(AssertionError, 'lib/bootstrap.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_payroll_transport_or_recipient_change_is_outside_the_reviewed_delta(self):
        path = self.app / 'lib/payroll.php'
        path.write_bytes(path.read_bytes() + b'\n// unreviewed recipient, scheduler or transport change\n')
        with self.assertRaisesRegex(AssertionError, 'lib/payroll.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_undeclared_runtime_route_is_rejected_without_git_diff(self):
        (self.app / 'member/auto-clock.php').write_bytes(b'<?php echo "unreviewed";')
        with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
            self.verify()

    def test_each_functional_file_is_required(self):
        for name in sorted(MODIFIED):
            path = self.app / name
            raw = path.read_bytes()
            with self.subTest(path=name):
                path.unlink()
                with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
                    self.verify()
                path.write_bytes(raw)

    def test_equal_bytes_cannot_be_supplied_by_a_symbolic_link(self):
        path = self.app / 'lib/timeclock.php'
        outside = Path(self.directory.name) / 'equal-library'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, 'may not add symbolic links'):
            self.verify()

    def test_application_mount_cannot_be_a_symbolic_link(self):
        outside = Path(self.directory.name) / 'remounted-application'
        shutil.move(str(self.app), str(outside))
        self.app.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, 'application mount must be an ordinary source directory'):
            self.verify()

    def test_application_mount_must_exist(self):
        shutil.rmtree(str(self.app))
        with self.assertRaisesRegex(AssertionError, 'application mount must be an ordinary source directory'):
            self.verify()

    def test_executable_mode_change_is_rejected_with_equal_bytes(self):
        path = self.app / 'lib/timeclock.php'
        path.chmod(path.stat().st_mode | 0o100)
        with self.assertRaisesRegex(AssertionError, 'canonical manual-clock application executable mode required'):
            self.verify()

    def test_fixture_cannot_be_rewritten_to_accept_local_source(self):
        path = self.root / FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable manual-clock fixture'):
            self.verify()

    def test_original_visual_fixture_is_still_immutable(self):
        path = self.root / VISUAL_FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable visual/navigation fixture'):
            self.verify()

    def test_older_jobs_need_no_new_themed_commit_object_or_fetch(self):
        class HistoricalObjectsOnly(ManualClockLayer):
            def git(self, *args):
                if any(BASE in value for value in args):
                    raise AssertionError('Older workflow cannot require an additional themed Git object')
                return super(HistoricalObjectsOnly, self).git(*args)
        layer = HistoricalObjectsOnly(self.root, ROOT)
        self.assertEqual(set(layer.preimages), MODIFIED)

    def test_both_projections_are_exact_and_leave_current_source_unchanged(self):
        before = {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.app.rglob('*') if p.is_file()}
        layer = self.verify()
        themed = Path(self.directory.name) / 'themed'
        layer.copy_baseline(themed)
        themed_tree = {
            p.relative_to(themed).as_posix():
            ('100755' if p.stat().st_mode & 0o111 else '100644', blob(p.read_bytes()))
            for p in themed.rglob('*') if p.is_file()
        }
        self.assertEqual(app_tree_oid(themed_tree), BASE_APP_TREE)
        # Functional and later health edits must be reversed before the visual
        # layer copies the exact b0c application for older package tests.
        visual = VisualLayer(self.root, ROOT)
        installed = Path(self.directory.name) / 'installed'
        visual.copy_baseline(installed)
        for name in ['lib/timeclock.php', 'admin/timecards-export.php', 'admin/health.php']:
            self.assertEqual((installed / name).read_bytes(), visual.git('show',
                             'b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9:' + PREFIX + name))
        self.assertFalse(any((installed / name).exists() for name in VISUAL_NEW_FILES))
        self.assertEqual(before, {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in self.app.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(AssertionError, 'must not already exist'):
            layer.copy_baseline(themed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
