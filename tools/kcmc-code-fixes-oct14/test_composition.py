#!/usr/bin/env python3
"""Synthetic composition of four real public candidates; no host/network writes."""
from __future__ import print_function

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
CANDIDATE_ROOT = HERE.parents[1] / 'KCMC-Connect-Phase6-Recreated'
if '--candidate-root' in sys.argv:
    index = sys.argv.index('--candidate-root')
    CANDIDATE_ROOT = Path(sys.argv[index + 1]).resolve()
    del sys.argv[index:index + 2]


def runner():
    spec = importlib.util.spec_from_file_location('isolated_combined_runner', str(HERE / 'installer.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def metadata(path):
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_atime_ns, info.st_mtime_ns, info.st_ctime_ns,
            stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid, info.st_nlink)


def fixture_bytes(path):
    """Assertions also avoid changing the access time being compared."""
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NOATIME', 0))
    try:
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk)
    finally:
        os.close(fd)


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-code-composition-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'app'
        self.app.mkdir()
        self.wrapper = runner()
        self.engines = self.wrapper.load_engines()
        self.before, self.after, self.modes = {}, {}, {}
        for group in self.wrapper.GROUPS:
            module = self.engines[group]
            module.APP = self.app
            module.BACKUPS = self.root / ('private-' + group)
            module.UID, module.GID = os.getuid(), os.getgid()
            for index, path in enumerate(module.PATHS):
                # Keep the exact frozen inventory. Restore canonical preimages from
                # actual reviewed candidate bytes using only its pinned replacements.
                item = module.FILES[path]
                candidate = (CANDIDATE_ROOT / path).read_bytes()
                self.assertEqual(sha(candidate), item['after_sha256'], 'Candidate is not the frozen reviewed output: ' + path)
                self.assertEqual(len(candidate), item['after_bytes'])
                original = candidate
                for old, new in reversed(item['replacements']):
                    old, new = old.encode('utf-8'), new.encode('utf-8')
                    self.assertEqual(original.count(new), 1, path)
                    original = original.replace(new, old, 1)
                self.assertEqual(sha(original), item['before_sha256'], path)
                self.assertEqual(len(original), item['before_bytes'])
                self.before[path], self.after[path] = original, candidate
                target = self.app / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)
                self.modes[path] = 0o664 if index == 1 else 0o644
                target.chmod(self.modes[path])
        # Only the PHP path is overridden. The real engine still runs its lint
        # argument/version logic; separate PHP 8.2 validation gates use real PHP.
        self.php_calls = self.root / 'php-calls'
        self.php_stub = self.root / 'php82-lint-stub'
        self.php_stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> '" + str(self.php_calls) + "'\n" +
                                 "case \"$*\" in\n  '-n -v') printf 'PHP 8.2.34 (cli)\\n' ;;\n" +
                                 "  '-n -l '*) printf 'No syntax errors detected\\n' ;;\n  *) exit 97 ;;\nesac\n")
        self.php_stub.chmod(0o700)
        self.real_choose_php82_cli = self.wrapper.choose_php82_cli
        # Save the real callable rather than stopping/restarting a patcher; this
        # remains safe with the actual Python 3.6 unittest.mock cleanup behavior.
        self.php_selection = mock.patch.object(self.wrapper, 'choose_php82_cli',
                                               return_value=(str(self.php_stub), '8.2.34'))
        self.php_selection_mock = self.php_selection.start()
        self.addCleanup(self.php_selection.stop)
        self.sentinels = {'config.php': b'<?php // synthetic private config\n',
                          'data/private/users.json': b'{"synthetic":"users unchanged"}',
                          'data/private/timeclock.json': b'{"synthetic":"records unchanged"}',
                          'data/content.json': b'{"synthetic":"published content unchanged"}',
                          '.git/HEAD': b'ref: refs/heads/main\n'}
        for path, data in self.sentinels.items():
            target = self.app / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o600)
        self.sentinel_metadata = {path: metadata(self.app / path) for path in self.sentinels}

    def invoke(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, 'argv', ['installer.py'] + list(args)), \
                mock.patch.object(self.wrapper, 'load_engines', return_value=self.engines), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = self.wrapper.main()
        return result, output.getvalue(), errors.getvalue()

    def sessions(self, group):
        return sorted(self.engines[group].BACKUPS.glob('repair-*'))

    def set_after(self, group):
        for path in self.engines[group].PATHS:
            (self.app / path).write_bytes(self.after[path])

    def snapshot(self):
        return {path: (fixture_bytes(self.app / path), metadata(self.app / path)) for path in self.before}

    def assert_unchanged(self, snapshot):
        self.assertEqual(snapshot, self.snapshot())
        self.assert_sentinels()

    def assert_sentinels(self):
        for path, data in self.sentinels.items():
            self.assertEqual(fixture_bytes(self.app / path), data, path)
            self.assertEqual(metadata(self.app / path), self.sentinel_metadata[path], path)

    def assert_state(self, php, skip):
        for group, expected in (('php', php), ('skip', skip)):
            for path in self.engines[group].PATHS:
                self.assertEqual(fixture_bytes(self.app / path), expected[path], path)
                info = (self.app / path).stat()
                self.assertEqual(stat.S_IMODE(info.st_mode), self.modes[path], path)
                self.assertEqual((info.st_uid, info.st_gid, info.st_nlink), (os.getuid(), os.getgid(), 1))
        self.assert_sentinels()

    def make_journal(self, group, phase='prepared', malformed=False):
        module = self.engines[group]
        state, files = module.inspect()
        self.assertEqual(state, 'before')
        module.private_dir(module.BACKUPS, create=True)
        session = module.session_name('repair-20261014T000000Z-' + ('a' if group == 'php' else 'b') * 32)
        module.private_dir(session, create=True)
        if malformed:
            module.write_private(session / 'journal.json', b'{"private":"RAW_RECORD_MUST_NOT_APPEAR"}\n')
        else:
            value = {'release': module.RELEASE, 'app': str(module.APP), 'phase': phase,
                     'intent': None, 'uncertain': [],
                     'files': {path: {'original': files[path][1], 'candidate': None, 'installed': None}
                               for path in module.PATHS}}
            module.journal(session, value)
        return session

    def test_all_four_old_repaired_with_independent_private_journals(self):
        code, output, errors = self.invoke('apply')
        self.assertEqual((code, errors), (0, ''))
        self.assert_state(self.after, self.after)
        self.assertLess(output.index('GROUP php APPLIED'), output.index('GROUP skip APPLIED'))
        self.assertIn('Groups apply separately;', output)
        for group in self.wrapper.GROUPS:
            session = self.sessions(group)[0]
            module = self.engines[group]
            self.assertEqual(module.load(session)['phase'], 'applied')
            self.assertEqual(stat.S_IMODE(module.BACKUPS.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(session.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((session / 'journal.json').stat().st_mode), 0o600)
            suffix = 'php' if group == 'php' else 'js'
            for index, path in enumerate(module.PATHS):
                backup = session / ('original-' + str(index) + '.' + suffix)
                self.assertEqual(backup.read_bytes(), self.before[path])
                self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
            self.assertIn('PRIVATE_SESSION ' + group + ' ' + str(session), output)
            self.assertIn('ROLLBACK_COMMAND python3 installer.py rollback --group ' + group +
                          ' --session ' + session.name, output)
        self.assertNotEqual(self.engines['php'].BACKUPS, self.engines['skip'].BACKUPS)
        calls = self.php_calls.read_text().splitlines()
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0], '-n -v')
        self.assertTrue(all(call.startswith('-n -l ') for call in calls[1:]))

    def test_php_already_repaired_only_js_changes(self):
        self.set_after('php')
        unchanged = {path: metadata(self.app / path) for path in self.engines['php'].PATHS}
        code, output, errors = self.invoke('apply')
        self.assertEqual((code, errors), (0, ''))
        self.assert_state(self.after, self.after)
        self.assertEqual(unchanged, {path: metadata(self.app / path) for path in unchanged})
        self.assertFalse(self.engines['php'].BACKUPS.exists())
        self.assertFalse(self.php_calls.exists())
        self.assertIn('GROUP php ALREADY_REPAIRED', output)
        self.assertEqual(len(self.sessions('skip')), 1)

    def test_js_already_repaired_only_php_changes(self):
        self.set_after('skip')
        before = metadata(self.app / 'app.js')
        code, output, errors = self.invoke('apply')
        self.assertEqual((code, errors), (0, ''))
        self.assert_state(self.after, self.after)
        self.assertEqual(before, metadata(self.app / 'app.js'))
        self.assertFalse(self.engines['skip'].BACKUPS.exists())
        self.assertIn('GROUP skip ALREADY_REPAIRED', output)
        self.assertEqual(len(self.sessions('php')), 1)

    def test_both_after_are_metadata_preserving_noop(self):
        self.set_after('php')
        self.set_after('skip')
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual((code, errors), (0, ''))
        self.assert_unchanged(before)
        self.assertFalse(self.php_calls.exists())
        self.assertTrue(all(not module.BACKUPS.exists() for module in self.engines.values()))
        self.assertEqual(output.count('no replacement or new backup.'), 2)

    def test_default_check_reads_only_and_creates_no_backup(self):
        before = self.snapshot()
        code, output, errors = self.invoke()
        self.assertEqual((code, errors), (0, ''))
        self.assert_unchanged(before)
        self.assertIn('GROUP php CHECK READY', output)
        self.assertIn('GROUP skip CHECK READY', output)
        self.assertFalse(self.php_calls.exists())
        self.assertTrue(all(not module.BACKUPS.exists() for module in self.engines.values()))

    def test_runtime_selection_precedes_both_ready_reports(self):
        code, output, errors = self.invoke('check')
        self.assertEqual((code, errors), (0, ''))
        self.assertLess(output.index('PHP_CLI '), output.index('GROUP php CHECK READY'))
        self.assertLess(output.index('PHP_CLI '), output.index('GROUP skip CHECK READY'))
        self.assertEqual(self.engines['php'].PHP, str(self.php_stub))
        self.php_selection_mock.assert_called_once_with()
        self.assertFalse(self.php_calls.exists())

    def test_unavailable_runtime_refuses_before_ready_backups_or_writes(self):
        self.php_selection_mock.side_effect = self.wrapper.Refusal(
            'No compatible PHP 8.2 CLI found; no backup or live replacement made')
        for action in ('check', 'apply'):
            before = self.snapshot()
            code, output, errors = self.invoke(action)
            self.assertEqual(code, 1)
            self.assertIn('No compatible PHP 8.2 CLI found', errors)
            self.assertNotIn('CHECK READY', output)
            self.assert_unchanged(before)
            self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))

    def test_php_after_does_not_probe_runtime_for_js_only_retry_or_noop(self):
        self.set_after('php')
        self.php_selection_mock.side_effect = AssertionError('No probe needed for repaired PHP')
        self.assertEqual(self.invoke('check')[0], 0)
        self.assertEqual(self.invoke('apply')[0], 0)
        self.assertEqual(self.invoke('apply')[0], 0)
        self.php_selection_mock.assert_not_called()
        self.assertFalse(self.php_calls.exists())
        self.assert_state(self.after, self.after)

    def test_rollback_does_not_need_php_runtime(self):
        self.assertEqual(self.invoke('apply')[0], 0)
        self.php_selection_mock.side_effect = AssertionError('Rollback restores verified backups')
        for group in ('skip', 'php'):
            session = self.sessions(group)[0]
            code, output, errors = self.invoke('rollback', '--group', group, '--session', session.name)
            self.assertEqual((code, errors), (0, ''))
        self.assert_state(self.before, self.before)

    def test_cloudlinux_fallback_is_used_by_full_staged_apply(self):
        self.php_selection_mock.side_effect = self.real_choose_php82_cli
        calls = []
        def command(argv, **kwargs):
            calls.append(argv)
            if argv[2] == '-v' and len(calls) <= 2:
                self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
            if argv[0] == '/opt/cpanel/ea-php82/root/usr/bin/php':
                raise FileNotFoundError(2, 'Unavailable')
            self.assertEqual(argv[0], '/opt/alt/php82/usr/bin/php')
            if argv[2] == '-v':
                return b'PHP 8.2.34 (cli) (built: test)\n'
            self.assertEqual(argv[1:3], ['-n', '-l'])
            return b'No syntax errors detected\n'
        with mock.patch.object(subprocess, 'check_output', side_effect=command):
            code, output, errors = self.invoke('apply')
        self.assertEqual((code, errors), (0, ''))
        self.assertIn('PHP_CLI /opt/alt/php82/usr/bin/php PHP 8.2.34', output)
        self.assertEqual(self.engines['php'].PHP, '/opt/alt/php82/usr/bin/php')
        self.assertEqual(len(calls), 6)
        self.assert_state(self.after, self.after)

    def test_unknown_js_blocks_php_before_any_write(self):
        (self.app / 'app.js').write_bytes(b'// RAW_RECORD_MUST_NOT_APPEAR: unknown newer script\n')
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP skip PREFLIGHT_REFUSED', errors)
        self.php_selection_mock.assert_not_called()
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)
        self.assert_unchanged(before)
        self.assertTrue(all(not module.BACKUPS.exists() for module in self.engines.values()))
        self.assertFalse(self.php_calls.exists())

    def test_skip_caller_mismatch_blocks_both_groups_before_any_write(self):
        self.engines['skip'].UID += 1
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP skip PREFLIGHT_REFUSED', errors)
        self.assertIn('hosting account UID 2162 / GID 2147', errors)
        self.assert_unchanged(before)
        self.assertTrue(all(not module.BACKUPS.exists() for module in self.engines.values()))
        self.assertFalse(self.php_calls.exists())

    def test_mixed_php_bundle_blocks_js_before_any_write(self):
        path = self.engines['php'].PATHS[0]
        (self.app / path).write_bytes(self.after[path])
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP php PREFLIGHT_REFUSED', errors)
        self.assert_unchanged(before)
        self.assertTrue(all(not module.BACKUPS.exists() for module in self.engines.values()))

    def test_unfinished_php_journal_blocks_js(self):
        self.make_journal('php')
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP php PREFLIGHT_REFUSED', errors)
        self.assert_unchanged(before)
        self.assertFalse(self.engines['skip'].BACKUPS.exists())
        self.assertEqual(len(self.sessions('php')), 1)
        self.assertFalse(self.php_calls.exists())

    def test_unfinished_skip_journal_blocks_php(self):
        self.make_journal('skip', phase='manual_review')
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP skip PREFLIGHT_REFUSED', errors)
        self.assert_unchanged(before)
        self.assertFalse(self.engines['php'].BACKUPS.exists())
        self.assertEqual(len(self.sessions('skip')), 1)
        self.assertFalse(self.php_calls.exists())

    def test_malformed_php_journal_blocks_js_without_raw_record_output(self):
        self.make_journal('php', malformed=True)
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP php PREFLIGHT_REFUSED', errors)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)
        self.assert_unchanged(before)
        self.assertFalse(self.engines['skip'].BACKUPS.exists())

    def test_malformed_skip_journal_blocks_php_without_raw_record_output(self):
        self.make_journal('skip', malformed=True)
        before = self.snapshot()
        code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assertIn('GROUP skip PREFLIGHT_REFUSED', errors)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)
        self.assert_unchanged(before)
        self.assertFalse(self.engines['php'].BACKUPS.exists())
        self.assertFalse(self.php_calls.exists())

    def test_explicit_php_rollback_preserves_js_install_and_journal(self):
        self.assertEqual(self.invoke('apply')[0], 0)
        php, skip = self.sessions('php')[0], self.sessions('skip')[0]
        js_meta = metadata(self.app / 'app.js')
        skip_journal = (skip / 'journal.json').read_bytes()
        code, output, errors = self.invoke('rollback', '--group', 'php', '--session', php.name)
        self.assertEqual((code, errors), (0, ''))
        self.assert_state(self.before, self.after)
        self.assertEqual(js_meta, metadata(self.app / 'app.js'))
        self.assertEqual(skip_journal, (skip / 'journal.json').read_bytes())
        self.assertEqual(self.engines['php'].load(php)['phase'], 'rolled_back')
        self.assertEqual(self.engines['skip'].load(skip)['phase'], 'applied')
        self.assertIn('GROUP php ROLLED_BACK', output)
        self.assertNotIn('ROLLBACK_COMMAND', output)

    def test_explicit_skip_rollback_preserves_php_install_and_journal(self):
        self.assertEqual(self.invoke('apply')[0], 0)
        php, skip = self.sessions('php')[0], self.sessions('skip')[0]
        php_metadata = {path: metadata(self.app / path) for path in self.engines['php'].PATHS}
        php_journal = (php / 'journal.json').read_bytes()
        code, output, errors = self.invoke('rollback', '--group', 'skip', '--session', skip.name)
        self.assertEqual((code, errors), (0, ''))
        self.assert_state(self.after, self.before)
        self.assertEqual(php_metadata, {path: metadata(self.app / path) for path in php_metadata})
        self.assertEqual(php_journal, (php / 'journal.json').read_bytes())
        self.assertEqual(self.engines['php'].load(php)['phase'], 'applied')
        self.assertEqual(self.engines['skip'].load(skip)['phase'], 'rolled_back')
        self.assertIn('GROUP skip ROLLED_BACK', output)

    def test_wrong_group_cannot_rollback_other_private_session(self):
        self.assertEqual(self.invoke('apply')[0], 0)
        before = self.snapshot()
        name = self.sessions('php')[0].name
        code, output, errors = self.invoke('rollback', '--group', 'skip', '--session', name)
        self.assertEqual(code, 1)
        self.assert_unchanged(before)
        self.assertIn('Unexpected failure; refused safely', errors)

    def test_second_group_lint_failure_keeps_php_success_and_reports_journals(self):
        with mock.patch.object(self.engines['skip'], 'lint', side_effect=RuntimeError('RAW_RECORD_MUST_NOT_APPEAR')):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.after, self.before)
        php, skip = self.sessions('php')[0], self.sessions('skip')[0]
        self.assertEqual(self.engines['php'].load(php)['phase'], 'applied')
        self.assertEqual(self.engines['skip'].load(skip)['phase'], 'rolled_back')
        self.assertIn('GROUP php APPLIED', output)
        self.assertIn('GROUP skip APPLY_FAILED', errors)
        self.assertIn('JOURNAL_PHASE skip rolled_back', output)
        self.assertIn('ROLLBACK_COMMAND python3 installer.py rollback --group php --session ' + php.name, output)
        self.assertNotIn('rollback --group skip', output)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)

    def test_first_group_lint_failure_prevents_skip_application(self):
        with mock.patch.object(self.engines['php'], 'lint', side_effect=RuntimeError('RAW_RECORD_MUST_NOT_APPEAR')):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.before, self.before)
        php = self.sessions('php')[0]
        self.assertEqual(self.engines['php'].load(php)['phase'], 'rolled_back')
        self.assertIn('GROUP php APPLY_FAILED', errors)
        self.assertIn('JOURNAL_PHASE php rolled_back', output)
        self.assertFalse(self.engines['skip'].BACKUPS.exists())
        self.assertNotIn('GROUP skip APPLIED', output)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)

    def test_second_group_uncertain_failure_keeps_php_success_and_reports_manual_review(self):
        with mock.patch.object(self.engines['skip'], 'move_code', side_effect=OSError('RAW_RECORD_MUST_NOT_APPEAR')):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.after, self.before)
        php, skip = self.sessions('php')[0], self.sessions('skip')[0]
        self.assertEqual(self.engines['php'].load(php)['phase'], 'applied')
        value = self.engines['skip'].load(skip)
        self.assertEqual(value['phase'], 'manual_review')
        self.assertEqual(value['uncertain'], ['app.js'])
        self.assertEqual(value['intent'], 'app.js')
        self.assertIn('JOURNAL_PHASE skip manual_review', output)
        self.assertNotIn('rollback --group skip', output)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)

    def test_unknown_second_engine_error_is_sanitized_and_keeps_first_success(self):
        with mock.patch.object(self.engines['skip'], 'apply', side_effect=ValueError('RAW_RECORD_MUST_NOT_APPEAR')):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.after, self.before)
        self.assertIn('GROUP skip APPLY_FAILED Unexpected failure; refused safely', errors)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)
        self.assertEqual(self.engines['php'].load(self.sessions('php')[0])['phase'], 'applied')
        self.assertFalse(self.engines['skip'].BACKUPS.exists())

    def test_second_group_private_listing_failure_is_contextual_and_keeps_php_success(self):
        original = self.wrapper.session_names
        def refuse_skip(module):
            if module is self.engines['skip']:
                raise OSError('RAW_RECORD_MUST_NOT_APPEAR')
            return original(module)
        with mock.patch.object(self.wrapper, 'session_names', side_effect=refuse_skip):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.after, self.before)
        self.assertIn('GROUP skip APPLY_FAILED Unexpected failure; refused safely', errors)
        self.assertIn('SESSION_STATUS skip UNVERIFIED', output)
        self.assertEqual(self.engines['php'].load(self.sessions('php')[0])['phase'], 'applied')
        self.assertFalse(self.engines['skip'].BACKUPS.exists())
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)

    def test_second_group_late_error_reports_applied_journal_and_rollback(self):
        original = self.engines['skip'].apply
        def fail_after_success():
            original()
            raise RuntimeError('RAW_RECORD_MUST_NOT_APPEAR')
        with mock.patch.object(self.engines['skip'], 'apply', side_effect=fail_after_success):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.after, self.after)
        skip = self.sessions('skip')[0]
        self.assertEqual(self.engines['skip'].load(skip)['phase'], 'applied')
        self.assertIn('GROUP skip APPLY_FAILED', errors)
        self.assertIn('JOURNAL_PHASE skip applied', output)
        self.assertIn('ROLLBACK_COMMAND python3 installer.py rollback --group skip --session ' + skip.name, output)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)

    def test_failed_diagnostic_journal_load_is_sanitized_without_rollback_command(self):
        original = self.engines['skip'].apply
        def fail_after_success():
            original()
            raise RuntimeError('RAW_RECORD_MUST_NOT_APPEAR')
        with mock.patch.object(self.engines['skip'], 'apply', side_effect=fail_after_success), \
                mock.patch.object(self.engines['skip'], 'load', side_effect=ValueError('RAW_RECORD_MUST_NOT_APPEAR')):
            code, output, errors = self.invoke('apply')
        self.assertEqual(code, 1)
        self.assert_state(self.after, self.after)
        self.assertIn('JOURNAL_PHASE skip unverified', output)
        self.assertNotIn('rollback --group skip', output)
        self.assertNotIn('RAW_RECORD_MUST_NOT_APPEAR', output + errors)

    def test_cli_accepts_group_session_only_together_for_rollback(self):
        before = self.snapshot()
        for args in (('check', '--group', 'php'), ('apply', '--session', 'repair-bogus'),
                     ('rollback',), ('rollback', '--group', 'php'),
                     ('rollback', '--session', 'repair-bogus')):
            code, output, errors = self.invoke(*args)
            self.assertEqual(code, 1, args)
            self.assertIn('Rollback requires both', errors)
        self.assert_unchanged(before)
        self.assertTrue(all(not module.BACKUPS.exists() for module in self.engines.values()))

    def test_rollback_rejects_nonexact_session_names(self):
        before = self.snapshot()
        for name in ('../outside', '/tmp/forged', 'repair-bogus', 'repair-20261014T000000Z-' + 'f' * 31):
            code, output, errors = self.invoke('rollback', '--group', 'php', '--session', name)
            self.assertEqual(code, 1)
            self.assertIn('exact private repair session name', errors)
        self.assert_unchanged(before)

    def test_frozen_load_is_nonmain_and_reads_no_production(self):
        with mock.patch('builtins.open', side_effect=AssertionError('Host read forbidden')), \
                mock.patch.object(os, 'open', side_effect=AssertionError('Host read forbidden')), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('Host read forbidden')):
            modules = self.wrapper.load_engines()
        for group in self.wrapper.GROUPS:
            self.assertNotEqual(modules[group].__name__, '__main__')
            self.assertEqual(modules[group].APP, Path('/home/bobsome1/public_html/kcmc-connect'))
            self.assertEqual((modules[group].UID, modules[group].GID), (2162, 2147))

    def test_corrupt_either_source_is_refused_before_any_exec_or_host_read(self):
        for group in self.wrapper.GROUPS:
            bad = dict(self.wrapper.EMBEDDED)
            source, expected = bad[group]
            bad[group] = (source + '\n# corrupt embedded source\n', expected)
            with mock.patch.object(self.wrapper, 'EMBEDDED', bad), \
                    mock.patch('builtins.exec', side_effect=AssertionError('Definitions executed too early')), \
                    mock.patch.object(os, 'open', side_effect=AssertionError('Host read forbidden')):
                with self.assertRaisesRegex(self.wrapper.Refusal, 'checksum mismatch'):
                    self.wrapper.load_engines()

    def test_environment_cannot_override_frozen_roots_ids_or_php(self):
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/forged', 'KCMC_UID': '0',
                                        'KCMC_GID': '0', 'KCMC_BACKUPS': '/tmp/forged-backups',
                                        'PHP': '/tmp/forged-php'}):
            modules = self.wrapper.load_engines()
        self.assertEqual(modules['php'].APP, Path('/home/bobsome1/public_html/kcmc-connect'))
        self.assertEqual(modules['skip'].APP, modules['php'].APP)
        self.assertEqual(modules['php'].BACKUPS, Path('/home/bobsome1/kcmc-minimal-repair-backups'))
        self.assertEqual(modules['skip'].BACKUPS, Path('/home/bobsome1/kcmc-skip-repair-backups'))
        self.assertEqual(modules['php'].PHP, '/opt/cpanel/ea-php82/root/usr/bin/php')
        self.assertTrue(all((module.UID, module.GID) == (2162, 2147) for module in modules.values()))


class PHPSelectionTests(unittest.TestCase):
    def setUp(self):
        self.w=runner()
    def test_missing_cpanel_runtime_falls_back_to_cloudlinux_cli(self):
        calls=[]
        def command(argv,**kwargs):
            calls.append(argv)
            self.assertEqual(argv[1:],['-n','-v'])
            if argv[0]=='/opt/cpanel/ea-php82/root/usr/bin/php':raise FileNotFoundError(2,'Unavailable')
            return b'PHP 8.2.34 (cli) (built: test)\n'
        with mock.patch.object(subprocess,'check_output',side_effect=command),mock.patch.object(self.w.shutil,'which',return_value=None):
            self.assertEqual(self.w.choose_php82_cli(),('/opt/alt/php82/usr/bin/php','8.2.34'))
        self.assertEqual(len(calls),2)
    def test_unavailable_fixed_paths_fall_back_to_hosting_path_command(self):
        def command(argv,**kwargs):
            if argv[0]=='/usr/local/bin/php':return b'PHP 8.2.27 (cli)\n'
            raise FileNotFoundError(2,'Unavailable')
        with mock.patch.object(subprocess,'check_output',side_effect=command),mock.patch.object(self.w.shutil,'which',return_value='/usr/local/bin/php'):
            self.assertEqual(self.w.choose_php82_cli(),('/usr/local/bin/php','8.2.27'))
    def test_wrong_versions_and_non_cli_banners_are_rejected(self):
        banners=[b'PHP 8.1.34 (cli)\n',b'PHP 8.3.1 (cli)\n',b'PHP 8.2.34 (cgi-fcgi)\n',b'PHP 8.2.34 (fpm-fcgi)\n',b'Warning first\nPHP 8.2.34 (cli)\n']
        for banner in banners:
            with self.subTest(banner=banner),mock.patch.object(subprocess,'check_output',return_value=banner),mock.patch.object(self.w.shutil,'which',return_value=None):
                with self.assertRaisesRegex(self.w.Refusal,'No compatible PHP 8.2 CLI'):
                    self.w.choose_php82_cli()
    def test_nonzero_exit_and_timeout_are_not_accepted_as_valid_cli(self):
        failures=[subprocess.CalledProcessError(1,['php'],output=b'PHP 8.2.34 (cli)\n'),subprocess.TimeoutExpired(['php'],8),PermissionError(13,'Unavailable')]
        for error in failures:
            with self.subTest(error=type(error).__name__),mock.patch.object(subprocess,'check_output',side_effect=error),mock.patch.object(self.w.shutil,'which',return_value=None):
                with self.assertRaises(self.w.Refusal):self.w.choose_php82_cli()
    def test_candidates_are_absolute_and_duplicates_removed(self):
        with mock.patch.object(self.w.shutil,'which',return_value='/opt/alt/php82/usr/bin/php'):
            paths=self.w.php82_candidates()
        self.assertEqual(len(paths),len(set(paths)));self.assertTrue(all(os.path.isabs(path) for path in paths))
        self.assertEqual(paths[0],'/opt/cpanel/ea-php82/root/usr/bin/php')
    def test_no_user_php_argument_override(self):
        with mock.patch.object(sys,'argv',['installer.py','check','--php','/tmp/arbitrary']),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:self.w.main()
        self.assertEqual(error.exception.code,2)

class ProvenanceTests(unittest.TestCase):
    def test_embedded_engines_are_exact_frozen_sibling_sources(self):
        w = runner()
        for group, sibling in (('php', 'kcmc-minimal-repair-oct14'),
                               ('skip', 'kcmc-skip-repair-oct14')):
            source, expected = w.EMBEDDED[group]
            raw = (HERE.parent / sibling / 'installer.py').read_bytes()
            self.assertEqual(source.encode('utf-8'), raw)
            self.assertEqual(expected, sha(raw))
        proof = json.loads((HERE / 'provenance.json').read_text())
        self.assertEqual(proof['installer_sha256'], sha((HERE / 'installer.py').read_bytes()))
        helper = (HERE / 'installer.py').read_text()
        helper = helper[helper.index('def php82_candidates():'):helper.index('def preflight(')].rstrip()
        self.assertEqual(proof['php_discovery_sha256'], sha(helper.encode('utf-8')))
        self.assertEqual(proof['scope'], ['lib/timeclock.php', 'member/activate.php',
                                         'member/reset-password.php', 'app.js'])

if __name__ == '__main__':
    unittest.main()
