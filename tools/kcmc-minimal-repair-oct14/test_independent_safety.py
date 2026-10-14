#!/usr/bin/env python3
"""Independent synthetic failure checks; no host/app/data/config execution."""
from __future__ import print_function

import os
from pathlib import Path
import sys
import unittest
from unittest import mock

# Reuse only the author's synthetic fixture setup. Explicit suite selection below
# does not rerun the inherited primary cases or operate on production constants.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_installer import TransactionTests


class IndependentSafety(TransactionTests):
    def test_concurrent_edit_to_untouched_file_retained_when_owned_step_restored(self):
        move = self.m.move_code
        edited_path = self.m.PATHS[2]
        edited = b'<?php // independent unrelated newer code\n'
        def step(source, path, expected, candidate, lock):
            result = move(source, path, expected, candidate, lock)
            if source.name == 'stage-0.php':
                (self.app / edited_path).write_bytes(edited)
            return result
        with mock.patch.object(self.m, 'move_code', side_effect=step):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), self.before[self.m.PATHS[0]])
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.before[self.m.PATHS[1]])
        self.assertEqual((self.app / edited_path).read_bytes(), edited)
        with self.assertRaisesRegex(self.m.Refusal, 'Unknown'):
            self.m.inspect()
        for path, original in self.sentinels.items():
            self.assertEqual((self.app / path).read_bytes(), original)

    def test_stage_edit_after_candidate_lease_is_never_published(self):
        move = self.m.move_code
        forged = b'<?php // independent stage tampering\n'
        def step(source, path, expected, candidate, lock):
            if source.name == 'stage-1.php':
                source.write_bytes(forged)
            return move(source, path, expected, candidate, lock)
        with mock.patch.object(self.m, 'move_code', side_effect=step):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assert_bundle(self.before)
        value = self.m.load(self.sessions()[0])
        self.assertEqual(value['phase'], 'manual_review')
        self.assertIsNone(value['files'][self.m.PATHS[0]]['installed'])
        self.assertIsNone(value['files'][self.m.PATHS[1]]['installed'])

    def test_post_rename_directory_fsync_failure_retains_uncertain_code(self):
        real_replace, real_fsync = self.m.replace, self.m.os.fsync
        pending = [False]
        def replace(source, target, **kwargs):
            real_replace(source, target, **kwargs)
            if source == 'stage-1.php':
                pending[0] = True
        def fsync(fd):
            if pending[0]:
                pending[0] = False
                raise OSError('synthetic post-rename directory fsync failure')
            return real_fsync(fd)
        with mock.patch.object(self.m, 'replace', side_effect=replace), mock.patch.object(self.m.os, 'fsync', side_effect=fsync):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertEqual((self.app / self.m.PATHS[0]).read_bytes(), self.before[self.m.PATHS[0]])
        self.assertEqual((self.app / self.m.PATHS[1]).read_bytes(), self.after[self.m.PATHS[1]])
        self.assertEqual((self.app / self.m.PATHS[2]).read_bytes(), self.before[self.m.PATHS[2]])
        self.assertEqual(self.m.load(self.sessions()[0])['phase'], 'manual_review')
        with self.assertRaisesRegex(self.m.Refusal, 'Unfinished'):
            self.m.unfinished()

    def test_checkpoint_failure_after_verified_install_can_restore_owned_identity(self):
        real_journal = self.m.journal
        failed = [False]
        def journal(session, value):
            if not failed[0] and value['phase'] == 'applying' and value['files'][self.m.PATHS[0]]['installed'] is not None and value['intent'] is None:
                failed[0] = True
                raise OSError('synthetic verified checkpoint failure')
            return real_journal(session, value)
        with mock.patch.object(self.m, 'journal', side_effect=journal):
            with self.assertRaises(self.m.Refusal):
                self.m.apply()
        self.assertTrue(failed[0])
        self.assert_bundle(self.before)
        self.assertEqual(self.m.load(self.sessions()[0])['phase'], 'rolled_back')

    def test_persistent_journal_failure_never_claims_complete_recovery(self):
        real_journal = self.m.journal
        armed = [False]
        def journal(session, value):
            if value['phase'] == 'applying' and value['files'][self.m.PATHS[0]]['installed'] is not None:
                armed[0] = True
            if armed[0]:
                raise OSError('synthetic persistent private journal failure')
            return real_journal(session, value)
        with mock.patch.object(self.m, 'journal', side_effect=journal):
            with self.assertRaisesRegex(self.m.Refusal, 'manual review'):
                self.m.apply()
        self.assertTrue(armed[0])
        # The durable record remains unfinished even if an in-memory owned
        # identity was safely restored; a retry must not silently start anew.
        with self.assertRaisesRegex(self.m.Refusal, 'Unfinished'):
            self.m.unfinished()
        for path, original in self.sentinels.items():
            self.assertEqual((self.app / path).read_bytes(), original)

    def test_after_noop_preserves_code_identity_and_metadata(self):
        for path in self.m.PATHS:
            (self.app / path).write_bytes(self.after[path])
        before = {path: (self.app / path).stat() for path in self.m.PATHS}
        self.assertIsNone(self.m.apply())
        for path in self.m.PATHS:
            actual = (self.app / path).stat()
            original = before[path]
            self.assertEqual((actual.st_dev, actual.st_ino, actual.st_mtime_ns, actual.st_ctime_ns, actual.st_mode, actual.st_uid, actual.st_gid),
                             (original.st_dev, original.st_ino, original.st_mtime_ns, original.st_ctime_ns, original.st_mode, original.st_uid, original.st_gid))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.m.BACKUPS.exists())


CASES = (
    'test_concurrent_edit_to_untouched_file_retained_when_owned_step_restored',
    'test_stage_edit_after_candidate_lease_is_never_published',
    'test_post_rename_directory_fsync_failure_retains_uncertain_code',
    'test_checkpoint_failure_after_verified_install_can_restore_owned_identity',
    'test_persistent_journal_failure_never_claims_complete_recovery',
    'test_after_noop_preserves_code_identity_and_metadata',
)
if __name__ == '__main__':
    suite = unittest.TestSuite(IndependentSafety(name) for name in CASES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
