#!/usr/bin/env python3
"""Temporary-copy safety, exact source provenance and staged-code tests."""
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
THEME = HERE.parent / 'kcmc-app-theme-oct15'
CANDIDATE = '--candidate' in sys.argv
if CANDIDATE: sys.argv.remove('--candidate')
PREFIX = 'candidate-' if CANDIDATE else ''
GIT_ROOT = None
if '--git-root' in sys.argv:
    index = sys.argv.index('--git-root'); GIT_ROOT = Path(sys.argv[index + 1]); del sys.argv[index:index + 2]


def sha(content): return hashlib.sha256(content).hexdigest()


def identity(path):
    info = path.lstat()
    return tuple(getattr(info, key) for key in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
                                             'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def loaded(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


class Fixture:
    def __init__(self, variant='livecalendar', image='before'):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-manual-clock-'); self.root = Path(self.temp.name)
        self.app = self.root / 'app'; self.app.mkdir(); self.variant = variant
        self.theme = loaded(THEME / 'installer.py', 'isolated_theme')
        assert sha((THEME / 'installer.py').read_bytes()) == derive.THEME_SHA256
        self.w = loaded(HERE / (PREFIX + 'installer.py'), 'isolated_manual_clock')
        self.c = loaded(HERE / (PREFIX + 'coordinator.py'), 'isolated_coordinator')
        self.theme_modules = {}; self.manual_modules = {}
        def factory(wrapper, original, cache, label, variant=None):
            if variant is None:
                probe = factory(wrapper, original, cache, label, 'main')
                variant = wrapper.select_variant(probe)
            if variant not in cache:
                module = original(variant); module.APP = self.app
                module.BACKUPS = self.root / ('private-' + label + ('-' + variant if label == 'theme' else ''))
                module.UID, module.GID = os.getuid(), os.getgid(); cache[variant] = module
            return cache[variant]
        original_theme, original_manual = self.theme.load_engine, self.w.load_engine
        self.theme.load_engine = lambda variant=None: factory(self.theme, original_theme, self.theme_modules, 'theme', variant)
        self.w.load_engine = lambda variant=None: factory(self.w, original_manual, self.manual_modules, 'manual', variant)
        self.tm = self.theme.load_engine(variant); self.m = self.w.load_engine(variant)
        self.before = {path: (HERE / 'evidence/before' / path).read_bytes() for path in self.m.PATHS}
        self.after = {path: (HERE / 'evidence/after' / path).read_bytes() for path in self.m.PATHS}
        # Build a complete exact old theme tuple with functional prerequisites.
        for path, row in self.tm.FILES.items():
            if path == 'index.php': source = THEME / 'evidence/public' / variant / ('index-before.php' if image == 'pretheme' else 'index-after.php')
            elif image == 'pretheme' and row['before_sha256'] is None: continue
            else: source = THEME / ('evidence/before' if image == 'pretheme' else 'evidence/after') / path
            self.write(path, source.read_bytes())
        for path in self.theme.prerequisites(self.tm):
            source = THEME / ('evidence/public/' + variant if path in self.tm.PUBLIC_PREREQUISITES else 'evidence/prerequisite') / path
            self.write(path, source.read_bytes())
        if image != 'pretheme':
            for path, content in (self.after if image == 'after' else self.before).items(): self.write(path, content)
        self.guards = self.w.prerequisites(self.m)
        self.guard_before = {path: self.app.joinpath(path).read_bytes() for path in self.guards if self.app.joinpath(path).is_file()}
        self.guard_ids = {path: identity(self.app / path) for path in self.guard_before}
        self.sentinels = {'config.php': b'<?php // existing private owner configuration\n', '.htaccess': b'# existing host routing\n',
            'data/content.json': b'{"existing editorial":"unchanged"}', 'data/private/users.json': b'{"roles":"unchanged"}',
            'data/private/timeclock.json': b'{"punches and historical approval records":"unchanged"}',
            'data/private/payroll-settings.json': b'{"channel":"off"}',
            'data/private/prayers.json': b'{"care":"private"}', 'assets/real-photo.jpg': b'photo untouched',
            '.git/HEAD': b'ref: refs/heads/main\n'}
        for path, content in self.sentinels.items(): self.write(path, content, 0o600)
        self.sentinel_ids = {path: identity(self.app / path) for path in self.sentinels}
        self.real_choose = self.w.choose_php82_cli
        self.w.choose_php82_cli = self.theme.choose_php82_cli = lambda: ('/synthetic/php82', '8.2.34')
    def close(self): self.temp.cleanup()
    def write(self, path, content, mode=None):
        target = self.app / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
        target.chmod(mode if mode is not None else (0o664 if path == 'member/timeclock.php' else 0o644))
    def foreign(self, path, content=None):
        target = self.app / path; temporary = self.root / 'foreign'
        temporary.write_bytes(target.read_bytes() if content is None else content); temporary.chmod(0o644)
        os.replace(str(temporary), str(target))
    def php(self, argv, **kwargs):
        assert argv[:2] == ['/synthetic/php82', '-n'], argv
        if argv[-1] == '-v': return b'PHP 8.2.34 (cli)\n'
        assert argv[2] == '-l' and Path(argv[3]).name.startswith('stage-') and Path(argv[3]).is_file(), argv
        return b'No syntax errors detected\n'
    def cli(self, *args):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['installer.py'] + list(args)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.w.main()
        return code, output.getvalue()
    def apply(self):
        with mock.patch.object(subprocess, 'check_output', side_effect=self.php): return self.cli('apply')
    def coordinate(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), mock.patch.object(subprocess, 'check_output', side_effect=self.php):
            self.c.coordinate(self.theme, self.w)
        return output.getvalue()
    def preserved(self, check_guards=True, except_guard=None):
        for path, data in self.sentinels.items():
            assert (self.app / path).read_bytes() == data and identity(self.app / path) == self.sentinel_ids[path], path
        if check_guards:
            for path, data in self.guard_before.items():
                if path == except_guard: continue
                assert (self.app / path).read_bytes() == data and identity(self.app / path) == self.guard_ids[path], path
    def session(self): return next(self.m.BACKUPS.glob('repair-*'))


class Transactions(unittest.TestCase):
    def fixture(self, *args, **kwargs):
        result = Fixture(*args, **kwargs); self.addCleanup(result.close); return result
    def test_all_five_existing_targets_apply_noop_rollback_both_public_variants(self):
        for variant in ('main', 'livecalendar'):
            f = self.fixture(variant)
            code, text = f.cli('check'); self.assertEqual(code, 0, text); self.assertFalse(f.m.BACKUPS.exists())
            with mock.patch.object(subprocess, 'check_output', side_effect=f.php) as calls: code, text = f.cli('apply')
            self.assertEqual(code, 0, text); self.assertEqual(sum(c[0][0][2] == '-l' for c in calls.call_args_list), 5)
            for path, data in f.after.items(): self.assertEqual((f.app / path).read_bytes(), data)
            self.assertEqual((f.app / 'member/timeclock.php').stat().st_mode & 0o777, 0o664)
            self.assertLess((f.session() / 'journal.json').stat().st_size, f.m.MAX_BYTES)
            original = {p: identity(f.app / p) for p in f.m.PATHS}; journal = identity(f.session() / 'journal.json')
            code, text = f.cli('apply'); self.assertEqual(code, 0, text)
            self.assertEqual(original, {p: identity(f.app / p) for p in f.m.PATHS}); self.assertEqual(journal, identity(f.session() / 'journal.json'))
            code, text = f.cli('rollback', '--session', f.session().name); self.assertEqual(code, 0, text)
            for path, data in f.before.items(): self.assertEqual((f.app / path).read_bytes(), data)
            f.preserved()
    def test_each_target_mixed_or_unknown_image_stops_before_backup(self):
        for path in derive.PATHS:
            for content in (None, b'<?php // unreviewed local changes\n'):
                f = self.fixture(); f.foreign(path, f.after[path] if content is None else content)
                code, text = f.apply(); self.assertEqual(code, 1, path + text)
                self.assertFalse(f.m.BACKUPS.exists()); f.preserved()
                with self.assertRaises(f.w.Refusal): f.w.classify_targets(f.m)
    def test_every_final_readonly_guard_is_required(self):
        seed = self.fixture()
        self.assertEqual(len(seed.guards), 60)
        for path in seed.guards:
            f = self.fixture(); f.foreign(path, b'<?php // unrelated current code\n')
            code, text = f.apply(); self.assertEqual(code, 1, path + text)
            self.assertFalse(f.m.BACKUPS.exists()); f.preserved(except_guard=path)
    def test_staged_tamper_cannot_publish_and_missing_php_cannot_create_backup(self):
        f = self.fixture(); lint = f.m.lint
        def changed(session): (session / 'stage-0.code').write_bytes(b'<?php // forged stage\n'); return lint(session)
        with mock.patch.object(f.m, 'lint', side_effect=changed): code, text = f.apply()
        self.assertEqual(code, 1, text); self.assertIn('no live replacement', text)
        for path, data in f.before.items(): self.assertEqual((f.app / path).read_bytes(), data)
        f.preserved()
        f = self.fixture(); f.w.choose_php82_cli = f.real_choose
        with mock.patch.object(f.w, 'php82_candidates', return_value=[]): code, text = f.cli('apply')
        self.assertEqual(code, 1, text); self.assertFalse(f.m.BACKUPS.exists())
    def test_owned_checkpoint_failure_rolls_back_all_five(self):
        f = self.fixture(); journal = f.m.journal; failed = [False]
        def stopped(session, value):
            if value['phase'] == 'applying' and value['files']['member/timeclock.php']['installed'] is not None and value['intent'] is None and not failed[0]:
                failed[0] = True; raise OSError('Synthetic owned checkpoint failure')
            return journal(session, value)
        with mock.patch.object(f.m, 'journal', side_effect=stopped): code, text = f.apply()
        self.assertEqual(code, 1, text); self.assertTrue(failed[0]); self.assertEqual(f.m.load(f.session())['phase'], 'rolled_back')
        for path, data in f.before.items(): self.assertEqual((f.app / path).read_bytes(), data)
        f.preserved()
    def test_ambiguous_move_retains_candidates_and_refuses_retry(self):
        f = self.fixture(); replace = f.m.replace
        def interrupted(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-1.code': raise OSError('Synthetic uncertain replacement')
            return result
        with mock.patch.object(f.m, 'replace', side_effect=interrupted): code, text = f.apply()
        self.assertEqual(code, 1, text); value = f.m.load(f.session())
        self.assertEqual(value['phase'], 'manual_review'); self.assertIn('member/timeclock.php', value['uncertain'])
        self.assertIsNotNone(value['files']['lib/timeclock.php']['installed'])
        self.assertEqual((f.app / 'lib/timeclock.php').read_bytes(), f.after['lib/timeclock.php'])
        code, text = f.apply(); self.assertEqual(code, 1, text); self.assertNotIn('CHECK ALREADY_REPAIRED', text); f.preserved()
    def test_restored_consumer_recreation_retains_its_new_library(self):
        f = self.fixture(); self.assertEqual(f.apply()[0], 0); journal = f.m.journal; changed = [False]
        path = 'member/timeclock.php'
        def recreated(session, value):
            result = journal(session, value)
            if value['phase'] == 'rolling_back' and value['files'][path]['installed'] is None and value['intent'] is None and not changed[0]:
                changed[0] = True; f.foreign(path, f.after[path])
            return result
        with mock.patch.object(f.m, 'journal', side_effect=recreated): code, text = f.cli('rollback', '--session', f.session().name)
        self.assertEqual(code, 1, text); self.assertTrue(changed[0]); value = f.m.load(f.session())
        self.assertEqual(value['phase'], 'manual_review'); self.assertIn(path, value['uncertain'])
        self.assertIsNotNone(value['files']['lib/timeclock.php']['installed'])
        self.assertEqual((f.app / 'lib/timeclock.php').read_bytes(), f.after['lib/timeclock.php']); f.preserved()
    def test_future_consumer_drift_after_library_install_retains_provider(self):
        f = self.fixture(); journal = f.m.journal; changed = [False]; path = 'member/timeclock.php'
        def future(session, value):
            result = journal(session, value)
            if value['phase'] == 'applying' and value['files']['lib/timeclock.php']['installed'] is not None and value['files'][path]['installed'] is None and value['intent'] is None and not changed[0]:
                changed[0] = True; f.foreign(path, f.after[path])
            return result
        with mock.patch.object(f.m, 'journal', side_effect=future): code, text = f.apply()
        self.assertEqual(code, 1, text); self.assertTrue(changed[0]); value = f.m.load(f.session())
        self.assertEqual(value['phase'], 'manual_review'); self.assertIn(path, value['uncertain'])
        self.assertIsNotNone(value['files']['lib/timeclock.php']['installed'])
        self.assertEqual((f.app / 'lib/timeclock.php').read_bytes(), f.after['lib/timeclock.php']); f.preserved()
    def test_late_same_byte_readonly_replacement_prevents_success(self):
        f = self.fixture(); journal = f.m.journal; path = 'app-theme.css'
        def changed(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': f.foreign(path)
            return result
        with mock.patch.object(f.m, 'journal', side_effect=changed): code, text = f.apply()
        self.assertEqual(code, 1, text); self.assertNotIn('CHECK ALREADY_REPAIRED', text); f.preserved(except_guard=path)
    def test_noop_requires_no_php_and_unchanged_initial_target_leases(self):
        f = self.fixture(image='after')
        with mock.patch.object(f.w, 'choose_php82_cli', side_effect=AssertionError('No PHP required')): code, text = f.cli('apply')
        self.assertEqual(code, 0, text); self.assertFalse(f.m.BACKUPS.exists())
        apply = f.m.apply
        def raced(): result = apply(); f.foreign('member/timeclock.php'); return result
        with mock.patch.object(f.m, 'apply', side_effect=raced): code, text = f.cli('apply')
        self.assertEqual(code, 1, text); self.assertIn('Code lease changed', text)
    def test_fixed_host_roots_inventory_and_unchanged_engine(self):
        f = self.fixture(); w = loaded(HERE / (PREFIX + 'installer.py'), 'fixed_scope')
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/forged', 'KCMC_PRIVATE_DATA_DIR': '/tmp/private', 'KCMC_UID': '0'}): m = w.load_engine('main')
        self.assertEqual(m.APP, Path('/home/bobsome1/public_html/kcmc-connect'))
        self.assertEqual(m.BACKUPS, Path('/home/bobsome1/kcmc-manual-timeclock-backups'))
        self.assertEqual((m.UID, m.GID), (2162, 2147)); self.assertEqual(m.PATHS, derive.PATHS)
        self.assertEqual(m.DEPENDENCIES, derive.DEPENDENCIES); self.assertTrue(all(row['before_sha256'] for row in m.FILES.values()))


class Coordination(unittest.TestCase):
    def fixture(self, *args, **kwargs):
        result = Fixture(*args, **kwargs); self.addCleanup(result.close); return result
    def test_pretheme_and_themed_and_final_reruns_both_public_variants(self):
        for variant in ('main', 'livecalendar'):
            for image in ('pretheme', 'before', 'after'):
                f = self.fixture(variant, image); output = f.coordinate()
                self.assertIn('COMPLETE_ALREADY_REPAIRED' if image == 'after' else 'COMPLETE_REPAIRED', output)
                self.assertEqual(f.m.inspect()[0], 'after'); f.preserved(check_guards=image != 'pretheme')
                snapshots = {p: identity(f.app / p) for p in f.m.PATHS + tuple(f.guards)}
                with mock.patch.object(f.theme, 'main', side_effect=AssertionError('Obsolete theme main must not run')): output = f.coordinate()
                self.assertIn('obsolete theme installer skipped', output)
                self.assertEqual(snapshots, {p: identity(f.app / p) for p in snapshots})
    def test_unknown_or_mixed_targets_do_not_enter_either_installer(self):
        for image in ('pretheme', 'before', 'after'):
            for path in derive.PATHS:
                f = self.fixture(image=image); f.foreign(path, b'<?php // unknown local patch\n')
                with mock.patch.object(f.theme, 'main', side_effect=AssertionError('No old helper')), mock.patch.object(f.w, 'main', side_effect=AssertionError('No new helper')):
                    with self.assertRaises(f.w.Refusal): f.coordinate()
                self.assertFalse(f.m.BACKUPS.exists()); self.assertFalse(f.tm.BACKUPS.exists())
        f = self.fixture(); f.foreign('member/timeclock.php', f.after['member/timeclock.php'])
        with self.assertRaises(f.w.Refusal): f.coordinate()
    def test_old_whole_bundle_drift_prevents_pretheme_upgrade(self):
        f = self.fixture(image='pretheme'); f.foreign('admin/posts.php', b'<?php // independent local edit\n')
        with self.assertRaises((f.theme.Refusal, f.tm.Refusal)): f.coordinate()
        self.assertFalse(f.m.BACKUPS.exists()); self.assertFalse(f.tm.BACKUPS.exists()); f.preserved(check_guards=False)
    def test_final_state_requires_all_theme_guards_and_unfinished_old_journals(self):
        f = self.fixture(image='after'); f.foreign('app-navigation.js', b'// independent future code\n')
        with self.assertRaises(f.m.Refusal): f.coordinate()
        f = self.fixture(image='after')
        with mock.patch.object(f.tm, 'unfinished', side_effect=f.tm.Refusal('Unfinished synthetic old theme repair')):
            with self.assertRaises(f.tm.Refusal): f.coordinate()
        self.assertFalse(f.m.BACKUPS.exists())
        f = self.fixture(image='after'); other = f.theme.load_engine('main')
        with mock.patch.object(other, 'unfinished', side_effect=other.Refusal('Unfinished alternate old theme repair')):
            with self.assertRaises(other.Refusal): f.coordinate()
        self.assertFalse(f.m.BACKUPS.exists())
    def test_incomplete_manual_journal_never_reenters_old_theme(self):
        f = self.fixture(image='after'); f.m.private_dir(f.m.BACKUPS, create=True)
        with mock.patch.object(f.w.load_engine('main'), 'unfinished', side_effect=f.m.Refusal('Unfinished manual repair')):
            with mock.patch.object(f.theme, 'main', side_effect=AssertionError('Old helper must not run')):
                with self.assertRaises(f.m.Refusal): f.coordinate()
    def test_alternate_old_journal_stops_both_before_states_before_any_helper(self):
        for image in ('pretheme', 'before'):
            for variant in ('main', 'livecalendar'):
                f = self.fixture(variant, image)
                other = f.theme.load_engine('main' if variant == 'livecalendar' else 'livecalendar')
                prior = {str(p.relative_to(f.app)): identity(p) for p in f.app.rglob('*') if p.is_file()}
                with mock.patch.object(other, 'unfinished', side_effect=other.Refusal('Unfinished alternate theme repair')):
                    with mock.patch.object(f.theme, 'main', side_effect=AssertionError('No old helper')), mock.patch.object(f.w, 'main', side_effect=AssertionError('No new helper')):
                        with self.assertRaises(other.Refusal): f.coordinate()
                self.assertEqual(prior, {str(p.relative_to(f.app)): identity(p) for p in f.app.rglob('*') if p.is_file()})
                self.assertFalse(f.m.BACKUPS.exists()); self.assertFalse(f.tm.BACKUPS.exists())
    def test_theme_success_survives_later_manual_refusal(self):
        f = self.fixture(image='pretheme'); run = f.c.run_action
        def later(helper, action):
            if helper is f.w and action == 'apply': raise f.c.Refusal('Synthetic manual stage refusal')
            return run(helper, action)
        with mock.patch.object(f.c, 'run_action', side_effect=later):
            with self.assertRaises(f.c.Refusal): f.coordinate()
        self.assertEqual(f.tm.inspect()[0], 'after'); self.assertEqual(f.m.inspect()[0], 'before')
        self.assertFalse(f.m.BACKUPS.exists()); f.preserved(check_guards=False)
    def test_both_helpers_verified_before_either_executes(self):
        f = self.fixture(); theme_path = f.root / 'theme.py'; manual_path = f.root / 'manual.py'
        theme_path.write_bytes((THEME / 'installer.py').read_bytes()); manual_path.write_bytes((HERE / (PREFIX + 'installer.py')).read_bytes())
        helpers = f.c.load_helpers(theme_path, manual_path); self.assertEqual(len(helpers), 2)
        with mock.patch.object(f.c, 'helper_bytes', side_effect=[theme_path.read_bytes(), f.c.Refusal('Invalid second helper')]), mock.patch('builtins.compile', side_effect=AssertionError('First helper must not execute early')):
            with self.assertRaises(f.c.Refusal): f.c.load_helpers(theme_path, manual_path)
        manual_path.unlink(); manual_path.symlink_to(theme_path)
        with self.assertRaises(OSError): f.c.load_helpers(theme_path, manual_path)


class Provenance(unittest.TestCase):
    def test_exact_delta_guards_and_reproducibility(self):
        raw, extension, source, runtime, guards, variants, pretheme = derive.verify_inputs(allow_unapproved=CANDIDATE)
        self.assertEqual(sha(raw), derive.FROZEN_SHA256); self.assertEqual(sha(extension), derive.EXTENSION_SHA256)
        old_runtime = json.loads((THEME / 'runtime-reviewed.json').read_text())
        old_guards = json.loads((THEME / 'prerequisites-reviewed.json').read_text())
        self.assertEqual(set(guards), (set(old_runtime) | set(old_guards)) - set(derive.PATHS) - {'index.php'})
        for variant in variants:
            for path, row in variants[variant]['guards'].items():
                data = (THEME / 'evidence/public' / variant / ('index-after.php' if path == 'index.php' else path)).read_bytes()
                self.assertEqual(data, (HERE / 'evidence/public' / variant / path).read_bytes())
                self.assertEqual((sha(data), len(data)), (row['sha256'], row['bytes']))
        for path in derive.PATHS:
            prior = THEME / 'evidence/before' / path
            data = prior.read_bytes() if prior.exists() else (HERE / 'evidence/before' / path).read_bytes()
            self.assertEqual(data, (HERE / 'evidence/pretheme' / path).read_bytes())
        if GIT_ROOT is not None:
            self.assertIsNotNone(derive.SOURCE_COMMIT)
            prefix = 'KCMC-Connect-Phase6-Recreated/'
            changed = subprocess.check_output(['git', 'diff', '--name-only', derive.BASE_COMMIT, derive.SOURCE_COMMIT, '--', prefix], cwd=str(GIT_ROOT)).decode().splitlines()
            self.assertEqual(set(changed), set(prefix + p for p in derive.PATHS))
            for path in derive.PATHS:
                for kind, ref in (('before', derive.BASE_COMMIT), ('after', derive.SOURCE_COMMIT)):
                    data = subprocess.check_output(['git', 'show', ref + ':' + prefix + path], cwd=str(GIT_ROOT))
                    self.assertEqual(data, (HERE / 'evidence' / kind / path).read_bytes())
                    mode = subprocess.check_output(['git', 'ls-tree', ref, '--', prefix + path], cwd=str(GIT_ROOT)).split()[0]
                    self.assertEqual(mode, b'100644')
            for path, row in guards.items():
                for ref in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                    data = subprocess.check_output(['git', 'show', ref + ':' + prefix + path], cwd=str(GIT_ROOT))
                    self.assertEqual((sha(data), len(data)), (row['sha256'], row['bytes']))
        with tempfile.TemporaryDirectory(prefix='kcmc-manual-clock-reproduce-') as directory:
            copied = Path(directory) / 'package'; shutil.copytree(str(HERE), str(copied))
            command = [sys.executable, '-B', '-c', 'import derive_installer as d; d.build(candidate=True)'] if CANDIDATE else [sys.executable, '-B', 'derive_installer.py']
            subprocess.check_call(command, cwd=str(copied))
            for name in ('installer.py', 'coordinator.py', 'provenance.json'):
                self.assertEqual((HERE / (PREFIX + name)).read_bytes(), (copied / (PREFIX + name)).read_bytes())


if __name__ == '__main__': unittest.main()
