#!/usr/bin/env python3
"""Negative controls for the exact public-design historical projection."""
from pathlib import Path
import hashlib
import shutil
import tempfile
import unittest
from welcome_home_source_layer import WelcomeLayer, ROOT, PREFIX, FIXTURE, BRAND_FIXTURE, MODIFIED, ADDED


class WelcomeProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in [FIXTURE, BRAND_FIXTURE] + [PREFIX + p for p in MODIFIED | ADDED]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_exact_design_recovers_original_text(self):
        layer = WelcomeLayer(self.root)
        self.assertEqual(hashlib.sha256(layer.before('sw.js')).hexdigest(),
                         '100dc03b25fa0999c48fc6a0db2d684209ba972f28325ac6f59460c3a0873a7c')
        with self.assertRaises(AssertionError):
            layer.before('home-welcome.css')

    def test_each_changed_asset_must_match_exactly(self):
        for name in sorted(MODIFIED | ADDED):
            with self.subTest(name=name):
                target = self.root / PREFIX / name
                raw = target.read_bytes()
                target.write_bytes(raw + b'changed')
                with self.assertRaises(AssertionError):
                    WelcomeLayer(self.root)
                target.write_bytes(raw)

    def test_fixture_edits_refuse(self):
        target = self.root / FIXTURE
        target.write_bytes(target.read_bytes() + b' ')
        with self.assertRaises(AssertionError):
            WelcomeLayer(self.root)

    def test_current_brand_fixture_edits_refuse(self):
        target = self.root / BRAND_FIXTURE
        target.write_bytes(target.read_bytes() + b' ')
        with self.assertRaises(AssertionError):
            WelcomeLayer(self.root)

    def test_executable_target_refuses(self):
        (self.root / PREFIX / 'index.php').chmod(0o755)
        with self.assertRaises(AssertionError):
            WelcomeLayer(self.root)

    def test_symlink_target_refuses(self):
        target = self.root / PREFIX / 'home-welcome.css'
        saved = self.root / 'saved.css'
        target.rename(saved)
        target.symlink_to(saved)
        with self.assertRaises(AssertionError):
            WelcomeLayer(self.root)

    def test_current_application_cannot_be_rewritten(self):
        layer = WelcomeLayer(self.root)
        with self.assertRaises(AssertionError):
            layer.restore_copy(self.root / PREFIX)


if __name__ == '__main__':
    unittest.main()
