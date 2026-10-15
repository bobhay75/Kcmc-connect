#!/usr/bin/env python3
"""Publication CAS and denial routes with isolated stores; no HTTP/socket/delivery.

The publication route's php://input stream is replaced with a fixture file in a
temporary copy. All authorization, validation, locking and persistence are real.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('KCMC_TEST_PHP', 'php')
RUNNER = r'''<?php
ini_set('session.save_path', $argv[2]);
$_SERVER['SCRIPT_NAME']='/app/'.$argv[3]; $_SERVER['REQUEST_URI']=$_SERVER['SCRIPT_NAME'];
$_SERVER['REQUEST_METHOD']=$argv[5]==='-'?'GET':'POST'; $_SERVER['HTTPS']='on';
$_SERVER['HTTP_HOST']='fixture.example.invalid'; $_SERVER['HTTP_ACCEPT']=$argv[8];
$_GET=json_decode($argv[6],true); $GLOBALS['fixture_payload_path']=$argv[7];
require $argv[1].'/lib/bootstrap.php';
if($argv[4]!=='-'){ kcmc_login_user(kcmc_find_user_by_id($argv[4])); $_SESSION['kcmc_auth_started_at']=time()-1200; $_SESSION['kcmc_auth_last_activity_at']=time()-600; }
$before=$_SESSION['kcmc_auth_last_activity_at']??null;
register_shutdown_function(static function()use($before):void{
 fwrite(STDERR,"\nFIXTURE_RESULT=".json_encode(['status'=>http_response_code()?:200,'before'=>$before,'after'=>$_SESSION['kcmc_auth_last_activity_at']??null,'session_status'=>session_status()])."\n");
});
if($argv[5]!=='-'){$_POST=json_decode($argv[5],true);$provided=$_POST['csrf']??null;$_POST['csrf']=is_array($provided)?$provided:($provided==='bad'?'bad':($_SESSION['csrf']??''));file_put_contents($argv[7],json_encode($_POST));}
require $argv[1].'/'.$argv[3];
'''
WORKER = r'''<?php
require $argv[1].'/lib/publication-drafts.php';
while(!is_file($argv[2]))usleep(1000);
try{$p=kcmc_publication_save_draft(['name'=>$argv[4],'pages'=>[['pageSize'=>'letter','orientation'=>'portrait','items'=>[]]]],$argv[3],1,'synthetic-owner');echo json_encode(['ok'=>true,'revision'=>$p['revision']]);}
catch(KcmcPublicationConflict $e){echo json_encode(['ok'=>false,'conflict'=>true]);}
'''


class PublicationCollaboration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='kcmc-publication-collaboration-')
        self.root=Path(self.tmp.name); self.app=self.root/'app'
        shutil.copytree(ROOT/'KCMC-Connect-Phase6-Recreated',self.app)
        self.private=self.root/'private';self.private.mkdir(mode=0o700)
        self.sessions=self.root/'sessions';self.sessions.mkdir(mode=0o700)
        self.runner=self.root/'route.php';self.runner.write_text(RUNNER)
        self.payload=self.root/'body.json'
        (self.app/'config.php').write_text('<?php return ["session_name"=>"KCMC_PUBLICATION_CAS"];')
        api=self.app/'admin/publication-projects.php';source=api.read_text()
        self.assertEqual(source.count("'php://input'"),1)
        api.write_text(source.replace("'php://input'","$GLOBALS['fixture_payload_path']"))
        password=subprocess.check_output([PHP,'-r','echo password_hash("Synthetic-Only-2031!",PASSWORD_DEFAULT);'],text=True)
        users=[dict(id=uid,role=role,active=True,display_name=uid,email=uid+'@example.invalid',password_hash=password)
            for uid,role in [('owner','recovery_admin'),('publisher','pastor_admin'),('other','recovery_admin'),('member','member'),('prayer','prayer_team')]]
        (self.private/'users.json').write_text(json.dumps({'version':1,'users':users}))
        self.env={k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        self.env.update(KCMC_PRIVATE_DATA_DIR=str(self.private),KCMC_OPERATIONS_OWNER_USER_ID='owner')
        self.public=self.app/'data/content.json'
        self.public.write_text(json.dumps({'meta':{'content_release':'3.0.0'},'contact':{'email':'office@example.invalid'},'announcements':[{'id':'owner-announcement','title':'Original','body':'Original approved text','status':'hidden'}],'events':[],'bulletin':{'notes':[]}}))

    def tearDown(self): self.tmp.cleanup()

    def route(self,path='admin/publication-projects.php',actor='owner',post=None,query=None,accept='application/json'):
        run=subprocess.run([PHP,'-d','output_buffering=0',str(self.runner),str(self.app),str(self.sessions),path,actor or '-',json.dumps(post) if post is not None else '-',json.dumps(query or {}),str(self.payload),accept],env=self.env,capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        self.assertNotRegex(run.stderr+run.stdout,r'Warning:|Fatal error|Deprecated:|headers already sent')
        match=re.search(r'FIXTURE_RESULT=(\{[^\n]*\})',run.stderr);self.assertIsNotNone(match)
        result=json.loads(match[1]);result['body']=run.stdout
        return result

    def draft(self,name='Shared draft',**extra):
        return dict(name=name,pages=[{'pageSize':'letter','orientation':'portrait','items':[{'type':'text','text':'  Exact words\n\n________  ','x':10,'y':10,'w':400,'h':100}]}],revision=0,**extra)

    def create(self):
        result=self.route(post=self.draft());self.assertEqual(result['status'],200)
        return json.loads(result['body'])['project']

    def test_two_publishers_stale_save_returns_409_without_overwriting_the_first(self):
        initial=self.create();one=self.draft('First editor',id=initial['id']);one['revision']=1
        saved=json.loads(self.route(actor='publisher',post=one)['body'])['project']
        before=(self.private/'publications.json').read_bytes()
        stale=self.draft('Second editor unsaved',id=initial['id']);stale['revision']=1
        result=self.route(post=stale)
        self.assertEqual(result['status'],409);self.assertIn('Your edits are still here',result['body'])
        self.assertEqual((self.private/'publications.json').read_bytes(),before)
        self.assertEqual(saved['revision'],2)
        copy=self.route(post=self.draft('Second editor unsaved copy'))
        self.assertEqual(copy['status'],200)
        self.assertNotEqual(json.loads(copy['body'])['project']['id'],initial['id'])

    def test_real_simultaneous_php_processes_allow_one_revision_winner(self):
        initial=self.create();worker=self.root/'worker.php';worker.write_text(WORKER);gate=self.root/'go'
        processes=[subprocess.Popen([PHP,str(worker),str(self.app),str(gate),initial['id'],'editor-'+str(n)],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for n in range(6)]
        gate.write_text('go');results=[]
        for process in processes:
            output,error=process.communicate(timeout=15);self.assertEqual(process.returncode,0,error);results.append(json.loads(output))
        self.assertEqual(sum(r['ok'] for r in results),1)
        self.assertEqual(sum(r.get('conflict',False) for r in results),5)
        self.assertEqual(json.loads((self.private/'publications.json').read_text())['projects'][0]['revision'],2)

    def test_legacy_revision_zero_updates_without_rewriting_other_projects(self):
        one=self.create();two=self.create();store=self.private/'publications.json';state=json.loads(store.read_text())
        for project in state['projects']: project.pop('revision')
        store.write_text(json.dumps(state));unrelated=next(p for p in state['projects'] if p['id']==two['id'])
        changed=self.draft('Legacy safely updated',id=one['id']);result=self.route(post=changed)
        self.assertEqual(result['status'],200);self.assertEqual(json.loads(result['body'])['project']['revision'],1)
        self.assertEqual(next(p for p in json.loads(store.read_text())['projects'] if p['id']==two['id']),unrelated)

    def test_corrupt_store_and_backup_failure_preserve_exact_live_bytes(self):
        path=self.private/'publications.json';path.write_bytes(b'{invalid-private-json')
        result=self.route(post=self.draft());self.assertEqual(result['status'],503);self.assertEqual(path.read_bytes(),b'{invalid-private-json')
        path.unlink();saved=self.create();before=path.read_bytes();(self.private/'publications.json.previous.json').mkdir()
        change=self.draft('Cannot commit',id=saved['id']);change['revision']=1
        self.assertEqual(self.route(post=change)['status'],503);self.assertEqual(path.read_bytes(),before)
        self.assertFalse(list(self.private.glob('publications.json.tmp-*')))

    def test_passive_watch_releases_session_and_does_not_extend_idle_activity(self):
        saved=self.create();result=self.route(query={'watch':'1','id':saved['id']})
        self.assertEqual(result['status'],200);self.assertEqual(result['before'],result['after']);self.assertEqual(result['session_status'],1)
        self.assertEqual(set(json.loads(result['body'])['project']),{'id','revision','updated'})
        self.assertEqual(self.route(actor=None,query={'watch':'1','id':saved['id']})['status'],401)
        self.assertEqual(self.route(actor='member',query={'watch':'1','id':saved['id']})['status'],403)

    def test_existing_project_requires_revision_and_mutations_require_csrf_and_publisher(self):
        saved=self.create();before=(self.private/'publications.json').read_bytes()
        missing=self.draft(id=saved['id']);missing.pop('revision')
        self.assertEqual(self.route(post=missing)['status'],428)
        self.assertEqual(self.route(post=self.draft(csrf='bad'))['status'],403)
        for actor in ['member','prayer']:
            result=self.route(actor=actor,post=self.draft());self.assertEqual(result['status'],403)
            self.assertIn('href="/app/"',result['body']);self.assertIn('My account',result['body'])
            self.assertNotIn('Exact words',result['body'])
        self.assertEqual((self.private/'publications.json').read_bytes(),before)

    def test_malformed_csrf_arrays_return_clean_denials(self):
        for path, body in [('admin/publication-projects.php', self.draft(csrf=['bad'])), ('admin/save.php', dict(self.publish_input('0'*64), csrf=['bad']))]:
            self.assertEqual(self.route(path, post=body)['status'], 403)

    def test_hardlinked_store_lock_or_backup_is_refused_without_modifying_other_names(self):
        saved=self.create(); path=self.private/'publications.json'
        change=self.draft('Do not write', id=saved['id']); change['revision']=1
        original=path.read_bytes()
        for suffix in ['', '.lock', '.previous.json']:
            candidate=Path(str(path)+suffix)
            if suffix and candidate.exists(): candidate.unlink()
            if suffix: candidate.write_bytes(b'KEEP OTHER FILE')
            other=self.root/('linked-'+str(len(suffix))); os.link(candidate,other)
            before=other.read_bytes()
            self.assertEqual(self.route(post=change)['status'],503)
            self.assertEqual(other.read_bytes(),before)
            self.assertEqual(path.read_bytes(),original)
            other.unlink()
            if suffix: candidate.unlink()

    def test_design_text_keeps_whitespace_and_unknown_id_never_creates_a_replacement(self):
        saved=self.create();self.assertEqual(saved['pages'][0]['items'][0]['text'],'  Exact words\n\n________  ')
        before=(self.private/'publications.json').read_bytes()
        self.assertEqual(self.route(post=self.draft(id='pub_'+'f'*24))['status'],409)
        self.assertEqual((self.private/'publications.json').read_bytes(),before)

    def publish_input(self,version):
        return dict(version=version,confirm_publish='1',contact_email='office@example.invalid',contact_phone='123',contact_hours='Tuesday',contact_address='Synthetic location',announcement_id='owner-announcement',announcement_title='My unsaved announcement',announcement_body='My exact text',announcement_status='hidden')

    def test_publishing_desk_stale_or_missing_hash_cannot_replace_current_content(self):
        import hashlib
        version=hashlib.sha256(self.public.read_bytes()).hexdigest();body=self.publish_input(version)
        first=self.route('admin/save.php',post=body);self.assertEqual(first['status'],200)
        saved=json.loads(first['body']);self.assertTrue(saved['ok']);self.assertEqual(saved['version'],hashlib.sha256(self.public.read_bytes()).hexdigest())
        before=self.public.read_bytes();stale=self.route('admin/save.php',post=body)
        self.assertEqual(stale['status'],409);self.assertEqual(self.public.read_bytes(),before)
        body.pop('version');self.assertEqual(self.route('admin/save.php',post=body)['status'],428);self.assertEqual(self.public.read_bytes(),before)

    def test_corrupt_public_content_cannot_be_reset_by_the_normal_editor(self):
        import hashlib
        for invalid in [b'{broken-public-json', b'{"contact":[],"announcements":[],"events":"bad","bulletin":[]}']:
            self.public.write_bytes(invalid)
            version=hashlib.sha256(invalid).hexdigest()
            result=self.route('admin/save.php',post=self.publish_input(version))
            self.assertEqual(result['status'],409)
            self.assertEqual(self.public.read_bytes(),invalid)

    def test_partial_content_write_is_removed_before_live_replacement(self):
        source=(self.app/'lib/bootstrap.php').read_text()
        function=source[source.index('function kcmc_write_content('):source.index('function kcmc_users_store(')]
        live=self.root/'fault-content.json';live.write_text('{"keep":"original"}')
        backups=self.root/'fault-backups'
        # Namespaced fault injection executes the exact actual helper body and
        # makes only its staged write short. All other I/O remains native PHP.
        prefix='namespace PublicationFault; use \\RuntimeException; const KCMC_DATA='+json.dumps(str(live))+';const KCMC_BACKUPS='+json.dumps(str(backups))+'; function file_put_contents($path,$data,$flags=0){return \\file_put_contents($path,substr($data,0,-1),$flags);}'
        code='<?php '+prefix+function+'try{kcmc_write_content(["new"=>"data"],"fixture");echo "BAD";}catch(RuntimeException $e){echo file_get_contents(KCMC_DATA)==="{\\"keep\\":\\"original\\"}"&&count(glob(KCMC_DATA.".tmp-*"))===0?"PASS":"BAD";}'
        runner=self.root/'short-write.php';runner.write_text(code)
        run=subprocess.run([PHP,str(runner)],env=self.env,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout,'PASS')

    def test_content_writer_checks_expected_hash_inside_real_lock(self):
        import hashlib
        version=hashlib.sha256(self.public.read_bytes()).hexdigest()
        code="require $argv[1].'/lib/bootstrap.php';$data=kcmc_content();kcmc_write_content($data,'first',$argv[2]);$current=file_get_contents(KCMC_DATA);try{kcmc_write_content($data,'stale',$argv[2]);echo 'BAD';}catch(RuntimeException $e){echo file_get_contents(KCMC_DATA)===$current?'PASS':'BAD';}"
        output=subprocess.check_output([PHP,'-r',code,str(self.app),version],env=self.env,text=True)
        self.assertEqual(output,'PASS')

    def test_html_conflict_keeps_copyable_escaped_input_and_fixed_navigation(self):
        body=self.publish_input('0'*64);body['announcement_body']='</textarea><script>unsafe()</script>'
        result=self.route('admin/save.php',post=body,accept='text/html')
        self.assertEqual(result['status'],409);self.assertIn('Copy your unsaved input',result['body']);self.assertIn('href="/app/"',result['body'])
        self.assertNotIn('<script>unsafe()',result['body']);self.assertIn('&lt;script&gt;',result['body'])

    def test_owner_denial_keeps_status_message_and_safe_home_account_links(self):
        result=self.route('admin/operations.php',actor='other')
        self.assertEqual(result['status'],403);self.assertIn('Operations access is restricted to the designated owner.',result['body'])
        self.assertIn('href="/app/"',result['body']);self.assertIn('href="/app/member/"',result['body'])
        self.assertNotIn('owner@example.invalid',result['body']);self.assertNotIn('Private release diagnostics',result['body'])


if __name__=='__main__': unittest.main(verbosity=2)
