#!/usr/bin/env python3
"""Four owner-guard transactions and a preserved read-only bootstrap prerequisite."""
from __future__ import print_function
import ast
import contextlib
import hashlib
import importlib.util
import io
import itertools
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
import derive_installer as derive

HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = None
GIT_ROOT = None
for option, label in [('--runtime-root', 'runtime'), ('--git-root', 'git')]:
    if option in sys.argv:
        i = sys.argv.index(option); value = Path(sys.argv[i + 1]); del sys.argv[i:i + 2]
        if label == 'runtime': RUNTIME_ROOT = value
        else: GIT_ROOT = value


def wrapper():
    spec = importlib.util.spec_from_file_location('isolated_owner_wrapper', str(HERE / 'installer.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


def sha(data): return hashlib.sha256(data).hexdigest()


def identity(path):
    info = path.lstat()
    return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_mode,
            info.st_uid, info.st_gid, info.st_nlink, info.st_size)


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-owner-four-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.app = self.root / 'app'; self.app.mkdir()
        self.w = wrapper(); self.engines = self.w.load_engines(); self.m = self.engines['main93']
        self.m.APP = self.app; self.m.BACKUPS = self.root / 'private'; self.m.UID = os.getuid(); self.m.GID = os.getgid()
        self.real_choose = self.w.choose_php82_cli
        self.choose_patch = mock.patch.object(self.w, 'choose_php82_cli', return_value=('/opt/alt/php82/usr/bin/php', '8.2.34'))
        self.selected = self.choose_patch.start(); self.addCleanup(self.choose_patch.stop)
        self.sentinels = {'config.php': b'<?php // owner setting retained\n', 'data/content.json': b'{"synthetic":"editorial retained"}',
            'data/private/users.json': b'{"synthetic":"accounts retained"}', 'data/private/prayers.json': b'{"synthetic":"prayers retained"}',
            'data/private/timeclock.json': b'{"synthetic":"timecards retained"}', '.git/HEAD': b'ref: refs/heads/main\n',
            'index.php': b'<?php // fish retained\n', 'app.js': b'// prior skip fix retained\n',
            'public-presentation.css': b'/* fish retained */\n', 'sw.js': b'// fish retained\n',
            'lib/session-lifetime.php': b'<?php // session repair retained\n', 'member/login.php': b'<?php // session login retained\n',
            'member/password.php': b'<?php // password change retained\n', 'member/activate.php': b'<?php // activation retained\n',
            'member/reset-password.php': b'<?php // bearer reset handling retained\n'}
        for path, content in self.sentinels.items():
            target = self.app / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content); target.chmod(0o600)
        self.sentinel_ids = {p: identity(self.app / p) for p in self.sentinels}
        self.seed()
        self.bootstrap = self.app / 'lib/bootstrap.php'
        self.bootstrap.write_bytes((HERE / 'evidence/prerequisite/lib/bootstrap.php').read_bytes()); self.bootstrap.chmod(0o644)
        self.bootstrap_identity = identity(self.bootstrap)
        self.old = {p: (self.app / p).read_bytes() for p in derive.PATHS}
    def seed(self, states=None):
        states = states or ['before'] * 4
        for path, kind in zip(derive.PATHS, states):
            target = self.app / path; target.parent.mkdir(parents=True, exist_ok=True)
            before = (HERE / 'evidence/main93' / path).read_bytes()
            target.write_bytes(before if kind == 'before' else self.m.repair(path, before)); target.chmod(0o644)
    def unchanged(self):
        for path, content in self.sentinels.items():
            self.assertEqual((self.app / path).read_bytes(), content, path)
            self.assertEqual(identity(self.app / path), self.sentinel_ids[path], path)
    def cli(self, *args):
        output = io.StringIO()
        with mock.patch.object(self.w, 'load_engines', return_value=self.engines), mock.patch.object(sys, 'argv', ['installer.py'] + list(args)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = self.w.main()
        self.unchanged(); return result, output.getvalue()
    def php(self, command, **kwargs):
        self.assertEqual(command[0], '/opt/alt/php82/usr/bin/php'); self.assertEqual(command[1], '-n')
        if command[2] == '-v': return b'PHP 8.2.34 (cli)\n'
        self.assertEqual(command[2], '-l'); self.assertIn(Path(command[3]).name, ['stage-' + str(i) + '.code' for i in range(4)])
        return b'No syntax errors detected\n'
    def apply(self):
        with mock.patch.object(subprocess, 'check_output', side_effect=self.php) as calls:
            code, text = self.cli('apply')
        self.assertEqual(code, 0, text); return text, calls.call_args_list
    def session(self): return next(self.m.BACKUPS.glob('repair-*'))
    def no_success(self, text):
        for marker in ['CHECK READY', 'CHECK ALREADY_REPAIRED', 'REPAIRED ', 'ALREADY_REPAIRED;', 'ROLLED_BACK ']:
            self.assertNotIn(marker, text)
    def drift_bootstrap(self, new_bytes=None):
        replacement = self.root / 'later-bootstrap.php'
        replacement.write_bytes(new_bytes if new_bytes is not None else self.bootstrap.read_bytes()); replacement.chmod(0o644)
        os.replace(str(replacement), str(self.bootstrap))
    def test_check_is_read_only_and_prerequisite_is_not_a_write_target(self):
        before = {p: identity(self.app / p) for p in derive.PATHS}
        code, text = self.cli(); self.assertEqual(code, 0, text); self.assertIn('CHECK READY', text)
        self.assertNotIn('lib/bootstrap.php', self.m.PATHS); self.assertEqual(len(self.m.PATHS), 4)
        self.assertEqual(identity(self.bootstrap), self.bootstrap_identity); self.assertFalse(self.m.BACKUPS.exists())
        for p, prior in before.items(): self.assertEqual(identity(self.app / p), prior)
    def test_apply_all_four_noop_modes_private_backups_and_exact_rollback(self):
        (self.app / 'admin/users.php').chmod(0o664)
        text, calls = self.apply(); self.assertIn('REPAIRED ', text); self.assertEqual(len(calls), 5)
        session = self.session(); self.assertEqual(stat.S_IMODE(session.stat().st_mode), 0o700)
        for i, path in enumerate(derive.PATHS):
            self.assertEqual(sha((self.app / path).read_bytes()), self.m.FILES[path]['after_sha256'])
            self.assertEqual((session / ('original-' + str(i) + '.code')).read_bytes(), self.old[path])
            self.assertEqual(stat.S_IMODE((session / ('original-' + str(i) + '.code')).stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.app / 'admin/users.php').stat().st_mode), 0o664)
        ids = {p: identity(self.app / p) for p in derive.PATHS}; journal_id = identity(session / 'journal.json')
        self.selected.side_effect = AssertionError('No-op must not discover PHP')
        text, calls = self.apply(); self.assertIn('ALREADY_REPAIRED;', text); self.assertEqual(calls, [])
        code, text = self.cli('check'); self.assertEqual(code, 0, text); self.assertIn('CHECK ALREADY_REPAIRED', text)
        self.assertEqual(identity(session / 'journal.json'), journal_id)
        for p, prior in ids.items(): self.assertEqual(identity(self.app / p), prior)
        code, text = self.cli('rollback', '--variant', 'main93', '--session', session.name); self.assertEqual(code, 0, text)
        for p in derive.PATHS: self.assertEqual((self.app / p).read_bytes(), self.old[p])
        self.assertEqual(identity(self.bootstrap), self.bootstrap_identity)
    def test_only_two_of_sixteen_complete_fourfile_tuples_are_accepted(self):
        accepted = refused = 0
        for states in itertools.product(('before', 'after'), repeat=4):
            self.seed(states); code, text = self.cli('check')
            if len(set(states)) == 1:
                self.assertEqual(code, 0, text); accepted += 1
            else:
                self.assertEqual(code, 1, text); self.assertIn('Unknown or mixed', text); refused += 1
            self.assertFalse(self.m.BACKUPS.exists())
        self.assertEqual((accepted, refused), (2, 14))
    def test_unknown_code_diagnose_is_hashes_only_and_readonly(self):
        target = self.app / derive.PATHS[0]; target.write_bytes(b'<?php // unknown code not disclosed\n')
        self.selected.side_effect = AssertionError('Unknown code must not discover PHP')
        code, text = self.cli('apply'); self.assertEqual(code, 1); self.assertIn('Use diagnose', text)
        ids = {p: identity(self.app / p) for p in derive.PATHS + ('lib/bootstrap.php',)}
        code, text = self.cli('diagnose'); self.assertEqual(code, 0, text); self.assertEqual(text.count('CODE '), 5)
        self.assertNotIn('unknown code not disclosed', text); self.assertNotIn('owner setting retained', text)
        for p, prior in ids.items(): self.assertEqual(identity(self.app / p), prior)
        self.assertFalse(self.m.BACKUPS.exists())
    def test_unknown_or_linked_bootstrap_refused_before_any_backup(self):
        original = self.bootstrap.read_bytes()
        for variant in ['unknown', 'symlink', 'hardlink', 'mode', 'missing']:
            with self.subTest(variant=variant):
                if variant == 'unknown': self.bootstrap.write_bytes(b'<?php // newer bootstrap retained\n')
                elif variant == 'symlink': self.bootstrap.unlink(); self.bootstrap.symlink_to(self.app / 'config.php')
                elif variant == 'hardlink': os.link(str(self.bootstrap), str(self.root / 'bootstrap-link'))
                elif variant == 'mode': self.bootstrap.chmod(0o666)
                else: self.bootstrap.unlink()
                code, text = self.cli('apply'); self.assertEqual(code, 1); self.no_success(text)
                self.assertFalse(self.m.BACKUPS.exists())
                for p in derive.PATHS: self.assertEqual((self.app / p).read_bytes(), self.old[p])
                if self.bootstrap.exists() or self.bootstrap.is_symlink(): self.bootstrap.unlink()
                if (self.root / 'bootstrap-link').exists(): (self.root / 'bootstrap-link').unlink()
                self.bootstrap.write_bytes(original); self.bootstrap.chmod(0o644)
    def test_unknown_bootstrap_can_be_diagnosed_without_payload_or_php(self):
        self.bootstrap.write_bytes(b'<?php // private diagnostic marker never disclosed\n')
        self.selected.side_effect = AssertionError('No PHP diagnostic probe')
        code, text = self.cli('diagnose'); self.assertEqual(code, 0, text)
        self.assertIn(sha(self.bootstrap.read_bytes()), text); self.assertNotIn('private diagnostic marker', text)
        self.assertFalse(self.m.BACKUPS.exists())
    def test_check_ready_refuses_same_bytes_new_bootstrap_inode_during_php_probe(self):
        def choose(): self.drift_bootstrap(); return ('/opt/alt/php82/usr/bin/php', '8.2.34')
        self.selected.side_effect = choose
        code, text = self.cli('check'); self.assertEqual(code, 1); self.no_success(text)
        self.assertFalse(self.m.BACKUPS.exists())
    def test_check_after_refuses_prerequisite_change_during_inspection(self):
        self.seed(['after'] * 4); select = self.w.select
        def drift(engines): result = select(engines); self.drift_bootstrap(); return result
        with mock.patch.object(self.w, 'select', side_effect=drift): code, text = self.cli('check')
        self.assertEqual(code, 1); self.no_success(text); self.assertFalse(self.m.BACKUPS.exists())
    def test_noop_apply_final_boundary_refuses_prerequisite_change(self):
        self.seed(['after'] * 4); apply = self.m.apply
        def drift(): result = apply(); self.drift_bootstrap(); return result
        with mock.patch.object(self.m, 'apply', side_effect=drift): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text); self.assertFalse(self.m.BACKUPS.exists())
    def test_lint_failure_fourth_stage_preserves_live_code_and_bootstrap(self):
        def bad(command, **kwargs):
            if command[-1].endswith('stage-3.code'): raise subprocess.CalledProcessError(255, command)
            return self.php(command, **kwargs)
        with mock.patch.object(subprocess, 'check_output', side_effect=bad): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.assertIn('no live replacement', text); self.no_success(text)
        self.assertEqual(self.m.load(self.session())['phase'], 'rolled_back')
        for p in derive.PATHS: self.assertEqual((self.app / p).read_bytes(), self.old[p])
        self.assertEqual(identity(self.bootstrap), self.bootstrap_identity)
    def test_prerequisite_loss_after_staging_before_first_replace_preserves_all_preimages(self):
        lint = self.m.lint
        def drift(session): lint(session); self.drift_bootstrap(b'<?php // concurrent bootstrap edit retained\n')
        with mock.patch.object(self.m, 'lint', side_effect=drift), mock.patch.object(subprocess, 'check_output', side_effect=self.php): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text)
        for p in derive.PATHS: self.assertEqual((self.app / p).read_bytes(), self.old[p])
        self.assertEqual(self.m.load(self.session())['phase'], 'prepared')
        self.assertIn(b'concurrent bootstrap edit retained', self.bootstrap.read_bytes())
    def test_postrename_prerequisite_loss_is_uncertain_manual_review_without_overwrite(self):
        replace = self.m.replace
        def drift(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-0.code': self.drift_bootstrap(b'<?php // concurrent bootstrap edit retained\n')
            return result
        with mock.patch.object(self.m, 'replace', side_effect=drift), mock.patch.object(subprocess, 'check_output', side_effect=self.php): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text); self.assertIn('manual review', text)
        value = self.m.load(self.session()); self.assertEqual(value['phase'], 'manual_review')
        self.assertIn(derive.PATHS[0], value['uncertain']); self.assertEqual(value['intent'], derive.PATHS[0])
        self.assertEqual(sha((self.app / derive.PATHS[0]).read_bytes()), self.m.FILES[derive.PATHS[0]]['after_sha256'])
        for p in derive.PATHS[1:]: self.assertEqual((self.app / p).read_bytes(), self.old[p])
        self.assertIn(b'concurrent bootstrap edit retained', self.bootstrap.read_bytes())
    def test_loss_before_second_replace_retains_recorded_first_installed_lease(self):
        move = self.m.move_code
        def drift(source, path, *args, **kwargs):
            if path == derive.PATHS[1]: self.drift_bootstrap(b'<?php // concurrent bootstrap edit retained\n')
            return move(source, path, *args, **kwargs)
        with mock.patch.object(self.m, 'move_code', side_effect=drift), mock.patch.object(subprocess, 'check_output', side_effect=self.php): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text)
        value = self.m.load(self.session()); self.assertEqual(value['phase'], 'manual_review')
        self.assertIsNotNone(value['files'][derive.PATHS[0]]['installed'])
        self.m.verify_lease(derive.PATHS[0], value['files'][derive.PATHS[0]]['installed'])
        self.assertEqual((self.app / derive.PATHS[1]).read_bytes(), self.old[derive.PATHS[1]])
    def late_journal_drift(self, phase):
        journal = self.m.journal
        def drift(session, value):
            result = journal(session, value)
            if value['phase'] == phase: self.drift_bootstrap(b'<?php // late prerequisite edit retained\n')
            return result
        return mock.patch.object(self.m, 'journal', side_effect=drift)
    def assert_fully_applied_journal_retained(self):
        value = self.m.load(self.session()); self.assertEqual(value['phase'], 'applied')
        self.assertIsNone(value['intent']); self.assertEqual(value['uncertain'], [])
        for p in derive.PATHS:
            self.assertIsNotNone(value['files'][p]['installed']); self.m.verify_lease(p, value['files'][p]['installed'])
    def test_late_prerequisite_loss_after_applied_journal_never_reports_success(self):
        with self.late_journal_drift('applied'), mock.patch.object(subprocess, 'check_output', side_effect=self.php): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text); self.assertIn('manual review', text)
        self.assert_fully_applied_journal_retained()
    def test_prerequisite_loss_during_frozen_lock_exit_never_reports_success(self):
        locked = self.m.locked
        @contextlib.contextmanager
        def late_locked():
            with locked() as check:
                yield check
                self.drift_bootstrap(b'<?php // lock-exit prerequisite edit retained\n')
        with mock.patch.object(self.m, 'locked', late_locked), mock.patch.object(subprocess, 'check_output', side_effect=self.php): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text); self.assert_fully_applied_journal_retained()
        self.assertIn('PRIVATE_BACKUP_ROOT /home/bobsome1/kcmc-owner-guard-backups', text)
    def test_prerequisite_loss_after_engine_apply_return_boundary_never_reports_success(self):
        apply = self.m.apply
        def late_apply():
            result = apply(); self.drift_bootstrap(); return result
        with mock.patch.object(self.m, 'apply', side_effect=late_apply), mock.patch.object(subprocess, 'check_output', side_effect=self.php): code, text = self.cli('apply')
        self.assertEqual(code, 1); self.no_success(text); self.assert_fully_applied_journal_retained()
    def test_rollback_refuses_unknown_bootstrap_before_any_code_or_journal_write(self):
        self.apply(); session = self.session(); before = {p: identity(self.app / p) for p in derive.PATHS}; journal = identity(session / 'journal.json')
        self.drift_bootstrap(b'<?php // newer bootstrap retained\n')
        code, text = self.cli('rollback', '--variant', 'main93', '--session', session.name)
        self.assertEqual(code, 1); self.no_success(text)
        for p, prior in before.items(): self.assertEqual(identity(self.app / p), prior)
        self.assertEqual(identity(session / 'journal.json'), journal)
    def test_prerequisite_loss_during_rollback_preserves_uncertain_original_and_other_leases(self):
        self.apply(); session = self.session(); replace = self.m.replace
        def drift(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source.startswith('restore-'): self.drift_bootstrap(b'<?php // rollback prerequisite edit retained\n')
            return result
        with mock.patch.object(self.m, 'replace', side_effect=drift): code, text = self.cli('rollback', '--variant', 'main93', '--session', session.name)
        self.assertEqual(code, 1); self.no_success(text); self.assertIn('manual review', text)
        value = self.m.load(session); self.assertEqual(value['phase'], 'manual_review'); self.assertIn(derive.PATHS[-1], value['uncertain'])
        self.assertEqual((self.app / derive.PATHS[-1]).read_bytes(), self.old[derive.PATHS[-1]])
        for p in derive.PATHS[:-1]: self.m.verify_lease(p, value['files'][p]['installed'])
        self.assertIn(b'rollback prerequisite edit retained', self.bootstrap.read_bytes())
    def test_prerequisite_loss_after_rolledback_journal_never_reports_success(self):
        self.apply(); session = self.session()
        with self.late_journal_drift('rolled_back'): code, text = self.cli('rollback', '--variant', 'main93', '--session', session.name)
        self.assertEqual(code, 1); self.no_success(text); value = self.m.load(session); self.assertEqual(value['phase'], 'rolled_back')
        for p in derive.PATHS: self.assertEqual((self.app / p).read_bytes(), self.old[p])
    def test_php_discovery_rejects_noncli_before_backup_and_accepts_path_fallback(self):
        self.selected.side_effect = self.real_choose; candidates = ['/missing', '/cgi', '/other', '/cli']; self.w.php82_candidates = lambda: candidates
        seen = []
        def version(command, **kwargs):
            self.assertFalse(self.m.BACKUPS.exists()); seen.append(command[0])
            if command[0] == '/missing': raise OSError(2, 'Absent synthetic PHP')
            return {'/cgi': b'PHP 8.2.34 (cgi-fcgi)\n', '/other': b'PHP 8.3.2 (cli)\n', '/cli': b'PHP 8.2.34 (cli)\n'}[command[0]]
        with mock.patch.object(subprocess, 'check_output', side_effect=version): code, text = self.cli('check')
        self.assertEqual(code, 0, text); self.assertEqual(seen, candidates); self.assertIn('PHP_CLI /cli', text)
    def test_later_target_edit_blocks_entire_rollback(self):
        self.apply(); session = self.session(); (self.app / derive.PATHS[2]).write_bytes(b'<?php // newer target retained\n')
        prior = {p: identity(self.app / p) for p in derive.PATHS}
        code, text = self.cli('rollback', '--variant', 'main93', '--session', session.name); self.assertEqual(code, 1); self.no_success(text)
        for p, old in prior.items(): self.assertEqual(identity(self.app / p), old)
    def test_unknown_environment_and_incomplete_cli_rollback_cannot_widen_scope(self):
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/wrong', 'KCMC_UID': '0', 'KCMC_PRIVATE_DATA_DIR': '/tmp/no'}):
            module = self.w.load_engines()['main93']; self.assertEqual(module.APP, Path('/home/bobsome1/public_html/kcmc-connect'))
            self.assertEqual(module.BACKUPS, Path('/home/bobsome1/kcmc-owner-guard-backups')); self.assertEqual(module.PATHS, derive.PATHS)
            self.assertEqual(self.w.PRIVATE_BACKUP_ROOT, str(module.BACKUPS))
        for args in [('apply', '--variant', 'main93'), ('rollback',), ('rollback', '--session', 'repair-incomplete')]:
            code, text = self.cli(*args); self.assertEqual(code, 1); self.no_success(text)
        self.assertFalse(self.m.BACKUPS.exists())


class ProvenanceTests(unittest.TestCase):
    def test_exact_fourfile_delta_and_readonly_prerequisite_provenance(self):
        runtime = derive.verify_runtime(); prerequisite = derive.verify_prerequisite()
        self.assertNotIn(prerequisite['path'], derive.PATHS)
        if RUNTIME_ROOT is not None:
            for path, item in runtime['main93'].items():
                before = (HERE / 'evidence/main93' / path).read_bytes(); after = before
                for old, new in item['replacements']: after = after.replace(old.encode(), new.encode(), 1)
                self.assertEqual(after, (RUNTIME_ROOT / path).read_bytes())
            self.assertEqual(sha((RUNTIME_ROOT / prerequisite['path']).read_bytes()), prerequisite['sha256'])
    def test_all_frozen_transaction_functions_and_classes_are_unchanged(self):
        raw = (HERE / 'provenance/frozen-minimal-installer.py').read_bytes(); self.assertEqual(sha(raw), derive.ENGINE_SHA256)
        original = ast.parse(raw.decode())
        def nodes(tree): return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name != 'lint'}
        expected = nodes(original)
        for source, unused in wrapper().EMBEDDED.values():
            actual = nodes(ast.parse(source)); self.assertEqual(set(actual), set(expected))
            for name, node in actual.items():
                for item in ast.walk(node):
                    attribute = 'value' if sys.version_info >= (3, 8) else 's'; value = getattr(item, attribute, None)
                    if isinstance(value, str):
                        value = value.replace('the four reviewed files', 'the three reviewed files').replace('all four code files', 'all three code files')
                        setattr(item, attribute, '.php' if value == '.code' else value)
                self.assertEqual(ast.dump(node), ast.dump(expected[name]), name)
    def test_reproducible_installer_and_provenance(self):
        before = (HERE / 'installer.py').read_bytes(); proof = (HERE / 'provenance.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='kcmc-owner-derive-') as directory:
            copied = Path(directory) / 'package'; shutil.copytree(str(HERE), str(copied))
            subprocess.check_call([sys.executable, '-B', 'derive_installer.py'], cwd=str(copied))
            self.assertEqual((copied / 'installer.py').read_bytes(), before); self.assertEqual((copied / 'provenance.json').read_bytes(), proof)
    def test_evidence_membership_in_exact_canonical_source(self):
        if GIT_ROOT is None: self.skipTest('Git membership runs in the current-Python CI job')
        for path in derive.PATHS:
            canonical = subprocess.check_output(['git', 'show', derive.COMMIT + ':KCMC-Connect-Phase6-Recreated/' + path], cwd=str(GIT_ROOT))
            self.assertEqual((HERE / 'evidence/main93' / path).read_bytes(), canonical)
        content = (HERE / 'evidence/prerequisite/lib/bootstrap.php').read_bytes()
        fixture = json.loads((HERE / 'provenance/session-credential-reviewed.json').read_text())
        for old, new in reversed(fixture['files']['lib/bootstrap.php']['replacements']): content = content.replace(new.encode(), old.encode(), 1)
        canonical = subprocess.check_output(['git', 'show', derive.COMMIT + ':KCMC-Connect-Phase6-Recreated/lib/bootstrap.php'], cwd=str(GIT_ROOT))
        self.assertEqual(content, canonical)


if __name__ == '__main__': unittest.main()
