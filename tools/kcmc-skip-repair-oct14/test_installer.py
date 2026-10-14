#!/usr/bin/env python3
"""Temporary-copy transaction tests; no host, JavaScript, PHP or network execution."""
from __future__ import print_function

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

import derive_installer

HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = None
if '--runtime-root' in sys.argv:
    index = sys.argv.index('--runtime-root')
    RUNTIME_ROOT = Path(sys.argv[index + 1])
    del sys.argv[index:index + 2]


def module():
    spec = importlib.util.spec_from_file_location('isolated_skip_installer', str(HERE / 'installer.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def identity(path):
    info = path.lstat()
    return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns,
            info.st_mode, info.st_uid, info.st_gid, info.st_nlink, info.st_size)


def ast_string(value):
    # ast.Str is the native string node on Python 3.6; modern runtimes use
    # Constant and warn if the compatibility Str constructor is called.
    return ast.Constant(value=value) if sys.version_info >= (3, 8) else ast.Str(s=value)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-skip-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'app'
        self.app.mkdir()
        self.target = self.app / 'app.js'
        self.m = module()
        self.m.APP = self.app
        self.m.BACKUPS = self.root / 'private-repairs'
        self.m.UID, self.m.GID = os.getuid(), os.getgid()
        self.before = b"(() => {\n  'use strict';\n  // synthetic original\n})();\n"
        self.after = self.before.replace(b'original', b'repaired')
        self.target.write_bytes(self.before)
        self.target.chmod(0o644)
        self.m.FILES = {'app.js': {'before_sha256': sha(self.before), 'after_sha256': sha(self.after),
                                 'before_bytes': len(self.before), 'after_bytes': len(self.after),
                                 'replacements': [['// synthetic original', '// synthetic repaired']]}}
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
        self.sentinel_identity = {path: identity(self.app / path) for path in self.sentinels}
        self.web_paths = sorted(str(path.relative_to(self.app)) for path in self.app.rglob('*'))
        self.subprocess = mock.patch.object(self.m.subprocess, 'check_output', side_effect=AssertionError('Host subprocess forbidden'))
        self.calls = self.subprocess.start()
        self.addCleanup(self.subprocess.stop)

    def assert_sentinels(self):
        for path, data in self.sentinels.items():
            self.assertEqual((self.app / path).read_bytes(), data, path)
            self.assertEqual(identity(self.app / path), self.sentinel_identity[path], path)
        self.assertEqual(sorted(str(path.relative_to(self.app)) for path in self.app.rglob('*')), self.web_paths)
        self.assertFalse(self.calls.called)

    def assert_code(self, expected, expected_mode=0o644):
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(mode(self.target), expected_mode)
        self.assert_sentinels()

    def sessions(self):
        return sorted(self.m.BACKUPS.glob('repair-*'))

    def value(self):
        self.assertEqual(len(self.sessions()), 1)
        return self.m.load(self.sessions()[0])

    def assert_unfinished(self):
        with self.assertRaisesRegex(self.m.Refusal, 'Unfinished'):
            self.m.unfinished()
        with self.assertRaises(self.m.Refusal):
            self.m.apply()

    def test_cli_default_check_is_readonly(self):
        before = identity(self.target)
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['installer.py']), contextlib.redirect_stdout(output):
            self.assertEqual(self.m.main(), 0)
        self.assertIn('CHECK READY', output.getvalue())
        self.assertEqual(identity(self.target), before)
        self.assertFalse(self.m.BACKUPS.exists())
        self.assert_code(self.before)

    def test_apply_preserves_mode_ownership_and_private_only_backups(self):
        for code_mode in (0o644, 0o664):
            self.target.chmod(code_mode)
            session = self.m.apply()
            self.assert_code(self.after, code_mode)
            self.assertEqual(mode(self.m.BACKUPS), 0o700)
            self.assertEqual(mode(session), 0o700)
            self.assertEqual(mode(session / 'journal.json'), 0o600)
            self.assertEqual(mode(session / 'original-0.js'), 0o600)
            self.assertEqual((session / 'original-0.js').read_bytes(), self.before)
            self.assertFalse((session / 'stage-0.js').exists())
            info = self.target.stat()
            self.assertEqual((info.st_uid, info.st_gid, info.st_nlink), (os.getuid(), os.getgid(), 1))
            self.assertEqual(self.m.load(session)['phase'], 'applied')
            self.m.rollback(session.name)
            self.assert_code(self.before, code_mode)

    def test_after_noop_preserves_metadata_creates_no_backup(self):
        self.target.write_bytes(self.after)
        before = identity(self.target)
        self.assertIsNone(self.m.apply())
        self.assertEqual(identity(self.target), before)
        self.assertFalse(self.m.BACKUPS.exists())
        self.assert_code(self.after)

    def test_after_noop_with_applied_session_creates_no_new_backup(self):
        session = self.m.apply()
        before = identity(self.target)
        journal_before = identity(session / 'journal.json')
        self.assertIsNone(self.m.apply())
        self.assertEqual(self.sessions(), [session])
        self.assertEqual(identity(self.target), before)
        self.assertEqual(identity(session / 'journal.json'), journal_before)
        self.assert_code(self.after)

    def test_unknown_bytes_refused_before_any_backup(self):
        unknown = b'// independent newer JavaScript\n'
        self.target.write_bytes(unknown)
        before = identity(self.target)
        with self.assertRaisesRegex(self.m.Refusal, 'Unknown'):
            self.m.apply()
        self.assertEqual(identity(self.target), before)
        self.assertFalse(self.m.BACKUPS.exists())
        self.assert_code(unknown)

    def test_missing_file_refused_without_backup(self):
        self.target.unlink()
        with self.assertRaises(OSError):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_symlink_file_refused(self):
        outside = self.root / 'outside.js'
        outside.write_bytes(self.before)
        self.target.unlink()
        self.target.symlink_to(outside)
        with self.assertRaises(OSError):
            self.m.apply()
        self.assertEqual(outside.read_bytes(), self.before)
        self.assertFalse(self.m.BACKUPS.exists())

    def test_symlink_app_parent_refused(self):
        moved = self.root / 'moved-app'
        self.app.rename(moved)
        self.app.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(OSError):
            self.m.apply()
        self.assertEqual((moved / 'app.js').read_bytes(), self.before)

    def test_hardlinked_file_refused(self):
        os.link(str(self.target), str(self.root / 'linked.js'))
        with self.assertRaisesRegex(self.m.Refusal, 'linked'):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_fifo_refused_without_blocking(self):
        self.target.unlink()
        os.mkfifo(str(self.target))
        with self.assertRaises(self.m.Refusal):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_unsafe_code_and_app_modes_refused(self):
        for code_mode in (0o600, 0o666, 0o755):
            self.target.chmod(code_mode)
            with self.assertRaisesRegex(self.m.Refusal, 'Code mode'):
                self.m.apply()
        self.target.chmod(0o644)
        self.app.chmod(0o777)
        with self.assertRaisesRegex(self.m.Refusal, 'Unsafe application directory'):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_wrong_caller_or_file_owner_refused(self):
        self.m.UID += 1
        with self.assertRaisesRegex(self.m.Refusal, 'hosting account'):
            self.m.apply()
        with mock.patch.object(self.m, 'caller'):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())

    def test_fixed_environment_cannot_override_scope(self):
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/forged', 'KCMC_UID': '0', 'KCMC_PRIVATE_DATA_DIR': '/tmp/private'}):
            production = module()
            self.assertEqual(production.APP, Path('/home/bobsome1/public_html/kcmc-connect'))
            self.assertEqual(production.BACKUPS, Path('/home/bobsome1/kcmc-skip-repair-backups'))
            self.assertEqual((production.UID, production.GID), (2162, 2147))
            self.assertEqual(production.PATHS, ('app.js',))

    def test_cross_filesystem_refused_before_staging(self):
        with mock.patch.object(self.m, 'backup_device', return_value=self.target.stat().st_dev + 1):
            with self.assertRaisesRegex(self.m.Refusal, 'same filesystem'):
                self.m.apply()
        self.assertEqual(self.sessions(), [])
        self.assert_code(self.before)

    def test_hash_gate_failure_keeps_private_stage_and_live_original(self):
        with mock.patch.object(self.m, 'lint', side_effect=RuntimeError('synthetic stage verifier failure')):
            with self.assertRaisesRegex(self.m.Refusal, 'byte verification failed; no live replacement'):
                self.m.apply()
        self.assert_code(self.before)
        self.assertEqual(self.value()['phase'], 'rolled_back')
        for path in self.sessions()[0].iterdir():
            self.assertEqual(mode(path), 0o600)

    def test_stage_tamper_before_hash_gate_is_never_published(self):
        lint = self.m.lint
        def mutate(session):
            (session / 'stage-0.js').write_bytes(b'// forged stage\n')
            return lint(session)
        with mock.patch.object(self.m, 'lint', side_effect=mutate):
            with self.assertRaisesRegex(self.m.Refusal, 'no live replacement'):
                self.m.apply()
        self.assert_code(self.before)
        self.assertEqual(self.value()['phase'], 'rolled_back')

    def test_linked_stage_before_hash_gate_is_never_published(self):
        lint = self.m.lint
        def mutate(session):
            os.link(str(session / 'stage-0.js'), str(self.root / 'stage-link'))
            return lint(session)
        with mock.patch.object(self.m, 'lint', side_effect=mutate):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assert_code(self.before)
        self.assertEqual(self.value()['phase'], 'rolled_back')

    def test_hash_gate_also_checks_byte_count(self):
        self.m.FILES['app.js']['after_bytes'] += 1
        session = self.root / 'stage-test'
        session.mkdir(mode=0o700)
        staged = session / 'stage-0.js'
        staged.write_bytes(self.after)
        staged.chmod(0o600)
        with self.assertRaisesRegex(self.m.Refusal, 'stage bytes changed'):
            self.m.lint(session)
        self.assert_code(self.before)

    def test_pre_rename_failure_after_intent_requires_manual_review(self):
        with mock.patch.object(self.m, 'move_code', side_effect=OSError('synthetic pre-rename failure')):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(self.before)
        value = self.value()
        self.assertEqual((value['phase'], value['intent'], value['uncertain']), ('manual_review', 'app.js', ['app.js']))
        self.assertIsNone(value['files']['app.js']['installed'])
        self.assertEqual(value['files']['app.js']['candidate']['sha256'], sha(self.after))
        self.assert_unfinished()

    def test_stage_tamper_after_candidate_lease_is_never_published(self):
        move = self.m.move_code
        def mutate(source, path, expected, candidate, lock):
            source.write_bytes(b'// forged after candidate lease\n')
            return move(source, path, expected, candidate, lock)
        with mock.patch.object(self.m, 'move_code', side_effect=mutate):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(self.before)
        self.assertIsNone(self.value()['files']['app.js']['installed'])
        self.assert_unfinished()

    def test_rename_succeeded_then_exception_preserves_uncertain_after(self):
        replace = self.m.replace
        def fail(source, target, **kwargs):
            replace(source, target, **kwargs)
            if source == 'stage-0.js':
                raise OSError('synthetic error after successful rename')
        with mock.patch.object(self.m, 'replace', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(self.after)
        value = self.value()
        self.assertIsNone(value['files']['app.js']['installed'])
        self.assertEqual(value['intent'], 'app.js')
        self.assert_unfinished()

    def test_post_rename_fsync_failure_preserves_uncertain_after(self):
        replace, fsync = self.m.replace, self.m.os.fsync
        pending = [False]
        def replaced(source, target, **kwargs):
            replace(source, target, **kwargs)
            if source == 'stage-0.js':
                pending[0] = True
        def synced(fd):
            if pending[0]:
                pending[0] = False
                raise OSError('synthetic post-rename fsync failure')
            return fsync(fd)
        with mock.patch.object(self.m, 'replace', side_effect=replaced), mock.patch.object(self.m.os, 'fsync', side_effect=synced):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(self.after)
        self.assertIsNone(self.value()['files']['app.js']['installed'])
        self.assert_unfinished()

    def test_post_rename_stat_failure_preserves_durable_intent(self):
        replace, read = self.m.replace, self.m.read_at
        pending = [False]
        def replaced(source, target, **kwargs):
            replace(source, target, **kwargs)
            if source == 'stage-0.js':
                pending[0] = True
        def observed(parent, name):
            if pending[0] and name == 'app.js':
                raise OSError('synthetic installed poststat failure')
            return read(parent, name)
        with mock.patch.object(self.m, 'replace', side_effect=replaced), mock.patch.object(self.m, 'read_at', side_effect=observed):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(self.after)
        self.assertEqual(self.value()['intent'], 'app.js')
        self.assert_unfinished()

    def test_checkpoint_failure_after_verified_install_restores_owned_identity(self):
        journal = self.m.journal
        failed = [False]
        def checkpoint(session, value):
            if not failed[0] and value['phase'] == 'applying' and value['files']['app.js']['installed'] is not None and value['intent'] is None:
                failed[0] = True
                raise OSError('synthetic verified checkpoint failure')
            return journal(session, value)
        with mock.patch.object(self.m, 'journal', side_effect=checkpoint):
            with self.assertRaisesRegex(self.m.Refusal, 'verified owned code restored'):
                self.m.apply()
        self.assertTrue(failed[0])
        self.assert_code(self.before)
        self.assertEqual(self.value()['phase'], 'rolled_back')

    def test_persistent_journal_failure_cannot_claim_complete_recovery(self):
        journal = self.m.journal
        armed = [False]
        def checkpoint(session, value):
            if value['phase'] == 'applying' and value['files']['app.js']['installed'] is not None:
                armed[0] = True
            if armed[0]:
                raise OSError('synthetic persistent journal failure')
            return journal(session, value)
        with mock.patch.object(self.m, 'journal', side_effect=checkpoint):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertTrue(armed[0])
        # Persistent journaling failure also prevents durable restore intent.
        # The installed code remains after; the installer cannot claim rollback.
        self.assert_code(self.after)
        self.assert_unfinished()

    def test_prepared_journal_precedes_each_private_write_and_blocks_retry(self):
        write = self.m.write_private
        for name in ('original-0.js', 'stage-0.js'):
            with self.subTest(name=name):
                def fail(path, data):
                    if Path(path).name == name:
                        value = self.m.load(Path(path).parent)
                        self.assertEqual(value['phase'], 'prepared')
                        raise OSError('synthetic preparation failure')
                    return write(path, data)
                with mock.patch.object(self.m, 'write_private', side_effect=fail):
                    with self.assertRaises(OSError):
                        self.m.apply()
                self.assert_code(self.before)
                self.assert_unfinished()
                # Finish this synthetic session without changing the code so the
                # second preparation point can be exercised independently.
                prepared = [(session, self.m.load(session)) for session in self.sessions()
                            if self.m.load(session)['phase'] == 'prepared']
                self.assertEqual(len(prepared), 1)
                session, value = prepared[0]
                value['phase'] = 'rolled_back'
                self.m.journal(session, value)

    def test_concurrent_edit_of_installed_file_is_never_overwritten(self):
        move = self.m.move_code
        edited = b'// independent concurrent edit\n'
        def mutate(source, path, expected, candidate, lock):
            result = move(source, path, expected, candidate, lock)
            if source.name == 'stage-0.js':
                self.target.write_bytes(edited)
            return result
        with mock.patch.object(self.m, 'move_code', side_effect=mutate):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(edited)
        self.assert_unfinished()

    def test_final_descriptor_check_preserves_replaced_target(self):
        move = self.m.move_code
        edited = b'// final-boundary concurrent writer\n'
        def changed(source, path, expected, candidate, lock):
            def boundary():
                lock()
                concurrent = self.root / 'concurrent.js'
                concurrent.write_bytes(edited)
                concurrent.chmod(0o644)
                os.replace(str(concurrent), str(self.target))
            return move(source, path, expected, candidate, boundary)
        with mock.patch.object(self.m, 'move_code', side_effect=changed):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(edited)

    def test_final_parent_descriptor_check_preserves_replaced_app(self):
        move = self.m.move_code
        edited = b'// new parent namespace\n'
        displaced = self.root / 'displaced-app'
        def changed(source, path, expected, candidate, lock):
            def boundary():
                lock()
                self.app.rename(displaced)
                self.app.mkdir(mode=0o700)
                self.target.write_bytes(edited)
                self.target.chmod(0o644)
            return move(source, path, expected, candidate, boundary)
        with mock.patch.object(self.m, 'move_code', side_effect=changed):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual(self.target.read_bytes(), edited)
        self.assertEqual((displaced / 'app.js').read_bytes(), self.before)
        for path, data in self.sentinels.items():
            self.assertEqual((displaced / path).read_bytes(), data)

    def test_lock_replacement_after_commit_blocks_recovery(self):
        move = self.m.move_code
        def changed(source, path, expected, candidate, lock):
            result = move(source, path, expected, candidate, lock)
            if source.name == 'stage-0.js':
                target = self.m.BACKUPS / '.repair.lock'
                target.unlink()
                target.write_bytes(b'')
                target.chmod(0o600)
            return result
        with mock.patch.object(self.m, 'move_code', side_effect=changed):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_code(self.after)
        self.assert_unfinished()

    def test_concurrent_installer_lock_refused_without_session(self):
        with self.m.locked():
            with self.assertRaises(BlockingIOError):
                self.m.apply()
        self.assertEqual(self.sessions(), [])
        self.assert_code(self.before)

    def test_unsafe_backup_root_and_symlink_refused(self):
        self.m.BACKUPS.mkdir(mode=0o755)
        self.m.BACKUPS.chmod(0o755)
        with self.assertRaisesRegex(self.m.Refusal, 'Backup directory'):
            self.m.apply()
        self.m.BACKUPS.rmdir()
        outside = self.root / 'outside'
        outside.mkdir(mode=0o700)
        self.m.BACKUPS.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(self.m.Refusal):
            self.m.apply()
        self.assertEqual(list(outside.iterdir()), [])
        self.assert_code(self.before)

    def test_explicit_rollback_restores_exact_bytes_mode_and_only_session(self):
        self.target.chmod(0o664)
        session = self.m.apply()
        self.m.rollback(session.name)
        self.assert_code(self.before, 0o664)
        self.assertEqual(self.m.load(session)['phase'], 'rolled_back')
        with self.assertRaisesRegex(self.m.Refusal, 'fully verified applied'):
            self.m.rollback(session.name)

    def test_same_bytes_new_inode_prevents_rollback(self):
        session = self.m.apply()
        concurrent = self.root / 'concurrent.js'
        concurrent.write_bytes(self.after)
        concurrent.chmod(0o644)
        os.replace(str(concurrent), str(self.target))
        before = identity(self.target)
        with self.assertRaisesRegex(self.m.Refusal, 'lease changed'):
            self.m.rollback(session.name)
        self.assertEqual(identity(self.target), before)
        self.assert_code(self.after)

    def test_same_inode_same_bytes_ctime_change_prevents_rollback(self):
        session = self.m.apply()
        previous = self.target.stat()
        self.target.write_bytes(self.after)
        os.utime(str(self.target), ns=(previous.st_atime_ns, previous.st_mtime_ns))
        before = identity(self.target)
        with self.assertRaisesRegex(self.m.Refusal, 'lease changed'):
            self.m.rollback(session.name)
        self.assertEqual(identity(self.target), before)
        self.assert_code(self.after)

    def test_concurrent_mode_change_prevents_rollback(self):
        session = self.m.apply()
        self.target.chmod(0o664)
        with self.assertRaisesRegex(self.m.Refusal, 'lease changed'):
            self.m.rollback(session.name)
        self.assert_code(self.after, 0o664)

    def test_corrupt_backup_cannot_be_used_for_rollback(self):
        session = self.m.apply()
        (session / 'original-0.js').write_bytes(b'// forged original backup\n')
        with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
            self.m.rollback(session.name)
        self.assert_code(self.after)
        self.assertEqual(self.value()['phase'], 'manual_review')

    def test_uncertain_explicit_rollback_retains_visible_original_and_intent(self):
        session = self.m.apply()
        replace = self.m.replace
        def fail(source, target, **kwargs):
            replace(source, target, **kwargs)
            if source.startswith('restore-'):
                raise OSError('synthetic rollback error after rename')
        with mock.patch.object(self.m, 'replace', side_effect=fail):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.rollback(session.name)
        self.assert_code(self.before)
        value = self.value()
        self.assertEqual((value['phase'], value['intent'], value['uncertain']), ('manual_review', 'app.js', ['app.js']))
        self.assert_unfinished()

    def test_rollback_fsync_or_poststat_failure_keeps_uncertain_original(self):
        for point in ('fsync', 'poststat'):
            with self.subTest(point=point):
                session = self.m.apply()
                replace, fsync, read = self.m.replace, self.m.os.fsync, self.m.read_at
                pending = [False]
                def replaced(source, target, **kwargs):
                    replace(source, target, **kwargs)
                    if source.startswith('restore-'):
                        pending[0] = True
                def synced(fd):
                    if pending[0] and point == 'fsync':
                        pending[0] = False
                        raise OSError('synthetic rollback fsync failure')
                    return fsync(fd)
                def observed(parent, name):
                    if pending[0] and point == 'poststat' and name == 'app.js':
                        raise OSError('synthetic rollback poststat failure')
                    return read(parent, name)
                with mock.patch.object(self.m, 'replace', side_effect=replaced), mock.patch.object(self.m.os, 'fsync', side_effect=synced), mock.patch.object(self.m, 'read_at', side_effect=observed):
                    with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                        self.m.rollback(session.name)
                self.assert_code(self.before)
                value = self.m.load(session)
                self.assertEqual((value['phase'], value['intent'], value['uncertain']), ('manual_review', 'app.js', ['app.js']))
                self.assert_unfinished()
                # Finish only the isolated synthetic journal to exercise the
                # other failure point without altering the engine's policy.
                value['phase'], value['intent'], value['uncertain'] = 'rolled_back', None, []
                value['files']['app.js']['installed'] = None
                self.m.journal(session, value)

    def test_out_of_scope_inventory_refused(self):
        self.m.FILES['config.php'] = self.m.FILES['app.js']
        with self.assertRaisesRegex(self.m.Refusal, 'exactly'):
            self.m.apply()
        self.assertFalse(self.m.BACKUPS.exists())
        self.assert_code(self.before)

    def test_session_traversal_and_missing_cli_session_refused(self):
        for name in ('../outside', 'repair-forged', '/tmp/repair-other'):
            with self.assertRaisesRegex(self.m.Refusal, 'exact private'):
                self.m.rollback(name)
        with mock.patch.object(sys, 'argv', ['installer.py', 'rollback']), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.m.main(), 1)
        self.assertFalse(self.m.BACKUPS.exists())

    def test_tampered_journal_scope_and_unknown_fields_refused(self):
        session = self.m.apply()
        original = json.loads((session / 'journal.json').read_text())
        for variant in ('scope', 'field', 'phase', 'release', 'app', 'lease'):
            value = json.loads(json.dumps(original))
            if variant == 'scope':
                value['files']['config.php'] = value['files']['app.js']
            elif variant == 'field':
                value['unreviewed'] = True
            elif variant == 'phase':
                value['phase'] = 'unknown'
            elif variant == 'release':
                value['release'] = 'another-repair'
            elif variant == 'app':
                value['app'] = '/tmp/another-app'
            else:
                value['files']['app.js']['installed']['mode'] = 0o777
            self.m.journal(session, value)
            with self.assertRaises(self.m.Refusal):
                self.m.rollback(session.name)
            self.assert_code(self.after)
        self.m.journal(session, original)

    def test_unfinished_session_blocks_after_noop_and_readonly_check(self):
        session = self.m.apply()
        value = self.m.load(session)
        value['phase'] = 'manual_review'
        self.m.journal(session, value)
        before = identity(self.target)
        with self.assertRaisesRegex(self.m.Refusal, 'Unfinished'):
            self.m.apply()
        with mock.patch.object(sys, 'argv', ['installer.py']), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.m.main(), 1)
        self.assertEqual(identity(self.target), before)
        self.assert_code(self.after)

    def test_old_session_does_not_authorize_new_application_rollback(self):
        first = self.m.apply()
        self.m.rollback(first.name)
        second = self.m.apply()
        with self.assertRaisesRegex(self.m.Refusal, 'fully verified applied'):
            self.m.rollback(first.name)
        self.assertEqual(self.m.load(second)['phase'], 'applied')
        self.assert_code(self.after)


class ProvenanceTests(unittest.TestCase):
    def test_production_scope_and_reviewed_inventory(self):
        production = module()
        files = json.loads((HERE / 'runtime-reviewed.json').read_text())
        fixture = json.loads((HERE / 'provenance/skip-link-reviewed.json').read_text())
        self.assertEqual(production.FILES, files)
        reviewed = files['app.js'].copy()
        self.assertEqual((reviewed.pop('before_bytes'), reviewed.pop('after_bytes')), (18999, 19463))
        self.assertEqual({'app.js': reviewed}, fixture['files'])
        self.assertEqual(production.PATHS, ('app.js',))
        self.assertEqual(production.FILES['app.js']['before_sha256'], '2a3e82a72ad689cec36984541c8c5a4c1b740fa2de7e38b2e1cd7b5aee373348')
        self.assertEqual(production.FILES['app.js']['after_sha256'], 'd2d349264224e119482187e0fdbfcee6cd6ed29c16b1874c65c88cf29dd93963')
        production.inventory()

    def test_exact_frozen_engine_derivation_and_python_parse(self):
        frozen = (HERE / 'provenance/frozen-minimal-installer.py').read_bytes()
        installer = (HERE / 'installer.py').read_bytes()
        self.assertEqual(sha(frozen), derive_installer.ENGINE_SHA256)
        self.assertEqual(installer, derive_installer.derive(frozen, module().FILES))
        compile(installer, 'installer.py', 'exec')
        compile((HERE / 'derive_installer.py').read_bytes(), 'derive_installer.py', 'exec')

    def test_ast_transaction_engine_is_unchanged_except_enumerated_deltas(self):
        old = ast.parse((HERE / 'provenance/frozen-minimal-installer.py').read_text())
        new = ast.parse((HERE / 'installer.py').read_text())
        constants = set(['BACKUPS', 'RELEASE', 'PATHS', 'FILES'])
        strings = {
            'Three pinned KCMC PHP repairs; Python 3.6+, offline, no application execution.': 'module-description',
            'One pinned KCMC app.js repair; Python 3.6+, offline, no application execution.': 'module-description',
            'Repair inventory is not exactly the three reviewed files': 'scope-description',
            'Repair inventory is not exactly the reviewed app.js file': 'scope-description',
            'Backup staging and all three code files must use the same filesystem; no replacement made': 'device-description',
            'Backup staging and app.js must use the same filesystem; no replacement made': 'device-description',
            'Staged PHP 8.2 syntax verification failed; no live replacement. Private session: ': 'stage-description',
            'Pinned staged JavaScript byte verification failed; no live replacement. Private session: ': 'stage-description',
            '.php': 'code-suffix', '.js': 'code-suffix',
        }
        class Normalize(ast.NodeTransformer):
            def visit_Module(self, node):
                result = []
                for child in node.body:
                    if isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name):
                        name = child.targets[0].id
                        if name == 'PHP':
                            continue
                        if name in constants:
                            child.value = ast_string('reviewed-' + name)
                    result.append(self.visit(child))
                node.body = result
                return node
            def visit_FunctionDef(self, node):
                if node.name == 'lint':
                    node.body = [ast.Pass()]
                    return node
                return self.generic_visit(node)
            def visit_Str(self, node):
                return ast.copy_location(ast_string(strings.get(node.s, node.s)), node)
            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    return ast.copy_location(ast_string(strings.get(node.value, node.value)), node)
                return node
        self.assertEqual(ast.dump(Normalize().visit(old)), ast.dump(Normalize().visit(new)))

    def test_host_installer_has_no_subprocess_call_or_js_execution(self):
        tree = ast.parse((HERE / 'installer.py').read_text())
        forbidden = ('check_output', 'run', 'Popen', 'system', 'execv', 'execve', 'eval', 'exec')
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                self.assertNotIn(name, forbidden)

    @unittest.skipIf(RUNTIME_ROOT is None, 'Use --runtime-root to verify the actual reviewed app.js')
    def test_actual_reviewed_app_reconstructs_exact_before_and_after(self):
        production = module()
        after = (RUNTIME_ROOT / 'app.js').read_bytes()
        item = production.FILES['app.js']
        self.assertEqual((sha(after), len(after)), (item['after_sha256'], item['after_bytes']))
        before = after
        for old, new in reversed(item['replacements']):
            self.assertEqual(before.count(new.encode('utf-8')), 1)
            before = before.replace(new.encode('utf-8'), old.encode('utf-8'), 1)
        self.assertEqual((sha(before), len(before)), (item['before_sha256'], item['before_bytes']))
        self.assertEqual(production.repair('app.js', before), after)
        self.assertEqual(len(after.splitlines()) - len(before.splitlines()), 9)
        with tempfile.TemporaryDirectory(prefix='kcmc-skip-reviewed-') as temporary:
            root = Path(temporary)
            production.APP = root / 'app'
            production.APP.mkdir()
            production.BACKUPS = root / 'private-repairs'
            production.UID, production.GID = os.getuid(), os.getgid()
            target = production.APP / 'app.js'
            target.write_bytes(before)
            target.chmod(0o644)
            with mock.patch.object(production.subprocess, 'check_output', side_effect=AssertionError('Host subprocess forbidden')):
                session = production.apply()
                self.assertEqual(target.read_bytes(), after)
                installed = identity(target)
                self.assertIsNone(production.apply())
                self.assertEqual(identity(target), installed)
                production.rollback(session.name)
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(mode(target), 0o644)


if __name__ == '__main__':
    unittest.main()
