#!/usr/bin/env python3
"""Reject unreviewed health links, authorization, mount and fixture changes."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from health_actions_source_layer import (
    BEFORE_SHA256, FIXTURE, MODIFIED, PREFIX, ROOT, HealthActionsLayer,
)


class ExactHealthActionsSource(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='kcmc-health-actions-source-negative-')
        self.root = Path(self.directory.name) / 'source'
        self.app = self.root / PREFIX
        for name in MODIFIED:
            target = self.app / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / PREFIX / name, target)
        fixture = self.root / FIXTURE
        fixture.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / FIXTURE, fixture)

    def tearDown(self):
        self.directory.cleanup()

    def verify(self):
        return HealthActionsLayer(self.root)

    def test_unreviewed_health_action_or_side_effect_is_rejected(self):
        path = self.app / 'admin/health.php'
        path.write_bytes(path.read_bytes() + b'\n<?php mail("unreviewed@example.invalid", "health", "send"); ?>\n')
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed health-actions target bytes'):
            self.verify()

    def test_operations_owner_gate_cannot_be_removed(self):
        path = self.app / 'admin/health.php'
        raw = path.read_bytes()
        self.assertEqual(raw.count(b'kcmc_require_operations_owner();'), 1)
        path.write_bytes(raw.replace(b'kcmc_require_operations_owner();', b'/* owner gate removed */', 1))
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed health-actions target bytes'):
            self.verify()

    def test_private_headers_cannot_be_removed(self):
        path = self.app / 'admin/health.php'
        raw = path.read_bytes()
        self.assertEqual(raw.count(b'kcmc_private_headers();'), 1)
        path.write_bytes(raw.replace(b'kcmc_private_headers();', b'/* headers removed */', 1))
        with self.assertRaisesRegex(AssertionError, 'only exact reviewed health-actions target bytes'):
            self.verify()

    def test_equal_health_bytes_cannot_be_supplied_by_a_symbolic_link(self):
        path = self.app / 'admin/health.php'
        outside = Path(self.directory.name) / 'equal-health.php'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, 'target must be an ordinary source file'):
            self.verify()

    def test_admin_directory_cannot_be_a_symbolic_link(self):
        parent = self.app / 'admin'
        outside = Path(self.directory.name) / 'remounted-admin'
        shutil.move(str(parent), str(outside))
        parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, 'parent must be an ordinary source directory'):
            self.verify()

    def test_health_route_cannot_be_omitted(self):
        (self.app / 'admin/health.php').unlink()
        with self.assertRaisesRegex(AssertionError, 'target must be an ordinary source file'):
            self.verify()

    def test_equal_bytes_cannot_gain_an_executable_bit(self):
        path = self.app / 'admin/health.php'
        path.chmod(path.stat().st_mode | 0o100)
        with self.assertRaisesRegex(AssertionError, 'canonical health-actions executable mode required'):
            self.verify()

    def test_fixture_cannot_be_rewritten_to_accept_a_local_change(self):
        path = self.root / FIXTURE
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(AssertionError, 'Exact immutable health-actions fixture'):
            self.verify()

    def test_exact_installed_preimage_is_recovered_without_changing_source(self):
        path = self.app / 'admin/health.php'
        before = path.read_bytes()
        layer = self.verify()
        self.assertEqual(set(layer.preimages), MODIFIED)
        self.assertEqual(layer.paths, frozenset(PREFIX + name for name in MODIFIED))
        self.assertEqual(hashlib.sha256(layer.before('admin/health.php')).hexdigest(), BEFORE_SHA256)
        self.assertNotEqual(before, layer.before('admin/health.php'))
        self.assertEqual(path.read_bytes(), before)
        for name in ['/etc/passwd', '../health.php', 'admin/../health.php', '']:
            with self.subTest(path=name), self.assertRaisesRegex(AssertionError, 'source paths must be bounded'):
                layer.before(name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
