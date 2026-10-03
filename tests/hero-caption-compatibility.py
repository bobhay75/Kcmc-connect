#!/usr/bin/env python3
"""Local transaction/compatibility fixtures; no production access.
Run: python3 tests/hero-caption-compatibility.py
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('hero_caption_fix', Path(__file__).resolve().parents[1] / 'tools/hero_caption_fix.py')
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = self.root / 'app'
        self.backups = self.root / 'backups'
        self.app.mkdir(); self.backups.mkdir()
        self.before = {
            'public-presentation.js': ("const motion = window.matchMedia; const selector = '[data-hero-gallery]'; function schedule() {} function show() {}\n" + fix.OLD_TIMER + '\n').encode(),
            'public-presentation.css': b'.hero-photo {display:block} .photo-source {display:block}\n',
            'index.php': b'''<?php /* fixture */ ?><section data-hero-gallery><img src="image.webp" alt="Church photo"></section><link href="public-presentation.css?v=tony-staff-20261001"><script src="public-presentation.js?v=tony-staff-20261001"></script>''',
            'sw.js': b"const CACHE='kcmc-connect-v3.0.3-public-only-tony-staff-20261001';\nconst CORE=['public-presentation.css?v=1.0.0','public-presentation.js?v=1.0.0'];\nfunction privatePolicy(){return 'NO CHANGE';}\n"
        }
        for name, body in self.before.items():
            (self.app/name).write_bytes(body); (self.app/name).chmod(0o640)
        for name in ['admin/health.php','member/login.php','member/timeclock.php','data/content.json','data/private/users.json']:
            path=self.app/name; path.parent.mkdir(exist_ok=True,parents=True); path.write_text('private sentinel')
    def tearDown(self): self.temp.cleanup()
    def install(self, check=False):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(fix,'lint'):
            return fix.apply(self.app,self.backups,check)
    def assertOriginal(self):
        for name,body in self.before.items(): self.assertEqual((self.app/name).read_bytes(),body)
    def test_interval(self):
        result=fix.transform(self.before)
        self.assertIn(fix.NEW_TIMER.encode(),result['public-presentation.js'])
        self.assertEqual(result['public-presentation.js'],self.before['public-presentation.js'].replace(fix.OLD_TIMER.encode(),fix.NEW_TIMER.encode()))
    def test_caption_css_only(self):
        result=fix.transform(self.before)
        self.assertEqual(result['public-presentation.css'],self.before['public-presentation.css']+fix.CSS.encode())
        self.assertIn(b'alt="Church photo"',result['index.php'])
    def test_source_labels_hidden_in_every_location(self):
        # New photo layouts must not depend on a hero or family ancestor.
        self.assertIn('.photo-source { display:none !important; }',fix.CSS)
        self.assertIn('[data-hero-caption],',fix.CSS)
        self.assertNotIn('[data-family-welcome]',fix.CSS)
        self.assertNotIn('[data-hero-gallery]',fix.CSS)
    def test_upgrade_previous_caption_patch(self):
        previous=dict(self.before)
        previous['public-presentation.css']+=fix.LEGACY_CSS.encode()
        previous['public-presentation.js']=previous['public-presentation.js'].replace(fix.OLD_TIMER.encode(),fix.NEW_TIMER.encode())
        for name in ('index.php','sw.js'):
            previous[name]=previous[name].replace(b'tony-staff-20261001',fix.LEGACY_VERSION.encode()).replace(b'?v=1.0.0',b'?v='+fix.LEGACY_VERSION.encode())
        desired=fix.transform(previous)
        self.assertNotIn(fix.LEGACY_MARKER.encode(),desired['public-presentation.css'])
        self.assertIn(fix.CSS.encode(),desired['public-presentation.css'])
        self.assertEqual(fix.transform(desired),desired)
    def test_cache_only_no_private_policy_changes(self):
        result=fix.transform(self.before)
        self.assertEqual(result['sw.js'].split(b'function privatePolicy()')[1],self.before['sw.js'].split(b'function privatePolicy()')[1])
        self.assertEqual(result['sw.js'].count(fix.VERSION.encode()),3)
    def test_idempotent(self):
        self.install(); state={n:(self.app/n).read_bytes() for n in fix.FILES}
        self.assertIsNone(self.install())
        self.assertEqual(state,{n:(self.app/n).read_bytes() for n in fix.FILES})
    def test_rollback(self):
        backup=self.install(); self.assertEqual(fix.rollback(self.app,backup),4); self.assertOriginal()
    def test_later_edit_rollback_refusal(self):
        backup=self.install(); (self.app/'sw.js').write_text('later edit')
        with self.assertRaises(fix.Stop): fix.rollback(self.app,backup)
        self.assertEqual((self.app/'sw.js').read_text(),'later edit')
    def test_unknown_timer_no_write(self):
        (self.app/'public-presentation.js').write_bytes(self.before['public-presentation.js'].replace(b'8000',b'9000'))
        with self.assertRaises(fix.Stop): self.install()
        for name in fix.FILES[1:]: self.assertEqual((self.app/name).read_bytes(),self.before[name])
    def test_unknown_worker_no_write(self):
        (self.app/'sw.js').write_bytes(self.before['sw.js'].replace(b'3.0.3',b'9.0.0'))
        with self.assertRaises(fix.Stop): self.install()
        self.assertEqual((self.app/'public-presentation.js').read_bytes(),self.before['public-presentation.js'])
    def test_check_no_live_write(self): self.install(True); self.assertOriginal()
    def test_preserve_non_targets_and_permissions(self):
        self.install()
        for path in self.app.rglob('*'):
            if path.is_file() and path.name not in fix.FILES: self.assertEqual(path.read_text(),'private sentinel')
        for name in fix.FILES: self.assertEqual((self.app/name).stat().st_mode & 0o777,0o640)
    def test_partial_css_no_write(self):
        (self.app/'public-presentation.css').write_text(fix.MARKER)
        with self.assertRaises(fix.Stop): self.install()
        self.assertEqual((self.app/'public-presentation.js').read_bytes(),self.before['public-presentation.js'])
    def test_symlink_refusal(self):
        original=self.app/'index.php'; original.rename(self.root/'index-real.php');original.symlink_to(self.root/'index-real.php')
        with self.assertRaises(fix.Stop): self.install()
    def test_lint_failure_no_write(self):
        with patch.object(fix,'lint',side_effect=fix.Stop('lint error')):
            with self.assertRaises(fix.Stop): fix.apply(self.app,self.backups)
        self.assertOriginal()
    def test_partial_write_failure_restores(self):
        replace=os.replace
        def fail_once(src,dst):
            if str(src).endswith('patched/public-presentation.css'): raise OSError('simulated write failure')
            return replace(src,dst)
        with patch.object(fix.os,'replace',side_effect=fail_once):
            with self.assertRaises(OSError): self.install()
        self.assertOriginal()
    def test_gallery_without_optional_source_styles(self):
        self.before['public-presentation.css'] = b'.hero-photo {display:block}\n'
        (self.app/'public-presentation.css').write_bytes(self.before['public-presentation.css'])
        backup = self.install()
        self.assertIn(fix.NEW_TIMER.encode(), (self.app/'public-presentation.js').read_bytes())
        self.assertEqual((self.app/'public-presentation.css').read_bytes(), self.before['public-presentation.css'] + fix.CSS.encode())
        self.assertIsNone(self.install())
        self.assertEqual(fix.rollback(self.app, backup), 4)
        self.assertOriginal()
    def test_missing_gallery_styles_refused(self):
        (self.app/'public-presentation.css').write_bytes(b'.photo-source {display:block}\n')
        with self.assertRaises(fix.Stop): self.install()
        self.assertEqual((self.app/'public-presentation.js').read_bytes(), self.before['public-presentation.js'])

if __name__=='__main__': unittest.main(verbosity=2)
