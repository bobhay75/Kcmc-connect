"""Fault matrix for a fixture-only absence/dependency extension; no host/network."""
import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import prototype


def sha(content): return hashlib.sha256(content).hexdigest()


def identity(path):
    i = path.lstat()
    return (i.st_dev, i.st_ino, i.st_mode, i.st_uid, i.st_gid, i.st_nlink, i.st_size, i.st_mtime_ns, i.st_ctime_ns)


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-absence-prototype-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.app = self.root / 'app'; self.app.mkdir()
        for name in ['lib', 'admin', 'member']: (self.app / name).mkdir()
        self.m = prototype.engine(); self.m.APP = self.app; self.m.BACKUPS = self.root / 'private'
        self.m.UID = os.getuid(); self.m.GID = os.getgid(); self.m.PHP = '/synthetic/php82'
        self.paths = ('lib/provider-a.php', 'lib/provider-b.php', 'admin/new-route.php', 'member/consumer.php')
        self.m.PATHS = self.paths
        self.m.DEPENDENCIES = {self.paths[1]: (self.paths[0],), self.paths[2]: (self.paths[1],), self.paths[3]: (self.paths[1],)}
        self.before = {p: None for p in self.paths}; self.before[self.paths[-1]] = b'<?php\n// old consumer\n'
        self.after = {p: ('<?php\n// fixture new ' + p + '\n').encode() for p in self.paths}
        self.after[self.paths[-1]] = b'<?php\n// updated consumer\n'
        self.m.FILES = {}
        for p in self.paths:
            before = self.before[p]; after = self.after[p]
            row = {'before_sha256': sha(before) if before else None, 'before_bytes': len(before) if before else 0,
                   'after_sha256': sha(after), 'after_bytes': len(after), 'replacements': [['// old consumer', '// updated consumer']] if before else []}
            if before is None: row['after_base64'] = base64.b64encode(after).decode()
            else: (self.app / p).write_bytes(before); (self.app / p).chmod(0o664)
            self.m.FILES[p] = row
        self.sentinels = {'config.php': b'<?php // owner configuration retained\n', 'data/private/users.json': b'{"accounts":"untouched"}',
            'data/private/timeclock.json': b'{"live punches":"untouched"}', 'data/content.json': b'{"editorial":"untouched"}',
            'lib/bootstrap.php': b'<?php // owner/session bootstrap retained\n', '.git/HEAD': b'ref: refs/heads/main\n'}
        for p, content in self.sentinels.items():
            target = self.app / p; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content); target.chmod(0o600)
        self.ids = {p: identity(self.app / p) for p in self.sentinels}
        def php(command, **kwargs):
            self.assertEqual(command[:2], ['/synthetic/php82', '-n'])
            if command[-1] == '-v': return b'PHP 8.2.34 (cli)\n'
            self.assertEqual(command[2], '-l'); self.assertTrue(Path(command[3]).is_file())
            return b'No syntax errors detected\n'
        self.php = mock.patch.object(self.m.subprocess, 'check_output', side_effect=php); self.php.start(); self.addCleanup(self.php.stop)
    def tearDown(self):
        for p, content in self.sentinels.items():
            self.assertEqual((self.app / p).read_bytes(), content, p); self.assertEqual(identity(self.app / p), self.ids[p], p)
    def session(self): return next(self.m.BACKUPS.glob('repair-*'))
    def value(self): return self.m.load(self.session())
    def assert_before(self):
        for p, content in self.before.items():
            if content is None: self.assertFalse((self.app / p).exists(), p)
            else: self.assertEqual((self.app / p).read_bytes(), content, p)
    def fail_apply(self):
        with self.assertRaises(self.m.Refusal): self.m.apply()
    def foreign(self, path, content=b'<?php // foreign edit retained\n'):
        replacement = self.root / 'foreign.php'; replacement.write_bytes(content); replacement.chmod(0o644)
        os.replace(str(replacement), str(self.app / path)); return identity(self.app / path)
    def test_readonly_inspection_accepts_absence_without_backup(self):
        state, files = self.m.inspect(); self.assertEqual(state, 'before'); self.assertFalse(self.m.BACKUPS.exists())
        for p in self.paths[:-1]: self.assertIsNone(files[p][1]); self.assertEqual(set(files[p][2]), set(self.m.PARENT_KEYS))
        self.assert_before()
    def test_apply_noop_and_rollback_restore_absence_and_existing_mode(self):
        session = self.m.apply(); value = self.value(); self.assertEqual(value['phase'], 'applied')
        for i, p in enumerate(self.paths):
            self.assertEqual((self.app / p).read_bytes(), self.after[p]); self.assertEqual((self.app / p).stat().st_nlink, 1)
            self.assertEqual(stat.S_IMODE((self.app / p).stat().st_mode), 0o664 if self.before[p] else 0o644)
            original = session / ('original-' + str(i) + '.code')
            self.assertEqual(original.exists(), self.before[p] is not None)
            if original.exists(): self.assertEqual(original.read_bytes(), self.before[p])
        before = {p: identity(self.app / p) for p in self.paths}; journal = identity(session / 'journal.json')
        self.assertIsNone(self.m.apply()); self.assertEqual(identity(session / 'journal.json'), journal)
        for p, prior in before.items(): self.assertEqual(identity(self.app / p), prior)
        self.m.rollback(session.name); self.assert_before(); self.assertEqual(self.value()['phase'], 'rolled_back')
    def test_parent_directories_are_required_and_never_created(self):
        (self.app / 'admin').rmdir()
        with self.assertRaises(OSError): self.m.apply()
        self.assertFalse((self.app / 'admin').exists()); self.assertFalse(self.m.BACKUPS.exists())
    def test_unsupported_link_primitives_refuse_before_backup(self):
        with mock.patch.object(self.m.os, 'supports_dir_fd', set()):
            with self.assertRaisesRegex(self.m.Refusal, 'No-clobber'): self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists()); self.assert_before()
    def test_unknown_new_target_is_not_adopted_or_overwritten(self):
        p = self.paths[0]; (self.app / p).write_bytes(b'<?php // unrelated existing helper\n'); (self.app / p).chmod(0o644)
        prior = identity(self.app / p)
        with self.assertRaisesRegex(self.m.Refusal, 'Unknown code bytes'): self.m.apply()
        self.assertEqual(identity(self.app / p), prior); self.assertFalse(self.m.BACKUPS.exists())
    def test_only_complete_before_or_after_tuples_are_accepted(self):
        import itertools
        accepted = 0
        for states in itertools.product((False, True), repeat=4):
            for p, state in zip(self.paths, states):
                content = self.after[p] if state else self.before[p]
                if (self.app / p).exists(): (self.app / p).unlink()
                if content is not None: (self.app / p).write_bytes(content); (self.app / p).chmod(0o644)
            if len(set(states)) == 1:
                self.m.inspect(); accepted += 1
            else:
                with self.assertRaises(self.m.Refusal): self.m.inspect()
        self.assertEqual(accepted, 2); self.assertFalse(self.m.BACKUPS.exists())
    def test_absent_parent_identity_is_pinned_through_staging(self):
        lint = self.m.lint
        def race(session):
            lint(session); (self.app / 'admin').rename(self.root / 'old-admin'); (self.app / 'admin').mkdir()
        with mock.patch.object(self.m, 'lint', side_effect=race): self.fail_apply()
        self.assert_before(); self.assertEqual(self.value()['phase'], 'prepared')
    def test_intent_is_durable_before_first_publication(self):
        link = self.m.no_clobber_link
        def checked(source, target, **kwargs):
            value = self.value(); self.assertEqual(value['phase'], 'applying'); self.assertEqual(value['intent'], self.paths[0])
            self.assertIsNone(value['files'][self.paths[0]]['installed']); self.assertFalse((self.app / self.paths[0]).exists())
            return link(source, target, **kwargs)
        with mock.patch.object(self.m, 'no_clobber_link', side_effect=checked):
            # Observe only the first link; later links have different intents.
            first = [True]
            def once(source, target, **kwargs):
                if first[0]: first[0] = False; return checked(source, target, **kwargs)
                return link(source, target, **kwargs)
            self.m.no_clobber_link.side_effect = once; self.m.apply()
    def test_raced_in_target_refuses_atomically_without_overwrite(self):
        link = self.m.no_clobber_link; p = self.paths[0]; expected = []
        def race(source, target, **kwargs):
            expected.append(self.foreign(p)); return link(source, target, **kwargs)
        with mock.patch.object(self.m, 'no_clobber_link', side_effect=race): self.fail_apply()
        self.assertEqual(identity(self.app / p), expected[0]); self.assertIn(b'foreign edit retained', (self.app / p).read_bytes())
        self.assertEqual(self.value()['phase'], 'manual_review'); self.assertIn(p, self.value()['uncertain'])
    def test_raced_in_same_bytes_target_does_not_grant_ownership(self):
        link = self.m.no_clobber_link; p = self.paths[0]; expected = []
        def race(source, target, **kwargs):
            expected.append(self.foreign(p, self.after[p])); return link(source, target, **kwargs)
        with mock.patch.object(self.m, 'no_clobber_link', side_effect=race): self.fail_apply()
        self.assertEqual(identity(self.app / p), expected[0]); self.assertIsNone(self.value()['files'][p]['installed'])
    def test_raced_in_symlink_is_preserved_without_following(self):
        link = self.m.no_clobber_link; p = self.paths[0]
        def race(source, target, **kwargs):
            (self.app / p).symlink_to(self.app / 'config.php'); return link(source, target, **kwargs)
        with mock.patch.object(self.m, 'no_clobber_link', side_effect=race): self.fail_apply()
        self.assertTrue((self.app / p).is_symlink()); self.assertEqual(self.value()['phase'], 'manual_review')
    def test_failure_after_link_retains_two_links_and_uncertain_intent(self):
        link = self.m.no_clobber_link
        def fail(*args, **kwargs): link(*args, **kwargs); raise OSError('post-link fault')
        with mock.patch.object(self.m, 'no_clobber_link', side_effect=fail): self.fail_apply()
        p = self.paths[0]; value = self.value(); self.assertEqual(value['phase'], 'manual_review')
        self.assertEqual((self.app / p).stat().st_nlink, 2); self.assertEqual((self.session() / 'stage-0.code').stat().st_nlink, 2)
        self.assertIsNone(value['files'][p]['installed']); self.assertIn(p, value['uncertain'])
    def test_failure_before_unlink_stage_retains_hardlinks_without_candidate_deletion(self):
        with mock.patch.object(self.m, 'unlink_name', side_effect=OSError('pre-unlink fault')): self.fail_apply()
        self.assertEqual((self.app / self.paths[0]).stat().st_nlink, 2); self.assertEqual(self.value()['phase'], 'manual_review')
    def test_failure_after_unlink_stage_keeps_unrecorded_new_target(self):
        unlink = self.m.unlink_name
        def fail(name, **kwargs): unlink(name, **kwargs); raise OSError('post-unlink stage fault')
        with mock.patch.object(self.m, 'unlink_name', side_effect=fail): self.fail_apply()
        p = self.paths[0]; value = self.value(); self.assertEqual(value['phase'], 'manual_review')
        self.assertEqual((self.app / p).stat().st_nlink, 1); self.assertFalse((self.session() / 'stage-0.code').exists())
        self.assertIsNone(value['files'][p]['installed']); self.assertIn(p, value['uncertain'])
    def test_successful_installed_lease_captures_nlink_one_after_ctime_changes(self):
        self.m.apply(); value = self.value()
        for p in self.paths[:-1]:
            self.assertEqual(value['files'][p]['installed']['nlink'], 1)
            self.m.verify_lease(p, value['files'][p]['installed'])
            self.assertNotEqual(value['files'][p]['candidate']['ctime_ns'], value['files'][p]['installed']['ctime_ns'])
    def test_uncertain_existing_consumer_keeps_all_shared_providers(self):
        replace = self.m.replace
        def fail(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-3.code': raise OSError('post-rename consumer fault')
            return result
        with mock.patch.object(self.m, 'replace', side_effect=fail): self.fail_apply()
        value = self.value(); self.assertEqual(value['phase'], 'manual_review'); self.assertIn(self.paths[-1], value['uncertain'])
        for p in self.paths[:2]: self.assertEqual((self.app / p).read_bytes(), self.after[p]); self.m.verify_lease(p, value['files'][p]['installed'])
        self.assertFalse((self.app / self.paths[2]).exists(), 'Verified new route may restore absence while shared providers remain')
    def test_consumer_rollback_failure_keeps_shared_helpers_and_manual_review(self):
        session = self.m.apply(); move = self.m.move_code
        def fail(source, path, *args, **kwargs):
            if path == self.paths[-1]: raise OSError('consumer restore fault')
            return move(source, path, *args, **kwargs)
        with mock.patch.object(self.m, 'move_code', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'): self.m.rollback(session.name)
        value = self.value(); self.assertEqual(value['phase'], 'manual_review')
        for p in self.paths[:2]: self.m.verify_lease(p, value['files'][p]['installed'])
    def test_new_route_edit_during_rollback_preserves_foreign_route_and_helpers(self):
        session = self.m.apply(); move = self.m.move_code; foreign = []
        def race(source, path, *args, **kwargs):
            result = move(source, path, *args, **kwargs)
            if path == self.paths[-1]: foreign.append(self.foreign(self.paths[2]))
            return result
        with mock.patch.object(self.m, 'move_code', side_effect=race):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'): self.m.rollback(session.name)
        self.assertEqual(identity(self.app / self.paths[2]), foreign[0]); value = self.value()
        for p in self.paths[:2]: self.m.verify_lease(p, value['files'][p]['installed'])
    def test_new_file_changed_before_explicit_rollback_blocks_all_mutations(self):
        session = self.m.apply(); self.foreign(self.paths[0], self.after[self.paths[0]])
        before = {p: identity(self.app / p) for p in self.paths}
        with self.assertRaises(self.m.Refusal): self.m.rollback(session.name)
        for p, prior in before.items(): self.assertEqual(identity(self.app / p), prior)
    def test_delete_race_before_final_descriptor_check_refuses_foreign_unlink(self):
        session = self.m.apply(); delete = self.m.delete_created_code; foreign = []
        def raced_delete(path, expected, check_lock):
            if path != self.paths[2]: return delete(path, expected, check_lock)
            first = [True]
            def race():
                check_lock()
                if first[0]: first[0] = False; foreign.append(self.foreign(path))
            return delete(path, expected, race)
        with mock.patch.object(self.m, 'delete_created_code', side_effect=raced_delete):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'): self.m.rollback(session.name)
        self.assertEqual(identity(self.app / self.paths[2]), foreign[0]); self.assertEqual(self.value()['phase'], 'manual_review')
    def test_postdelete_fault_retains_intent_and_helpers_without_claimed_success(self):
        session = self.m.apply(); unlink = self.m.unlink_name
        def fail(name, **kwargs): unlink(name, **kwargs); raise OSError('post-delete fault')
        with mock.patch.object(self.m, 'unlink_name', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'): self.m.rollback(session.name)
        self.assertFalse((self.app / self.paths[2]).exists()); value = self.value()
        self.assertIn(self.paths[2], value['uncertain']); self.assertEqual(value['phase'], 'manual_review')
        for p in self.paths[:2]: self.m.verify_lease(p, value['files'][p]['installed'])
    def test_dependency_order_and_reverse_recovery_order_are_explicit(self):
        moved, deleted = [], []; move = self.m.move_code; delete = self.m.delete_created_code
        def capture_move(source, path, *args, **kwargs): moved.append(path); return move(source, path, *args, **kwargs)
        def capture_delete(path, *args, **kwargs): deleted.append(path); return delete(path, *args, **kwargs)
        with mock.patch.object(self.m, 'move_code', side_effect=capture_move), mock.patch.object(self.m, 'delete_created_code', side_effect=capture_delete):
            session = self.m.apply(); self.assertEqual(moved, list(self.paths)); moved[:] = []
            self.m.rollback(session.name)
        self.assertEqual(moved, [self.paths[-1]]); self.assertEqual(deleted, list(reversed(self.paths[:-1])))
    def test_dependency_cycle_or_provider_after_consumer_refuses_before_backup(self):
        self.m.DEPENDENCIES[self.paths[0]] = (self.paths[-1],)
        with self.assertRaisesRegex(self.m.Refusal, 'Providers must precede'): self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())
    def test_nullable_original_does_not_authorize_deleting_an_existing_preimage(self):
        session = self.m.apply(); value = self.value(); value['files'][self.paths[-1]]['original'] = None; self.m.journal(session, value)
        before = {p: identity(self.app / p) for p in self.paths}
        with self.assertRaisesRegex(self.m.Refusal, 'Missing existing'): self.m.rollback(session.name)
        for p, prior in before.items(): self.assertEqual(identity(self.app / p), prior)
    def test_tampered_parent_lease_refuses_before_rollback_writes(self):
        session = self.m.apply(); value = self.value(); value['files'][self.paths[0]]['parent']['ino'] += 1; self.m.journal(session, value)
        before = {p: identity(self.app / p) for p in self.paths}
        with self.assertRaisesRegex(self.m.Refusal, 'parent lease'): self.m.rollback(session.name)
        for p, prior in before.items(): self.assertEqual(identity(self.app / p), prior)
    def test_fourth_stage_lint_failure_keeps_initial_absence_and_existing_code(self):
        check = self.m.subprocess.check_output.side_effect
        def fail(command, **kwargs):
            if command[-1].endswith('stage-3.code'): raise self.m.subprocess.CalledProcessError(255, command)
            return check(command, **kwargs)
        self.m.subprocess.check_output.side_effect = fail
        with self.assertRaisesRegex(self.m.Refusal, 'no live replacement'): self.m.apply()
        self.assert_before(); self.assertEqual(self.value()['phase'], 'rolled_back')


class ProvenanceTests(unittest.TestCase):
    def test_frozen_source_and_finite_override_inventory(self):
        root = Path(__file__).resolve().parent
        self.assertEqual(sha((root / 'frozen-minimal-installer.py').read_bytes()), prototype.FROZEN_SHA256)
        original = ast.parse((root / 'frozen-minimal-installer.py').read_text())
        extension = ast.parse((root / 'extension.py').read_text())
        old = {n.name for n in original.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        new = {n.name for n in extension.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(old & new, prototype.REPLACED_FUNCTIONS)
        module = prototype.engine()
        spec = importlib.util.spec_from_file_location('independent_frozen', str(root / 'frozen-minimal-installer.py'))
        frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)
        for name in old - prototype.REPLACED_FUNCTIONS:
            a, b = getattr(module, name), getattr(frozen, name)
            if hasattr(a, '__code__'):
                self.assertEqual(a.__code__.co_code, b.__code__.co_code, name)
                self.assertEqual(a.__code__.co_consts, b.__code__.co_consts, name)
        self.assertEqual(module.frozen_move_code.__code__.co_code, frozen.move_code.__code__.co_code)
    def test_default_prototype_has_no_production_manifest_or_mutation_path(self):
        module = prototype.engine(); self.assertEqual(module.FILES, {}); self.assertEqual(module.PATHS, ())
        self.assertIn('__unconfigured_fixture_only__', str(module.APP))
        with self.assertRaises(module.Refusal): module.inventory()


if __name__ == '__main__': unittest.main(verbosity=2)
