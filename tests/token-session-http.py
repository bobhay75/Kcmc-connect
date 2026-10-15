#!/usr/bin/env python3
"""Actual original-app token routes with output buffering disabled.

All users/tokens are synthetic; no mail or push transport is configured or used.
Run --app /path/to/KCMC-Connect-Phase6-Recreated. --case selects a specific
semantic assertion for an unchanged-source negative control.
"""
import argparse
import copy
import hashlib
import html
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

APP = None
OLD_PASSWORD = 'Synthetic-Token-Original-2031!'
NEW_PASSWORD = 'Synthetic-Token-Replacement-2031!'
SESSION_NAME = 'KCMC_TOKEN_SESSION_FIXTURE'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

class Client:
    def __init__(self, base):
        self.base = base
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies), NoRedirect())
    def request(self, path, data=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            response = self.opener.open(self.base + path, body, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        result = response.code, response.headers, response.read().decode('utf-8')
        if result[0] >= 500:
            raise AssertionError('Unexpected PHP route failure: ' + path)
        return result

class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-token-session-http-')
        self.root = Path(self.temp.name)
        self.app = self.root / 'app'
        shutil.copytree(APP, self.app)
        # Test-only config replaces any source config; delivery env is cleared below.
        (self.app / 'config.php').write_text('<?php return ["session_name"=>"'+SESSION_NAME+'", "church_email"=>"fixture@example.invalid"];\n')
        self.private = self.root / 'private'; self.private.mkdir(mode=0o750)
        self.sessions = self.root / 'sessions'; self.sessions.mkdir(mode=0o700)
        hashed = subprocess.check_output(['php','-r','echo password_hash($argv[1],PASSWORD_DEFAULT);',OLD_PASSWORD],text=True).strip()
        users = [dict(id=uid,email=uid+'@example.invalid',email_normalized=uid+'@example.invalid',
                 display_name='Synthetic '+uid,role=role,active=active,password_hash=hashed)
                 for uid,role,active in [('issuer','pastor_admin',True),('member','member',True),('inactive','member',False)]]
        self.write('users.json', {'version':1,'users':users})
        self.write('invites.json', {'version':1,'invites':[]})
        self.write('password-resets.json', {'version':1,'resets':[]})
        self.write('login-attempts.json', {'attempts':{}})
        self.content = (self.app / 'data/content.json').read_bytes()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
        self.base = 'http://127.0.0.1:'+str(port)+'/app'
        env = {k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(self.private),KCMC_SETUP_KEY='')
        self.log = (self.root / 'server.log').open('w')
        # These temporary fixtures may replace PHP source to model a competing
        # write. Never let OPcache reuse a same-second pre-hook compilation.
        self.server = subprocess.Popen(['php','-d','opcache.enable=0','-d','opcache.enable_cli=0',
             '-d','output_buffering=0','-d','zlib.output_compression=0',
             '-d','display_errors=1','-d','log_errors=1','-d','session.save_path='+str(self.sessions),
             '-S','127.0.0.1:'+str(port),'-t',str(self.root)],env=env,stdout=self.log,stderr=self.log,start_new_session=True)
        for _ in range(80):
            try:
                if self.client().request('/member/login.php')[0] == 200: break
            except (OSError, AssertionError): time.sleep(.05)
        else:
            self.close()
            raise AssertionError('Synthetic PHP server did not start')
    def close(self):
        os.killpg(self.server.pid,signal.SIGTERM)
        self.server.wait(timeout=5); self.log.close(); self.temp.cleanup()
    def client(self): return Client(self.base)
    def read(self,name): return json.loads((self.private/name).read_text())
    def write(self,name,state): (self.private/name).write_text(json.dumps(state))
    def user(self,uid): return next(u for u in self.read('users.json')['users'] if u['id']==uid)
    def password_matches(self,uid,password):
        return subprocess.check_output(['php','-r','echo password_verify($argv[1],$argv[2])?"yes":"no";',
             password,self.user(uid)['password_hash']],text=True).strip()=='yes'
    def seed(self,kind,used=False,expired=False,target='member'):
        token = ('c' if kind=='invite' else 'd')*64
        record = dict(id='synthetic_'+kind,token_hash=hashlib.sha256(token.encode()).hexdigest(),
             created_by='issuer',created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
             expires_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()+(-60 if expired else 3600))),
             used_at='already_used' if used else None)
        if kind=='invite': record.update(email='new@example.invalid',display_name='Synthetic new member',role='prayer_team')
        else: record.update(user_id=target,email_normalized=target+'@example.invalid')
        self.write('invites.json' if kind=='invite' else 'password-resets.json',
                   {'version':1,'invites' if kind=='invite' else 'resets':[record]})
        return '/member/'+('activate.php' if kind=='invite' else 'reset-password.php')+'?token='+token, token

class TokenSessionHTTP(unittest.TestCase):
    def setUp(self): self.fixture=Fixture()
    def tearDown(self): self.fixture.close()
    def form(self,kind):
        route,token=self.fixture.seed(kind); client=self.fixture.client()
        status,headers,body=client.request(route)
        self.assertEqual(status,200)
        cookies=headers.get_all('Set-Cookie') or []
        self.assertTrue(any(cookie.startswith(SESSION_NAME+'=') for cookie in cookies),
             'Token GET must emit session cookie before any HTML output')
        self.assertTrue(any(cookie.name==SESSION_NAME for cookie in client.cookies),
             'Browser must retain token form session cookie')
        self.assertNotRegex(body,r'(?i)Warning:|Fatal error|headers already sent',
             'Token GET must not attempt session/header changes after output')
        match=re.search(r'name="csrf" value="([^"]+)"',body)
        self.assertIsNotNone(match,'Valid token GET must render a CSRF field')
        csrf=html.unescape(match.group(1))
        self.assertRegex(csrf,r'\A[a-f0-9]{48}\Z')
        self.assertIn('no-store',headers.get('Cache-Control',''))
        self.assertIn('no-referrer',headers.get('Referrer-Policy',''))
        return client,route,token,csrf
    def valid_anonymous_csrf(self,client):
        # An unavailable token page has no form. Use this same anonymous browser's
        # ordinary sign-in form to obtain a genuine session-bound CSRF token.
        status,_,body=client.request('/member/login.php')
        self.assertEqual(status,200)
        match=re.search(r'name="csrf" value="([^"]+)"',body)
        self.assertIsNotNone(match,'Anonymous sign-in must provide a valid CSRF fixture')
        return html.unescape(match.group(1))
    def submit(self,client,route,token,csrf):
        return client.request(route,{'csrf':csrf,'token':token,'password':NEW_PASSWORD,'confirm':NEW_PASSWORD})
    def test_invitation_session_roundtrip(self):
        original=copy.deepcopy(self.fixture.read('users.json')['users'])
        client,route,token,csrf=self.form('invite')
        self.assertFalse(self.fixture.read('invites.json')['invites'][0]['used_at'],'GET must not consume invitation')
        status,headers,body=self.submit(client,route,token,csrf)
        self.assertEqual(status,302,'Valid invitation POST must complete with original route redirect')
        self.assertTrue(headers.get('Location','').endswith('/member/'))
        self.assertNotRegex(body,r'(?i)Warning:|Fatal error|headers already sent')
        users=self.fixture.read('users.json')['users']
        self.assertEqual(users[:-1],original,'Invitation must preserve existing accounts')
        created=users[-1]
        self.assertEqual(created['email'],'new@example.invalid')
        self.assertEqual(created['email_normalized'],'new@example.invalid')
        self.assertEqual(created['display_name'],'Synthetic new member')
        self.assertEqual(created['role'],'prayer_team')
        self.assertTrue(created['active'])
        self.assertTrue(created['id'].startswith('usr_'))
        self.assertTrue(self.fixture.password_matches(created['id'],NEW_PASSWORD))
        self.assertTrue(self.fixture.read('invites.json')['invites'][0]['used_at'])
        self.assertEqual(client.request('/member/')[0],200,'Successful activation retains intended member session')
        self.assertEqual((self.fixture.app/'data/content.json').read_bytes(),self.fixture.content)
    def test_reset_session_roundtrip(self):
        before=copy.deepcopy(self.fixture.user('member')); issuer=copy.deepcopy(self.fixture.user('issuer'))
        client,route,token,csrf=self.form('reset')
        self.assertFalse(self.fixture.read('password-resets.json')['resets'][0]['used_at'],'GET must not consume reset')
        status,headers,body=self.submit(client,route,token,csrf)
        self.assertEqual(status,302,'Valid ordinary reset POST must complete with original route redirect')
        self.assertTrue(headers.get('Location','').endswith('/member/login.php?reset=1'))
        self.assertNotRegex(body,r'(?i)Warning:|Fatal error|headers already sent')
        after=self.fixture.user('member')
        for field in ('id','email','email_normalized','display_name','role','active'):
            self.assertEqual(after[field],before[field],'Reset must preserve '+field)
        self.assertNotEqual(after['password_hash'],before['password_hash'])
        self.assertTrue(self.fixture.password_matches('member',NEW_PASSWORD))
        self.assertFalse(self.fixture.password_matches('member',OLD_PASSWORD))
        self.assertEqual(self.fixture.user('issuer'),issuer)
        self.assertTrue(self.fixture.read('password-resets.json')['resets'][0]['used_at'])
        self.assertEqual(client.request('/member/')[0],302,'Password reset does not silently sign in a bearer')
        self.assertEqual((self.fixture.app/'data/content.json').read_bytes(),self.fixture.content)
    def test_bad_csrf_and_get_preserve_tokens_and_users(self):
        for kind in ('invite','reset'):
            with self.subTest(kind=kind):
                client,route,token,_=self.form(kind)
                store='invites.json' if kind=='invite' else 'password-resets.json'
                before_tokens=(self.fixture.private/store).read_bytes()
                before_users=(self.fixture.private/'users.json').read_bytes()
                self.assertEqual(client.request(route)[0],200)
                status,_,body=self.submit(client,route,token,'invalid')
                self.assertEqual(status,200)
                self.assertIn('Please reload',body)
                self.assertEqual((self.fixture.private/store).read_bytes(),before_tokens)
                self.assertEqual((self.fixture.private/'users.json').read_bytes(),before_users)
                self.assertEqual(client.request('/member/')[0],302)
    def test_used_and_expired_tokens_preserve_state(self):
        for kind in ('invite','reset'):
            for state in ('used','expired'):
                with self.subTest(kind=kind,state=state):
                    route,token=self.fixture.seed(kind,used=state=='used',expired=state=='expired')
                    store='invites.json' if kind=='invite' else 'password-resets.json'
                    before_tokens=(self.fixture.private/store).read_bytes()
                    before_users=(self.fixture.private/'users.json').read_bytes()
                    client=self.fixture.client()
                    status,_,body=client.request(route)
                    self.assertEqual(status,200)
                    self.assertIn('This link is no longer valid.',body)
                    self.assertNotIn('name="password"',body)
                    self.assertNotEqual(self.submit(client,route,token,self.valid_anonymous_csrf(client))[0],302)
                    self.assertEqual((self.fixture.private/store).read_bytes(),before_tokens)
                    self.assertEqual((self.fixture.private/'users.json').read_bytes(),before_users)
                    self.assertEqual(client.request('/member/')[0],302)
    def test_disabled_reset_account_preserves_state(self):
        route,token=self.fixture.seed('reset',target='inactive'); client=self.fixture.client()
        before_tokens=(self.fixture.private/'password-resets.json').read_bytes()
        before_users=(self.fixture.private/'users.json').read_bytes()
        status,_,body=client.request(route)
        self.assertEqual(status,200)
        self.assertIn('This link is no longer valid.',body)
        self.assertNotEqual(self.submit(client,route,token,self.valid_anonymous_csrf(client))[0],302)
        self.assertEqual((self.fixture.private/'password-resets.json').read_bytes(),before_tokens)
        self.assertEqual((self.fixture.private/'users.json').read_bytes(),before_users)
    def test_successful_tokens_cannot_be_reused(self):
        for kind in ('invite','reset'):
            with self.subTest(kind=kind):
                client,route,token,csrf=self.form(kind)
                self.assertEqual(self.submit(client,route,token,csrf)[0],302)
                # Use an independent anonymous browser, not the newly activated session.
                client=self.fixture.client()
                before_users=(self.fixture.private/'users.json').read_bytes()
                store='invites.json' if kind=='invite' else 'password-resets.json'
                before_tokens=(self.fixture.private/store).read_bytes()
                self.assertIn('This link is no longer valid.',client.request(route)[2])
                self.assertNotEqual(self.submit(client,route,token,self.valid_anonymous_csrf(client))[0],302)
                self.assertEqual((self.fixture.private/'users.json').read_bytes(),before_users)
                self.assertEqual((self.fixture.private/store).read_bytes(),before_tokens)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--app',type=Path,required=True); parser.add_argument('--case')
    args=parser.parse_args(); APP=args.app.resolve()
    if not (APP/'lib/bootstrap.php').is_file(): parser.error('--app must contain the real PHP application')
    names=unittest.defaultTestLoader.getTestCaseNames(TokenSessionHTTP)
    suite=unittest.TestSuite(TokenSessionHTTP(name) for name in names if not args.case or args.case in name)
    if not suite.countTestCases(): parser.error('--case did not match a semantic test')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
