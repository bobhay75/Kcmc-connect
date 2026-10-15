#!/usr/bin/env python3
"""Exact four-file session transactions on temporary synthetic trees only."""
from __future__ import print_function
import ast
import contextlib
import copy
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

HERE=Path(__file__).resolve().parent
RUNTIME_ROOT=None
GIT_ROOT=None
if '--runtime-root' in sys.argv:
    i=sys.argv.index('--runtime-root');RUNTIME_ROOT=Path(sys.argv[i+1]);del sys.argv[i:i+2]
if '--git-root' in sys.argv:
    i=sys.argv.index('--git-root');GIT_ROOT=Path(sys.argv[i+1]);del sys.argv[i:i+2]

def wrapper():
    spec=importlib.util.spec_from_file_location('isolated_session_wrapper',str(HERE/'installer.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def sha(data):return hashlib.sha256(data).hexdigest()
def identity(path):
    info=path.lstat()
    return (info.st_dev,info.st_ino,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink,info.st_size)

class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kcmc-session-four-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.app=self.root/'app';self.app.mkdir()
        self.w=wrapper();self.engines=self.w.load_engines();self.real_choose=self.w.choose_php82_cli
        self.selection=mock.patch.object(self.w,'choose_php82_cli',return_value=('/opt/alt/php82/usr/bin/php','8.2.34'))
        self.selected=self.selection.start();self.addCleanup(self.selection.stop)
        for variant,module in self.engines.items():
            module.APP=self.app;module.BACKUPS=self.root/('private-'+variant);module.UID=os.getuid();module.GID=os.getgid()
        self.sentinels={'config.php':b'<?php // owner configuration retained\n','data/content.json':b'{"synthetic":"editorial retained"}',
            'data/private/users.json':b'{"synthetic":"accounts retained"}','data/private/prayers.json':b'{"synthetic":"private prayers retained"}',
            'data/private/timeclock.json':b'{"synthetic":"timecards retained"}','.git/HEAD':b'ref: refs/heads/main\n',
            'index.php':b'<?php // fish homepage retained\n','public-presentation.css':b'/* fish retained */\n','sw.js':b'// fish worker retained\n',
            'member/activate.php':b'<?php // separate token repair retained\n','member/reset-password.php':b'<?php // separate reset repair retained\n',
            'lib/timeclock.php':b'<?php // separate timecard repair retained\n','app.js':b'// separate skip-link repair retained\n'}
        for path,data in self.sentinels.items():
            file=self.app/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data);file.chmod(0o600)
        self.sentinel_ids={path:identity(self.app/path) for path in self.sentinels}
        self.seed('live154')
    def seed(self,variant):
        for path in self.engines[variant].PATHS:
            file=self.app/path;file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes((HERE/'evidence'/variant/path).read_bytes());file.chmod(0o644)
    def sentinels_unchanged(self):
        for path,data in self.sentinels.items():
            self.assertEqual((self.app/path).read_bytes(),data,path);self.assertEqual(identity(self.app/path),self.sentinel_ids[path],path)
    def cli(self,*args):
        output=io.StringIO()
        with mock.patch.object(self.w,'load_engines',return_value=self.engines),mock.patch.object(sys,'argv',['installer.py']+list(args)),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            result=self.w.main()
        self.sentinels_unchanged();return result,output.getvalue()
    def fake_php(self,argv,**kwargs):
        self.assertEqual(argv[0],'/opt/alt/php82/usr/bin/php');self.assertEqual(argv[1],'-n')
        if argv[2]=='-v':return b'PHP 8.2.34 (cli)\n'
        self.assertEqual(argv[2],'-l');self.assertIn(Path(argv[3]).name,['stage-'+str(i)+'.code' for i in range(4)])
        return b'No syntax errors detected\n'
    def apply(self):
        with mock.patch.object(subprocess,'check_output',side_effect=self.fake_php) as call:
            code,text=self.cli('apply')
        self.assertEqual(code,0,text);return text,call.call_args_list
    def test_default_check_is_readonly_and_dependency_order_exact(self):
        before={p:identity(self.app/p) for p in derive.PATHS}
        code,text=self.cli();self.assertEqual(code,0,text);self.assertIn('CHECK READY',text)
        self.assertEqual(self.engines['live154'].PATHS,derive.PATHS)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
        for path,old in before.items():self.assertEqual(identity(self.app/path),old)
    def test_variants_apply_lint_all_four_preserve_modes_noop_rollback(self):
        for variant in self.w.VARIANTS:
            self.seed(variant);module=self.engines[variant];originals={p:(self.app/p).read_bytes() for p in derive.PATHS}
            (self.app/'member/password.php').chmod(0o664)
            text,calls=self.apply();self.assertIn('VARIANT '+variant,text);self.assertEqual(len(calls),5)
            self.assertEqual([Path(call[0][0][3]).name for call in calls[1:]],['stage-'+str(i)+'.code' for i in range(4)])
            session=next(module.BACKUPS.glob('repair-*'))
            for p in derive.PATHS:self.assertEqual(sha((self.app/p).read_bytes()),module.FILES[p]['after_sha256'])
            self.assertEqual(stat.S_IMODE((self.app/'member/password.php').stat().st_mode),0o664)
            installed={p:identity(self.app/p) for p in derive.PATHS}
            text,calls=self.apply();self.assertIn('ALREADY_REPAIRED',text);self.assertEqual(calls,[])
            for p,old in installed.items():self.assertEqual(identity(self.app/p),old)
            code,text=self.cli('rollback','--variant',variant,'--session',session.name);self.assertEqual(code,0,text)
            for p,data in originals.items():self.assertEqual((self.app/p).read_bytes(),data)
    def test_only_four_complete_before_after_tuples_accepted(self):
        runtime=json.loads((HERE/'runtime-reviewed.json').read_text())
        bootstraps={}
        for variant in self.w.VARIANTS:
            before=(HERE/'evidence'/variant/'lib/bootstrap.php').read_bytes()
            bootstraps[(variant,'before')]=before
            bootstraps[(variant,'after')]=self.engines[variant].repair('lib/bootstrap.php',before)
        paths=('lib/session-lifetime.php','member/login.php','member/password.php')
        accepted=0;refused=0
        for (variant,bootstrap_state),states in itertools.product(bootstraps,itertools.product(('before','after'),repeat=3)):
            (self.app/'lib/bootstrap.php').write_bytes(bootstraps[(variant,bootstrap_state)])
            for path,state in zip(paths,states):
                before=(HERE/'evidence'/variant/path).read_bytes()
                (self.app/path).write_bytes(before if state=='before' else self.engines[variant].repair(path,before))
            if set(states)=={bootstrap_state}:
                selected,state,unused=self.w.select(self.engines);self.assertEqual((selected,state),(variant,bootstrap_state));accepted+=1
            else:
                with self.assertRaisesRegex(self.w.Refusal,'Unknown or mixed'):self.w.select(self.engines)
                refused+=1
        self.assertEqual((accepted,refused),(4,28));self.sentinels_unchanged()
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
    def test_unknown_code_refused_then_diagnose_emits_hashes_only(self):
        (self.app/'lib/bootstrap.php').write_bytes(b'<?php // unknown later host code\n')
        before={p:identity(self.app/p) for p in derive.PATHS}
        code,text=self.cli('apply');self.assertEqual(code,1);self.assertIn('Use diagnose',text)
        self.selected.side_effect=AssertionError('Diagnostic must not probe PHP')
        code,text=self.cli('diagnose');self.assertEqual(code,0,text);self.assertEqual(text.count('CODE '),4)
        self.assertIn(sha((self.app/'lib/bootstrap.php').read_bytes()),text);self.assertNotIn('unknown later host code',text)
        for data in self.sentinels.values():self.assertNotIn(data.decode().strip(),text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
        for p,old in before.items():self.assertEqual(identity(self.app/p),old)
    def test_diagnose_linked_code_refused_without_reading_target(self):
        target=self.app/'lib/bootstrap.php';target.unlink();target.symlink_to(self.app/'config.php')
        code,text=self.cli('diagnose');self.assertEqual(code,1);self.assertNotIn('owner configuration',text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
    def test_php_discovery_precedes_backup_and_rejects_non_cli(self):
        self.selected.side_effect=self.real_choose
        candidates=['/not-a-runtime','/php-cgi','/wrong-version','/right-cli'];self.w.php82_candidates=lambda:candidates
        calls=[]
        def version(argv,**kwargs):
            self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()));calls.append(argv[0])
            if argv[0]==candidates[0]:raise FileNotFoundError(2,'synthetic absent path')
            return {'/php-cgi':b'PHP 8.2.34 (cgi-fcgi)\n','/wrong-version':b'PHP 8.3.12 (cli)\n','/right-cli':b'PHP 8.2.34 (cli) (built: synthetic)\n'}[argv[0]]
        with mock.patch.object(subprocess,'check_output',side_effect=version):code,text=self.cli('check')
        self.assertEqual(code,0,text);self.assertEqual(calls,candidates);self.assertIn('PHP_CLI /right-cli PHP 8.2.34',text)
    def test_no_runtime_refused_without_any_backup(self):
        self.selected.side_effect=self.w.Refusal('No compatible PHP 8.2 CLI found; no backup or live replacement made')
        for action in ('check','apply'):
            code,text=self.cli(action);self.assertEqual(code,1);self.assertNotIn('CHECK READY',text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
    def test_lint_failure_on_fourth_stage_keeps_live_preimages(self):
        before={p:identity(self.app/p) for p in derive.PATHS}
        def failed(argv,**kwargs):
            if argv[-1].endswith('stage-3.code'):raise subprocess.CalledProcessError(255,argv)
            return self.fake_php(argv,**kwargs)
        with mock.patch.object(subprocess,'check_output',side_effect=failed):code,text=self.cli('apply')
        self.assertEqual(code,1);self.assertIn('no live replacement',text)
        module=self.engines['live154'];session=next(module.BACKUPS.glob('repair-*'));value=module.load(session)
        self.assertEqual((value['phase'],value['intent'],value['uncertain']),('rolled_back',None,[]))
        self.assertTrue(all(value['files'][p]['installed'] is None for p in derive.PATHS))
        for p,old in before.items():self.assertEqual(identity(self.app/p),old)
    def test_another_variants_unfinished_journal_cannot_be_bypassed(self):
        other=self.engines['main93'];self.seed('main93');other.PHP='/opt/alt/php82/usr/bin/php'
        with mock.patch.object(subprocess,'check_output',side_effect=self.fake_php):session=other.apply()
        value=other.load(session);value['phase']='prepared';other.journal(session,value)
        self.seed('live154')
        for action in ('check','apply'):
            code,text=self.cli(action);self.assertEqual(code,1);self.assertIn('Unfinished',text)
    def test_after_noop_does_not_probe_php(self):
        self.apply();self.selected.side_effect=AssertionError('After no-op does not need PHP')
        for action in ('check','apply'):
            code,text=self.cli(action);self.assertEqual(code,0,text);self.assertIn('ALREADY_REPAIRED',text)
    def test_later_edit_blocks_entire_explicit_rollback(self):
        self.apply();module=self.engines['live154'];session=next(module.BACKUPS.glob('repair-*'))
        (self.app/'member/login.php').write_bytes(b'<?php // later account fix\n');before={p:identity(self.app/p) for p in derive.PATHS}
        code,text=self.cli('rollback','--variant','live154','--session',session.name);self.assertEqual(code,1)
        for p,old in before.items():self.assertEqual(identity(self.app/p),old)
    def test_apply_and_rollback_dependency_order(self):
        module=self.engines['live154'];move=module.move_code;order=[]
        def recorded(*args,**kwargs):
            order.append(args[1]);return move(*args,**kwargs)
        with mock.patch.object(module,'move_code',side_effect=recorded):
            self.apply();session=next(module.BACKUPS.glob('repair-*'))
            self.assertEqual(order,list(derive.PATHS));order[:]=[]
            code,text=self.cli('rollback','--variant','live154','--session',session.name);self.assertEqual(code,0,text)
            self.assertEqual(order,list(reversed(derive.PATHS)))
        self.assertLess(derive.PATHS.index('lib/session-lifetime.php'),derive.PATHS.index('lib/bootstrap.php'))
    def uncertain_commit(self,index,alter_helper=None):
        module=self.engines['live154'];rename=module.replace
        def injected(source,target,**kwargs):
            result=rename(source,target,**kwargs)
            if source=='stage-'+str(index)+'.code':
                if alter_helper is not None:alter_helper(self.app/'lib/session-lifetime.php')
                raise OSError('Synthetic post-rename uncertainty')
            return result
        with mock.patch.object(module,'replace',side_effect=injected),mock.patch.object(subprocess,'check_output',side_effect=self.fake_php):
            code,text=self.cli('apply')
        self.assertEqual(code,1);self.assertIn('manual review',text)
        session=next(module.BACKUPS.glob('repair-*'));value=module.load(session)
        self.assertEqual(value['phase'],'manual_review');self.assertIn(derive.PATHS[index],value['uncertain'])
        self.assertIsNotNone(value['files']['lib/session-lifetime.php']['installed'])
        self.assertTrue((session/'original-0.code').exists())
        for action in ('check','apply'):
            code,text=self.cli(action);self.assertEqual(code,1);self.assertIn('Unfinished',text)
        return module,session,value
    def test_uncertain_bootstrap_retains_new_verified_helper(self):
        module,session,value=self.uncertain_commit(1)
        self.assertEqual(sha((self.app/'lib/bootstrap.php').read_bytes()),module.FILES['lib/bootstrap.php']['after_sha256'])
        self.assertEqual(sha((self.app/'lib/session-lifetime.php').read_bytes()),module.FILES['lib/session-lifetime.php']['after_sha256'])
        module.verify_lease('lib/session-lifetime.php',value['files']['lib/session-lifetime.php']['installed'])
    def test_uncertain_password_retains_helper_after_other_consumers_restore(self):
        module,session,value=self.uncertain_commit(3)
        self.assertEqual(sha((self.app/'member/password.php').read_bytes()),module.FILES['member/password.php']['after_sha256'])
        self.assertEqual(sha((self.app/'lib/bootstrap.php').read_bytes()),module.FILES['lib/bootstrap.php']['before_sha256'])
        self.assertEqual(sha((self.app/'member/login.php').read_bytes()),module.FILES['member/login.php']['before_sha256'])
        self.assertEqual(sha((self.app/'lib/session-lifetime.php').read_bytes()),module.FILES['lib/session-lifetime.php']['after_sha256'])
        module.verify_lease('lib/session-lifetime.php',value['files']['lib/session-lifetime.php']['installed'])
    def test_corrupt_helper_is_not_overwritten_or_claimed_recovered(self):
        changed=b'<?php // concurrent helper edit retained\n'
        module,session,value=self.uncertain_commit(1,lambda path:path.write_bytes(changed))
        self.assertEqual((self.app/'lib/session-lifetime.php').read_bytes(),changed)
        self.assertNotEqual(sha(changed),value['files']['lib/session-lifetime.php']['installed']['sha256'])
        self.assertEqual(value['phase'],'manual_review')
    def test_missing_helper_is_not_recreated_or_claimed_recovered(self):
        module,session,value=self.uncertain_commit(1,lambda path:path.unlink())
        self.assertFalse((self.app/'lib/session-lifetime.php').exists());self.assertEqual(value['phase'],'manual_review')
    def test_consumer_edit_during_rollback_keeps_helper_and_manual_review(self):
        self.apply();module=self.engines['live154'];session=next(module.BACKUPS.glob('repair-*'));rename=module.replace
        changed=b'<?php // concurrent consumer update retained\n'
        def injected(source,target,**kwargs):
            result=rename(source,target,**kwargs)
            if target=='password.php':(self.app/'lib/bootstrap.php').write_bytes(changed)
            return result
        with mock.patch.object(module,'replace',side_effect=injected):
            code,text=self.cli('rollback','--variant','live154','--session',session.name)
        self.assertEqual(code,1);self.assertIn('manual review',text)
        value=module.load(session);self.assertEqual(value['phase'],'manual_review')
        self.assertEqual((self.app/'lib/bootstrap.php').read_bytes(),changed)
        self.assertEqual(sha((self.app/'lib/session-lifetime.php').read_bytes()),module.FILES['lib/session-lifetime.php']['after_sha256'])
        module.verify_lease('lib/session-lifetime.php',value['files']['lib/session-lifetime.php']['installed'])

class ProvenanceTests(unittest.TestCase):
    def test_exact_literals_fixture_and_canonical_target(self):
        runtime=derive.verify_runtime();self.assertEqual(tuple(runtime),tuple(derive.COMMITS))
        for variant,files in runtime.items():
            for path,item in files.items():
                before=(HERE/'evidence'/variant/path).read_bytes();after=before
                for old,new in item['replacements']:after=after.replace(old.encode(),new.encode(),1)
                if variant=='main93' and RUNTIME_ROOT is not None:self.assertEqual(after,(RUNTIME_ROOT/path).read_bytes())
    def test_frozen_policy_has_only_reviewed_lint_and_dependency_guard_changes(self):
        raw=(HERE/'provenance/frozen-minimal-installer.py').read_bytes();self.assertEqual(sha(raw),derive.ENGINE_SHA256)
        original=ast.parse(raw.decode())
        def nodes(tree):return {node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name!='lint'}
        expected=nodes(original)
        package=wrapper()
        for source,unused in package.EMBEDDED.values():
            safe=derive.RECOVERY_SAFE.replace("+ '.php'","+ '.code'")
            original_guard=derive.RECOVERY_ANCHOR.replace("+ '.php'","+ '.code'")
            self.assertEqual(source.count(safe),1)
            source=source.replace(safe,original_guard,1)
            derived=ast.parse(source)
            actual=nodes(derived);self.assertEqual(set(actual),set(expected))
            for name,node in actual.items():
                for item in ast.walk(node):
                    attribute='value' if sys.version_info >= (3,8) else 's'
                    text=getattr(item,attribute,None)
                    if isinstance(text,str):
                        text=text.replace('the four reviewed files','the three reviewed files').replace('all four code files','all three code files')
                        setattr(item,attribute,'.php' if text=='.code' else text)
                self.assertEqual(ast.dump(node),ast.dump(expected[name]),name)
    def test_reproducible_derivation(self):
        before=(HERE/'installer.py').read_bytes();proof=(HERE/'provenance.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='kcmc-session-derive-') as temporary:
            copied=Path(temporary)/'package';shutil.copytree(str(HERE),str(copied))
            subprocess.check_call([sys.executable,'-B','derive_installer.py'],cwd=str(copied))
            self.assertEqual((copied/'installer.py').read_bytes(),before);self.assertEqual((copied/'provenance.json').read_bytes(),proof)
    def test_evidence_is_exact_approved_git_source(self):
        if GIT_ROOT is None:self.skipTest('Git source membership runs in the current-Python CI job')
        for variant,commit in derive.COMMITS.items():
            for path in derive.PATHS:
                canonical=subprocess.check_output(['git','show',commit+':KCMC-Connect-Phase6-Recreated/'+path],cwd=str(GIT_ROOT))
                self.assertEqual((HERE/'evidence'/variant/path).read_bytes(),canonical)
        canonical=subprocess.check_output(['git','show',derive.COMMITS['main93']+':tools/kcmc-scoped-release-oct13/approved-inventory.json'],cwd=str(GIT_ROOT))
        self.assertEqual((HERE/'provenance/oct13-approved-inventory.json').read_bytes(),canonical)

if __name__=='__main__':unittest.main()
