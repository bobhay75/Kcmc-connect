#!/usr/bin/env python3
"""Fixed payload transactions in temporary fixtures; never execute app code."""
from __future__ import print_function
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
CANDIDATE = '--candidate' in sys.argv
if CANDIDATE: sys.argv.remove('--candidate')
INSTALLER = 'candidate-installer.py' if CANDIDATE else 'installer.py'
PROVENANCE = 'candidate-provenance.json' if CANDIDATE else 'provenance.json'
RUNTIME_ROOT = None; GIT_ROOT = None
CANDIDATE_SOURCE = None
if '--candidate-source-ref' in sys.argv:
    if not CANDIDATE: raise ValueError('Candidate source reference is test-only and requires --candidate')
    index=sys.argv.index('--candidate-source-ref'); CANDIDATE_SOURCE=sys.argv[index+1]; del sys.argv[index:index+2]
for option in ('--runtime-root','--git-root'):
    if option in sys.argv:
        index = sys.argv.index(option); path = Path(sys.argv[index+1]); del sys.argv[index:index+2]
        if option == '--runtime-root': RUNTIME_ROOT = path
        else: GIT_ROOT = path


def sha(content): return hashlib.sha256(content).hexdigest()


def identity(path):
    value = path.lstat()
    return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


def wrapper():
    spec = importlib.util.spec_from_file_location('isolated_team_payroll_installer',str(HERE/INSTALLER))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


class Fixture:
    def __init__(self, after=False):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-team-payroll-release-'); self.root = Path(self.temp.name)
        self.app = self.root/'app'; self.app.mkdir(); self.w = wrapper(); self.m = self.w.load_engine()
        self.m.APP = self.app; self.m.BACKUPS = self.root/'private'; self.m.UID = os.getuid(); self.m.GID = os.getgid()
        for name in ('lib','admin','member','api'): (self.app/name).mkdir()
        self.before = {}
        for path,row in self.m.FILES.items():
            before = (HERE/'evidence/before'/path).read_bytes() if row['before_sha256'] is not None else None
            self.before[path] = before
            content = (HERE/'evidence/after'/path).read_bytes() if after else before
            if content is not None:
                (self.app/path).write_bytes(content); (self.app/path).chmod(0o664 if path=='lib/bootstrap.php' else 0o644)
        self.prerequisites = {}
        for path in self.w.PREREQUISITES:
            content = (HERE/'evidence/prerequisite'/path).read_bytes(); (self.app/path).write_bytes(content); (self.app/path).chmod(0o644)
            self.prerequisites[path] = (content,identity(self.app/path))
        self.sentinels = {'config.php':b'<?php // private owner configuration stays exactly here\n',
            'config.example.php':b'<?php // local template is not installed\n',
            'data/content.json':b'{"editorial":"unchanged"}', 'data/private/users.json':b'{"accounts":"unchanged"}',
            'data/private/timeclock.json':b'{"live punches":"unchanged"}', 'data/private/prayers.json':b'{"private prayers":"unchanged"}',
            'data/private/payroll-settings.json':b'{"channel":"off","reviewer_id":""}',
            'data/private/team-workspace.json':b'{"private tasks":"unchanged"}', '.git/HEAD':b'ref: refs/heads/main\n',
            'index.php':b'<?php // fish homepage unchanged\n','public-presentation.css':b'/* fish style unchanged */\n','sw.js':b'// worker unchanged\n'}
        for path,content in self.sentinels.items():
            target = self.app/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(content); target.chmod(0o600)
        self.ids = {path:identity(self.app/path) for path in self.sentinels}
        self.crontab = self.root/'synthetic-crontab'; self.crontab.write_bytes(b'5 * * * * existing-unrelated-job\n'); self.crontab.chmod(0o600)
        self.crontab_identity = identity(self.crontab)
        self.w.load_engine = lambda:self.m; self.real_choose = self.w.choose_php82_cli
        self.w.choose_php82_cli = lambda:('/synthetic/php82','8.2.34')
    def close(self): self.temp.cleanup()
    def php(self, command, **kwargs):
        assert command[:2]==['/synthetic/php82','-n']
        if command[-1]=='-v': return b'PHP 8.2.34 (cli)\n'
        assert command[2]=='-l' and Path(command[3]).is_file()
        return b'No syntax errors detected\n'
    def cli(self,*args):
        output=io.StringIO()
        with mock.patch.object(sys,'argv',['installer.py']+list(args)),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output): code=self.w.main()
        return code,output.getvalue()
    def apply(self):
        with mock.patch.object(subprocess,'check_output',side_effect=self.php): return self.cli('apply')
    def session(self): return next(self.m.BACKUPS.glob('repair-*'))
    def journal(self): return self.m.load(self.session())
    def foreign(self,path,content=None):
        destination=self.app/path; replacement=self.root/'concurrent-code'
        replacement.write_bytes(destination.read_bytes() if content is None else content); replacement.chmod(0o644)
        os.replace(str(replacement),str(destination)); return identity(destination)
    def preserved(self,allow_prerequisite=None):
        for path,content in self.sentinels.items():
            assert (self.app/path).read_bytes()==content and identity(self.app/path)==self.ids[path],path
        for path,(content,prior) in self.prerequisites.items():
            if path==allow_prerequisite: continue
            assert (self.app/path).read_bytes()==content and identity(self.app/path)==prior,path
        assert self.crontab.read_bytes()==b'5 * * * * existing-unrelated-job\n' and identity(self.crontab)==self.crontab_identity
    def assert_before(self):
        for path,content in self.before.items():
            if content is None: assert not (self.app/path).exists(),path
            else: assert (self.app/path).read_bytes()==content,path


class CoordinatorTests(unittest.TestCase):
    def setUp(self): self.f=Fixture(); self.addCleanup(self.f.close)
    def test_default_check_is_readonly_and_needs_complete_core_after(self):
        code,text=self.f.cli(); self.assertEqual(code,0,text); self.assertIn('CHECK READY',text)
        self.assertFalse(self.f.m.BACKUPS.exists()); self.f.assert_before(); self.f.preserved()
    def test_apply_exact_after_noop_and_reverse_rollback(self):
        with mock.patch.object(subprocess,'check_output',side_effect=self.f.php) as calls: code,text=self.f.cli('apply')
        self.assertEqual(code,0,text); self.assertIn('REPAIRED lib/bootstrap.php',text)
        self.assertEqual(sum(call[0][0][2]=='-l' for call in calls.call_args_list),sum(path.endswith('.php') for path in self.f.m.PATHS))
        value=self.f.journal(); self.assertEqual(value['phase'],'applied')
        for path,row in self.f.m.FILES.items():
            self.assertEqual(sha((self.f.app/path).read_bytes()),row['after_sha256']); self.f.m.verify_lease(path,value['files'][path]['installed'])
        self.assertEqual((self.f.app/'lib/bootstrap.php').stat().st_mode&0o777,0o664)
        ids={path:identity(self.f.app/path) for path in self.f.m.PATHS}; journal_id=identity(self.f.session()/'journal.json')
        code,text=self.f.cli('apply'); self.assertEqual(code,0,text); self.assertIn('ALREADY_REPAIRED; no replacement',text)
        self.assertEqual(identity(self.f.session()/'journal.json'),journal_id)
        for path,prior in ids.items(): self.assertEqual(identity(self.f.app/path),prior)
        code,text=self.f.cli('rollback','--session',self.f.session().name); self.assertEqual(code,0,text); self.assertIn('ROLLED_BACK ',text)
        self.f.assert_before(); self.f.preserved(); self.assertEqual(self.f.journal()['phase'],'rolled_back')
    def test_complete_after_is_noop_without_new_backup_or_php_probe(self):
        f=Fixture(after=True); self.addCleanup(f.close)
        with mock.patch.object(f.w,'choose_php82_cli',side_effect=AssertionError('No PHP needed')): code,text=f.cli('apply')
        self.assertEqual(code,0,text); self.assertIn('ALREADY_REPAIRED',text); self.assertFalse(f.m.BACKUPS.exists()); f.preserved()
    def test_noop_retains_initial_target_lease_across_engine_result(self):
        f=Fixture(after=True); self.addCleanup(f.close); apply=f.m.apply
        def changed(): result=apply(); f.foreign('lib/bootstrap.php'); return result
        with mock.patch.object(f.m,'apply',side_effect=changed): code,text=f.cli('apply')
        self.assertEqual(code,1); self.assertNotIn('ALREADY_REPAIRED',text)
        self.assertIn('Code lease changed: lib/bootstrap.php',text); self.assertFalse(f.m.BACKUPS.exists()); f.preserved()
    def test_noop_initial_lease_still_required_after_fresh_inspection(self):
        f=Fixture(after=True); self.addCleanup(f.close); unfinished=f.m.unfinished; calls=[0]
        def changed(*args,**kwargs):
            result=unfinished(*args,**kwargs); calls[0]+=1
            if calls[0]==3: f.foreign('lib/bootstrap.php')
            return result
        # preflight, engine no-op, final result boundary.
        with mock.patch.object(f.m,'unfinished',side_effect=changed): code,text=f.cli('apply')
        self.assertEqual(code,1); self.assertNotIn('ALREADY_REPAIRED',text)
        self.assertIn('Code lease changed: lib/bootstrap.php',text); self.assertFalse(f.m.BACKUPS.exists()); f.preserved()
    def test_each_single_target_flip_refuses_as_mixed_before_backup(self):
        for path in self.f.m.PATHS:
            target=self.f.app/path; target.write_bytes((HERE/'evidence/after'/path).read_bytes()); target.chmod(0o644)
            code,text=self.f.cli('apply'); self.assertEqual(code,1,path+text); self.assertFalse(self.f.m.BACKUPS.exists())
            if self.f.before[path] is None: target.unlink()
            else: target.write_bytes(self.f.before[path]); target.chmod(0o644)
        self.f.assert_before(); self.f.preserved()
    def test_each_unrepaired_or_unknown_readonly_core_path_refuses_before_backup(self):
        for path,(content,prior) in self.f.prerequisites.items():
            target=self.f.app/path; target.write_bytes(b'<?php // unrecognized or missing core protection\n')
            code,text=self.f.cli('apply'); self.assertEqual(code,1,path+text); self.assertIn('Complete core repair required',text)
            self.assertFalse(self.f.m.BACKUPS.exists()); target.write_bytes(content)
        self.f.assert_before()
    def test_unknown_bootstrap_bytes_refuse_as_code_target_not_prerequisite_exception(self):
        self.f.foreign('lib/bootstrap.php',b'<?php // unknown local bootstrap preserved\n')
        code,text=self.f.cli('apply'); self.assertEqual(code,1); self.assertIn('Unknown code bytes: lib/bootstrap.php',text)
        self.assertFalse(self.f.m.BACKUPS.exists()); self.f.preserved()
    def test_diagnose_prints_only_38_fixed_code_paths_and_no_private_records(self):
        code,text=self.f.cli('diagnose'); self.assertEqual(code,0,text); self.assertEqual(text.count('CODE '),38); self.assertEqual(text.count(' ABSENT '),9)
        self.assertNotIn('private owner configuration',text); self.assertNotIn('live punches',text); self.assertFalse(self.f.m.BACKUPS.exists()); self.f.preserved()
    def test_same_byte_prerequisite_replacement_during_php_probe_refuses_before_backup(self):
        path=next(iter(self.f.w.PREREQUISITES))
        def choose(): self.f.foreign(path); return '/synthetic/php82','8.2.34'
        self.f.w.choose_php82_cli=choose; code,text=self.f.cli('check')
        self.assertEqual(code,1); self.assertNotIn('CHECK READY',text); self.assertFalse(self.f.m.BACKUPS.exists()); self.f.preserved(path)
    def test_prerequisite_drift_in_staging_prevents_bootstrap_replacement(self):
        path=next(iter(self.f.w.PREREQUISITES)); lint=self.f.m.lint
        def changed(session): lint(session); self.f.foreign(path)
        with mock.patch.object(self.f.m,'lint',side_effect=changed): code,text=self.f.apply()
        self.assertEqual(code,1); self.assertNotIn('REPAIRED ',text); self.f.assert_before(); self.f.preserved(path)
        self.assertEqual(self.f.journal()['phase'],'prepared')
    def test_late_readonly_drift_after_applied_journal_preserves_installed_leases_without_success(self):
        path=next(iter(self.f.w.PREREQUISITES)); journal=self.f.m.journal
        def changed(session,value):
            result=journal(session,value)
            if value['phase']=='applied': self.f.foreign(path)
            return result
        with mock.patch.object(self.f.m,'journal',side_effect=changed): code,text=self.f.apply()
        self.assertEqual(code,1); self.assertNotIn('REPAIRED ',text); self.assertIn('PRIVATE_BACKUP_ROOT ',text)
        value=self.f.journal(); self.assertEqual(value['phase'],'applied')
        for target in self.f.m.PATHS: self.f.m.verify_lease(target,value['files'][target]['installed'])
        self.f.preserved(path)
    def test_late_same_bytes_bootstrap_replacement_cannot_claim_applied_success(self):
        journal=self.f.m.journal
        def changed(session,value):
            result=journal(session,value)
            if value['phase']=='applied': self.f.foreign('lib/bootstrap.php')
            return result
        with mock.patch.object(self.f.m,'journal',side_effect=changed): code,text=self.f.apply()
        self.assertEqual(code,1); self.assertNotIn('REPAIRED ',text); self.assertIn('Code lease changed: lib/bootstrap.php',text)
        self.assertEqual(self.f.journal()['phase'],'applied'); self.f.preserved()
    def test_final_engine_context_exit_bootstrap_drift_refuses_apply_and_rollback_success(self):
        for action in ('apply','rollback'):
            f=Fixture(); self.addCleanup(f.close)
            if action=='rollback': self.assertEqual(f.apply()[0],0)
            previous=f.m.locked
            @contextlib.contextmanager
            def changed_at_exit():
                with previous() as check:
                    yield check
                    f.foreign('lib/bootstrap.php')
            with mock.patch.object(f.m,'locked',changed_at_exit):
                code,text=f.apply() if action=='apply' else f.cli('rollback','--session',f.session().name)
            self.assertEqual(code,1,text); self.assertNotIn('REPAIRED ',text); self.assertNotIn('ROLLED_BACK ',text)
            self.assertIn('Code lease changed: lib/bootstrap.php',text)
            self.assertEqual(f.journal()['phase'],'applied' if action=='apply' else 'rolled_back'); f.preserved()
    def test_new_asset_same_bytes_foreign_inode_blocks_entire_explicit_rollback(self):
        self.assertEqual(self.f.apply()[0],0); path='member/workspace.js'; foreign=self.f.foreign(path)
        prior={target:identity(self.f.app/target) for target in self.f.m.PATHS}; journal=identity(self.f.session()/'journal.json')
        code,text=self.f.cli('rollback','--session',self.f.session().name); self.assertEqual(code,1); self.assertNotIn('ROLLED_BACK ',text)
        self.assertEqual(identity(self.f.app/path),foreign)
        for target,value in prior.items(): self.assertEqual(identity(self.f.app/target),value)
        self.assertEqual(identity(self.f.session()/'journal.json'),journal); self.f.preserved()
    def test_completed_deleted_and_restored_consumers_reappearing_keep_their_providers(self):
        for path in ('member/work.php','member/index.php'):
            f=Fixture(); self.addCleanup(f.close); self.assertEqual(f.apply()[0],0)
            journal=f.m.journal; injected=[False]; foreign=[None]
            def changed(session,value):
                result=journal(session,value)
                if value['phase']=='rolling_back' and value['files'][path]['installed'] is None and value['intent'] is None and not injected[0]:
                    injected[0]=True; foreign[0]=f.foreign(path,(HERE/'evidence/after'/path).read_bytes())
                return result
            with mock.patch.object(f.m,'journal',side_effect=changed): code,text=f.cli('rollback','--session',f.session().name)
            self.assertTrue(injected[0]); self.assertEqual(code,1,text); self.assertNotIn('ROLLED_BACK ',text)
            self.assertEqual(identity(f.app/path),foreign[0]); value=f.journal(); self.assertEqual(value['phase'],'manual_review')
            self.assertIn(path,value['uncertain'])
            for provider in ('lib/bootstrap.php','lib/team-workspace.php','api/team-workspace.php'):
                self.assertIsNotNone(value['files'][provider]['installed'],provider); f.m.verify_lease(provider,value['files'][provider]['installed'])
            f.preserved()
    def test_future_uninstalled_foreign_consumer_during_apply_keeps_installed_providers(self):
        journal=self.f.m.journal; path='member/index.php'; injected=[False]; foreign=[None]
        def changed(session,value):
            result=journal(session,value)
            if value['phase']=='applying' and value['files']['lib/payroll.php']['installed'] is not None and value['files'][path]['installed'] is None and value['intent'] is None and not injected[0]:
                injected[0]=True; foreign[0]=self.f.foreign(path,(HERE/'evidence/after'/path).read_bytes())
            return result
        with mock.patch.object(self.f.m,'journal',side_effect=changed): code,text=self.f.apply()
        self.assertTrue(injected[0]); self.assertEqual(code,1,text); self.assertIn('manual review',text)
        self.assertEqual(identity(self.f.app/path),foreign[0]); value=self.f.journal(); self.assertEqual(value['phase'],'manual_review')
        for provider in ('lib/bootstrap.php','lib/team-workspace.php','lib/payroll.php'):
            self.assertIsNotNone(value['files'][provider]['installed'],provider); self.f.m.verify_lease(provider,value['files'][provider]['installed'])
        self.f.preserved()
    def test_reappeared_consumer_after_provider_restore_intent_is_caught_before_unlink(self):
        self.assertEqual(self.f.apply()[0],0); journal=self.f.m.journal; path='member/work.php'; injected=[False]; foreign=[None]
        def changed(session,value):
            result=journal(session,value)
            if value['phase']=='rolling_back' and value['intent']=='api/team-workspace.php' and not injected[0]:
                self.assertIsNone(value['files'][path]['installed']); injected[0]=True
                foreign[0]=self.f.foreign(path,(HERE/'evidence/after'/path).read_bytes())
            return result
        with mock.patch.object(self.f.m,'journal',side_effect=changed): code,text=self.f.cli('rollback','--session',self.f.session().name)
        self.assertTrue(injected[0]); self.assertEqual(code,1,text); self.assertNotIn('ROLLED_BACK ',text)
        self.assertEqual(identity(self.f.app/path),foreign[0]); value=self.f.journal(); self.assertEqual(value['phase'],'manual_review')
        for provider in ('lib/bootstrap.php','lib/team-workspace.php','api/team-workspace.php'):
            self.assertIsNotNone(value['files'][provider]['installed'],provider); self.f.m.verify_lease(provider,value['files'][provider]['installed'])
        self.f.preserved()
    def test_first_new_provider_link_uncertainty_retains_bootstrap_and_intent(self):
        link=self.f.m.no_clobber_link; path=next(path for path in self.f.m.PATHS if self.f.before[path] is None)
        def changed(*args,**kwargs): link(*args,**kwargs); raise OSError('Synthetic ambiguous provider link')
        with mock.patch.object(self.f.m,'no_clobber_link',side_effect=changed): code,text=self.f.apply()
        self.assertEqual(code,1); self.assertIn('manual review',text); value=self.f.journal(); self.assertEqual(value['phase'],'manual_review')
        self.assertIn(path,value['uncertain']); self.assertIsNone(value['files'][path]['installed']); self.assertEqual((self.f.app/path).stat().st_nlink,2)
        self.assertIsNotNone(value['files']['lib/bootstrap.php']['installed']); self.f.m.verify_lease('lib/bootstrap.php',value['files']['lib/bootstrap.php']['installed']); self.f.preserved()
    def test_raced_in_api_route_is_not_overwritten(self):
        link=self.f.m.no_clobber_link; path='api/team-workspace.php'; foreign=[]
        def changed(source,target,**kwargs):
            if target=='team-workspace.php':
                (self.f.app/path).write_bytes(b'<?php // concurrent route stays\n'); (self.f.app/path).chmod(0o644); foreign.append(identity(self.f.app/path))
            return link(source,target,**kwargs)
        with mock.patch.object(self.f.m,'no_clobber_link',side_effect=changed): code,text=self.f.apply()
        self.assertEqual(code,1); self.assertEqual(identity(self.f.app/path),foreign[0]); self.assertIn('manual review',text); self.f.preserved()
    def test_uncertain_final_account_consumer_retains_all_installed_providers(self):
        replace=self.f.m.replace; index=self.f.m.PATHS.index('member/index.php')
        def changed(source,target,**kwargs):
            result=replace(source,target,**kwargs)
            if source=='stage-'+str(index)+'.code': raise OSError('Synthetic ambiguous account replacement')
            return result
        with mock.patch.object(self.f.m,'replace',side_effect=changed): code,text=self.f.apply()
        self.assertEqual(code,1); self.assertIn('manual review',text); value=self.f.journal()
        for path in ('lib/bootstrap.php','lib/payroll.php','lib/team-workspace.php','member/work.php'):
            self.assertIsNotNone(value['files'][path]['installed'],path); self.f.m.verify_lease(path,value['files'][path]['installed'])
        self.f.preserved()
    def test_prerequisite_drift_before_rollback_makes_no_code_or_journal_changes(self):
        self.assertEqual(self.f.apply()[0],0); path=next(iter(self.f.w.PREREQUISITES)); self.f.foreign(path,b'<?php // unrecognized core change\n')
        prior={target:identity(self.f.app/target) for target in self.f.m.PATHS}; journal=identity(self.f.session()/'journal.json')
        code,text=self.f.cli('rollback','--session',self.f.session().name); self.assertEqual(code,1); self.assertNotIn('ROLLED_BACK ',text)
        for target,value in prior.items(): self.assertEqual(identity(self.f.app/target),value)
        self.assertEqual(identity(self.f.session()/'journal.json'),journal); self.f.preserved(path)
    def test_missing_api_parent_refuses_without_creating_live_directory_or_backup(self):
        (self.f.app/'api').rmdir(); code,text=self.f.cli('apply'); self.assertEqual(code,1)
        self.assertFalse((self.f.app/'api').exists()); self.assertFalse(self.f.m.BACKUPS.exists()); self.f.preserved()
    def test_fixed_environment_cannot_override_roots_targets_or_config(self):
        with mock.patch.dict(os.environ,{'KCMC_APP_ROOT':'/tmp/forged','KCMC_PRIVATE_DATA_DIR':'/tmp/records','KCMC_UID':'0'}):
            w=wrapper(); m=w.load_engine(); self.assertEqual(m.APP,Path('/home/bobsome1/public_html/kcmc-connect'))
            self.assertEqual(m.BACKUPS,Path('/home/bobsome1/kcmc-team-payroll-backups')); self.assertEqual((m.UID,m.GID),(2162,2147))
            self.assertEqual((len(m.PATHS),len(w.PREREQUISITES)),(23,15)); self.assertEqual(m.PATHS[0],'lib/bootstrap.php')
            self.assertFalse(set(m.PATHS)&set(w.PREREQUISITES)); self.assertNotIn('config.php',m.PATHS); self.assertNotIn('config.example.php',m.PATHS)


class ProvenanceTests(unittest.TestCase):
    def test_exact_inputs_targets_and_optional_git_membership(self):
        raw,extension,source,runtime,prerequisites,core=derive.verify_inputs(allow_unapproved=CANDIDATE)
        if RUNTIME_ROOT is not None:
            for path in source['paths']: self.assertEqual((HERE/'evidence/after'/path).read_bytes(),(RUNTIME_ROOT/path).read_bytes())
            for path,row in prerequisites.items(): self.assertEqual(sha((RUNTIME_ROOT/path).read_bytes()),row['sha256'])
        if GIT_ROOT is not None:
            source_ref=derive.SOURCE_COMMIT if derive.SOURCE_COMMIT is not None else CANDIDATE_SOURCE
            self.assertIsNotNone(source_ref,'Candidate Git proof requires its actual source object')
            for path,row in runtime.items():
                object_path=':KCMC-Connect-Phase6-Recreated/'+path
                target=subprocess.check_output(['git','show',source_ref+object_path],cwd=str(GIT_ROOT))
                self.assertEqual(target,(HERE/'evidence/after'/path).read_bytes())
                if row['before_sha256'] is None:
                    absent=subprocess.call(['git','cat-file','-e',derive.BASE_COMMIT+object_path],cwd=str(GIT_ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    self.assertNotEqual(absent,0,path)
                else:
                    before=subprocess.check_output(['git','show',derive.BASE_COMMIT+object_path],cwd=str(GIT_ROOT))
                    self.assertEqual(before,(HERE/'evidence/before'/path).read_bytes())
            for path,row in core.items():
                before=subprocess.check_output(['git','show',derive.BASE_COMMIT+':KCMC-Connect-Phase6-Recreated/'+path],cwd=str(GIT_ROOT))
                self.assertEqual((sha(before),len(before)),(row['sha256'],row['bytes']))
            for path,row in prerequisites.items():
                target=subprocess.check_output(['git','show',source_ref+':KCMC-Connect-Phase6-Recreated/'+path],cwd=str(GIT_ROOT))
                self.assertEqual((sha(target),len(target)),(row['sha256'],row['bytes']))
    def test_reproducible_installer_and_provenance(self):
        with tempfile.TemporaryDirectory(prefix='kcmc-team-payroll-rederive-') as directory:
            copied=Path(directory)/'package'; shutil.copytree(str(HERE),str(copied))
            command=[sys.executable,'-B','-c','import derive_installer as d; d.build(candidate=True)'] if CANDIDATE else [sys.executable,'-B','derive_installer.py']
            subprocess.check_call(command,cwd=str(copied))
            for name in (INSTALLER,PROVENANCE): self.assertEqual((HERE/name).read_bytes(),(copied/name).read_bytes(),name)
    def test_foundation_and_extension_are_identical_to_reviewed_pins(self):
        self.assertEqual(sha((HERE/'frozen-minimal-installer.py').read_bytes()),derive.FROZEN_SHA256)
        self.assertEqual(sha((HERE/'extension.py').read_bytes()),derive.EXTENSION_SHA256)
        self.assertEqual(sha((HERE/'frozen-workflows-extension.py').read_bytes()),derive.FROZEN_EXTENSION_SHA256)


if __name__=='__main__': unittest.main()
