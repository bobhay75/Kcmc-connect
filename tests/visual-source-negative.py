#!/usr/bin/env python3
"""Reject unreviewed visual or authorization bytes before historical projection."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from visual_source_layer import FIXTURE, NEW_FILES, PREFIX, ROOT, VisualLayer
from manual_clock_source_layer import FIXTURE as MANUAL_FIXTURE
from health_actions_source_layer import FIXTURE as HEALTH_FIXTURE
from workflow_followup_source_layer import FIXTURE as FOLLOWUP_FIXTURE


class ExactVisualSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-visual-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        shutil.copytree(ROOT / PREFIX, self.app)
        for name in [FIXTURE, MANUAL_FIXTURE, HEALTH_FIXTURE, FOLLOWUP_FIXTURE]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return VisualLayer(self.root, ROOT)

    def test_undeclared_public_route_cannot_hide_outside_git_diff(self):
        (self.app / 'unreviewed-route.php').write_text('<?php echo "not approved";')
        with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
            self.verify()

    def test_undeclared_homepage_content_cannot_hide_inside_navigation_update(self):
        path = self.app / 'index.php'
        path.write_bytes(path.read_bytes() + b'\n<!-- unreviewed public banner -->\n')
        with self.assertRaisesRegex(AssertionError, 'index.php: only exact reviewed workflow-followup target bytes'):
            self.verify()

    def test_admin_role_change_cannot_hide_inside_ui_helper_loading(self):
        path = self.app / 'lib/bootstrap.php'
        path.write_bytes(path.read_bytes() + b'\n// unreviewed role or owner change\n')
        with self.assertRaisesRegex(AssertionError, 'lib/bootstrap.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_payroll_data_change_cannot_hide_inside_denied_page_rendering(self):
        path = self.app / 'lib/payroll.php'
        path.write_bytes(path.read_bytes() + b'\n// unreviewed recipient or transport change\n')
        with self.assertRaisesRegex(AssertionError, 'lib/payroll.php: all runtime bytes outside the reviewed manual-clock delta'):
            self.verify()

    def test_each_new_provider_is_pinned_and_required(self):
        self.assertTrue(NEW_FILES, 'Visual release must enumerate its new providers')
        for name in sorted(NEW_FILES):
            path = self.app / name
            raw = path.read_bytes()
            with self.subTest(path=name, condition='modified'):
                path.write_bytes(raw + b'\n/* unreviewed provider code */\n')
                with self.assertRaisesRegex(AssertionError, 'exact reviewed new visual/navigation file required'):
                    self.verify()
                path.write_bytes(raw)
            with self.subTest(path=name, condition='missing'):
                path.unlink()
                with self.assertRaisesRegex(AssertionError, 'membership must equal the exact themed baseline'):
                    self.verify()
                path.write_bytes(raw)

    def test_symbolic_link_cannot_substitute_equal_provider_bytes(self):
        name = sorted(NEW_FILES)[0]
        path = self.app / name
        outside = Path(self.directory.name) / 'equal-provider'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, 'may not add symbolic links'):
            self.verify()

    def test_executable_change_cannot_hide_behind_equal_bytes(self):
        path = self.app / 'lib/payroll.php'
        path.chmod(path.stat().st_mode | 0o100)
        with self.assertRaisesRegex(AssertionError, 'canonical manual-clock application executable mode required'):
            self.verify()

    def test_fixture_cannot_be_rewritten_to_allow_a_local_edit(self):
        path = self.root / FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable visual/navigation fixture'):
            self.verify()

    def test_exact_installed_projection_is_isolated_and_does_not_overwrite(self):
        before = {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.app.rglob('*') if p.is_file()}
        layer = self.verify()
        destination = Path(self.directory.name) / 'installed'
        layer.copy_baseline(destination)
        self.assertFalse(any((destination / name).exists() for name in NEW_FILES))
        self.assertEqual((destination / 'lib/team-workspace.php').read_bytes(), (self.app / 'lib/team-workspace.php').read_bytes())
        self.assertEqual(before, {p.relative_to(self.app): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in self.app.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(AssertionError, 'must not already exist'):
            layer.copy_baseline(destination)


if __name__ == '__main__':
    unittest.main(verbosity=2)
