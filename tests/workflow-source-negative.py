#!/usr/bin/env python3
"""Require workflow history composition to reject undeclared source changes."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from workflow_source_layer import FIXTURE, Layer, PREFIX, ROOT


class ExactWorkflowSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-workflow-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        shutil.copytree(ROOT / PREFIX, self.app)
        (self.root / FIXTURE).parent.mkdir(parents=True)
        shutil.copyfile(ROOT / FIXTURE, self.root / FIXTURE)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return Layer(self.root, ROOT)

    def test_undeclared_runtime_file_cannot_hide_outside_git_diff(self):
        (self.app / 'member/undeclared-owner-shortcut.php').write_text('<?php echo "undeclared";')
        with self.assertRaisesRegex(AssertionError, 'exact baseline plus five reviewed files'):
            self.verify()

    def test_undeclared_bootstrap_change_cannot_hide_behind_workflow_preimages(self):
        path = self.app / 'lib/bootstrap.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared authorization change\n')
        with self.assertRaisesRegex(AssertionError, 'outside the reviewed workflow delta'):
            self.verify()

    def test_extra_change_inside_reviewed_route_is_rejected(self):
        path = self.app / 'admin/push.php'
        path.write_bytes(path.read_bytes() + b'\n<!-- undeclared sender change -->\n')
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed workflow target bytes'):
            self.verify()

    def test_changed_new_admin_route_is_rejected(self):
        path = self.app / 'admin/prayer-care.php'
        path.write_bytes(path.read_bytes() + b'\n// undeclared route change\n')
        with self.assertRaisesRegex(AssertionError, 'exact reviewed new workflow file'):
            self.verify()

    def test_missing_new_route_is_rejected(self):
        (self.app / 'admin/home.php').unlink()
        with self.assertRaisesRegex(AssertionError, 'exact baseline plus five reviewed files'):
            self.verify()

    def test_fixture_cannot_be_silently_rewritten(self):
        path = self.root / FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable workflow fixture'):
            self.verify()

    def test_historical_fixture_is_isolated_and_exact_without_mutating_current_source(self):
        before = {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.app.rglob('*') if p.is_file()}
        layer = self.verify()
        destination = Path(self.directory.name) / 'historical'
        layer.copy_baseline(destination)
        self.assertFalse((destination / 'admin/home.php').exists())
        self.assertIn(b'Send update', (destination / 'member/notifications.php').read_bytes())
        self.assertNotIn(b'Send update', (self.app / 'member/notifications.php').read_bytes())
        self.assertEqual(before, {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in self.app.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(AssertionError, 'must not already exist'):
            layer.copy_baseline(destination)


if __name__ == '__main__':
    unittest.main(verbosity=2)
