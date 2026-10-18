#!/usr/bin/env python3
"""Isolated filesystem plus executable fake crontab; no live schedule or mail."""
from __future__ import print_function
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SPEC = importlib.util.spec_from_file_location('payroll_schedule_fixture', str(HERE / 'schedule.py'))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

FAKE_CRON = r'''#!PYTHON
import json, os, pathlib, pwd, sys
base=pathlib.Path(__file__).parent
state=base/'cron-state.json'
value=json.loads(state.read_text())
with (base/'cron-calls.jsonl').open('a') as f:f.write(json.dumps(sys.argv[1:])+"\n")
if sys.argv[1:]==['-l']:
    if value.get('read_error'):
        sys.stderr.write('unexpected read failure\n');sys.exit(2)
    if value.get('wrong_absent_user'):
        sys.stderr.write('no crontab for a-different-account\n');sys.exit(1)
    if value['exists']:
        if value.get('read_warning'):sys.stderr.write('unexpected warning\n')
        sys.stdout.buffer.write(bytes.fromhex(value['raw']));sys.exit(0)
    sys.stderr.write('no crontab for '+pwd.getpwuid(os.getuid()).pw_name+'\n');sys.exit(1)
if value.get('install_error'):
    sys.stderr.write('fake install failed\n');sys.exit(2)
if sys.argv[1:]==['-r']:
    value['exists']=False;value['raw']=''
else:
    value['exists']=True;value['raw']=pathlib.Path(sys.argv[1]).read_bytes().hex()
    if value.get('edit_after_install'):
        value['raw']=(b'7 * * * * later-editor-job\n').hex()
    if value.get('fail_readback'):
        value['read_error']=True
state.write_text(json.dumps(value))
'''


def identity(private):
    info = private.stat()
    parts = ['kcmc-payroll-store-v1', str(private / 'timeclock.json'), str(info.st_dev), str(info.st_ino),
             str(info.st_uid), str(info.st_gid), str(stat.S_IMODE(info.st_mode))]
    return {'version': 1, 'fingerprint': hashlib.sha256('\0'.join(parts).encode()).hexdigest(),
            'private_directory': str(private), 'timeclock_path': str(private / 'timeclock.json'),
            'store_exists': True, 'directory_mode': format(stat.S_IMODE(info.st_mode), '04o')}


class Fixture(object):
    def __init__(self, real_php=None):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-payroll-schedule-')
        self.root = Path(self.temp.name)
        self.app = self.root / 'live-app'; self.app.mkdir(mode=0o755)
        self.private = self.root / 'private-store'; self.private.mkdir(mode=0o750); self.private.chmod(0o750)
        self.backups = self.root / 'schedule-backups'
        for name, expected in M.GUARDS.items():
            path = self.app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = (ROOT / 'KCMC-Connect-Phase6-Recreated' / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == expected, name
            path.write_bytes(raw); path.chmod(0o644)
        self.config_sentinel = self.root / 'config-was-executed'
        (self.app / 'config.php').write_text("<?php file_put_contents(" + json.dumps(str(self.config_sentinel)) + ", 'FORBIDDEN'); throw new RuntimeException('config must not execute');")
        (self.app / 'config.php').chmod(0o644)
        self.write('timeclock.json', {'version': 1, 'entries': [], 'periods': []})
        self.write('users.json', {'version': 1, 'users': [{'id': 'selected-recipient', 'display_name': 'PRIVATE NOT OUTPUT',
                     'email': 'private-recipient@example.test', 'role': 'member', 'active': True}]})
        self.write('payroll-settings.json', {'version': 1, 'channel': 'queue', 'reviewer_id': 'selected-recipient'})
        self.cron = self.root / 'fake-crontab'
        self.cron.write_text(FAKE_CRON.replace('PYTHON', sys.executable, 1)); self.cron.chmod(0o700)
        self.set_cron(True, b'5 * * * * unrelated-original-job\n')
        self.php = Path(real_php).resolve() if real_php else Path(sys.executable).resolve()
        self.original_run = M.run
        self.patches = [mock.patch.object(M, 'APP', self.app), mock.patch.object(M, 'BACKUPS', self.backups),
                        mock.patch.object(M, 'UID', os.getuid()), mock.patch.object(M, 'GID', os.getgid()),
                        mock.patch.object(M, 'PHP', self.php), mock.patch.object(M, 'crontab_executable', lambda: str(self.cron))]
        if not real_php:
            self.patches.append(mock.patch.object(M, 'run', self.fake_php))
            self.patches.append(mock.patch.object(M, 'verify_php_metadata', lambda: None))
        for patch in self.patches: patch.start()
        self.expected = identity(self.private)['fingerprint']

    def fake_php(self, arguments, env=None):
        if arguments[0] != str(self.php):
            return self.original_run(arguments, env=env)
        if arguments == [str(self.php), '-n', '-v']:
            return subprocess.CompletedProcess(arguments, 0, b'PHP 8.2.34 (cli) (synthetic)\n', b'')
        assert arguments == [str(self.php), '-n', str(self.app / 'admin/timeclock-period-close.php'), '--diagnose'], arguments
        assert env['KCMC_PRIVATE_DATA_DIR'] == str(self.private)
        return subprocess.CompletedProcess(arguments, 0, json.dumps(identity(self.private)).encode(), b'')

    def close(self):
        for patch in reversed(self.patches): patch.stop()
        self.temp.cleanup()

    def write(self, name, data):
        path = self.private / name
        path.write_text(json.dumps(data)); path.chmod(0o640)

    def set_cron(self, exists, raw=b'', **extra):
        value = {'exists': exists, 'raw': raw.hex()}; value.update(extra)
        (self.root / 'cron-state.json').write_text(json.dumps(value))

    def cron_state(self):
        value = json.loads((self.root / 'cron-state.json').read_text())
        return value['exists'], bytes.fromhex(value['raw'])

    def update_cron(self, **extra):
        path = self.root / 'cron-state.json'; value = json.loads(path.read_text()); value.update(extra); path.write_text(json.dumps(value))

    def plan(self):
        return M.inspect(self.private, self.expected)

    def apply(self, plan=None):
        plan = plan or self.plan()
        return M.apply(self.private, self.expected, 'selected-recipient', plan['status']['plan_sha256'])

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode), path.stat().st_ino)
                for base in (self.app, self.private) for path in base.rglob('*') if path.is_file()}

    def sessions(self):
        return sorted(self.backups.glob('schedule-*')) if self.backups.exists() else []

    def journal(self):
        return json.loads((self.sessions()[-1] / 'journal.json').read_text())

    def installs(self):
        path = self.root / 'cron-calls.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [row for row in rows if row != ['-l']]


class ScheduleTests(unittest.TestCase):
    def setUp(self): self.f = Fixture()
    def tearDown(self): self.f.close()

    def test_runtime_guards_match_reviewed_source(self):
        self.assertEqual(len(M.GUARDS), 5)
        for name, wanted in M.GUARDS.items():
            self.assertEqual(hashlib.sha256((ROOT / 'KCMC-Connect-Phase6-Recreated' / name).read_bytes()).hexdigest(), wanted)

    def test_plan_and_status_leave_app_private_records_and_schedule_unchanged(self):
        before = self.f.snapshot(); cron = self.f.cron_state()
        for _ in range(2):
            result = self.f.plan()['status']
            self.assertTrue(result['can_apply']); self.assertTrue(result['recipient_selected'])
            self.assertEqual(result['sender_readiness'], 'not_verified_preserved_config_not_executed')
            self.assertFalse(result['schedule_execution_verified'])
            raw = json.dumps(result)
            for private in ('PRIVATE NOT OUTPUT', 'private-recipient@example.test', 'net_minutes', 'entries'):
                self.assertNotIn(private, raw)
        self.assertEqual(before, self.f.snapshot()); self.assertEqual(cron, self.f.cron_state())
        self.assertFalse(self.f.backups.exists()); self.assertEqual(self.f.installs(), [])
        self.assertFalse(self.f.config_sentinel.exists())

    def test_queue_apply_and_exact_rollback_keep_all_unrelated_bytes(self):
        original = b'MAILTO="owner@example.test"\r\n# untouched\n5 * * * * old-job\n'
        self.f.set_cron(True, original); before = self.f.snapshot(); plan = self.f.plan()
        installed = self.f.apply(plan); session = self.f.sessions()[0]
        self.assertEqual(installed['result'], 'INSTALLED_NOT_RUN'); self.assertFalse(installed['schedule_execution_verified'])
        self.assertEqual(self.f.cron_state(), (True, plan['planned']))
        self.assertTrue(plan['planned'].startswith(original))
        self.assertEqual((session / 'before.crontab').read_bytes(), original)
        self.assertEqual(stat.S_IMODE(self.f.backups.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(session.stat().st_mode), 0o700)
        for path in session.iterdir(): self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        result = M.rollback(session.name)
        self.assertEqual(result['result'], 'ROLLED_BACK'); self.assertEqual(self.f.cron_state(), (True, original))
        self.assertEqual(before, self.f.snapshot()); self.assertFalse(self.f.config_sentinel.exists())

    def test_absent_and_existing_empty_crontabs_restore_distinct_states(self):
        for existed in (False, True):
            with self.subTest(existed=existed):
                self.f.set_cron(existed, b''); plan = self.f.plan()
                self.assertEqual(plan['plan']['crontab_existed'], existed)
                installed = self.f.apply(plan); M.rollback(installed['session'])
                self.assertEqual(self.f.cron_state(), (existed, b''))
                self.assertEqual(self.f.installs()[-1] == ['-r'], not existed)

    def test_same_block_is_no_op_without_extra_backup_or_install(self):
        self.f.apply(); sessions = self.f.sessions(); installs = self.f.installs()
        result = self.f.apply()
        self.assertEqual(result['result'], 'ALREADY_INSTALLED')
        self.assertEqual(self.f.sessions(), sessions); self.assertEqual(self.f.installs(), installs)

    def test_replacing_one_existing_block_preserves_prefix_and_suffix(self):
        original = b'ENV=value\n' + M.BEGIN + b'\n*/15 * * * * old-reviewed-command\n' + M.END + b'\n7 * * * * suffix\n'
        self.f.set_cron(True, original); plan = self.f.plan()
        self.assertEqual(plan['status']['managed_block'], 'different')
        self.assertTrue(plan['planned'].startswith(b'ENV=value\n' + M.BEGIN))
        self.assertTrue(plan['planned'].endswith(M.END + b'\n7 * * * * suffix\n'))

    def test_non_newline_final_job_is_preserved_before_appended_block(self):
        original = b'9 * * * * final-job'
        self.f.set_cron(True, original); plan = self.f.plan()
        self.assertTrue(plan['planned'].startswith(original + b'\n' + M.BEGIN))

    def test_malformed_duplicate_or_unknown_managed_blocks_refuse(self):
        block = M.BEGIN + b'\njob\n' + M.END + b'\n'
        for raw in (M.BEGIN + b'\njob\n', M.END + b'\n', block + block,
                    b' ' + block, block.replace(b'v1', b'v2'), M.END + b'\n' + M.BEGIN + b'\n'):
            self.f.set_cron(True, raw)
            with self.assertRaises(M.Refusal): self.f.plan()
        self.assertEqual(self.f.installs(), []); self.assertFalse(self.f.backups.exists())

    def test_unknown_read_errors_never_become_absent_baselines(self):
        for extra in ({'read_error': True}, {'wrong_absent_user': True}, {'read_warning': True}):
            self.f.set_cron(True, b'keep\n', **extra)
            with self.assertRaises(M.Refusal): self.f.plan()
        self.assertFalse(self.f.backups.exists()); self.assertEqual(self.f.installs(), [])

    def test_off_missing_inactive_and_duplicate_recipient_refuse_apply(self):
        for settings, users in [({'channel': 'off', 'reviewer_id': ''}, []),
                               ({'channel': 'queue', 'reviewer_id': 'missing'}, []),
                               ({'channel': 'queue', 'reviewer_id': 'selected-recipient'}, [{'id': 'selected-recipient', 'active': False}])]:
            self.f.write('payroll-settings.json', settings); self.f.write('users.json', {'users': users})
            self.assertFalse(self.f.plan()['status']['can_apply'])
            with self.assertRaises(M.Refusal): self.f.apply()
        self.f.write('users.json', {'users': [{'id': 'selected-recipient', 'active': True}] * 2})
        with self.assertRaises(M.Refusal): self.f.plan()
        for states in ((False, True), (True, False)):
            self.f.write('users.json', {'users': [{'id': 'selected-recipient', 'active': active} for active in states]})
            with self.assertRaises(M.Refusal): self.f.plan()
        self.assertEqual(self.f.installs(), []); self.assertFalse(self.f.backups.exists())

    def test_email_inspection_is_supported_but_unverified_email_apply_is_blocked(self):
        self.f.write('payroll-settings.json', {'channel': 'email', 'reviewer_id': 'selected-recipient',
                     'email_activation_date': '2026-10-18', 'review_url': 'https://bobsome1.com/kcmc-connect/admin/timecards.php'})
        with mock.patch.dict(os.environ, {'KCMC_PAYROLL_FROM': 'looks-valid@example.test'}):
            plan = self.f.plan()
            self.assertFalse(plan['status']['can_apply'])
            self.assertEqual(len(plan['status']['needs']), 1)
            with self.assertRaises(M.Refusal): self.f.apply(plan)
        self.assertFalse(self.f.config_sentinel.exists()); self.assertEqual(self.f.installs(), [])

    def test_wrong_recipient_plan_or_web_store_refuse_before_backup(self):
        plan = self.f.plan()
        for recipient, digest in [('another-account', plan['status']['plan_sha256']), ('selected-recipient', '0' * 64)]:
            with self.assertRaises(M.Refusal): M.apply(self.f.private, self.f.expected, recipient, digest)
        with self.assertRaises(M.Refusal): M.inspect(self.f.private, '0' * 64)
        self.assertFalse(self.f.backups.exists()); self.assertEqual(self.f.installs(), [])

    def test_settings_accounts_config_and_crontab_changes_invalidate_plan(self):
        plan = self.f.plan()
        for file in ('payroll-settings.json', 'users.json'):
            path = self.f.private / file; original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.assertRaises(M.Refusal): self.f.apply(plan)
            path.write_bytes(original)
        path = self.f.app / 'config.php'; original = path.read_bytes(); path.write_bytes(original + b' ')
        with self.assertRaises(M.Refusal): self.f.apply(plan)
        path.write_bytes(original)
        self.f.set_cron(True, b'new-editor-job\n')
        with self.assertRaises(M.Refusal): self.f.apply(plan)
        self.assertEqual(self.f.installs(), [])

    def test_staging_time_concurrent_edit_is_preserved_and_journal_blocks_retries(self):
        plan = self.f.plan(); save = M.save_journal
        def staged(session, value):
            save(session, value)
            if value['phase'] == 'prepared': self.f.set_cron(True, b'later-editor-job\n')
        with mock.patch.object(M, 'save_journal', staged):
            with self.assertRaises(M.Refusal): self.f.apply(plan)
        self.assertEqual(self.f.cron_state(), (True, b'later-editor-job\n'))
        self.assertEqual(self.f.journal()['phase'], 'conflict_before_install'); self.assertEqual(self.f.installs(), [])
        with self.assertRaises(M.Refusal): self.f.apply()

    def test_concurrent_settings_edit_after_backup_blocks_install(self):
        plan = self.f.plan(); save = M.save_journal
        def staged(session, value):
            save(session, value)
            if value['phase'] == 'prepared': self.f.write('payroll-settings.json', {'channel': 'off', 'reviewer_id': ''})
        with mock.patch.object(M, 'save_journal', staged):
            with self.assertRaises(M.Refusal): self.f.apply(plan)
        self.assertEqual(self.f.journal()['phase'], 'conflict_before_install')
        self.assertEqual(self.f.installs(), [])

    def test_concurrent_edit_after_installing_journal_is_preserved(self):
        plan = self.f.plan(); save = M.save_journal
        def staged(session, value):
            save(session, value)
            if value['phase'] == 'installing': self.f.set_cron(True, b'editor-after-installing-journal\n')
        with mock.patch.object(M, 'save_journal', staged):
            with self.assertRaises(M.Refusal): self.f.apply(plan)
        self.assertEqual(self.f.cron_state(), (True, b'editor-after-installing-journal\n'))
        self.assertEqual(self.f.journal()['phase'], 'conflict_before_install'); self.assertEqual(self.f.installs(), [])

    def test_install_failure_never_restores_or_erases_later_jobs(self):
        self.f.update_cron(install_error=True)
        before = self.f.cron_state()
        with self.assertRaises(M.Refusal): self.f.apply()
        self.assertEqual(self.f.cron_state(), before); self.assertEqual(self.f.journal()['phase'], 'uncertain')
        self.assertEqual(len(self.f.installs()), 1)
        with self.assertRaises(M.Refusal): M.rollback(self.f.sessions()[0].name)

    def test_failed_readback_preserves_uncertain_install_without_second_write(self):
        self.f.update_cron(fail_readback=True)
        plan = self.f.plan()
        with self.assertRaises(M.Refusal): self.f.apply(plan)
        self.assertEqual(self.f.cron_state(), (True, plan['planned']))
        self.assertEqual(self.f.journal()['phase'], 'uncertain'); self.assertEqual(len(self.f.installs()), 1)

    def test_changed_readback_preserves_external_editor_job(self):
        self.f.update_cron(edit_after_install=True)
        with self.assertRaises(M.Refusal): self.f.apply()
        self.assertEqual(self.f.cron_state(), (True, b'7 * * * * later-editor-job\n'))
        self.assertEqual(self.f.journal()['phase'], 'uncertain'); self.assertEqual(len(self.f.installs()), 1)

    def test_later_edit_blocks_rollback_without_writing(self):
        result = self.f.apply(); count = len(self.f.installs()); self.f.set_cron(True, b'another-editor-job\n')
        with self.assertRaises(M.Refusal): M.rollback(result['session'])
        self.assertEqual(self.f.cron_state(), (True, b'another-editor-job\n'))
        self.assertEqual(len(self.f.installs()), count); self.assertEqual(self.f.journal()['phase'], 'applied')

    def test_rollback_readback_conflict_is_preserved_as_uncertain(self):
        result = self.f.apply(); self.f.update_cron(edit_after_install=True)
        with self.assertRaises(M.Refusal): M.rollback(result['session'])
        self.assertEqual(self.f.cron_state(), (True, b'7 * * * * later-editor-job\n'))
        self.assertEqual(self.f.journal()['phase'], 'rollback_uncertain')

    def test_concurrent_edit_after_rollback_journal_is_preserved_before_restore(self):
        result = self.f.apply(); save = M.save_journal
        def staged(session, value):
            save(session, value)
            if value['phase'] == 'rolling_back': self.f.set_cron(True, b'editor-after-rollback-check\n')
        with mock.patch.object(M, 'save_journal', staged):
            with self.assertRaises(M.Refusal): M.rollback(result['session'])
        self.assertEqual(self.f.cron_state(), (True, b'editor-after-rollback-check\n'))
        self.assertEqual(self.f.journal()['phase'], 'rollback_conflict'); self.assertEqual(len(self.f.installs()), 1)

    def test_corrupted_backup_refuses_rollback(self):
        result = self.f.apply(); session = self.f.sessions()[0]
        (session / 'before.crontab').write_bytes(b'corrupt')
        with self.assertRaises(M.Refusal): M.rollback(result['session'])
        self.assertEqual(len(self.f.installs()), 1)

    def test_unsafe_runtime_or_settings_metadata_is_refused(self):
        path = self.f.app / 'lib/payroll.php'; original = path.read_bytes(); path.write_bytes(original + b' ')
        with self.assertRaises(M.Refusal): self.f.plan()
        path.write_bytes(original)
        path = self.f.private / 'payroll-settings.json'; path.chmod(0o666)
        with self.assertRaises(M.Refusal): self.f.plan()
        path.chmod(0o640); os.link(str(path), str(self.f.private / 'hardlink'))
        with self.assertRaises(M.Refusal): self.f.plan()
        (self.f.private / 'hardlink').unlink()
        alias = self.f.root / 'private-alias'; alias.symlink_to(self.f.private)
        with self.assertRaises(M.Refusal): M.inspect(alias, self.f.expected)
        self.assertEqual(self.f.installs(), [])

    def test_wrong_php_and_command_timeout_are_refused(self):
        original = self.f.fake_php
        def wrong_version(arguments, env=None):
            if arguments == [str(self.f.php), '-n', '-v']:
                return subprocess.CompletedProcess(arguments, 0, b'PHP 8.3.1 (cli)\n', b'')
            return original(arguments, env)
        with mock.patch.object(M, 'run', wrong_version):
            with self.assertRaises(M.Refusal): self.f.plan()
        with mock.patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('fake', 20)):
            with self.assertRaises(M.Refusal): self.f.plan()

    def test_store_directory_replacement_during_inspection_refuses(self):
        read = M.read_crontab
        def replace_directory():
            result = read()
            old = self.f.root / 'old-private-store'
            self.f.private.rename(old); shutil.copytree(str(old), str(self.f.private)); self.f.private.chmod(0o750)
            return result
        with mock.patch.object(M, 'read_crontab', replace_directory):
            with self.assertRaises(M.Refusal): self.f.plan()
        self.assertFalse(self.f.backups.exists()); self.assertEqual(self.f.installs(), [])

    def test_private_lock_and_backup_modes_are_enforced(self):
        with M.locked():
            with self.assertRaises(M.Refusal): self.f.apply()
        lock = self.f.backups / 'schedule.lock'; lock.chmod(0o640)
        with self.assertRaises(M.Refusal): self.f.apply()
        lock.chmod(0o600); self.f.backups.chmod(0o750)
        with self.assertRaises(M.Refusal): self.f.apply()

    def test_percent_and_shell_syntax_are_quoted_for_crontab(self):
        strange = Path("/home/owner/private%dir'a$b`c")
        line = M.cron_line(strange, 'a' * 64).decode()
        self.assertIn("KCMC_PRIVATE_DATA_DIR='/home/owner/private\\%dir'\"'\"'a$b`c'", line)
        self.assertIn('*/15 * * * * umask 077 &&', line)
        self.assertNotIn(' --diagnose', line)
        with self.assertRaises(M.Refusal): M.quote('bad\nargument')
        with self.assertRaises(M.Refusal): M.cron_line(Path('/home/owner/private\\%dir'), 'a' * 64)
        with self.assertRaises(M.Refusal): M.inspect(Path('/home/owner/private\\%dir'), 'a' * 64)

    def test_incompatible_inherited_shell_and_managed_environment_lines_refuse(self):
        for shell in (b'/bin/csh', b'"/bin/fish"', b'/unknown-shell'):
            self.f.set_cron(True, b'SHELL=' + shell + b'\n5 * * * * keep-job\n')
            with self.assertRaises(M.Refusal): self.f.plan()
        self.f.set_cron(True, M.BEGIN + b'\nSHELL=/bin/bash\n*/15 * * * * old-command\n' + M.END + b'\n')
        with self.assertRaises(M.Refusal): self.f.plan()
        self.f.set_cron(True, b'SHELL = "/bin/bash"\n5 * * * * keep-job\n')
        self.assertTrue(self.f.plan()['status']['can_apply'])
        self.assertEqual(self.f.installs(), [])

    def test_receipt_status_is_minimal_and_never_claims_inbox_or_scheduled_execution(self):
        self.f.write('payroll-run-status.json', {'finished_at': '2026-10-18T14:00:00+00:00',
                     'store_fingerprint': self.f.expected, 'channel': 'queue', 'mail_accepted': 0,
                     'employee_secret': 'DO NOT OUTPUT'})
        status = self.f.plan()['status']
        self.assertTrue(status['runner_receipt_matches_store']); self.assertEqual(status['runner_finished_at'], '2026-10-18T14:00:00+00:00')
        self.assertFalse(status['schedule_execution_verified']); self.assertNotIn('DO NOT OUTPUT', json.dumps(status))


if __name__ == '__main__': unittest.main()
