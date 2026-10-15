#!/usr/bin/env python3
"""Actual fixed owner/workflow payloads in isolated temporary transactions only."""
from __future__ import print_function
import ast
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
RUNTIME_ROOT = None; GIT_ROOT = None
for option in ('--runtime-root', '--git-root'):
    if option in sys.argv:
        i = sys.argv.index(option); target = Path(sys.argv[i + 1]); del sys.argv[i:i + 2]
        if option == '--runtime-root': RUNTIME_ROOT = target
        else: GIT_ROOT = target


def sha(content): return hashlib.sha256(content).hexdigest()


def identity(path):
    s = path.lstat(); return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def wrapper():
    spec = importlib.util.spec_from_file_location('isolated_coordinator', str(HERE / 'installer.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


class Fixture:
    def __init__(self, profile='pre_a7', owner_after=False):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-workflows-release-'); self.root = Path(self.temp.name)
        self.app = self.root / 'app'; self.app.mkdir(); self.w = wrapper(); self.engines = self.w.load_engines()
        for key, module in self.engines.items():
            module.APP = self.app; module.BACKUPS = self.root / ('private-' + key); module.UID = os.getuid(); module.GID = os.getgid()
        self.profile = profile; self.m = self.engines[profile]
        for parent in ('lib', 'admin', 'member'): (self.app / parent).mkdir()
        self.before = {}
        for path, item in self.m.FILES.items():
            content = (HERE / 'evidence' / profile / path).read_bytes() if item['before_sha256'] is not None else None
            self.before[path] = content
            if content is not None: (self.app / path).write_bytes(content); (self.app / path).chmod(0o664 if path == 'member/timeclock.php' else 0o644)
        for path in self.engines['owner'].PATHS:
            content = (HERE / 'evidence' / ('owner_after' if owner_after else 'owner_before') / path).read_bytes()
            (self.app / path).write_bytes(content); (self.app / path).chmod(0o644); self.before[path] = content
        self.bootstrap = self.app / 'lib/bootstrap.php'
        self.bootstrap.write_bytes((HERE / 'evidence/prerequisite/lib/bootstrap.php').read_bytes()); self.bootstrap.chmod(0o644)
        self.sentinels = {'lib/bootstrap.php': self.bootstrap.read_bytes(), 'config.php': b'<?php // private owner setting retained\n',
            'data/content.json': b'{"editorial":"retained"}', 'data/private/users.json': b'{"accounts":"retained"}',
            'data/private/timeclock.json': b'{"punches":"retained"}', 'data/private/prayers.json': b'{"prayers":"retained"}',
            '.git/HEAD': b'ref: refs/heads/main\n', 'index.php': b'<?php // fish homepage retained\n', 'sw.js': b'// worker retained\n'}
        for path, content in self.sentinels.items():
            if path == 'lib/bootstrap.php': continue
            p = self.app / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(content); p.chmod(0o600)
        self.ids = {path: identity(self.app / path) for path in self.sentinels}
        self.w.load_engines = lambda: self.engines
        self.real_choose = self.w.choose_php82_cli
        self.w.choose_php82_cli = lambda: ('/synthetic/php82', '8.2.34')
    def close(self): self.temp.cleanup()
    def preserved(self, allow_bootstrap=False):
        for path, content in self.sentinels.items():
            if allow_bootstrap and path == 'lib/bootstrap.php': continue
            assert (self.app / path).read_bytes() == content and identity(self.app / path) == self.ids[path], path
    def php(self, command, **kwargs):
        assert command[0] == '/synthetic/php82' and command[1] == '-n'
        if command[-1] == '-v': return b'PHP 8.2.34 (cli)\n'
        assert command[2] == '-l' and Path(command[3]).is_file()
        return b'No syntax errors detected\n'
    def cli(self, *args):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['installer.py'] + list(args)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output): code = self.w.main()
        return code, output.getvalue()
    def apply(self):
        with mock.patch.object(subprocess, 'check_output', side_effect=self.php): return self.cli('apply')
    def session(self, group): return next(self.engines[group].BACKUPS.glob('repair-*'))
    def drift_bootstrap(self):
        p = self.root / 'external-bootstrap.php'; p.write_bytes(self.bootstrap.read_bytes()); p.chmod(0o644); os.replace(str(p), str(self.bootstrap))


class CoordinatorTests(unittest.TestCase):
    def setUp(self): self.f = Fixture(); self.addCleanup(self.f.close)
    def test_default_check_is_readonly_and_sees_both_groups(self):
        code, text = self.f.cli(); self.assertEqual(code, 0, text); self.assertIn('GROUP owner READY', text); self.assertIn('GROUP workflows READY', text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values())); self.f.preserved()
    def test_both_profiles_apply_common_after_noop_and_separate_rollbacks(self):
        for profile in derive.VARIANTS:
            f = Fixture(profile); self.addCleanup(f.close)
            with mock.patch.object(subprocess, 'check_output', side_effect=f.php) as calls: code, text = f.cli('apply')
            self.assertEqual(code, 0, text); self.assertIn('GROUP owner REPAIRED', text); self.assertIn('GROUP workflows REPAIRED', text)
            self.assertEqual(sum(call[0][0][2] == '-l' for call in calls.call_args_list), 20)
            self.assertEqual(f.w.select(f.engines)[:2], ('common_after', 'after'))
            code, text = f.cli('apply'); self.assertEqual(code, 0, text); self.assertIn('both independent code groups verified', text)
            code, text = f.cli('rollback', '--group', 'workflows', '--variant', profile, '--session', f.session(profile).name); self.assertEqual(code, 0, text)
            code, text = f.cli('rollback', '--group', 'owner', '--session', f.session('owner').name); self.assertEqual(code, 0, text)
            for path, before in f.before.items():
                if before is None: self.assertFalse((f.app / path).exists(), path)
                else: self.assertEqual((f.app / path).read_bytes(), before, path)
            f.preserved()
    def test_already_after_owner_group_is_skipped_without_backup(self):
        f = Fixture(owner_after=True); self.addCleanup(f.close); code, text = f.apply(); self.assertEqual(code, 0, text)
        self.assertIn('GROUP owner ALREADY_REPAIRED', text); self.assertFalse(f.engines['owner'].BACKUPS.exists()); f.preserved()
    def test_mixed_owner_group_refuses_before_workflow_or_backup(self):
        p = self.f.engines['owner'].PATHS[0]; (self.f.app / p).write_bytes((HERE / 'evidence/owner_after' / p).read_bytes())
        code, text = self.f.apply(); self.assertEqual(code, 1); self.assertNotIn(' REPAIRED', text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values()))
    def test_all_single_partial_workflow_flips_refuse_before_any_group_apply(self):
        for path in self.f.m.PATHS:
            before = self.f.before[path]; (self.f.app / path).write_bytes((HERE / 'evidence/after' / path).read_bytes()); (self.f.app / path).chmod(0o644)
            code, text = self.f.cli('check'); self.assertEqual(code, 1, path + text)
            if before is None: (self.f.app / path).unlink()
            else: (self.f.app / path).write_bytes(before); (self.f.app / path).chmod(0o644)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values()))
    def test_unknown_workflow_refuses_before_owner_apply(self):
        p = self.f.m.PATHS[0]; (self.f.app / p).write_bytes(b'<?php // unknown code retained\n')
        code, text = self.f.apply(); self.assertEqual(code, 1); self.assertIn('Use diagnose', text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values()))
        for p in self.f.engines['owner'].PATHS: self.assertEqual((self.f.app / p).read_bytes(), self.f.before[p])
    def test_diagnostic_prints_only_twentyone_code_targets_and_bootstrap(self):
        code, text = self.f.cli('diagnose'); self.assertEqual(code, 0, text); self.assertEqual(text.count('CODE '), 22)
        self.assertEqual(text.count(' ABSENT '), 5); self.assertNotIn('private owner setting', text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values())); self.f.preserved()
    def test_bootstrap_identity_drift_during_php_probe_refuses_ready(self):
        def choose(): self.f.drift_bootstrap(); return '/synthetic/php82', '8.2.34'
        self.f.w.choose_php82_cli = choose
        code, text = self.f.cli('check'); self.assertEqual(code, 1); self.assertNotIn('CHECK READY', text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values())); self.f.preserved(True)
    def test_later_workflow_lint_failure_preserves_verified_owner_success(self):
        def fail(command, **kwargs):
            if self.f.m.BACKUPS.exists() and command[-1].endswith('stage-17.code'): raise subprocess.CalledProcessError(255, command)
            return self.f.php(command, **kwargs)
        with mock.patch.object(subprocess, 'check_output', side_effect=fail): code, text = self.f.cli('apply')
        self.assertEqual(code, 1); self.assertIn('GROUP owner REPAIRED', text); self.assertIn('PRIOR_VERIFIED_GROUPS owner', text)
        self.assertNotIn('GROUP workflows REPAIRED', text)
        for p, row in self.f.engines['owner'].FILES.items(): self.assertEqual(sha((self.f.app / p).read_bytes()), row['after_sha256'])
        for p in self.f.m.PATHS:
            if self.f.before[p] is None: self.assertFalse((self.f.app / p).exists())
            else: self.assertEqual((self.f.app / p).read_bytes(), self.f.before[p])
        self.f.preserved()
    def test_postrename_consumer_uncertainty_retains_changed_providers(self):
        replace = self.f.m.replace
        def fail(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-17.code': raise OSError('post-rename consumer uncertainty')
            return result
        with mock.patch.object(self.f.m, 'replace', side_effect=fail): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertNotIn('GROUP workflows REPAIRED', text); self.assertIn('manual review', text)
        value = self.f.m.load(self.f.session(self.f.profile)); self.assertEqual(value['phase'], 'manual_review')
        for p in ('lib/timeclock.php', 'lib/push-subscriptions.php', 'admin/home.php'):
            self.assertIsNotNone(value['files'][p]['installed']); self.f.m.verify_lease(p, value['files'][p]['installed'])
        self.f.preserved()
    def test_late_workflow_journal_bootstrap_drift_reports_roots_without_success(self):
        journal = self.f.m.journal
        def fail(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': self.f.drift_bootstrap()
            return result
        with mock.patch.object(self.f.m, 'journal', side_effect=fail): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertNotIn('GROUP workflows REPAIRED', text); self.assertIn('PRIVATE_BACKUP_ROOT ', text)
        value = self.f.m.load(self.f.session(self.f.profile)); self.assertEqual(value['phase'], 'applied')
        for p in self.f.m.PATHS: self.f.m.verify_lease(p, value['files'][p]['installed'])
        self.f.preserved(True)
    def test_noop_bootstrap_drift_never_reports_workflow_success(self):
        self.assertEqual(self.f.apply()[0], 0); apply = self.f.m.apply
        def fail(): result = apply(); self.f.drift_bootstrap(); return result
        with mock.patch.object(self.f.m, 'apply', side_effect=fail): code, text = self.f.cli('apply')
        self.assertEqual(code, 1); self.assertNotIn('GROUP workflows ALREADY_REPAIRED', text); self.f.preserved(True)
    def test_link_race_does_not_overwrite_unknown_new_route(self):
        link = self.f.m.no_clobber_link; path = 'admin/prayer-care.php'; before = []
        def fail(source, target, **kwargs):
            if target == 'prayer-care.php':
                p = self.f.app / path; p.write_bytes(b'<?php // concurrent route retained\n'); p.chmod(0o644); before.append(identity(p))
            return link(source, target, **kwargs)
        with mock.patch.object(self.f.m, 'no_clobber_link', side_effect=fail): code, text = self.f.apply()
        self.assertEqual(code, 1); self.assertEqual(identity(self.f.app / path), before[0]); self.assertIn('manual review', text)
    def test_no_api_config_schedule_or_environment_override(self):
        w = wrapper(); modules = w.load_engines()
        self.assertEqual(sum(len(m.PATHS) for k, m in modules.items() if k in ('owner', 'pre_a7')), 21)
        self.assertNotIn('lib/bootstrap.php', set(modules['owner'].PATHS) | set(modules['pre_a7'].PATHS))
        for m in modules.values(): self.assertEqual(m.APP, Path('/home/bobsome1/public_html/kcmc-connect')); self.assertEqual((m.UID, m.GID), (2162, 2147))
        code, text = self.f.cli('apply', '--group', 'owner'); self.assertEqual(code, 1); self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values()))
    def test_rollback_prerequisite_drift_preserves_all_code_and_journal(self):
        self.assertEqual(self.f.apply()[0], 0); session = self.f.session(self.f.profile)
        ids = {p: identity(self.f.app / p) for p in self.f.m.PATHS}; journal = identity(session / 'journal.json'); self.f.drift_bootstrap(); self.f.bootstrap.write_bytes(b'<?php // unknown bootstrap edit retained\n')
        code, text = self.f.cli('rollback', '--group', 'workflows', '--variant', self.f.profile, '--session', session.name)
        self.assertEqual(code, 1); self.assertNotIn(' ROLLED_BACK ', text)
        for p, prior in ids.items(): self.assertEqual(identity(self.f.app / p), prior)
        self.assertEqual(identity(session / 'journal.json'), journal)


class ProvenanceTests(unittest.TestCase):
    def test_exact_inputs_targets_and_optional_canonical_source_membership(self):
        raw, manifest, runtime, owner, prerequisite = derive.verify_inputs()
        if RUNTIME_ROOT is not None:
            for path in manifest['paths']: self.assertEqual((HERE / 'evidence/after' / path).read_bytes(), (RUNTIME_ROOT / path).read_bytes())
            for path in owner: self.assertEqual((HERE / 'evidence/owner_after' / path).read_bytes(), (RUNTIME_ROOT / path).read_bytes())
            self.assertEqual(sha((RUNTIME_ROOT / prerequisite['path']).read_bytes()), prerequisite['sha256'])
        if GIT_ROOT is not None:
            for path, row in manifest['files'].items():
                target = subprocess.check_output(['git', 'show', derive.SOURCE_COMMIT + ':KCMC-Connect-Phase6-Recreated/' + path], cwd=str(GIT_ROOT))
                self.assertEqual((HERE / 'evidence/after' / path).read_bytes(), target)
                object_path = derive.BASE_COMMIT + ':KCMC-Connect-Phase6-Recreated/' + path
                if row['before_sha256'] is None:
                    absent = subprocess.call(['git', 'cat-file', '-e', object_path], cwd=str(GIT_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.assertNotEqual(absent, 0, path)
                else:
                    source = subprocess.check_output(['git', 'show', object_path], cwd=str(GIT_ROOT))
                    self.assertEqual((HERE / 'evidence/owner_a7' / path).read_bytes(), source)
            for path in owner:
                for commit in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                    source = subprocess.check_output(['git', 'show', commit + ':KCMC-Connect-Phase6-Recreated/' + path], cwd=str(GIT_ROOT))
                    self.assertEqual((HERE / 'evidence/owner_after' / path).read_bytes(), source)
            for commit in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                source = subprocess.check_output(['git', 'show', commit + ':KCMC-Connect-Phase6-Recreated/' + prerequisite['path']], cwd=str(GIT_ROOT))
                self.assertEqual((HERE / 'evidence/prerequisite' / prerequisite['path']).read_bytes(), source)
    def test_reproducible_standalone_installer_and_provenance(self):
        with tempfile.TemporaryDirectory(prefix='kcmc-workflows-rederive-') as directory:
            copied = Path(directory) / 'package'; shutil.copytree(str(HERE), str(copied))
            subprocess.check_call([sys.executable, '-B', 'derive_installer.py'], cwd=str(copied))
            for path in ('installer.py', 'provenance.json'): self.assertEqual((copied / path).read_bytes(), (HERE / path).read_bytes())
    def test_frozen_owner_policy_and_workflow_existing_mover_are_preserved(self):
        modules = wrapper().load_engines(); frozen = ast.parse((HERE / 'frozen-minimal-installer.py').read_text())
        original = {n.name: n for n in frozen.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name != 'lint'}
        owner = ast.parse(wrapper().EMBEDDED['owner'][0]); actual = {n.name: n for n in owner.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name != 'lint'}
        self.assertEqual(set(actual), set(original) | {'provider_needed'})
        policy = ast.parse((HERE / 'owner-dependency-extension.py').read_text())
        revised = {node.name: node for node in policy.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(set(revised), {'provider_needed', 'restore_owned'})
        for name in revised: self.assertEqual(ast.dump(actual[name]), ast.dump(revised[name]), name)
        for name, node in actual.items():
            if name in revised: continue
            for item in ast.walk(node):
                attribute = 'value' if sys.version_info >= (3, 8) else 's'; value = getattr(item, attribute, None)
                if isinstance(value, str): setattr(item, attribute, '.php' if value == '.code' else value)
            self.assertEqual(ast.dump(node), ast.dump(original[name]), name)
        for profile in derive.VARIANTS:
            self.assertEqual(modules[profile].frozen_move_code.__code__.co_code, modules['owner'].move_code.__code__.co_code)


if __name__ == '__main__': unittest.main(verbosity=2)
