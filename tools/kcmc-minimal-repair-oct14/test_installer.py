#!/usr/bin/env python3
"""Synthetic three-file transactions only. Python 3.6+, no host or network writes."""
from __future__ import print_function

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = None
if '--runtime-root' in sys.argv:
    index = sys.argv.index('--runtime-root')
    RUNTIME_ROOT = Path(sys.argv[index + 1])
    del sys.argv[index:index + 2]


def module():
    spec = importlib.util.spec_from_file_location('isolated_minimal_installer', str(HERE / 'installer.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-minimal-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'app'
        self.app.mkdir()
        self.m = module()
        self.m.APP = self.app
        self.m.BACKUPS = self.root / 'private-repairs'
        self.m.UID, self.m.GID = os.getuid(), os.getgid()
        self.before, self.after = {}, {}
        for index, path in enumerate(self.m.PATHS):
            old = ('<?php\n// synthetic original ' + str(index) + '\n').encode('ascii')
            new = old.replace(b'original', b'repaired')
            self.before[path], self.after[path] = old, new
            target = self.app / path
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(old)
            target.chmod(0o664 if index == 1 else 0o644)
        self.m.FILES = {path: {'before_sha256': sha(self.before[path]), 'after_sha256': sha(self.after[path]),
                              'before_bytes': len(self.before[path]), 'after_bytes': len(self.after[path]),
                              'replacements': [['// synthetic original ' + str(index), '// synthetic repaired ' + str(index)]]}
                        for index, path in enumerate(self.m.PATHS)}
        self.sentinels = {'config.php': b'<?php // private synthetic config\n',
                          'data/private/users.json': b'{"synthetic":"users unchanged"}',
                          'data/private/timeclock.json': b'{"synthetic":"time records unchanged"}',
                          'data/content.json': b'{"synthetic":"editorial unchanged"}',
                          '.git/HEAD': b'ref: refs/heads/main\n'}
        for path, data in self.sentinels.items():
            target = self.app / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o600)
        self.modes = {path: mode(self.app / path) for path in self.m.PATHS}
        self.calls = []
        def subprocess_stub(command, **kwargs):
            self.calls.append(command)
            return b'PHP 8.2.34 (cli)\n' if command[-1] == '-v' else b'No syntax errors detected\n'
        self.subprocess = mock.patch.object(self.m.subprocess, 'check_output', side_effect=subprocess_stub)
        self.subprocess.start()
        self.addCleanup(self.subprocess.stop)

    def assert_bundle(self, expected):
        for path in self.m.PATHS:
            self.assertEqual((self.app / path).read_bytes(), expected[path], path)
            self.assertEqual(mode(self.app / path), self.modes[path], path)
        for path, data in self.sentinels.items():
            self.assertEqual((self.app / path).read_bytes(), data, path)
            self.assertEqual(mode(self.app / path), 0o600, path)

    def sessions(self):
        return sorted(self.m.BACKUPS.glob('repair-*'))

    def test_default_check_is_readonly(self):
        inodes = {path: (self.app / path).stat().st_ino for path in self.m.PATHS}
        state, _ = self.m.inspect()
        self.assertEqual(state, 'before')
        self.m.unfinished()
        self.assertFalse(self.m.BACKUPS.exists())
        self.assertEqual(self.calls, [])
        self.assert_bundle(self.before)
        self.assertEqual(inodes, {path: (self.app / path).stat().st_ino for path in self.m.PATHS})

    def test_apply_preserves_modes_ownership_and_private_journal(self):
        session = self.m.apply()
        self.assert_bundle(self.after)
        self.assertEqual(mode(self.m.BACKUPS), 0o700)
        self.assertEqual(mode(session), 0o700)
        self.assertEqual(mode(session / 'journal.json'), 0o600)
        for index, path in enumerate(self.m.PATHS):
            original = session / ('original-' + str(index) + '.php')
            self.assertEqual(mode(original), 0o600)
            self.assertEqual(original.read_bytes(), self.before[path])
            info = (self.app / path).stat()
            self.assertEqual((info.st_uid, info.st_gid, info.st_nlink), (os.getuid(), os.getgid(), 1))
        self.assertEqual(self.m.load(session)['phase'], 'applied')
        self.assertTrue(all(command[1] == '-n' for command in self.calls))
        self.assertTrue(all('-r' not in command for command in self.calls))
        self.assertEqual(len(self.calls), 4)

    def test_already_after_is_noop_without_php_or_backup(self):
        for path in self.m.PATHS:
            (self.app / path).write_bytes(self.after[path])
        self.assertIsNone(self.m.apply())
        self.assertEqual(self.calls, [])
        self.assertFalse(self.m.BACKUPS.exists())
        self.assert_bundle(self.after)

    def test_mixed_bundle_refused_before_any_backup(self):
        path = self.m.PATHS[0]
        (self.app / path).write_bytes(self.after[path])
        with self.assertRaisesRegex(self.m.Refusal, 'Mixed'):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())
        self.assertEqual(self.calls, [])

    def test_unknown_bytes_refused(self):
        target = self.app / self.m.PATHS[0]
        target.write_bytes(b'<?php // newer concurrent code\n')
        with self.assertRaisesRegex(self.m.Refusal, 'Unknown'):
            self.m.apply()
        self.assertEqual(target.read_bytes(), b'<?php // newer concurrent code\n')
        self.assertFalse(self.m.BACKUPS.exists())

    def test_missing_file_refused(self):
        (self.app / self.m.PATHS[0]).unlink()
        with self.assertRaises(OSError):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_symlink_refused(self):
        target = self.app / self.m.PATHS[0]
        outside = self.root / 'outside.php'
        outside.write_bytes(self.before[self.m.PATHS[0]])
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaises(OSError):
            self.m.apply()
        self.assertEqual(outside.read_bytes(), self.before[self.m.PATHS[0]])

    def test_linked_parent_refused(self):
        original = self.app / 'lib'
        moved = self.root / 'moved-lib'
        original.rename(moved)
        original.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(OSError):
            self.m.apply()

    def test_hardlink_refused(self):
        os.link(str(self.app / self.m.PATHS[0]), str(self.root / 'hardlink.php'))
        with self.assertRaisesRegex(self.m.Refusal, 'linked'):
            self.m.apply()

    def test_nonregular_refused(self):
        target = self.app / self.m.PATHS[0]
        target.unlink()
        os.mkfifo(str(target))
        with self.assertRaises(self.m.Refusal):
            self.m.apply()

    def test_unsafe_code_mode_refused(self):
        (self.app / self.m.PATHS[0]).chmod(0o600)
        with self.assertRaisesRegex(self.m.Refusal, 'Code mode'):
            self.m.apply()

    def test_caller_id_mismatch_refused(self):
        self.m.UID += 1
        with self.assertRaisesRegex(self.m.Refusal, 'hosting account'):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_file_gid_drift_refused_even_if_caller_check_stubbed(self):
        self.m.GID += 1
        with mock.patch.object(self.m, 'caller'):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()

    def test_fixed_environment_cannot_override_roots_ids(self):
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/forged', 'KCMC_UID': '0', 'KCMC_PRIVATE_DATA_DIR': '/tmp/private'}):
            production = module()
            self.assertEqual(production.APP, Path('/home/bobsome1/public_html/kcmc-connect'))
            self.assertEqual((production.UID, production.GID), (2162, 2147))
            self.assertEqual(production.BACKUPS, Path('/home/bobsome1/kcmc-minimal-repair-backups'))

    def test_syntax_failure_changes_no_live_code(self):
        with mock.patch.object(self.m, 'lint', side_effect=RuntimeError('synthetic lint failure')):
            with self.assertRaisesRegex(self.m.Refusal, 'no live replacement'):
                self.m.apply()
        self.assert_bundle(self.before)
        self.assertEqual(self.m.load(self.sessions()[0])['phase'], 'rolled_back')

    def test_cross_filesystem_preflight_refuses_before_staging(self):
        device = (self.app / self.m.PATHS[0]).stat().st_dev
        with mock.patch.object(self.m, 'backup_device', return_value=device + 1):
            with self.assertRaisesRegex(self.m.Refusal, 'same filesystem'):
                self.m.apply()
        self.assert_bundle(self.before)
        self.assertEqual(self.sessions(), [])
        self.assertEqual(self.calls, [])

    def test_wrong_php_version_refused_without_replacement(self):
        with mock.patch.object(self.m.subprocess, 'check_output', return_value=b'PHP 8.3.0 (cli)\n'):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assert_bundle(self.before)

    def test_stage_mutation_refused_before_rename(self):
        def mutate(session):
            (session / 'stage-0.php').write_bytes(b'<?php // forged stage\n')
        with mock.patch.object(self.m, 'lint', side_effect=mutate):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assert_bundle(self.before)
        self.assertEqual(self.m.load(self.sessions()[0])['phase'], 'rolled_back')

    def test_linked_stage_refused(self):
        def mutate(session):
            os.link(str(session / 'stage-0.php'), str(self.root / 'stage-link'))
        with mock.patch.object(self.m, 'lint', side_effect=mutate):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assert_bundle(self.before)

    def test_second_step_pre_rename_failure_restores_only_prior_owned_step(self):
        original = self.m.move_code
        def fail(source, path, expected, candidate, lock):
            if path == self.m.PATHS[1] and source.name.startswith('stage-'):
                raise OSError('synthetic second step failure')
            return original(source, path, expected, candidate, lock)
        with mock.patch.object(self.m, 'move_code', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_bundle(self.before)
        value = self.m.load(self.sessions()[0])
        self.assertEqual(value['phase'], 'manual_review')
        self.assertEqual(value['intent'], self.m.PATHS[1])
        self.assertIsNone(value['files'][self.m.PATHS[0]]['installed'])

    def test_rename_succeeded_then_error_keeps_uncertain_new_file(self):
        original = self.m.replace
        def fail(source, target, **kwargs):
            original(source, target, **kwargs)
            if source == 'stage-1.php':
                raise OSError('synthetic error after successful rename')
        with mock.patch.object(self.m, 'replace', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), self.before[self.m.PATHS[0]])
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.after[self.m.PATHS[1]])
        self.assertEqual((self.app / self.m.PATHS[2]).read_bytes(), self.before[self.m.PATHS[2]])
        value = self.m.load(self.sessions()[0])
        self.assertEqual(value['phase'], 'manual_review')
        self.assertEqual(value['intent'], self.m.PATHS[1])
        self.assertEqual(value['files'][self.m.PATHS[1]]['candidate']['sha256'], sha(self.after[self.m.PATHS[1]]))
        with self.assertRaisesRegex(self.m.Refusal, 'Unfinished'):
            self.m.unfinished()

    def test_poststat_failure_preserves_durable_intent(self):
        original_replace, original_read = self.m.replace, self.m.read_at
        fail = [False]
        def replace(source, target, **kwargs):
            original_replace(source, target, **kwargs)
            if source == 'stage-1.php':
                fail[0] = True
        def read(parent, name):
            if fail[0] and name == 'activate.php':
                raise OSError('synthetic poststat failure')
            return original_read(parent, name)
        with mock.patch.object(self.m, 'replace', side_effect=replace), mock.patch.object(self.m, 'read_at', side_effect=read):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.after[self.m.PATHS[1]])
        self.assertEqual(self.m.load(self.sessions()[0])['intent'], self.m.PATHS[1])

    def test_concurrent_edit_of_installed_file_is_never_overwritten(self):
        original = self.m.move_code
        changed = b'<?php // independent concurrent edit\n'
        def modify(source, path, expected, candidate, lock):
            result = original(source, path, expected, candidate, lock)
            if source.name == 'stage-0.php':
                (self.app / path).write_bytes(changed)
            return result
        with mock.patch.object(self.m, 'move_code', side_effect=modify):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), changed)
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.before[self.m.PATHS[1]])

    def test_same_bytes_new_inode_prevents_rollback(self):
        session = self.m.apply()
        target = self.app / self.m.PATHS[0]
        replacement = self.root / 'concurrent.php'
        replacement.write_bytes(target.read_bytes())
        replacement.chmod(self.modes[self.m.PATHS[0]])
        os.replace(str(replacement), str(target))
        with self.assertRaisesRegex(self.m.Refusal, 'lease changed'):
            self.m.rollback(session.name)
        self.assert_bundle(self.after)

    def test_same_inode_same_bytes_ctime_change_prevents_rollback(self):
        session = self.m.apply()
        target = self.app / self.m.PATHS[0]
        previous = target.stat()
        target.write_bytes(target.read_bytes())
        os.utime(str(target), ns=(previous.st_atime_ns, previous.st_mtime_ns))
        with self.assertRaisesRegex(self.m.Refusal, 'lease changed'):
            self.m.rollback(session.name)
        self.assert_bundle(self.after)

    def test_explicit_rollback_restores_exact_code_modes(self):
        session = self.m.apply()
        self.m.rollback(session.name)
        self.assert_bundle(self.before)
        self.assertEqual(self.m.load(session)['phase'], 'rolled_back')

    def test_concurrent_mode_change_blocks_rollback(self):
        session = self.m.apply()
        target = self.app / self.m.PATHS[0]
        target.chmod(0o664)
        with self.assertRaisesRegex(self.m.Refusal, 'lease changed'):
            self.m.rollback(session.name)
        self.assertEqual(target.read_bytes(), self.after[self.m.PATHS[0]])

    def test_lock_replacement_after_first_commit_blocks_further_writes(self):
        original = self.m.move_code
        def swap(source, path, expected, candidate, lock):
            result = original(source, path, expected, candidate, lock)
            if source.name == 'stage-0.php':
                target = self.m.BACKUPS / '.repair.lock'
                target.unlink()
                target.write_bytes(b'')
                target.chmod(0o600)
            return result
        with mock.patch.object(self.m, 'move_code', side_effect=swap):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), self.after[self.m.PATHS[0]])
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.before[self.m.PATHS[1]])

    def test_unsafe_backup_root_mode_refused(self):
        self.m.BACKUPS.mkdir(mode=0o755)
        self.m.BACKUPS.chmod(0o755)
        with self.assertRaisesRegex(self.m.Refusal, 'Backup directory'):
            self.m.apply()
        self.assert_bundle(self.before)

    def test_backup_symlink_refused(self):
        outside = self.root / 'outside'
        outside.mkdir(mode=0o700)
        self.m.BACKUPS.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(self.m.Refusal):
            self.m.apply()
        self.assertEqual(list(outside.iterdir()), [])

    def test_world_writable_app_descendant_refused(self):
        (self.app / 'member').chmod(0o777)
        with self.assertRaisesRegex(self.m.Refusal, 'Unsafe application directory'):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_final_descriptor_check_preserves_replaced_target(self):
        original = self.m.move_code
        changed = b'<?php // final-boundary concurrent writer\n'
        def move(source, path, expected, candidate, lock):
            if source.name == 'stage-0.php':
                def boundary():
                    lock()
                    replacement = self.root / 'final-boundary.php'
                    replacement.write_bytes(changed)
                    replacement.chmod(self.modes[path])
                    os.replace(str(replacement), str(self.app / path))
                return original(source, path, expected, candidate, boundary)
            return original(source, path, expected, candidate, lock)
        with mock.patch.object(self.m, 'move_code', side_effect=move):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), changed)
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.before[self.m.PATHS[1]])

    def test_final_descriptor_check_preserves_replaced_parent(self):
        original = self.m.move_code
        changed = b'<?php // new parent namespace\n'
        displaced = self.root / 'displaced-lib'
        def move(source, path, expected, candidate, lock):
            if source.name == 'stage-0.php':
                def boundary():
                    lock()
                    (self.app / 'lib').rename(displaced)
                    (self.app / 'lib').mkdir(mode=0o700)
                    target = self.app / path
                    target.write_bytes(changed)
                    target.chmod(self.modes[path])
                return original(source, path, expected, candidate, boundary)
            return original(source, path, expected, candidate, lock)
        with mock.patch.object(self.m, 'move_code', side_effect=move):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), changed)
        self.assertEqual((displaced / 'timeclock.php').read_bytes(), self.before[self.m.PATHS[0]])

    def test_uncertain_apply_and_restore_are_both_journaled(self):
        original = self.m.replace
        def fail(source, target, **kwargs):
            original(source, target, **kwargs)
            if source == 'stage-1.php' or source.startswith('restore-'):
                raise OSError('synthetic error after rename')
        with mock.patch.object(self.m, 'replace', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        value = self.m.load(self.sessions()[0])
        self.assertEqual(set(value['uncertain']), set(self.m.PATHS[:2]))
        self.assertEqual(value['phase'], 'manual_review')
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), self.before[self.m.PATHS[0]])
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.after[self.m.PATHS[1]])

    def test_out_of_scope_inventory_refused(self):
        self.m.FILES['config.php'] = self.m.FILES[self.m.PATHS[0]]
        with self.assertRaisesRegex(self.m.Refusal, 'exactly'):
            self.m.apply()
        self.assert_bundle(self.before)

    def test_session_traversal_refused(self):
        with self.assertRaisesRegex(self.m.Refusal, 'exact private'):
            self.m.rollback('../outside')
        self.assertFalse(self.m.BACKUPS.exists())

    def test_tampered_journal_scope_refused(self):
        session = self.m.apply()
        value = json.loads((session / 'journal.json').read_text())
        value['files']['config.php'] = value['files'][self.m.PATHS[0]]
        self.m.journal(session, value)
        with self.assertRaises(self.m.Refusal):
            self.m.rollback(session.name)
        self.assert_bundle(self.after)

    def test_old_session_does_not_authorize_rollback_of_new_application(self):
        first = self.m.apply()
        self.m.rollback(first.name)
        second = self.m.apply()
        with self.assertRaisesRegex(self.m.Refusal, 'fully verified applied'):
            self.m.rollback(first.name)
        self.assertEqual(self.m.load(second)['phase'], 'applied')
        self.assert_bundle(self.after)


class ReviewedSourceTests(unittest.TestCase):
    def test_production_inventory_matches_reviewed_fixture(self):
        production = module()
        fixture = json.loads((HERE / 'runtime-reviewed.json').read_text())
        self.assertEqual(production.FILES, fixture)
        production.inventory()
        self.assertEqual(production.PATHS, ('lib/timeclock.php', 'member/activate.php', 'member/reset-password.php'))
        self.assertEqual(production.PHP, '/opt/cpanel/ea-php82/root/usr/bin/php')

    @unittest.skipIf(RUNTIME_ROOT is None, 'Use --runtime-root to verify the actual reviewed candidate bytes')
    def test_actual_three_runtime_files_reconstruct_exact_before_and_after(self):
        production = module()
        for path in production.PATHS:
            after = (RUNTIME_ROOT / path).read_bytes()
            item = production.FILES[path]
            self.assertEqual(sha(after), item['after_sha256'])
            before = after
            for old, new in reversed(item['replacements']):
                self.assertEqual(before.count(new.encode()), 1)
                before = before.replace(new.encode(), old.encode(), 1)
            self.assertEqual(sha(before), item['before_sha256'])
            self.assertEqual(production.repair(path, before), after)


if __name__ == '__main__':
    unittest.main()
