#!/usr/bin/env python3
"""Exact approved variants and transaction composition; temporary files only."""
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
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import derive_installer

HERE=Path(__file__).resolve().parent
RUNTIME_ROOT=None
if '--runtime-root' in sys.argv:
    index=sys.argv.index('--runtime-root');RUNTIME_ROOT=Path(sys.argv[index+1]);del sys.argv[index:index+2]
COMMITS={'live154':'154b779a0ea3d27a11300bfe0454f8a7c4aca355','main130':'1af697ac828724a74ba15f9c7167f09b45e35f89'}
def module():
    spec=importlib.util.spec_from_file_location('isolated_fish_wrapper',str(HERE/'installer.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
def sha(data):
    return hashlib.sha256(data).hexdigest()
def identity(path):
    info=path.lstat()
    return (info.st_dev,info.st_ino,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink,info.st_size)
def source(variant,path):
    fixture=HERE/'evidence'/variant/path
    if fixture.exists():
        return fixture.read_bytes()
    return subprocess.check_output(['git','show',COMMITS[variant]+':KCMC-Connect-Phase6-Recreated/'+path],cwd=str(HERE))

class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kcmc-fish-variant-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.app=self.root/'app';self.app.mkdir()
        self.w=module();self.engines=self.w.load_engines()
        for variant,m in self.engines.items():
            m.APP=self.app;m.BACKUPS=self.root/('private-'+variant);m.UID=os.getuid();m.GID=os.getgid()
        self.sentinels={'config.php':b'<?php // owner config untouched\n','data/content.json':b'{"owner":"editorial"}',
                        'data/private/users.json':b'{"owner":"users"}', '.git/HEAD':b'ref: refs/heads/main\n','app.js':b'// another repair untouched\n'}
        for path,data in self.sentinels.items():
            p=self.app/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(0o600)
        self.sentinel_ids={p:identity(self.app/p) for p in self.sentinels}
        self.install_before('live154')
    def install_before(self,variant):
        for path in self.engines[variant].PATHS:
            p=self.app/path;p.write_bytes(source(variant,path));p.chmod(0o644)
    def assert_sentinels(self):
        for path,data in self.sentinels.items():
            self.assertEqual((self.app/path).read_bytes(),data);self.assertEqual(identity(self.app/path),self.sentinel_ids[path])
    def run_cli(self,*args):
        output=io.StringIO()
        with mock.patch.object(self.w,'load_engines',return_value=self.engines),mock.patch.object(sys,'argv',['installer.py']+list(args)),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            code=self.w.main()
        self.assert_sentinels();return code,output.getvalue()
    def fake_lint(self,command,**kwargs):
        self.assertEqual(command[0],'/opt/cpanel/ea-php82/root/usr/bin/php')
        if command[2]=='-v':return b'PHP 8.2.34 (cli)\n'
        self.assertEqual(command[1:3],['-n','-l'])
        self.assertTrue(command[3].endswith('stage-0.code'))
        return b'No syntax errors detected\n'
    def apply(self):
        with mock.patch.object(subprocess,'check_output',side_effect=self.fake_lint) as called:
            code,output=self.run_cli('apply')
        self.assertEqual(code,0,output);return output,called.call_args_list
    def test_default_check_readonly_selects_live154(self):
        original={p:identity(self.app/p) for p in self.engines['live154'].PATHS}
        code,text=self.run_cli();self.assertEqual(code,0);self.assertIn('VARIANT live154',text);self.assertIn('CHECK READY',text)
        for p,i in original.items():self.assertEqual(identity(self.app/p),i)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
    def test_both_known_variants_apply_noop_and_explicit_rollback(self):
        for variant in self.w.VARIANTS:
            self.install_before(variant);m=self.engines[variant]
            originals={p:(self.app/p).read_bytes() for p in m.PATHS}
            (self.app/'public-presentation.css').chmod(0o664)
            text,calls=self.apply();self.assertIn('VARIANT '+variant,text);self.assertEqual(len(calls),2)
            session=sorted(m.BACKUPS.glob('repair-*'))[-1]
            for p in m.PATHS:self.assertEqual(sha((self.app/p).read_bytes()),m.FILES[p]['after_sha256'])
            self.assertEqual(stat.S_IMODE((self.app/'public-presentation.css').stat().st_mode),0o664)
            installed={p:identity(self.app/p) for p in m.PATHS};text,calls=self.apply();self.assertIn('ALREADY_REPAIRED',text);self.assertEqual(calls,[])
            for p,i in installed.items():self.assertEqual(identity(self.app/p),i)
            code,text=self.run_cli('rollback','--variant',variant,'--session',session.name);self.assertEqual(code,0,text)
            for p,data in originals.items():self.assertEqual((self.app/p).read_bytes(),data)
    def test_mixed_old_variants_refused_without_backups(self):
        (self.app/'public-presentation.css').write_bytes(source('main130','public-presentation.css'))
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertIn('Unknown or mixed',text)
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
    def test_original_pinned_wrapper_refuses_exact_host_bundle_new_wrapper_accepts(self):
        self.install_before('livecalendar')
        raw=(HERE/'provenance/frozen-fish-oct14-installer.py').read_bytes()
        self.assertEqual(sha(raw),'1c2104c6607d9a5e235c4cb63ba5ae717509ee6d22df289c2c12bc79a49c50ea')
        spec=importlib.util.spec_from_file_location('original_reviewed_fish',str(HERE/'provenance/frozen-fish-oct14-installer.py'))
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        before={path:identity(self.app/path) for path in self.engines['livecalendar'].PATHS}
        with self.assertRaisesRegex(old.Refusal,'Unknown or mixed'):
            old.select({variant:self.engines[variant] for variant in old.VARIANTS})
        for path,value in before.items():self.assertEqual(identity(self.app/path),value)
        variant,state,unused=self.w.select(self.engines)
        self.assertEqual((variant,state),('livecalendar','before'))
        self.apply()
        for path,item in self.engines['livecalendar'].FILES.items():
            self.assertEqual(sha((self.app/path).read_bytes()),item['after_sha256'])
        self.assert_sentinels()
    def test_only_three_exact_before_combinations_are_accepted(self):
        known={('live154','live154','live154'):'live154',('main130','main130','main130'):'main130',
               ('livecalendar','live154','live154'):'livecalendar'}
        paths=self.engines['livecalendar'].PATHS
        for combination in itertools.product(self.w.VARIANTS,('live154','main130'),('live154','main130')):
            with self.subTest(combination=combination):
                for path,variant in zip(paths,combination):
                    (self.app/path).write_bytes(source(variant,path))
                if combination in known:
                    variant,state,unused=self.w.select(self.engines)
                    self.assertEqual((variant,state),(known[combination],'before'))
                else:
                    with self.assertRaisesRegex(self.w.Refusal,'Unknown or mixed'):
                        self.w.select(self.engines)
                self.assert_sentinels()
        self.assertTrue(all(not m.BACKUPS.exists() for m in self.engines.values()))
    def test_new_variant_backup_journal_cannot_be_bypassed(self):
        self.install_before('livecalendar');m=self.engines['livecalendar']
        with mock.patch.object(m,'move_code',side_effect=OSError('Synthetic uncertain boundary')),mock.patch.object(subprocess,'check_output',side_effect=self.fake_lint):
            code,text=self.run_cli('apply')
        self.assertEqual(code,1);self.install_before('live154')
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertIn('Unfinished repair',text)
    def test_diagnostic_reasons_explain_hashes_without_source_or_raw_errors(self):
        for name in self.engines['live154'].PATHS:(self.app/name).write_bytes(b'UNAPPROVED_SOURCE_MARKER')
        code,text=self.run_cli('check');self.assertEqual(code,1)
        self.assertIn('livecalendar: Unknown code bytes: index.php',text)
        self.assertNotIn('UNAPPROVED_SOURCE_MARKER',text)
        with mock.patch.object(self.engines['livecalendar'],'inspect',side_effect=self.engines['livecalendar'].Refusal('RAW_SECRET_ERROR_MARKER')):
            code,text=self.run_cli('check')
        self.assertEqual(code,1);self.assertIn('Read-only preflight guard refused',text);self.assertNotIn('RAW_SECRET_ERROR_MARKER',text)
    def test_partial_before_after_bundle_refused(self):
        m=self.engines['live154'];p='sw.js';(self.app/p).write_bytes(m.repair(p,(self.app/p).read_bytes()))
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertIn('Unknown or mixed',text)
    def test_unknown_owner_edit_is_preserved(self):
        p=self.app/'index.php';data=p.read_bytes()+b'<!-- owner change -->';p.write_bytes(data);meta=identity(p)
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertEqual(p.read_bytes(),data);self.assertEqual(identity(p),meta)
    def test_wrong_user_refused_without_inspection(self):
        for m in self.engines.values():m.UID+=1
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertIn('hosting account',text)
    def test_symlink_file_refused_without_changes(self):
        p=self.app/'sw.js';p.rename(self.root/'outside-sw.js');p.symlink_to(self.root/'outside-sw.js')
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertTrue(p.is_symlink())
    def test_other_variant_unsafe_backup_refused_before_apply(self):
        self.engines['main130'].BACKUPS.mkdir(mode=0o755);self.engines['main130'].BACKUPS.chmod(0o755)
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertIn('owner/group/mode',text)
    def test_php_lint_failure_preserves_all_three_files(self):
        originals={p:(self.app/p).read_bytes() for p in self.engines['live154'].PATHS}
        with mock.patch.object(subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,['php'])):
            code,text=self.run_cli('apply')
        self.assertEqual(code,1);self.assertIn('no live replacement',text)
        for p,data in originals.items():self.assertEqual((self.app/p).read_bytes(),data)
    def test_wrong_php_version_refused(self):
        with mock.patch.object(subprocess,'check_output',return_value=b'PHP 8.3.0\n'):
            code,text=self.run_cli('apply')
        self.assertEqual(code,1);self.assertIn('no live replacement',text)
    def test_failure_after_first_commit_restores_only_owned_files(self):
        m=self.engines['live154'];originals={p:(self.app/p).read_bytes() for p in m.PATHS};journal=m.journal;failed=[False]
        def fail(session,value):
            if not failed[0] and value['files']['index.php']['installed'] and value['intent'] is None:
                failed[0]=True;raise OSError('Synthetic checkpoint failure')
            return journal(session,value)
        with mock.patch.object(m,'journal',side_effect=fail),mock.patch.object(subprocess,'check_output',side_effect=self.fake_lint):
            code,text=self.run_cli('apply')
        self.assertEqual(code,1);self.assertIn('verified owned code restored',text)
        for p,data in originals.items():self.assertEqual((self.app/p).read_bytes(),data)
    def test_incomplete_other_variant_journal_blocks_known_apply(self):
        m=self.engines['main130'];self.install_before('main130')
        with mock.patch.object(m,'move_code',side_effect=OSError('synthetic uncertain replacement')),mock.patch.object(subprocess,'check_output',side_effect=self.fake_lint):
            code,text=self.run_cli('apply')
        self.assertEqual(code,1);self.install_before('live154')
        code,text=self.run_cli('apply');self.assertEqual(code,1);self.assertIn('Unfinished repair',text)
    def test_rollback_cannot_override_private_record_scope(self):
        text,unused=self.apply();m=self.engines['live154'];session=next(m.BACKUPS.glob('repair-*'))
        code,text=self.run_cli('rollback','--variant','main130','--session',session.name);self.assertEqual(code,1)
        for p in m.PATHS:self.assertEqual(sha((self.app/p).read_bytes()),m.FILES[p]['after_sha256'])
    def test_embedded_tamper_refused_before_any_definitions(self):
        self.w.EMBEDDED['live154'][0]+='\n# unexpected source\n'
        with mock.patch.object(self.w,'types') as typed:
            with self.assertRaises(self.w.Refusal):self.w.load_engines()
            self.assertFalse(typed.ModuleType.called)
    def test_cli_session_and_variant_overrides_refused(self):
        for args in [('apply','--variant','live154'),('check','--session','bad'),('rollback',),('rollback','--variant','live154')]:
            code,text=self.run_cli(*args);self.assertEqual(code,1)

class ProvenanceTests(unittest.TestCase):
    def test_host_index_reconstructs_from_frozen_calendar_patch_and_git154_source(self):
        self.assertEqual(derive_installer.verify_livecalendar_preimage(),source('livecalendar','index.php'))
        self.assertEqual(len(source('livecalendar','index.php')),33550)
        self.assertEqual(sha(source('livecalendar','index.php')),'745bdc1f31824b8962ef49440a83e313dbdea70e4a8e0620ff746049f656df3d')
    def test_older_engines_remain_byte_for_byte_pinned(self):
        raw=(HERE/'provenance/frozen-fish-oct14-installer.py').read_bytes()
        self.assertEqual(sha(raw),'1c2104c6607d9a5e235c4cb63ba5ae717509ee6d22df289c2c12bc79a49c50ea')
        tree=ast.parse(raw.decode('utf-8'))
        old=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='EMBEDDED' for target in node.targets))
        new=module().EMBEDDED
        for variant in ('live154','main130'):self.assertEqual(old[variant],new[variant])
    @unittest.skipIf(RUNTIME_ROOT is None,'Pass --runtime-root to compare the main output with the exact application candidate')
    def test_main_output_equals_reviewed_application(self):
        m=module().load_engines()['main130']
        for path in m.PATHS:
            self.assertEqual(m.repair(path,source('main130',path)),(RUNTIME_ROOT/path).read_bytes())
    def test_frozen_exact_engine_derivation_and_python36_parse(self):
        w=module();runtime=json.loads((HERE/'runtime-reviewed.json').read_text());raw=(HERE/'provenance/frozen-minimal-installer.py').read_bytes()
        self.assertEqual(sha(raw),derive_installer.ENGINE_SHA256)
        for variant in w.VARIANTS:
            source_text,expected=w.EMBEDDED[variant]
            self.assertEqual(derive_installer.derive_engine(raw,variant,runtime[variant]),source_text)
            self.assertEqual(sha(source_text.encode('utf-8')),expected);ast.parse(source_text)
    def test_pinned_variants_reconstruct_exact_outputs_preserving_unrelated_source(self):
        w=module();engines=w.load_engines()
        for variant,m in engines.items():
            self.assertEqual(m.PATHS,('index.php','public-presentation.css','sw.js'));self.assertEqual((m.UID,m.GID),(2162,2147))
            for p in m.PATHS:
                before=source(variant,p);after=m.repair(p,before)
                self.assertEqual(sha(before),m.FILES[p]['before_sha256']);self.assertEqual(sha(after),m.FILES[p]['after_sha256'])
                restored=after
                for old,new in reversed(m.FILES[p]['replacements']):
                    # Empty removals can only be reconstructed at source review; exact
                    # original backups handle transaction rollback, not text guessing.
                    if new:restored=restored.replace(new.encode('utf-8'),old.encode('utf-8'),1)
                if p=='index.php':
                    self.assertNotIn(b'phase6-announcement',after);self.assertNotIn(b'class="mobile-nav"',after);self.assertNotIn(b'phase6-bulletin-fab',after)
                    self.assertIn(b'Announcements &amp; church updates',after)
                    self.assertEqual(b"require_once __DIR__ . '/lib/event-calendar.php';" in after,variant in ('main130','livecalendar'))
                    self.assertEqual(after[after.index(b'<section class="view" data-view="news">'):after.index(b'</main>')],before[before.index(b'<section class="view" data-view="news">'):before.index(b'</main>')])
                if p=='sw.js':self.assertIn(b'public-only-fish-home-20261014',after);self.assertIn(b'fish-only-home-20261014',after)
    def test_wrapper_derivation_exact(self):
        w=module();raw=(HERE/'wrapper.py.in').read_text().replace('# EMBEDDED_ENGINES','EMBEDDED = '+repr(w.EMBEDDED))
        self.assertEqual(raw,(HERE/'installer.py').read_text())

if __name__=='__main__':
    unittest.main()
