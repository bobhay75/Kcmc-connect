#!/usr/bin/env python3
"""Exact payload and transaction tests in isolated temporary fixture roots."""
from __future__ import print_function
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import derive_installer as derive

HERE = Path(__file__).resolve().parent
CANDIDATE = '--candidate' in sys.argv
if CANDIDATE: sys.argv.remove('--candidate')
INSTALLER = 'candidate-installer.py' if CANDIDATE else 'installer.py'
PROVENANCE = 'candidate-provenance.json' if CANDIDATE else 'provenance.json'
GIT_ROOT = None
if '--git-root' in sys.argv:
    index = sys.argv.index('--git-root'); GIT_ROOT = Path(sys.argv[index + 1]); del sys.argv[index:index + 2]


def sha(content): return hashlib.sha256(content).hexdigest()


def identity(path):
    i = path.lstat()
    return (i.st_dev, i.st_ino, i.st_mode, i.st_uid, i.st_gid, i.st_nlink, i.st_size, i.st_mtime_ns, i.st_ctime_ns)


def wrapper():
    spec = importlib.util.spec_from_file_location('isolated_theme_installer', str(HERE / INSTALLER))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


class Fixture:
    def __init__(self, variant='livecalendar', after=False):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-app-theme-fixture-'); self.root = Path(self.temp.name)
        self.app = self.root / 'app'; self.app.mkdir(); self.w = wrapper(); self.m = self.w.load_engine(variant)
        self.m.APP = self.app; self.m.BACKUPS = self.root / 'private'; self.m.UID = os.getuid(); self.m.GID = os.getgid()
        self.before = {}; self.after = {}
        for path, row in self.m.FILES.items():
            if path == 'index.php':
                before = (HERE / 'evidence/public' / variant / 'index-before.php').read_bytes()
                target = (HERE / 'evidence/public' / variant / 'index-after.php').read_bytes()
            else:
                before = (HERE / 'evidence/before' / path).read_bytes() if row['before_sha256'] is not None else None
                target = (HERE / 'evidence/after' / path).read_bytes()
            self.before[path] = before; self.after[path] = target
            (self.app / path).parent.mkdir(parents=True, exist_ok=True)
            content = target if after else before
            if content is not None:
                (self.app / path).write_bytes(content); (self.app / path).chmod(0o664 if path == 'member/timeclock.php' else 0o644)
        self.prereqs = self.w.prerequisites(self.m)
        for path in self.prereqs:
            source = HERE / ('evidence/public/' + variant if path in self.m.PUBLIC_PREREQUISITES else 'evidence/prerequisite') / path
            target = self.app / path; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes()); target.chmod(0o644)
        self.prerequisite_before = {path: (self.app / path).read_bytes() for path in self.prereqs}
        self.prerequisite_ids = {path: identity(self.app / path) for path in self.prereqs}
        self.sentinels = {'config.php': b'<?php // owner configuration preserved\n',
            '.htaccess': b'# existing host routing preserved\n',
            'data/content.json': b'{"editorial":"preserved"}', 'data/private/users.json': b'{"accounts":"preserved"}',
            'data/private/timeclock.json': b'{"live punches":"preserved"}',
            'data/private/prayers.json': b'{"confidential":"preserved"}',
            'data/private/payroll-settings.json': b'{"channel":"off"}',
            'data/private/team-workspace.json': b'{"tasks":"preserved"}',
            'assets/visuals/real-photo.jpg': b'photo fixture untouched', '.git/HEAD': b'ref: refs/heads/main\n'}
        for path, content in self.sentinels.items():
            target = self.app / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content); target.chmod(0o600)
        self.sentinel_ids = {path: identity(self.app / path) for path in self.sentinels}
        self.w.load_engine = lambda: self.m
        self.real_choose = self.w.choose_php82_cli; self.w.choose_php82_cli = lambda: ('/synthetic/php82', '8.2.34')
    def close(self): self.temp.cleanup()
    def php(self, command, **kwargs):
        assert command[:2] == ['/synthetic/php82', '-n']
        if command[-1] == '-v': return b'PHP 8.2.34 (cli)\n'
        assert command[2] == '-l' and Path(command[3]).is_file()
        return b'No syntax errors detected\n'
    def cli(self, *args):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['installer.py'] + list(args)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.w.main()
        return code, output.getvalue()
    def apply(self):
        with mock.patch.object(subprocess, 'check_output', side_effect=self.php): return self.cli('apply')
    def session(self): return next(self.m.BACKUPS.glob('repair-*'))
    def journal(self): return self.m.load(self.session())
    def foreign(self, path, content=None):
        target = self.app / path; replacement = self.root / 'foreign-code'
        replacement.write_bytes(target.read_bytes() if content is None else content); replacement.chmod(0o644)
        os.replace(str(replacement), str(target)); return identity(target)
    def assert_before(self):
        for path, content in self.before.items():
            if content is None: assert not (self.app / path).exists(), path
            else: assert (self.app / path).read_bytes() == content, path
    def preserved(self, except_prerequisite=None):
        for path, content in self.sentinels.items():
            assert (self.app / path).read_bytes() == content and identity(self.app / path) == self.sentinel_ids[path], path
        for path, content in self.prerequisite_before.items():
            if path == except_prerequisite: continue
            assert (self.app / path).read_bytes() == content and identity(self.app / path) == self.prerequisite_ids[path], path


class ThemeTransactions(unittest.TestCase):
    def setUp(self): self.f = Fixture(); self.addCleanup(self.f.close)
    def test_default_check_readonly_and_public_variant_selected_exactly(self):
        code, text = self.f.cli(); self.assertEqual(code, 0, text); self.assertIn('CHECK READY', text)
        self.assertEqual(self.f.w.select_variant(self.f.m), 'livecalendar')
        self.assertFalse(self.f.m.BACKUPS.exists()); self.f.assert_before(); self.f.preserved()
    def test_both_complete_variants_apply_noop_reverse_rollback(self):
        for variant in ('main', 'livecalendar'):
            f = Fixture(variant); self.addCleanup(f.close)
            with mock.patch.object(subprocess, 'check_output', side_effect=f.php) as calls: code, text = f.cli('apply')
            self.assertEqual(code, 0, text); self.assertIn('REPAIRED app-theme.css', text)
            self.assertEqual(sum(call[0][0][2] == '-l' for call in calls.call_args_list), sum(path.endswith('.php') for path in f.m.PATHS))
            for path, content in f.after.items(): self.assertEqual((f.app / path).read_bytes(), content, path)
            self.assertEqual((f.app / 'member/timeclock.php').stat().st_mode & 0o777, 0o664)
            self.assertLess((f.session() / 'journal.json').stat().st_size, f.m.MAX_BYTES)
            self.assertEqual(f.w.select_variant(f.m), variant)
            ids = {path: identity(f.app / path) for path in f.m.PATHS}; journal_id = identity(f.session() / 'journal.json')
            code, text = f.cli('apply'); self.assertEqual(code, 0, text); self.assertIn('ALREADY_REPAIRED; no replacement', text)
            for path, prior in ids.items(): self.assertEqual(identity(f.app / path), prior)
            self.assertEqual(identity(f.session() / 'journal.json'), journal_id)
            code, text = f.cli('rollback', '--session', f.session().name); self.assertEqual(code, 0, text)
            f.assert_before(); f.preserved(); self.assertEqual(f.journal()['phase'], 'rolled_back')
    def test_each_single_target_after_flip_is_refused_before_backup(self):
        for path in self.f.m.PATHS:
            f = Fixture(); self.addCleanup(f.close); (f.app / path).write_bytes(f.after[path]); (f.app / path).chmod(0o644)
            code, text = f.cli('apply'); self.assertEqual(code, 1, path + text); self.assertIn('Mixed before/after', text)
            self.assertFalse(f.m.BACKUPS.exists()); f.preserved()
    def test_each_readonly_prerequisite_unknown_bytes_refuses_before_backup(self):
        for path in self.f.prereqs:
            f = Fixture(); self.addCleanup(f.close); f.foreign(path, b'// unrelated current code\n')
            code, text = f.cli('apply'); self.assertEqual(code, 1, path + text)
            self.assertIn('Approved current code prerequisite required: ' + path, text)
            self.assertFalse(f.m.BACKUPS.exists()); f.assert_before(); f.preserved(path)
    def test_main_index_with_livecalendar_css_refused(self):
        content = (HERE / 'evidence/public/main/index-before.php').read_bytes()
        self.f.foreign('index.php', content)
        self.assertEqual(self.f.w.select_variant(self.f.m), 'main')
        self.f.m.FILES['index.php'] = self.f.w.VARIANTS['main']['index']
        self.f.m.PUBLIC_PREREQUISITES = self.f.w.VARIANTS['main']['public_prerequisites']
        code, text = self.f.cli('apply'); self.assertEqual(code, 1); self.assertIn('public-presentation.css', text)
        self.assertFalse(self.f.m.BACKUPS.exists())
    def test_unknown_homepage_variant_and_new_provider_not_adopted(self):
        self.f.foreign('index.php', b'<?php // local unknown homepage\n')
        with self.assertRaises(self.f.w.Refusal): self.f.w.select_variant(self.f.m)
        provider = self.f.app / 'app-theme.css'; provider.write_bytes(b'/* existing unrelated file */\n'); provider.chmod(0o644)
        code, text = self.f.cli('apply'); self.assertEqual(code, 1); self.assertFalse(self.f.m.BACKUPS.exists())
    def test_stage_tamper_never_published(self):
        lint = self.f.m.lint
        def changed(session): (session / 'stage-0.code').write_bytes(b'/* forged stylesheet */\n'); return lint(session)
        with mock.patch.object(self.f.m, 'lint', side_effect=changed): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertIn('no live replacement', text); self.f.assert_before(); self.f.preserved()
    def test_after_noop_requires_no_php_or_backup_and_initial_leases(self):
        f = Fixture(after=True); self.addCleanup(f.close)
        with mock.patch.object(f.w, 'choose_php82_cli', side_effect=AssertionError('No PHP needed')): code, text = f.cli('apply')
        self.assertEqual(code, 0, text); self.assertFalse(f.m.BACKUPS.exists())
        apply = f.m.apply
        def changed(): result = apply(); f.foreign('index.php'); return result
        with mock.patch.object(f.m, 'apply', side_effect=changed): code, text = f.cli('apply')
        self.assertEqual(code, 1); self.assertIn('Code lease changed: index.php', text)
    def test_missing_php_cli_refuses_before_backup(self):
        with mock.patch.object(self.f.w, 'php82_candidates', return_value=[]):
            self.f.w.choose_php82_cli = self.f.real_choose; code, text = self.f.cli('apply')
        self.assertEqual(code, 1); self.assertFalse(self.f.m.BACKUPS.exists()); self.f.assert_before()
    def test_owned_failure_restores_consumers_and_new_provider_absence(self):
        journal = self.f.m.journal; failed = [False]; consumer = 'member/timeclock.php'
        def stopped(session, value):
            if value['phase'] == 'applying' and value['files'][consumer]['installed'] is not None and value['intent'] is None and not failed[0]:
                failed[0] = True; raise OSError('Synthetic verified checkpoint failure')
            return journal(session, value)
        with mock.patch.object(self.f.m, 'journal', side_effect=stopped): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertTrue(failed[0]); self.assertIn('verified owned code restored', text)
        self.assertEqual(self.f.journal()['phase'], 'rolled_back'); self.f.assert_before(); self.f.preserved()
    def test_ambiguous_consumer_replacement_retains_all_new_providers(self):
        replace = self.f.m.replace; index = self.f.m.PATHS.index('index.php')
        def stopped(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-' + str(index) + '.code': raise OSError('Synthetic ambiguous homepage replacement')
            return result
        with mock.patch.object(self.f.m, 'replace', side_effect=stopped): code, text = self.f.apply()
        self.assertEqual(code, 1); value = self.f.journal(); self.assertEqual(value['phase'], 'manual_review')
        self.assertIn('index.php', value['uncertain'])
        for path in derive.PROVIDERS:
            self.assertIsNotNone(value['files'][path]['installed'], path); self.f.m.verify_lease(path, value['files'][path]['installed'])
        self.f.preserved()
    def test_ambiguous_new_provider_link_retains_both_names(self):
        link = self.f.m.no_clobber_link
        def stopped(*args, **kwargs): link(*args, **kwargs); raise OSError('Synthetic ambiguous hardlink')
        with mock.patch.object(self.f.m, 'no_clobber_link', side_effect=stopped): code, text = self.f.apply()
        self.assertEqual(code, 1); value = self.f.journal(); self.assertEqual(value['phase'], 'manual_review')
        self.assertIn('app-theme.css', value['uncertain']); self.assertEqual((self.f.app / 'app-theme.css').stat().st_nlink, 2)
        self.assertIsNone(value['files']['app-theme.css']['installed']); self.f.preserved()
    def test_completed_consumer_recreation_during_rollback_retains_providers(self):
        self.assertEqual(self.f.apply()[0], 0); journal = self.f.m.journal; changed = [False]; path = 'member/timeclock.php'
        def recreated(session, value):
            result = journal(session, value)
            if value['phase'] == 'rolling_back' and value['files'][path]['installed'] is None and value['intent'] is None and not changed[0]:
                changed[0] = True; self.f.foreign(path, self.f.after[path])
            return result
        with mock.patch.object(self.f.m, 'journal', side_effect=recreated): code, text = self.f.cli('rollback', '--session', self.f.session().name)
        self.assertEqual(code, 1); self.assertTrue(changed[0]); value = self.f.journal()
        self.assertEqual(value['phase'], 'manual_review'); self.assertIn(path, value['uncertain'])
        for provider in derive.PROVIDERS: self.assertIsNotNone(value['files'][provider]['installed'], provider)
        self.f.preserved()
    def test_future_consumer_drift_retains_providers(self):
        journal = self.f.m.journal; changed = [False]; path = 'member/timeclock.php'
        def future(session, value):
            result = journal(session, value)
            if value['phase'] == 'applying' and value['files'][derive.PROVIDERS[-1]]['installed'] is not None and value['files'][path]['installed'] is None and value['intent'] is None and not changed[0]:
                changed[0] = True; self.f.foreign(path, self.f.after[path])
            return result
        with mock.patch.object(self.f.m, 'journal', side_effect=future): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertTrue(changed[0]); value = self.f.journal(); self.assertEqual(value['phase'], 'manual_review')
        for provider in derive.PROVIDERS: self.assertIsNotNone(value['files'][provider]['installed'], provider)
        self.f.preserved()
    def test_late_prerequisite_drift_prevents_success(self):
        journal = self.f.m.journal; path = 'public-presentation.css'
        def changed(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': self.f.foreign(path)
            return result
        with mock.patch.object(self.f.m, 'journal', side_effect=changed): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertNotIn('CHECK ALREADY_REPAIRED', text); self.f.preserved(path)
    def test_fixed_roots_and_env_cannot_expand_scope(self):
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/forged', 'KCMC_UID': '0', 'KCMC_PRIVATE_DATA_DIR': '/tmp/records'}):
            m = wrapper().load_engine('livecalendar')
        self.assertEqual(m.APP, Path('/home/bobsome1/public_html/kcmc-connect'))
        self.assertEqual(m.BACKUPS, Path('/home/bobsome1/kcmc-app-theme-livecalendar-backups'))
        self.assertEqual((m.UID, m.GID), (2162, 2147)); self.assertNotIn('config.php', m.PATHS)


class Provenance(unittest.TestCase):
    def test_exact_canonical_membership_and_unchanged_policy(self):
        raw, extension, source, runtime, prereqs, variants = derive.verify_inputs(allow_unapproved=CANDIDATE)
        self.assertEqual(sha(raw), derive.FROZEN_SHA256); self.assertEqual(sha(extension), derive.EXTENSION_SHA256)
        if GIT_ROOT is not None:
            self.assertIsNotNone(derive.SOURCE_COMMIT, 'Exact Git proof requires a frozen source commit')
            changed = subprocess.check_output(['git', 'diff', '--name-only', derive.BASE_COMMIT, derive.SOURCE_COMMIT,
                '--', 'KCMC-Connect-Phase6-Recreated/'], cwd=str(GIT_ROOT)).decode('utf-8').splitlines()
            self.assertEqual(set(changed), set('KCMC-Connect-Phase6-Recreated/' + path for path in runtime),
                             'Hosting targets must cover the complete bounded source runtime delta')
            for path, row in runtime.items():
                suffix = ':KCMC-Connect-Phase6-Recreated/' + path
                target = subprocess.check_output(['git', 'show', derive.SOURCE_COMMIT + suffix], cwd=str(GIT_ROOT))
                self.assertEqual(target, (HERE / 'evidence/after' / path).read_bytes(), path)
                if row['before_sha256'] is None:
                    exists = subprocess.call(['git', 'cat-file', '-e', derive.BASE_COMMIT + suffix], cwd=str(GIT_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.assertNotEqual(exists, 0, path)
                else:
                    before = subprocess.check_output(['git', 'show', derive.BASE_COMMIT + suffix], cwd=str(GIT_ROOT))
                    self.assertEqual(before, (HERE / 'evidence/before' / path).read_bytes(), path)
            for path, row in prereqs.items():
                for ref in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                    content = subprocess.check_output(['git', 'show', ref + ':KCMC-Connect-Phase6-Recreated/' + path], cwd=str(GIT_ROOT))
                    self.assertEqual((sha(content), len(content)), (row['sha256'], row['bytes']), path)
            for path, row in variants['main']['public_prerequisites'].items():
                for ref in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                    content = subprocess.check_output(['git', 'show', ref + ':KCMC-Connect-Phase6-Recreated/' + path], cwd=str(GIT_ROOT))
                    self.assertEqual((sha(content), len(content)), (row['sha256'], row['bytes']), path)
            fish_paths = {'provenance/fish-livecalendar-reviewed.json': 'runtime-reviewed.json'}
            fish_paths.update({'provenance/fish-before/' + path: 'evidence/livecalendar/' + path
                               for path in ('index.php', 'public-presentation.css', 'sw.js')})
            for local, historical in fish_paths.items():
                content = subprocess.check_output(['git', 'show', derive.BASE_COMMIT + ':tools/kcmc-fish-home-oct15/' + historical], cwd=str(GIT_ROOT))
                self.assertEqual(content, (HERE / local).read_bytes(), historical)
    def test_reproducible_installer_and_provenance(self):
        with tempfile.TemporaryDirectory(prefix='kcmc-theme-rederive-') as directory:
            copied = Path(directory) / 'package'; shutil.copytree(str(HERE), str(copied))
            command = [sys.executable, '-B', '-c', 'import derive_installer as d; d.build(candidate=True)'] if CANDIDATE else [sys.executable, '-B', 'derive_installer.py']
            subprocess.check_call(command, cwd=str(copied))
            for name in (INSTALLER, PROVENANCE): self.assertEqual((HERE / name).read_bytes(), (copied / name).read_bytes(), name)


if __name__ == '__main__': unittest.main()
