#!/usr/bin/env python3
"""Actual-Git metadata transaction fixtures; no host, fetch, merge, or network.

The frozen verifier is loaded at its real checksum. Only repair's in-process
checkout/commit/owner/count/journal roots are redirected to temporary fixtures.
"""
from __future__ import print_function
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
APP = 'KCMC-Connect-Phase6-Recreated/'
EXACT_PATHS = ('.cpanel.yml', '.github/workflows/security-contract.yml', '.gitignore', APP+'.htaccess',
               APP+'admin/backup.php', APP+'admin/login.php', APP+'admin/logout.php', APP+'admin/prayers.php',
               APP+'admin/setup.php', APP+'member/logout.php', APP+'member/prayer-team.php',
               APP+'member/submit-prayer.php', 'README.md')
FORBIDDEN = set(['fetch', 'merge', 'checkout', 'reset', 'update-ref', 'push', 'stash', 'clean', 'add', 'commit'])

def git(repo, *args):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null',
               GIT_TERMINAL_PROMPT='0', LC_ALL='C')
    return subprocess.check_output(['git', '-C', str(repo)] + list(args), env=env, stderr=subprocess.PIPE)

def permissions(path):
    return stat.S_IMODE(path.stat().st_mode)

def snapshot(repo):
    result = {}
    for path in sorted(repo.rglob('*')):
        name = str(path.relative_to(repo))
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            result[name] = ('link', os.readlink(str(path)))
        elif stat.S_ISREG(info.st_mode):
            result[name] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(info.st_mode),
                            info.st_uid, info.st_gid, info.st_ino)
        elif not stat.S_ISDIR(info.st_mode):
            result[name] = ('special', stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode),
                            info.st_uid, info.st_gid, info.st_ino)
    return result

class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template_temp = tempfile.TemporaryDirectory(prefix='kcmc-metadata-template-')
        cls.template = Path(cls.template_temp.name) / 'repo'
        cls.template.mkdir()
        git(cls.template, 'init', '-b', 'main')
        git(cls.template, 'config', 'user.name', 'Synthetic metadata fixture')
        git(cls.template, 'config', 'user.email', 'metadata@example.invalid')
        git(cls.template, 'config', 'core.filemode', 'true')
        git(cls.template, 'remote', 'add', 'origin', 'https://github.com/bobhay75/Kcmc-connect.git')
        paths = list(EXACT_PATHS) + ['synthetic-files/file-{:03d}.txt'.format(n) for n in range(242)]
        for number, name in enumerate(paths):
            path = cls.template / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = ('CONTENT-NEVER-COPY-TO-JOURNAL-{:03d}\n'.format(number)).encode('ascii')
            if name == '.gitignore': data = b'ignored-sentinel.tmp\n'
            path.write_bytes(data)
            path.chmod(0o644)
        git(cls.template, 'add', '--all')
        git(cls.template, 'commit', '-m', 'Synthetic coherent 255-file baseline')
        cls.baseline = git(cls.template, 'rev-parse', 'HEAD').strip().decode('ascii')
        changed = cls.template / 'synthetic-files/file-000.txt'
        changed.write_bytes(b'SYNTHETIC TARGET CONTENT\n')
        git(cls.template, 'add', str(changed.relative_to(cls.template)))
        git(cls.template, 'commit', '-m', 'Synthetic target')
        cls.target = git(cls.template, 'rev-parse', 'HEAD').strip().decode('ascii')
        git(cls.template, 'reset', '--hard', cls.baseline)
        # Git respects the caller's potentially private umask on recreated
        # files. The canonical fixture starts at the exact sanctioned0644.
        for name in paths: (cls.template/name).chmod(0o644)
        assert len(git(cls.template, 'ls-files', '-z').split(b'\0')) - 1 == 255

    @classmethod
    def tearDownClass(cls):
        cls.template_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-metadata-repair-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'checkout'
        shutil.copytree(str(self.template), str(self.repo))
        spec = importlib.util.spec_from_file_location('isolated_metadata_repair', str(HERE/'repair.py'))
        self.repair = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.repair)
        self.assertEqual(self.repair.PATHS, EXACT_PATHS)
        self.repair.REPO = self.repo
        self.repair.BASELINE, self.repair.TARGET = self.baseline, self.target
        self.repair.UID, self.repair.GID = os.getuid(), os.getgid()
        self.repair.TRACKED_COUNT = 255
        self.repair.PRIVATE_ROOT = self.root / 'private-journals'
        self.helper = self.repair.load_helper()
        self.real_regular = self.helper.regular
        self.real_git = self.helper.git
        self.real_change = self.repair.change_mode
        self.commands, self.changes = [], []
        def observe_git(args, *a, **kw):
            self.commands.append(tuple(args))
            self.assertNotIn(args[0], FORBIDDEN, 'repair must not invoke a Git updater')
            return self.real_git(args, *a, **kw)
        def observe_mode(fd, value):
            self.changes.append((str(Path(os.readlink('/proc/self/fd/'+str(fd))).relative_to(self.repo)), value))
            return self.real_change(fd, value)
        self.helper.git = observe_git
        self.helper.main = mock.Mock(side_effect=AssertionError('frozen align main must not run'))
        self.repair.change_mode = observe_mode
        for name in EXACT_PATHS: (self.repo/name).chmod(0o664)

    def run_repair(self, action='repair'):
        return self.repair.run(action=action, helper=self.helper)

    def journal_value(self):
        sessions = list(self.repair.PRIVATE_ROOT.glob('repair-*'))
        self.assertEqual(len(sessions), 1)
        return json.loads((sessions[0]/'journal.json').read_text())

    def assert_refused_before_chmod(self):
        before = snapshot(self.repo)
        with self.assertRaises(Exception): self.run_repair()
        self.assertEqual(snapshot(self.repo), before)
        self.assertFalse(self.changes)
        self.assertFalse(self.repair.PRIVATE_ROOT.exists())
        self.assertIs(self.helper.regular, self.real_regular)
        self.helper.main.assert_not_called()

    def inject_after_changes(self, count, callback):
        original = self.repair.journal
        seen = []
        def fault(session, records, phase):
            result = original(session, records, phase)
            if phase == 'changing':
                seen.append(True)
                if len(seen) == count:
                    callback(records)
                    raise OSError('Synthetic journal failure after actual permission changes')
            return result
        self.repair.journal = fault

    def test_exact_thirteen_modes_only_repaired_and_refs_content_ownership_preserved(self):
        before = snapshot(self.repo)
        previous_signal = signal.getsignal(signal.SIGTERM)
        result = self.run_repair()
        after = snapshot(self.repo)
        self.assertEqual(result['status'], 'repaired')
        self.assertEqual(result['changed'], 13)
        self.assertEqual(self.changes, [(name,0o644) for name in EXACT_PATHS])
        self.assertEqual(set(before), set(after))
        for name, old in before.items():
            expected = (old[0],0o644)+old[2:] if name in EXACT_PATHS else old
            self.assertEqual(after[name], expected, name)
        self.assertEqual(git(self.repo,'rev-parse','HEAD').strip().decode(), self.baseline)
        self.assertIs(self.helper.regular,self.real_regular)
        self.assertIs(signal.getsignal(signal.SIGTERM),previous_signal)
        self.helper.main.assert_not_called()
        journal = self.journal_value()
        self.assertEqual(journal['phase'],'complete')
        self.assertEqual([r['path'] for r in journal['files']],list(EXACT_PATHS))
        for path in self.repair.PRIVATE_ROOT.rglob('*'):
            self.assertEqual(permissions(path),0o700 if path.is_dir() else 0o600)
            if path.is_file(): self.assertNotIn(b'CONTENT-NEVER-COPY',path.read_bytes())
        for row in journal['files']:
            self.assertEqual(set(row),set(['path','dev','ino','mode','uid','gid','blob_sha']))
            self.assertEqual(row['mode'],0o664)

    def test_all644_is_strict_noop_without_journal(self):
        for name in EXACT_PATHS: (self.repo/name).chmod(0o644)
        before = snapshot(self.repo)
        self.assertEqual(self.run_repair(),{'status':'already_repaired','changed':0})
        self.assertEqual(snapshot(self.repo),before)
        self.assertFalse(self.changes)
        self.assertFalse(self.repair.PRIVATE_ROOT.exists())

    def test_check_is_readonly_and_reports_eligible664(self):
        before = snapshot(self.repo)
        self.assertEqual(self.run_repair('check'),{'status':'eligible','changed':0})
        self.assertEqual(snapshot(self.repo),before)
        self.assertFalse(self.changes)

    def test_target_head_is_readonly_clean_and_never_normalized(self):
        git(self.repo,'reset','--hard',self.target)
        for name in git(self.repo,'ls-files','-z').decode().split('\0'):
            if name: (self.repo/name).chmod(0o644)
        before = snapshot(self.repo)
        self.assertEqual(self.run_repair(),{'status':'already_target','changed':0})
        self.assertEqual(snapshot(self.repo),before)
        self.assertFalse(self.changes)
        self.assertFalse(self.repair.PRIVATE_ROOT.exists())

    def test_target_head_bad_modes_refuse_instead_of_normalizing(self):
        git(self.repo,'reset','--hard',self.target)
        # Git versions differ in which unchanged files reset recreates.
        # Set the complete correct target, then introduce the measured violation.
        for name in git(self.repo,'ls-files','-z').decode().split('\0'):
            if name: (self.repo/name).chmod(0o644)
        (self.repo/EXACT_PATHS[0]).chmod(0o664)
        self.assert_refused_before_chmod()

    def test_mixed_target_modes_refuse(self):
        (self.repo/EXACT_PATHS[0]).chmod(0o644)
        self.assert_refused_before_chmod()

    def test_unknown_mode_refuses(self):
        (self.repo/EXACT_PATHS[0]).chmod(0o640)
        self.assert_refused_before_chmod()

    def test_nonallowlisted_mode_refuses(self):
        (self.repo/'synthetic-files/file-003.txt').chmod(0o664)
        self.assert_refused_before_chmod()

    def test_wrong_caller_uid_or_gid_refuses(self):
        for field in ['UID','GID']:
            with self.subTest(field=field):
                old = getattr(self.repair,field)
                setattr(self.repair,field,old+1)
                self.assert_refused_before_chmod()
                setattr(self.repair,field,old)

    def test_unknown_head_refuses(self):
        self.repair.BASELINE='a'*40
        self.assert_refused_before_chmod()

    def test_wrong_tracked_count_refuses(self):
        self.repair.TRACKED_COUNT=254
        self.assert_refused_before_chmod()

    def test_target_content_edit_refuses(self):
        (self.repo/EXACT_PATHS[0]).write_bytes(b'NEWER EDIT MUST BE PRESERVED')
        self.assert_refused_before_chmod()

    def test_other_tracked_content_edit_refuses(self):
        (self.repo/'synthetic-files/file-003.txt').write_bytes(b'NEWER OTHER EDIT')
        self.assert_refused_before_chmod()

    def test_staged_edit_refuses(self):
        (self.repo/'synthetic-files/file-003.txt').write_bytes(b'STAGED EDIT')
        git(self.repo,'add','synthetic-files/file-003.txt')
        self.assert_refused_before_chmod()

    def test_index_flags_refuse(self):
        for flag,undo in [('--assume-unchanged','--no-assume-unchanged'),('--skip-worktree','--no-skip-worktree')]:
            with self.subTest(flag=flag):
                git(self.repo,'update-index',flag,'synthetic-files/file-003.txt')
                self.assert_refused_before_chmod()
                git(self.repo,'update-index',undo,'synthetic-files/file-003.txt')

    def test_untracked_and_ignored_files_refuse(self):
        for name in ['unknown.txt','ignored-sentinel.tmp']:
            with self.subTest(name=name):
                path=self.repo/name
                path.write_bytes(b'PRESERVED UNTRACKED OR IGNORED CONTENT')
                self.assert_refused_before_chmod()
                path.unlink()

    def test_blocked_configuration_and_wrong_origin_refuse(self):
        for key,value in [('core.sparseCheckout','true'),('filter.fixture.clean','false'),
                          ('include.path','/nonexistent'),('remote.origin.url','https://example.invalid/other.git')]:
            with self.subTest(key=key):
                old=git(self.repo,'config','--get',key).strip() if key=='remote.origin.url' else None
                git(self.repo,'config',key,value)
                self.assert_refused_before_chmod()
                if old is None: git(self.repo,'config','--unset',key)
                else: git(self.repo,'config',key,old.decode())

    def test_target_symlink_refuses_without_following(self):
        path=self.repo/EXACT_PATHS[0]
        external=self.root/'outside.yml'
        external.write_bytes(path.read_bytes())
        external.chmod(0o644)
        path.unlink();os.symlink(str(external),str(path))
        self.assert_refused_before_chmod()
        self.assertEqual(permissions(external),0o644)

    def test_target_hardlink_refuses(self):
        os.link(str(self.repo/EXACT_PATHS[0]),str(self.root/'outside-hardlink'))
        self.assert_refused_before_chmod()

    def test_fifo_type_refuses_without_blocking(self):
        path=self.repo/EXACT_PATHS[0]
        path.unlink();os.mkfifo(str(path))
        self.assert_refused_before_chmod()

    def test_frozen_verifier_checksum_refuses_before_loading(self):
        real=self.repair.os.read
        frozen=HERE/'align-repository.py'
        def altered(fd,size):
            data=real(fd,size)
            if Path(os.readlink('/proc/self/fd/'+str(fd)))==frozen and data:
                return bytes([data[0]^1])+data[1:]
            return data
        with mock.patch.object(self.repair.os,'read',side_effect=altered):
            with self.assertRaisesRegex(self.repair.Refusal,'checksum mismatch'): self.repair.load_helper()
        self.assertFalse(self.changes)

    def test_helper_regular_proxy_restores_after_proof_refusal(self):
        original=self.helper.clean
        self.helper.clean=mock.Mock(side_effect=self.helper.Refusal('Synthetic proof failure'))
        self.assert_refused_before_chmod()
        self.assertIs(self.helper.regular,self.real_regular)
        self.helper.clean=original

    def test_failure_after_actual_second_fchmod_restores_all_leased_prior_modes(self):
        before=snapshot(self.repo)
        real=self.repair.change_mode
        seen=[]
        def fail(fd,value):
            real(fd,value)
            if value==0o644:
                seen.append(fd)
                if len(seen)==2: raise OSError('Failure after actual second fchmod')
        self.repair.change_mode=fail
        with self.assertRaises(self.repair.Refusal): self.run_repair()
        self.assertEqual(len(seen),2)
        self.assertEqual(snapshot(self.repo),before)
        self.assertEqual(self.journal_value()['phase'],'rolled_back')
        self.assertIs(self.helper.regular,self.real_regular)

    def test_journal_failure_after_actual_changes_restores_modes(self):
        before=snapshot(self.repo)
        self.inject_after_changes(2,lambda records:None)
        with self.assertRaises(self.repair.Refusal): self.run_repair()
        self.assertEqual(snapshot(self.repo),before)
        self.assertEqual(self.journal_value()['phase'],'rolled_back')

    def test_edited_file_preserved_but_other_leased_mode_restored(self):
        first=self.repo/EXACT_PATHS[0]
        self.inject_after_changes(2,lambda records:first.write_bytes(b'NEW FILE EDIT MUST SURVIVE ROLLBACK'))
        with self.assertRaisesRegex(self.repair.Refusal,'manual review'): self.run_repair()
        self.assertEqual(first.read_bytes(),b'NEW FILE EDIT MUST SURVIVE ROLLBACK')
        self.assertEqual(permissions(first),0o644)
        self.assertEqual(permissions(self.repo/EXACT_PATHS[1]),0o664)
        self.assertTrue(self.journal_value()['phase'].startswith('review_required'))

    def test_new_inode_preserved_but_other_leased_mode_restored(self):
        first=self.repo/EXACT_PATHS[0]
        inode=first.stat().st_ino
        def replace(records):
            new=self.root/'replacement.yml'
            new.write_bytes(b'NEW INODE CONTENT');new.chmod(0o640)
            os.replace(str(new),str(first))
        self.inject_after_changes(2,replace)
        with self.assertRaisesRegex(self.repair.Refusal,'manual review'): self.run_repair()
        self.assertNotEqual(first.stat().st_ino,inode)
        self.assertEqual(first.read_bytes(),b'NEW INODE CONTENT')
        self.assertEqual(permissions(first),0o640)
        self.assertEqual(permissions(self.repo/EXACT_PATHS[1]),0o664)

    def test_new_wrong_mode_preserved_but_other_leased_mode_restored(self):
        first=self.repo/EXACT_PATHS[0]
        self.inject_after_changes(2,lambda records:first.chmod(0o600))
        with self.assertRaisesRegex(self.repair.Refusal,'manual review'): self.run_repair()
        self.assertEqual(permissions(first),0o600)
        self.assertEqual(permissions(self.repo/EXACT_PATHS[1]),0o664)

    def assert_global_drift_preserved(self,mutate):
        captured=[]
        def change(records):
            mutate()
            captured.append(snapshot(self.repo))
        self.inject_after_changes(2,change)
        with self.assertRaisesRegex(self.repair.Refusal,'manual review'): self.run_repair()
        self.assertEqual(snapshot(self.repo),captured[0])
        self.assertEqual(self.changes,[(EXACT_PATHS[0],0o644),(EXACT_PATHS[1],0o644)])
        self.assertTrue(self.journal_value()['phase'].startswith('review_required'))

    def test_head_drift_preserves_all_new_checkout_state(self):
        self.assert_global_drift_preserved(lambda:git(self.repo,'update-ref','refs/heads/main',self.target))

    def test_index_drift_preserves_all_new_checkout_state(self):
        self.assert_global_drift_preserved(lambda:git(self.repo,'update-index','--assume-unchanged','synthetic-files/file-003.txt'))

    def test_config_drift_preserves_all_new_checkout_state(self):
        self.assert_global_drift_preserved(lambda:git(self.repo,'config','core.autocrlf','true'))

    def test_repository_identity_drift_preserves_all_new_checkout_state(self):
        moved=self.root/'moved-checkout'
        def replace():
            self.repo.rename(moved)
            shutil.copytree(str(self.template),str(self.repo))
            (self.repo/EXACT_PATHS[0]).chmod(0o600)
        self.assert_global_drift_preserved(replace)
        self.assertEqual(permissions(moved/EXACT_PATHS[0]),0o644)
        self.assertEqual(permissions(moved/EXACT_PATHS[1]),0o644)

    def test_global_drift_during_last_restore_requires_review_receipt(self):
        self.inject_after_changes(2,lambda records:None)
        real=self.repair.change_mode
        restored=[]
        def last(fd,value):
            real(fd,value)
            if value==0o664:
                restored.append(fd)
                if len(restored)==2: git(self.repo,'config','core.autocrlf','true')
        self.repair.change_mode=last
        with self.assertRaisesRegex(self.repair.Refusal,'manual review'): self.run_repair()
        self.assertEqual(len(restored),2)
        self.assertTrue(self.journal_value()['phase'].startswith('review_required'))

    def test_busy_private_lock_refuses_without_chmod(self):
        import fcntl
        self.repair.PRIVATE_ROOT.mkdir(mode=0o700)
        lock=self.repair.PRIVATE_ROOT/'.repair.lock'
        lock.write_bytes(b'');lock.chmod(0o600)
        with lock.open('r+b') as out:
            fcntl.flock(out.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(Exception): self.run_repair()
        self.assertFalse(self.changes)

    def test_signal_handler_restored_after_failure(self):
        previous=signal.getsignal(signal.SIGTERM)
        self.inject_after_changes(2,lambda records:None)
        with self.assertRaises(self.repair.Refusal): self.run_repair()
        self.assertIs(signal.getsignal(signal.SIGTERM),previous)

if __name__=='__main__': unittest.main(verbosity=2)
