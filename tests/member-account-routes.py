#!/usr/bin/env python3
"""Execute real PHP routes with synthetic private stores; no network or delivery.

This checks authorization, controls, status codes and store effects. HTTP header
transport and device push acceptance remain separate from this CLI harness.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1] / 'KCMC-Connect-Phase6-Recreated'
PHP = os.environ.get('KCMC_TEST_PHP', 'php')
RUNNER = r'''<?php
ini_set('session.save_path', $argv[2]);
ini_set('display_errors', '1');
$_SERVER['SCRIPT_NAME'] = '/app/' . $argv[3];
$_SERVER['REQUEST_METHOD'] = $argv[5] === '-' ? 'GET' : 'POST';
$_SERVER['HTTP_HOST'] = 'fixture.example.invalid';
$_SERVER['HTTPS'] = 'on';
$_GET = json_decode($argv[7], true);
register_shutdown_function(static function (): void {
    fwrite(STDERR, "\nKCMC_ROUTE_STATUS=" . json_encode(['status' => http_response_code() ?: 200]) . "\n");
});
require $argv[1] . '/lib/bootstrap.php';
if ($argv[4] !== '-') kcmc_login_user(kcmc_find_user_by_id($argv[4]));
if ($argv[5] !== '-') {
    $_POST = json_decode($argv[5], true);
    $_POST['csrf'] = $argv[6] === 'bad' ? 'invalid-csrf' : ($_SESSION['csrf'] ?? 'anonymous-invalid');
}
require $argv[1] . '/' . $argv[3];
'''

class Fixture:
    def __init__(self, app):
        self.tmp = tempfile.TemporaryDirectory(prefix='kcmc-member-account-')
        self.root = Path(self.tmp.name)
        self.app = self.root / 'app'
        shutil.copytree(app, self.app)
        (self.app / 'config.php').write_text('<?php return ["session_name"=>"KCMC_MEMBER_ACCOUNT_TEST"];?>\n')
        self.private = self.root / 'private'; self.private.mkdir(mode=0o700)
        self.sessions = self.root / 'sessions'; self.sessions.mkdir(mode=0o700)
        self.runner = self.root / 'route.php'; self.runner.write_text(RUNNER)
        pw = subprocess.check_output([PHP, '-r', 'echo password_hash("Synthetic-Fixture-2031!", PASSWORD_DEFAULT);'], text=True)
        self.users = [dict(id=uid, role=role, active=active, display_name='Synthetic '+uid,
            email=uid+'@example.invalid', password_hash=pw)
            for uid,role,active in [('owner','recovery_admin',True), ('pastor','pastor_admin',True),
                ('recovery','recovery_admin',True), ('member','member',True), ('prayer','prayer_team',True),
                ('inactive','pastor_admin',False)]]
        self.write('users.json', {'version':1,'users':self.users})
        self.write('prayers.json', {'version':1,'prayers':[
            dict(id='private-other',submitted_by='pastor',status='private',audience='pastors_only',public_name='Anonymous',message='SECRET OTHER PRAYER',created_at='2026-10-01T12:00:00Z'),
            dict(id='private-own',submitted_by='member',status='private',audience='pastors_only',public_name='Anonymous',message='OWN EARLIER PRAYER',created_at='2026-10-02T12:00:00Z'),
            dict(id='shared',submitted_by='pastor',status='approved',audience='members',public_name='Anonymous',message='APPROVED MEMBER WALL',created_at='2026-10-03T12:00:00Z'),
            dict(id='pending',submitted_by='pastor',status='pending',audience='members',public_name='Anonymous',message='SECRET PENDING WALL',created_at='2026-10-04T12:00:00Z')]})
        now=2000000000
        entries={}
        for uid, author, status, audience, consent, message in [
            ('private-other','pastor','private','pastoral',False,'SECRET OTHER CARE'),
            ('private-own','member','private','pastoral',False,'OWN CARE REQUEST'),
            ('pending','pastor','pending','members',True,'SECRET PENDING CARE'),
            ('shared','pastor','approved','members',True,'APPROVED CARE WALL')]:
            entries[uid]=dict(id=uid,author=author,status=status,audience=audience,consent=consent,
                message=message,kind='need',name='Anonymous',created_at=now-1000,updated_at=now-1000,expires_at=now+86400)
        self.write('prayer-care.json',dict(version=1,revision=0,warriors={'member':dict(name='Synthetic member',status='pending',requested_at=now-1000)},entries=entries,commitments={}))
        self.content=(self.app/'data/content.json').read_bytes()
    def write(self,name,value): (self.private/name).write_text(json.dumps(value))
    def read(self,name): return json.loads((self.private/name).read_text())
    def close(self): self.tmp.cleanup()
    def route(self,route,actor=None,post=None,query=None,bad_csrf=False,configured='owner'):
        env={k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(self.private),KCMC_OPERATIONS_OWNER_USER_ID=configured,KCMC_SETUP_KEY='')
        run=subprocess.run([PHP,'-d','output_buffering=0',str(self.runner),str(self.app),str(self.sessions),route,
            actor or '-',json.dumps(post) if post is not None else '-','bad' if bad_csrf else 'valid',json.dumps(query or {})],capture_output=True,text=True,env=env,timeout=15)
        if run.returncode != 0 or re.search(r'(?i)Warning:|Fatal error|headers already sent|Deprecated:',run.stdout+run.stderr):
            raise AssertionError(run.stdout+'\n'+run.stderr)
        match=re.search(r'KCMC_ROUTE_STATUS=(\{[^\n]*\})',run.stderr)
        if match is None: raise AssertionError(run.stderr)
        return json.loads(match.group(1))['status'],run.stdout

class MemberAccountRoutes(unittest.TestCase):
    def setUp(self): self.f=Fixture(APP)
    def tearDown(self):
        self.assertEqual((self.f.app/'data/content.json').read_bytes(),self.f.content)
        self.f.close()
    def test_personal_landing_is_small_and_never_reads_prayer_payloads(self):
        (self.f.private/'prayers.json').write_text('invalid prayer fixture must not be read')
        (self.f.private/'prayer-care.json').write_text('invalid care fixture must not be read')
        for actor in ['owner','pastor','recovery','member','prayer']:
            with self.subTest(actor=actor):
                status,page=self.f.route('member/index.php',actor)
                self.assertEqual(status,200)
                self.assertIn('<title>My Account',page)
                self.assertIn('Personal settings',page)
                self.assertIn(actor+'@example.invalid',page)
                self.assertNotIn('password_hash',page)
                for tool in ['Release health','Content restore','Audit history','Password resets','Push updates','Pastor approvals','Send private request']:
                    self.assertNotIn(tool,page)
                admin_links=re.findall(r'href="/app/admin/[^"]*"',page)
                self.assertEqual(admin_links,['href="/app/admin/home.php"'] if actor in ['owner','pastor','recovery','prayer'] else [])
                self.assertIn('href="/app/">← Home',page)
                self.assertIn('method="post" action="/app/member/logout.php"',page)
    def test_personal_information_is_escaped(self):
        users=self.f.read('users.json');users['users'][3]['display_name']='Name <script>bad()</script>';users['users'][3]['email']='bad<svg>@example.invalid'
        self.f.write('users.json',users)
        status,page=self.f.route('member/index.php','member')
        self.assertEqual(status,200);self.assertNotIn('<script>bad()',page);self.assertIn('&lt;script&gt;bad()',page);self.assertIn('&lt;svg&gt;',page)
    def test_admin_hub_matches_existing_capabilities_and_owner_gate(self):
        expected={'owner':(True,True,True),'pastor':(True,True,False),'recovery':(True,False,False),'prayer':(False,True,False)}
        for actor,(publish,prayers,owner) in expected.items():
            with self.subTest(actor=actor):
                status,page=self.f.route('admin/home.php',actor);self.assertEqual(status,200)
                for route,yes in [('admin/"',publish),('admin/users.php',publish),('admin/prayer-inbox.php',prayers),('admin/operations.php',owner),('admin/timecards.php',owner),('admin/push.php',owner)]:
                    self.assertEqual(('href="/app/'+route) in page,yes,route)
                self.assertEqual('admin/prayer-care.php' in page,actor in ['owner','pastor'])
                self.assertIn('href="/app/member/">← Account home',page)
        self.assertEqual(self.f.route('admin/home.php','member')[0],403)
        self.assertEqual(self.f.route('admin/home.php','owner',configured='')[0],200)
        self.assertNotIn('admin/operations.php',self.f.route('admin/home.php','owner',configured='')[1])
    def test_legacy_personal_prayers_preserve_wall_and_own_history_privacy(self):
        status,page=self.f.route('member/prayers.php','member');self.assertEqual(status,200)
        self.assertRegex(page,r'Oct 2, 2026</span><strong>Private</strong><small>Pastors and prayer team only')
        self.assertIn('APPROVED MEMBER WALL',page)
        self.assertNotIn('SECRET OTHER PRAYER',page);self.assertNotIn('SECRET PENDING WALL',page)
        self.assertIn('name="message"',page);self.assertIn('name="csrf"',page)
        self.assertIn('Your recent submissions',page)
        status,page=self.f.route('member/prayers.php','recovery');self.assertEqual(status,200)
        self.assertNotIn('APPROVED MEMBER WALL',page);self.assertNotIn('name="message"',page)
        self.assertIn('Prayer content is intentionally unavailable',page)
    def test_inbox_keeps_existing_role_limits_and_legacy_bookmark_redirect(self):
        for actor in ['owner','pastor','prayer']:
            status,page=self.f.route('admin/prayer-inbox.php',actor);self.assertEqual(status,200);self.assertIn('SECRET OTHER PRAYER',page)
            status,page=self.f.route('member/prayer-team.php',actor);self.assertEqual(status,303);self.assertEqual(page,'')
        for actor in ['member','recovery']:
            for route in ['admin/prayer-inbox.php','member/prayer-team.php']:
                self.assertEqual(self.f.route(route,actor)[0],403)
        self.assertEqual(self.f.route('member/prayer-team.php','prayer',{})[0],405)
    def test_member_care_has_no_administrative_review_controls_even_for_owner(self):
        for actor in ['member','prayer','pastor','owner']:
            status,page=self.f.route('member/prayer-care.php',actor);self.assertEqual(status,200)
            self.assertIn('APPROVED CARE WALL',page)
            for marker in ['SECRET OTHER CARE','SECRET PENDING CARE','Pastoral review','Approve chosen audience','Approve signup','Decline signup']:
                self.assertNotIn(marker,page)
            self.assertIn('member/prayers.php',page)
        status,page=self.f.route('member/prayer-care.php','member',query={'view':'mine'})
        self.assertEqual(status,200);self.assertIn('OWN CARE REQUEST',page);self.assertNotIn('SECRET OTHER CARE',page)
    def test_admin_care_review_is_private_and_legacy_get_redirects(self):
        for actor in ['owner','pastor']:
            status,page=self.f.route('admin/prayer-care.php',actor);self.assertEqual(status,200)
            self.assertIn('SECRET OTHER CARE',page);self.assertIn('SECRET PENDING CARE',page)
            self.assertIn('Approve chosen audience',page);self.assertIn('Approve signup',page)
            self.assertEqual(self.f.route('member/prayer-care.php',actor,query={'view':'review'}),(303,''))
        for actor in ['member','prayer','recovery']:
            self.assertEqual(self.f.route('admin/prayer-care.php',actor)[0],403)
            self.assertEqual(self.f.route('member/prayer-care.php',actor,query={'view':'review'})[0],403)
    def test_admin_post_and_legacy_post_preserve_csrf_and_single_mutation(self):
        before=(self.f.private/'prayer-care.json').read_bytes()
        post={'revision':'0','action':'approve_warrior','target':'member'}
        self.assertEqual(self.f.route('member/prayer-care.php','pastor',post)[0],307)
        self.assertEqual((self.f.private/'prayer-care.json').read_bytes(),before)
        for route,actor in [('member/prayer-care.php','pastor'),('admin/prayer-care.php','pastor'),('admin/prayer-care.php','member')]:
            self.assertEqual(self.f.route(route,actor,post,bad_csrf=True)[0],403)
            self.assertEqual((self.f.private/'prayer-care.json').read_bytes(),before)
        self.assertEqual(self.f.route('admin/prayer-care.php','pastor',post)[0],303)
        state=self.f.read('prayer-care.json');self.assertEqual(state['revision'],1)
        self.assertEqual(state['warriors']['member']['status'],'approved')
        self.assertEqual(state['warriors']['member']['reviewed_by'],'pastor')
    def test_own_member_actions_stay_personal_and_other_member_actions_do_not_mutate(self):
        before=(self.f.private/'prayer-care.json').read_bytes()
        self.assertEqual(self.f.route('member/prayer-care.php','member',{'revision':'0','action':'close','entry_id':'private-other'})[0],422)
        self.assertEqual((self.f.private/'prayer-care.json').read_bytes(),before)
        self.assertEqual(self.f.route('member/prayer-care.php','pastor',{'revision':'0','action':'close','entry_id':'private-own'})[0],307)
        self.assertEqual((self.f.private/'prayer-care.json').read_bytes(),before)
        self.assertEqual(self.f.route('member/prayer-care.php','member',{'revision':'0','action':'close','entry_id':'private-own'})[0],303)
        self.assertEqual(self.f.read('prayer-care.json')['entries']['private-own']['status'],'closed')
    def test_earlier_private_prayer_submission_is_retained(self):
        before=self.f.read('prayers.json')
        self.assertEqual(self.f.route('member/submit-prayer.php','member',{'message':'Synthetic personal request only.','name_display':'anonymous'})[0],302)
        after=self.f.read('prayers.json');self.assertEqual(after['prayers'][:-1],before['prayers'])
        self.assertEqual(after['prayers'][-1]['audience'],'pastors_only');self.assertEqual(after['prayers'][-1]['status'],'private')
    def test_anonymous_and_inactive_accounts_cannot_open_personal_or_admin_data(self):
        for actor in [None,'inactive']:
            for route in ['member/index.php','member/prayers.php','member/prayer-care.php','admin/home.php','admin/prayer-inbox.php','admin/prayer-care.php']:
                status,page=self.f.route(route,actor);self.assertEqual(status,302);self.assertNotIn('SECRET',page)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--app',type=Path,default=APP);p.add_argument('--case');args=p.parse_args();APP=args.app.resolve()
    suite=unittest.defaultTestLoader.loadTestsFromName(args.case,MemberAccountRoutes) if args.case else unittest.defaultTestLoader.loadTestsFromTestCase(MemberAccountRoutes)
    r=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not r.wasSuccessful())
