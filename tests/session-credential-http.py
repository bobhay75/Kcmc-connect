#!/usr/bin/env python3
"""Multi-browser credential revocation on the real routes, synthetic accounts only."""
import argparse
import copy
import hashlib
import hmac
import html
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
import unittest

spec = importlib.util.spec_from_file_location('token_session_fixture', Path(__file__).with_name('token-session-http.py'))
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
OLD_PASSWORD = fixture_module.OLD_PASSWORD
NEW_PASSWORD = fixture_module.NEW_PASSWORD
APP = None

class SessionCredentialHTTP(unittest.TestCase):
    def setUp(self):
        fixture_module.APP = APP
        self.fixture = fixture_module.Fixture()
    def tearDown(self): self.fixture.close()
    def csrf(self, client, route):
        status, _, body = client.request(route)
        self.assertEqual(status, 200)
        self.assertNotRegex(body, r'(?i)Warning:|Fatal error|headers already sent')
        match = re.search(r'name="csrf" value="([^"]+)"', body)
        self.assertIsNotNone(match, 'A real session-bound CSRF form is required')
        return html.unescape(match.group(1))
    def login(self, uid='member', password=OLD_PASSWORD):
        client = self.fixture.client()
        token = self.csrf(client, '/member/login.php')
        status, _, _ = client.request('/member/login.php', {'csrf': token, 'email': uid+'@example.invalid', 'password': password})
        self.assertEqual(status, 302, 'Fresh credentials must sign in')
        self.assertEqual(client.request('/member/')[0], 200)
        return client
    def cookie(self, client):
        return next(c.value for c in client.cookies if c.name == fixture_module.SESSION_NAME)
    def session(self, client, updates=None, remove=()):
        script = ('ini_set("session.save_path",$argv[1]); session_id($argv[2]); session_start(); '
                  '$updates=json_decode($argv[3],true); foreach($updates as $key=>$value) $_SESSION[$key]=$value; '
                  'foreach(json_decode($argv[4],true) as $key) unset($_SESSION[$key]); '
                  'echo json_encode($_SESSION); session_write_close();')
        return json.loads(subprocess.check_output(['php', '-r', script, str(self.fixture.sessions),
            self.cookie(client), json.dumps(updates or {}), json.dumps(list(remove))], text=True))
    def password_change(self, client, csrf=None):
        token = csrf if csrf is not None else self.csrf(client, '/member/password.php')
        return client.request('/member/password.php', {'csrf': token, 'current_password': OLD_PASSWORD,
            'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD})
    def assert_rejected(self, client):
        status, headers, _ = client.request('/member/')
        self.assertEqual(status, 302, 'Stale authenticated browser must be redirected before private content is served')
        self.assertIn('/member/login.php?', headers.get('Location', ''))
        self.assertIn('expired=1', headers.get('Location', ''))
    def assert_preserved(self, before, after):
        self.assertEqual(set(after)-set(before), set(), 'Credential update must add no account schema fields')
        for field, value in before.items():
            if field not in ('password_hash', 'updated_at', 'last_login_at'):
                self.assertEqual(after[field], value, 'Credential update must preserve '+field)
    def prepare_race(self, replacement_users):
        # Only the temporary copied app is instrumented. A competing write runs
        # immediately before the production users-store lock, after verification.
        bootstrap = self.fixture.app/'lib/bootstrap.php'
        marker = 'function kcmc_update_json_store(string $path, array $default, callable $callback): mixed {\n'
        source = bootstrap.read_text()
        self.assertEqual(source.count(marker), 1)
        hook = ('    if ($path === KCMC_USERS && is_file(KCMC_PRIVATE_DATA . "/synthetic-race.json")) {\n'
                '        file_put_contents(KCMC_USERS, file_get_contents(KCMC_PRIVATE_DATA . "/synthetic-race.json"));\n'
                '        unlink(KCMC_PRIVATE_DATA . "/synthetic-race.json");\n'
                '    }\n')
        bootstrap.write_text(source.replace(marker, marker+hook))
        self.fixture.write('synthetic-race.json', replacement_users)
    def test_password_change_preserves_only_current_browser_and_lifetime(self):
        actor = self.login(); other = self.login(); issuer = self.login('issuer')
        before = copy.deepcopy(self.fixture.user('member'))
        original_id = self.cookie(actor)
        original = self.session(actor)
        started = original['kcmc_auth_started_at'] - 1000
        self.session(actor, {'kcmc_auth_started_at': started})
        csrf = self.csrf(actor, '/member/password.php')
        status, _, body = self.password_change(actor, csrf)
        self.assertEqual(status, 200)
        self.assertIn('other sessions must sign in again', body)
        self.assertNotEqual(self.cookie(actor), original_id, 'Password change rotates the session ID')
        after = self.session(actor)
        self.assertNotEqual(after['csrf'], original['csrf'])
        self.assertNotEqual(after['kcmc_auth_credential_tag'], original['kcmc_auth_credential_tag'])
        self.assertEqual(after['kcmc_auth_started_at'], started, 'Password change must retain original absolute expiry')
        self.assertEqual(actor.request('/member/')[0], 200)
        self.assert_rejected(other)
        self.assertEqual(issuer.request('/member/')[0], 200, 'Other accounts retain access')
        self.assert_preserved(before, self.fixture.user('member'))
        self.assertTrue(self.fixture.password_matches('member', NEW_PASSWORD))
        self.assertFalse(self.fixture.password_matches('member', OLD_PASSWORD))
        for session_file in self.fixture.sessions.glob('sess_*'):
            raw = session_file.read_text()
            self.assertNotIn(before['password_hash'], raw)
            self.assertNotIn(self.fixture.user('member')['password_hash'], raw)
        self.assertEqual((self.fixture.app/'data/content.json').read_bytes(), self.fixture.content)
    def test_reset_revokes_both_existing_sessions_without_authenticating_bearer(self):
        first = self.login(); second = self.login(); issuer = self.login('issuer')
        route, token = self.fixture.seed('reset')
        bearer = self.fixture.client(); csrf = self.csrf(bearer, route)
        before = copy.deepcopy(self.fixture.user('member'))
        status, headers, _ = bearer.request(route, {'csrf': csrf, 'token': token, 'password': NEW_PASSWORD, 'confirm': NEW_PASSWORD})
        self.assertEqual(status, 302)
        self.assertTrue(headers['Location'].endswith('/member/login.php?reset=1'))
        self.assertEqual(bearer.request('/member/')[0], 302)
        self.assert_rejected(first); self.assert_rejected(second)
        self.assertEqual(issuer.request('/member/')[0], 200)
        self.assert_preserved(before, self.fixture.user('member'))
        self.login(password=NEW_PASSWORD)
    def test_signed_in_reset_browser_is_also_revoked(self):
        actor = self.login(); route, token = self.fixture.seed('reset')
        csrf = self.csrf(actor, route)
        self.assertEqual(actor.request(route, {'csrf': csrf, 'token': token, 'password': NEW_PASSWORD, 'confirm': NEW_PASSWORD})[0], 302)
        self.assert_rejected(actor)
    def test_legacy_and_tampered_sessions_require_fresh_sign_in(self):
        for mode in ('legacy', 'tampered'):
            with self.subTest(mode=mode):
                actor = self.login()
                if mode == 'legacy':
                    self.session(actor, remove=('kcmc_auth_credential_nonce', 'kcmc_auth_credential_tag'))
                else:
                    self.session(actor, {'kcmc_auth_credential_tag': '0'*64})
                self.assert_rejected(actor)
                self.login()
    def test_automatic_rehash_binds_new_hash_and_rejects_older_session(self):
        users = self.fixture.read('users.json')
        weak_hash = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1],PASSWORD_BCRYPT,["cost"=>4]);', OLD_PASSWORD], text=True).strip()
        users['users'][1]['password_hash'] = weak_hash
        self.fixture.write('users.json', users)
        # Represent a browser authenticated before the password-algorithm upgrade.
        older = self.fixture.client(); self.csrf(older, '/member/login.php')
        nonce = 'a'*64
        tag = hmac.new(nonce.encode(), b'kcmc-session-credential-v1\0member\0'+weak_hash.encode(), hashlib.sha256).hexdigest()
        now = int(time.time())
        self.session(older, {'kcmc_user_id': 'member', 'kcmc_auth_credential_nonce': nonce,
            'kcmc_auth_credential_tag': tag, 'kcmc_auth_started_at': now,
            'kcmc_auth_last_activity_at': now, 'kcmc_auth_last_regenerated_at': now})
        self.assertEqual(older.request('/member/')[0], 200)
        actor = self.login()
        self.assertNotEqual(self.fixture.user('member')['password_hash'], weak_hash)
        self.assertEqual(actor.request('/member/')[0], 200, 'Automatic rehash keeps the new login usable')
        self.assert_rejected(older)
        self.assert_preserved(users['users'][1], self.fixture.user('member'))
    def test_password_change_cannot_overwrite_concurrent_reset(self):
        actor = self.login(); csrf = self.csrf(actor, '/member/password.php')
        replacement = self.fixture.read('users.json')
        fresh_hash = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1],PASSWORD_DEFAULT);', 'Synthetic simultaneous reset 2031!'], text=True).strip()
        replacement['users'][1]['password_hash'] = fresh_hash
        self.prepare_race(replacement)
        status, _, body = self.password_change(actor, csrf)
        self.assertEqual(status, 200)
        self.assertIn('Your account changed.', body)
        self.assertEqual(self.fixture.user('member')['password_hash'], fresh_hash)
        self.assert_rejected(actor)
    def test_rehash_cannot_overwrite_concurrent_reset_or_deactivation(self):
        for race in ('reset', 'deactivation'):
            with self.subTest(race=race):
                weak_hash = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1],PASSWORD_BCRYPT,["cost"=>4]);', OLD_PASSWORD], text=True).strip()
                users = self.fixture.read('users.json'); users['users'][1]['active'] = True; users['users'][1]['password_hash'] = weak_hash
                self.fixture.write('users.json', users)
                replacement = copy.deepcopy(users)
                if race == 'deactivation': replacement['users'][1]['active'] = False
                else: replacement['users'][1]['password_hash'] = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1],PASSWORD_DEFAULT);', NEW_PASSWORD], text=True).strip()
                # Remove a previous test-only hook before inserting the next one.
                (self.fixture.app/'lib/bootstrap.php').write_bytes((APP/'lib/bootstrap.php').read_bytes())
                self.prepare_race(replacement)
                client = self.fixture.client(); csrf = self.csrf(client, '/member/login.php')
                status, _, body = client.request('/member/login.php', {'csrf': csrf, 'email': 'member@example.invalid', 'password': OLD_PASSWORD})
                self.assertEqual(status, 200)
                self.assertIn('The email or password was not recognized.', body)
                self.assertEqual(self.fixture.user('member'), replacement['users'][1], 'Stale rehash must not overwrite newer credential/activation state')
                self.assertEqual(client.request('/member/')[0], 302)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--app', type=Path, required=True); parser.add_argument('--case')
    args = parser.parse_args(); APP = args.app.resolve()
    if not (APP/'lib/bootstrap.php').is_file(): parser.error('--app must contain the real PHP application')
    names = unittest.defaultTestLoader.getTestCaseNames(SessionCredentialHTTP)
    suite = unittest.TestSuite(SessionCredentialHTTP(name) for name in names if not args.case or args.case in name)
    if not suite.countTestCases(): parser.error('--case did not match a semantic test')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
