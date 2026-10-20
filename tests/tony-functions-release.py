#!/usr/bin/env python3
"""Isolated release/rollback acceptance; no host path, mail or production data access."""
from pathlib import Path
import hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,unittest,zipfile
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tony_release_builder',ROOT/'tools/kcmc-tony-functions-oct20/build.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
class Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.work=Path(cls.temp.name)
        cls.manifest,cls.entries=builder.build(cls.work/'first.zip');builder.build(cls.work/'second.zip')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def fixture(self,variant='livecalendar'):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);work=Path(temp.name);stage=work/'stage';app=work/'app';stage.mkdir();app.mkdir()
        for name,raw in self.entries.items():
            p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);p.chmod(0o644)
        for name in builder.MODIFIED:
            p=app/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(self.entries['before/'+name]);p.chmod(0o644)
        for name in builder.GUARDS:
            raw=builder.source(name)
            if variant=='livecalendar' and name=='public-presentation.css':raw=subprocess.check_output(['git','show',builder.BASE+':tools/kcmc-follow-up-oct18/evidence/public/livecalendar/public-presentation.css'],cwd=ROOT)
            p=app/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);p.chmod(0o644)
        for name,raw in [('config.php',b'private settings sentinel'),('.htaccess',b'host settings sentinel'),('data/content.json',b'live editorial sentinel')]:
            p=app/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        spec=importlib.util.spec_from_file_location('temporary_transaction',stage/'install-functions.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.APP=app;m.BACKUPS=work/'private-backups';m.UID,m.GID=os.getuid(),os.getgid();m.PHP_CANDIDATES=(shutil.which('php'),)
        return m,app,stage
    def unchanged(self,m,app):
        for name in builder.MODIFIED:self.assertEqual((app/name).read_bytes(),self.entries['before/'+name])
        for name in builder.ADDED:self.assertFalse((app/name).exists())
        self.sentinels(app)
    def sentinels(self,app):
        self.assertEqual((app/'config.php').read_bytes(),b'private settings sentinel');self.assertEqual((app/'.htaccess').read_bytes(),b'host settings sentinel');self.assertEqual((app/'data/content.json').read_bytes(),b'live editorial sentinel')
    def test_reproducibility_and_no_private_stores_in_payload(self):
        self.assertEqual((self.work/'first.zip').read_bytes(),(self.work/'second.zip').read_bytes())
        self.assertEqual(len(builder.MODIFIED),12);self.assertEqual(len(builder.ADDED),2)
        self.assertFalse(any(Path(n).name in ('config.php','.htaccess','content.json') for n in self.entries))
    def test_both_variants_preflight_apply_idempotency_and_conservative_later_rollback(self):
        for variant in ['main','livecalendar']:
            with self.subTest(variant=variant):
                m,app,stage=self.fixture(variant);m.caller();reviewed=m.manifest();self.assertEqual(m.inspect(reviewed)[:2],(variant,'before'));self.assertFalse(m.BACKUPS.exists())
                result=m.apply(reviewed,variant);self.assertEqual(result['result'],'installed');self.assertEqual(m.inspect(reviewed)[:2],(variant,'after'));self.sentinels(app)
                self.assertEqual(m.apply(reviewed,variant)['result'],'already_installed')
                for name in m.MODIFIED:self.assertEqual(m.backup_path(Path(result['session']),name).read_bytes(),self.entries['before/'+name])
                rollback=m.rollback(reviewed,Path(result['session']).name);self.assertEqual(rollback['result'],'recovered_code_with_photos_retained')
                for name in m.MODIFIED:self.assertEqual((app/name).read_bytes(),self.entries['before/'+name])
                self.sentinels(app)
    def test_fault_after_each_atomic_live_replace_restores_all_originals(self):
        for number in range(len(builder.ORDER)):
            with self.subTest(after=builder.ORDER[number]):
                m,app,stage=self.fixture();reviewed=m.manifest();real=m.replace;count=[0];tripped=[False]
                def replace(source,target,*args):
                    real(source,target,*args)
                    if not tripped[0] and Path(source).name.startswith('stage-') and app in Path(target).parents:
                        current=count[0];count[0]+=1
                        if current==number:tripped[0]=True;raise RuntimeError('synthetic interruption after live atomic replacement')
                with mock.patch.object(m,'replace',side_effect=replace):
                    with self.assertRaisesRegex(m.Refusal,'original bundle was restored'):m.apply(reviewed,'livecalendar')
                self.assertTrue(tripped[0]);self.unchanged(m,app)
    def test_each_unrecognized_target_edit_refuses_without_backup_or_live_changes(self):
        for name in builder.MODIFIED:
            with self.subTest(name=name):
                m,app,stage=self.fixture();p=app/name;raw=p.read_bytes()+b'unknown';p.write_bytes(raw)
                with self.assertRaises(m.Refusal):m.apply(m.manifest(),'livecalendar')
                self.assertFalse(m.BACKUPS.exists());self.assertEqual(p.read_bytes(),raw);self.sentinels(app)
    def test_all_staged_php_is_linted_before_first_live_replacement(self):
        m,app,stage=self.fixture();real=subprocess.run;calls=[]
        def run(args,**kwargs):
            if '-l' in args:calls.append(Path(args[-1]).name)
            return real(args,**kwargs)
        with mock.patch.object(m.subprocess,'run',side_effect=run):m.apply(m.manifest(),'livecalendar')
        self.assertEqual(len(calls),sum(n.endswith('.php') for n in builder.MODIFIED+builder.ADDED))
    def test_guard_payload_and_source_metadata_tampering_are_refused(self):
        for kind in ['guard','payload','symlink','hardlink','executable','variant']:
            with self.subTest(kind=kind):
                m,app,stage=self.fixture();p=app/'index.php'
                if kind=='guard':(app/'styles.css').write_bytes(b'unknown stylesheet')
                elif kind=='payload':(stage/'after/index.php').write_bytes(b'unknown payload')
                elif kind in ['symlink','hardlink']:
                    outside=stage/'samebytes';outside.write_bytes(p.read_bytes());p.unlink()
                    if kind=='symlink':p.symlink_to(outside)
                    else:p.hardlink_to(outside)
                elif kind=='executable':p.chmod(0o755)
                with self.assertRaises((m.Refusal,OSError)):m.apply(m.manifest(),'main' if kind=='variant' else 'livecalendar')
                self.assertFalse(m.BACKUPS.exists());self.sentinels(app)
    def test_concurrent_edit_prevents_later_rollback(self):
        m,app,stage=self.fixture();reviewed=m.manifest();result=m.apply(reviewed,'livecalendar');p=app/'api/connection.php';raw=p.read_bytes()+b'newer staff code';p.write_bytes(raw)
        before={n:(app/n).read_bytes() for n in m.PATHS}
        with self.assertRaises(m.Refusal):m.rollback(reviewed,Path(result['session']).name)
        self.assertEqual(before,{n:(app/n).read_bytes() for n in m.PATHS});self.sentinels(app)
if __name__=='__main__':unittest.main(verbosity=2)
