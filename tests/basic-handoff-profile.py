#!/usr/bin/env python3
"""Build-profile regression and refusal tests; no host files or real accounts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = 'KCMC-Connect-Phase6-Recreated'
PROFILE = 'tools/basic-handoff/profile'


class BasicProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-profile-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        for folder in (APP, 'tools/basic-handoff'):
            shutil.copytree(ROOT / folder, self.root / folder)
        self.output = Path(self.temp.name) / 'candidate'

    def build(self):
        return subprocess.run([sys.executable, str(self.root / 'tools/basic-handoff/build.py'),
                               str(self.output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def assert_refused(self, message):
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertFalse(self.output.exists(), 'validation must finish before output is created')

    def test_package_preserves_the_accepted_basic_runtime_without_mutating_source(self):
        manifest = json.loads((self.root / 'tools/basic-handoff/profile.json').read_text())
        original = {p.relative_to(self.root / APP): p.read_bytes()
                    for p in (self.root / APP).rglob('*') if p.is_file()}
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, record in manifest['files'].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(),
                             record['candidate_sha256'])
        for name, data in original.items():
            self.assertEqual((self.root / APP / name).read_bytes(), data)
        for name in ('member/timeclock.php', 'admin/password-resets.php', 'admin/users.php',
                     'admin/publication-designer.php', 'api/push-subscription.php',
                     'lib/payroll.php', 'lib/password-lifecycle.php', 'data/private', 'config.php'):
            self.assertFalse((self.output / name).exists(), name)
        login = (self.output / 'member/login.php').read_text()
        self.assertIn("in_array(kcmc_role($user), ['pastor_admin', 'recovery_admin'], true)", login)
        self.assertIn('kcmc_verify_csrf(', login)
        self.assertIn('password_verify(', login)
        self.assertIn("kcmc_require_role(['pastor_admin', 'recovery_admin'])",
                      (self.output / 'admin/index.php').read_text())
        self.assertIn('key.startsWith(CACHE_NAMESPACE)', (self.output / 'sw.js').read_text())

    def test_shared_runtime_change_requires_reconciliation(self):
        p = self.root / APP / 'lib/bootstrap.php'
        p.write_bytes(p.read_bytes() + b'\n// changed upstream authentication\n')
        self.assert_refused('shared source changed')

    def test_profile_drift_is_refused(self):
        p = self.root / PROFILE / 'member/login.php'
        p.write_bytes(p.read_bytes() + b'\n// unreviewed change\n')
        self.assert_refused('profile bytes differ')

    def test_unlisted_profile_file_is_refused(self):
        (self.root / PROFILE / 'admin/users.php').write_text('<?php // excluded\n')
        self.assert_refused('profile file list differs')

    def test_symlink_profile_is_refused(self):
        p = self.root / PROFILE / 'index.php'
        p.unlink()
        p.symlink_to(self.root / APP / 'index.php')
        self.assert_refused('profile contains symlinks')

    def test_path_traversal_is_refused(self):
        p = self.root / 'tools/basic-handoff/profile.json'
        data = json.loads(p.read_text())
        data['files']['../escape.php'] = data['files'].pop('index.php')
        p.write_text(json.dumps(data))
        self.assert_refused('profile file list differs')


if __name__ == '__main__':
    unittest.main()
