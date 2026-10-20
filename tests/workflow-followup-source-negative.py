#!/usr/bin/env python3
"""Reject unreviewed push/navigation changes and retain exact older projections."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from workflow_followup_source_layer import (
    BASE, BEFORE_SHA256, FIXTURE, MODIFIED, PREFIX, ROOT, WorkflowFollowupLayer,
)
from manual_clock_source_layer import (
    EDITORIAL_FIXTURE,
    FIXTURE as MANUAL_FIXTURE, VISUAL_FIXTURE, ManualClockLayer,
)
from health_actions_source_layer import FIXTURE as HEALTH_FIXTURE
from welcome_home_source_layer import FIXTURE as WELCOME_FIXTURE, BRAND_FIXTURE
from visual_source_layer import VisualLayer


class ExactWorkflowFollowupSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-workflow-followup-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        shutil.copytree(ROOT / PREFIX, self.app)
        for name in [EDITORIAL_FIXTURE, BRAND_FIXTURE, WELCOME_FIXTURE, FIXTURE, MANUAL_FIXTURE, HEALTH_FIXTURE, VISUAL_FIXTURE]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return WorkflowFollowupLayer(self.root, ROOT)

    def test_each_reviewed_target_rejects_additional_code(self):
        for name in sorted(MODIFIED):
            path = self.app / name
            raw = path.read_bytes()
            with self.subTest(path=name):
                path.write_bytes(raw + b'\n/* unreviewed push/navigation behavior */\n')
                message = ('Only exact reviewed October 20 branding bytes permitted: '+name if name in {'index.php', 'sw.js'}
                           else 'only exact reviewed workflow-followup target bytes')
                with self.assertRaisesRegex(AssertionError, message):
                    self.verify()
                path.write_bytes(raw)

    def test_owner_authorization_gate_cannot_be_removed(self):
        path = self.app / 'admin/push.php'
        raw = path.read_bytes()
        self.assertEqual(raw.count(b'kcmc_require_operations_owner();'), 1)
        path.write_bytes(raw.replace(b'kcmc_require_operations_owner();', b'/* no owner check */', 1))
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed workflow-followup target bytes'):
            self.verify()

    def test_member_authentication_cannot_be_removed(self):
        path = self.app / 'member/notifications.php'
        raw = path.read_bytes()
        self.assertEqual(raw.count(b'kcmc_require_login()'), 1)
        path.write_bytes(raw.replace(b'kcmc_require_login()', b'[]', 1))
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed workflow-followup target bytes'):
            self.verify()

    def test_each_reviewed_existing_file_is_required(self):
        for name in sorted(MODIFIED):
            path = self.app / name
            raw = path.read_bytes()
            with self.subTest(path=name):
                path.unlink()
                message = ('Ordinary branding file required: '+name if name in {'index.php', 'sw.js'}
                           else 'target must be an ordinary source file')
                with self.assertRaisesRegex(AssertionError, message):
                    self.verify()
                path.write_bytes(raw)

    def test_equal_reviewed_bytes_cannot_be_supplied_by_symbolic_link(self):
        path = self.app / 'sw.js'
        outside = Path(self.directory.name) / 'equal-worker.js'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, 'Ordinary branding file required: sw.js'):
            self.verify()

    def test_equal_reviewed_parent_cannot_be_a_symbolic_link(self):
        parent = self.app / 'member'
        outside = Path(self.directory.name) / 'remounted-member'
        shutil.move(str(parent), str(outside))
        parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, 'parent must be an ordinary source directory'):
            self.verify()

    def test_equal_bytes_cannot_gain_an_executable_bit(self):
        path = self.app / 'member/push-settings.js'
        path.chmod(path.stat().st_mode | 0o100)
        with self.assertRaisesRegex(AssertionError, 'canonical workflow-followup executable mode required'):
            self.verify()

    def test_fixture_cannot_be_rewritten_to_accept_local_edits(self):
        path = self.root / FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable workflow-followup fixture required'):
            self.verify()

    def test_unreviewed_runtime_outside_the_six_file_delta_remains_rejected(self):
        for name in ['lib/bootstrap.php', 'lib/payroll.php', 'api/push-subscription.php']:
            path = self.app / name
            raw = path.read_bytes()
            with self.subTest(path=name):
                path.write_bytes(raw + b'\n/* unreviewed authorization, payroll or subscription edit */\n')
                with self.assertRaisesRegex(AssertionError, 'all runtime bytes outside the reviewed manual-clock delta'):
                    ManualClockLayer(self.root, ROOT)
                path.write_bytes(raw)

    def test_undeclared_runtime_file_still_rejected_by_complete_composition(self):
        (self.app / 'api/unreviewed-push.php').write_bytes(b'<?php echo "undeclared";')
        with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
            ManualClockLayer(self.root, ROOT)

    def test_original_health_fixture_still_immutable_in_composition(self):
        path = self.root / HEALTH_FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable health-actions fixture required'):
            ManualClockLayer(self.root, ROOT)

    def test_six_preimages_and_complete_historical_projection_are_exact_and_isolated(self):
        before = {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.app.rglob('*') if p.is_file()}
        layer = self.verify()
        self.assertEqual(set(layer.preimages), MODIFIED)
        self.assertEqual(layer.paths, frozenset(PREFIX + name for name in MODIFIED))
        for name in sorted(MODIFIED):
            self.assertEqual(hashlib.sha256(layer.before(name)).hexdigest(), BEFORE_SHA256[name])
            self.assertNotEqual(layer.before(name), (self.app / name).read_bytes())
        for name in ['/etc/passwd', '../outside.php', 'admin/../push.php', '']:
            with self.subTest(path=name), self.assertRaisesRegex(AssertionError, 'source paths must be bounded'):
                layer.before(name)

        class HistoricalObjectsOnly(ManualClockLayer):
            def git(self, *args):
                if any(BASE in value for value in args):
                    raise AssertionError('Existing jobs may not require the follow-up baseline Git object')
                return super(HistoricalObjectsOnly, self).git(*args)

        manual = HistoricalObjectsOnly(self.root, ROOT)
        themed = Path(self.directory.name) / 'themed'
        manual.copy_baseline(themed)
        visual = VisualLayer(self.root, ROOT)
        installed = Path(self.directory.name) / 'installed'
        visual.copy_baseline(installed)
        for name in sorted(MODIFIED | {'admin/health.php', 'member/timeclock.php'}):
            self.assertEqual((installed / name).read_bytes(), manual.git(
                'show', 'b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9:' + PREFIX + name))
        self.assertEqual(before, {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in self.app.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main(verbosity=2)
