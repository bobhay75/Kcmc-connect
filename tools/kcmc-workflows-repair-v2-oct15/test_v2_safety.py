#!/usr/bin/env python3
"""Regression faults for unchanged core app payloads and corrected result policy."""
from __future__ import print_function
import ast
import contextlib
import hashlib
import importlib.util
from pathlib import Path
import os
import unittest
from unittest import mock
import test_installer as fixture

HERE = Path(__file__).resolve().parent


def replace_exact(path, content=None):
    content = path.read_bytes() if content is None else content
    temporary = path.with_name('.external-' + path.name)
    temporary.write_bytes(content); temporary.chmod(0o644)
    os.replace(str(temporary), str(path))
    return fixture.identity(path)


class V2SafetyTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.Fixture(); self.addCleanup(self.f.close)
    def applied(self):
        code, text = self.f.apply(); self.assertEqual(code, 0, text)
    def rollback(self, group='workflows'):
        args = ['rollback', '--group', group]
        key = 'owner' if group == 'owner' else self.f.profile
        if group == 'workflows': args += ['--variant', self.f.profile]
        return self.f.cli(*(args + ['--session', self.f.session(key).name]))
    def no_success(self, code, text, group='workflows'):
        self.assertEqual(code, 1, text)
        self.assertNotIn('CHECK ALREADY_REPAIRED;', text)
        self.assertNotIn('GROUP ' + group + ' ROLLED_BACK ', text)
        self.assertNotIn('GROUP ' + group + ' REPAIRED', text)
        self.assertNotIn('GROUP ' + group + ' ALREADY_REPAIRED;', text)
    def test_unchanged_frozen_payloads_and_only_two_extension_functions_revised(self):
        old = ast.parse((HERE / 'provenance/original-package/extension.py').read_text())
        new = ast.parse((HERE / 'extension.py').read_text())
        left = {node.name: ast.dump(node) for node in old.body if isinstance(node, ast.FunctionDef)}
        right = {node.name: ast.dump(node) for node in new.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(set(left), set(right))
        self.assertEqual({name for name in left if left[name] != right[name]}, {'provider_needed', 'restore_owned'})
        fixture.derive.verify_original_package()
    def test_original_published_sessions_remain_rollback_compatible(self):
        new_wrapper, new_engines = self.f.w, self.f.engines
        spec = importlib.util.spec_from_file_location('original_published_core', str(HERE / 'provenance/original-package/installer.py'))
        old_wrapper = importlib.util.module_from_spec(spec); spec.loader.exec_module(old_wrapper)
        old_engines = old_wrapper.load_engines()
        for key, module in old_engines.items():
            for name in ('APP', 'BACKUPS', 'UID', 'GID'): setattr(module, name, getattr(new_engines[key], name))
        old_wrapper.load_engines = lambda: old_engines
        old_wrapper.choose_php82_cli = lambda: ('/synthetic/php82', '8.2.34')
        self.f.w, self.f.engines, self.f.m = old_wrapper, old_engines, old_engines[self.f.profile]
        self.assertEqual(self.f.apply()[0], 0)
        sessions = {key: self.f.session(key) for key in ('owner', self.f.profile)}
        self.f.w, self.f.engines, self.f.m = new_wrapper, new_engines, new_engines[self.f.profile]
        code, text = self.f.cli('apply'); self.assertEqual(code, 0, text)
        self.assertIn('both independent code groups verified', text)
        for group, key in (('workflows', self.f.profile), ('owner', 'owner')):
            args = ['rollback', '--group', group]
            if group == 'workflows': args += ['--variant', key]
            code, text = self.f.cli(*(args + ['--session', sessions[key].name])); self.assertEqual(code, 0, text)
        for path, before in self.f.before.items():
            if before is None: self.assertFalse((self.f.app / path).exists(), path)
            else: self.assertEqual((self.f.app / path).read_bytes(), before, path)
        self.f.preserved()
    def test_noop_keeps_initial_owner_inode_lease(self):
        self.applied(); module = self.f.engines['owner']; apply = module.apply; path = module.PATHS[0]; external = []
        def fault():
            result = apply(); external.append(replace_exact(self.f.app / path)); return result
        with mock.patch.object(module, 'apply', side_effect=fault): code, text = self.f.cli('apply')
        self.no_success(code, text, 'owner'); self.assertEqual(fixture.identity(self.f.app / path), external[0]); self.f.preserved()
    def test_noop_keeps_initial_workflows_inode_lease(self):
        self.applied(); module = self.f.m; apply = module.apply; path = module.PATHS[-1]; external = []
        def fault():
            result = apply(); external.append(replace_exact(self.f.app / path)); return result
        with mock.patch.object(module, 'apply', side_effect=fault): code, text = self.f.cli('apply')
        self.no_success(code, text); self.assertEqual(fixture.identity(self.f.app / path), external[0]); self.f.preserved()
    def test_approved_before_cannot_be_silently_adopted_as_noop(self):
        module = self.f.engines['owner']; external = []
        def fault():
            for path in module.PATHS:
                external.append(replace_exact(self.f.app / path, (HERE / 'evidence/owner_after' / path).read_bytes()))
            return None
        with mock.patch.object(module, 'apply', side_effect=fault): code, text = self.f.cli('apply')
        self.no_success(code, text, 'owner'); self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values()))
    def test_check_refuses_target_inode_drift_during_php_probe(self):
        path = self.f.m.PATHS[0]
        def fault(): replace_exact(self.f.app / path); return '/synthetic/php82', '8.2.34'
        self.f.w.choose_php82_cli = fault
        code, text = self.f.cli('check'); self.assertEqual(code, 1, text); self.assertNotIn('CHECK READY', text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.f.engines.values()))
    def test_applied_journal_target_replacement_does_not_adopt_new_inode(self):
        for key in ('owner', self.f.profile):
            f = fixture.Fixture(); self.addCleanup(f.close); module = f.engines[key]; journal = module.journal; path = module.PATHS[-1]; external = []
            def fault(session, value):
                result = journal(session, value)
                if value['phase'] == 'applied': external.append(replace_exact(f.app / path))
                return result
            with mock.patch.object(module, 'journal', side_effect=fault): code, text = f.apply()
            self.no_success(code, text, 'owner' if key == 'owner' else 'workflows')
            self.assertEqual(fixture.identity(f.app / path), external[0]); self.assertEqual(module.load(f.session(key))['phase'], 'applied'); f.preserved()
    def test_apply_result_rechecks_targets_after_transaction_lock_exit(self):
        for key in ('owner', self.f.profile):
            f = fixture.Fixture(); self.addCleanup(f.close); module = f.engines[key]; locked = module.locked; path = module.PATHS[-1]; external = []
            @contextlib.contextmanager
            def fault():
                with locked() as check: yield check
                external.append(replace_exact(f.app / path))
            with mock.patch.object(module, 'locked', fault): code, text = f.apply()
            self.no_success(code, text, 'owner' if key == 'owner' else 'workflows')
            self.assertEqual(fixture.identity(f.app / path), external[0]); f.preserved()
    def test_rollback_result_rechecks_original_or_absent_after_lock_exit(self):
        for group, path in (('owner', 'admin/users.php'), ('workflows', 'member/prayers.php')):
            f = fixture.Fixture(); self.addCleanup(f.close); self.assertEqual(f.apply()[0], 0)
            key = 'owner' if group == 'owner' else f.profile; module = f.engines[key]; locked = module.locked; external = []
            @contextlib.contextmanager
            def fault():
                with locked() as check: yield check
                external.append(replace_exact(f.app / path, (HERE / ('evidence/owner_before' if group == 'owner' else 'evidence/after') / path).read_bytes()))
            args = ['rollback', '--group', group]
            if group == 'workflows': args += ['--variant', f.profile]
            with mock.patch.object(module, 'locked', fault): code, text = f.cli(*(args + ['--session', f.session(key).name]))
            self.no_success(code, text, group); self.assertEqual(fixture.identity(f.app / path), external[0])
            self.assertEqual(module.load(f.session(key))['phase'], 'rolled_back'); f.preserved()
    def test_two_group_final_boundary_rechecks_previously_reported_owner_leases(self):
        path = self.f.engines['owner'].PATHS[0]; module = self.f.m; apply = module.apply; external = []
        def fault(): result = apply(); external.append(replace_exact(self.f.app / path)); return result
        with mock.patch.object(module, 'apply', side_effect=fault): code, text = self.f.apply()
        self.assertEqual(code, 1, text); self.assertNotIn('CHECK ALREADY_REPAIRED;', text)
        self.assertIn('GROUP owner REPAIRED', text); self.assertIn('PRIOR_VERIFIED_GROUPS owner', text)
        self.assertEqual(fixture.identity(self.f.app / path), external[0]); self.f.preserved()
    def test_recreated_completed_owner_consumer_retains_lifecycle_guard(self):
        for timing in ('consumer_complete', 'provider_intent'):
            f = fixture.Fixture(); self.addCleanup(f.close); self.assertEqual(f.apply()[0], 0)
            module = f.engines['owner']; journal = module.journal; external = []
            consumer = 'admin/password-resets.php'; provider = 'lib/password-lifecycle.php'
            def fault(session, value):
                result = journal(session, value)
                complete = value['phase'] == 'rolling_back' and value['files'][consumer]['installed'] is None
                trigger = complete and (timing == 'consumer_complete' or value['intent'] == provider)
                if trigger and not external:
                    external.append(replace_exact(f.app / consumer, (HERE / 'evidence/owner_after' / consumer).read_bytes()))
                return result
            with mock.patch.object(module, 'journal', side_effect=fault):
                code, text = f.cli('rollback', '--group', 'owner', '--session', f.session('owner').name)
            self.no_success(code, text, 'owner'); self.assertTrue(external, timing)
            self.assertEqual(fixture.identity(f.app / consumer), external[0])
            value = module.load(f.session('owner')); self.assertEqual(value['phase'], 'manual_review')
            self.assertIn(consumer, value['uncertain']); self.assertIsNotNone(value['files'][provider]['installed'])
            module.verify_lease(provider, value['files'][provider]['installed']); f.preserved()
    def test_recreated_completed_consumers_retain_transitive_providers(self):
        # Exercise both an existing consumer restored to its old inode and a new
        # consumer deleted to its absent preimage, at completion and final callback.
        for consumer, provider in (('member/index.php', 'admin/home.php'), ('admin/home.php', 'admin/prayer-inbox.php')):
            for timing in ('consumer_complete', 'provider_intent'):
                f = fixture.Fixture(); self.addCleanup(f.close); self.assertEqual(f.apply()[0], 0)
                module = f.m; journal = module.journal; external = []
                def fault(session, value):
                    result = journal(session, value)
                    complete = value['phase'] == 'rolling_back' and value['files'][consumer]['installed'] is None
                    trigger = complete and (timing == 'consumer_complete' or value['intent'] == provider)
                    if trigger and not external:
                        external.append(replace_exact(f.app / consumer, (HERE / 'evidence/after' / consumer).read_bytes()))
                    return result
                with mock.patch.object(module, 'journal', side_effect=fault):
                    code, text = f.cli('rollback', '--group', 'workflows', '--variant', f.profile, '--session', f.session(f.profile).name)
                self.no_success(code, text); self.assertTrue(external, (consumer, timing))
                self.assertEqual(fixture.identity(f.app / consumer), external[0])
                value = module.load(f.session(f.profile)); self.assertEqual(value['phase'], 'manual_review')
                self.assertIn(consumer, value['uncertain']); self.assertIsNotNone(value['files'][provider]['installed'])
                module.verify_lease(provider, value['files'][provider]['installed']); f.preserved()


if __name__ == '__main__': unittest.main(verbosity=2)
