#!/usr/bin/env python3
"""Historical and current account guards with real PHP routes; no delivery.

This is a CLI route harness, so it proves PHP authorization, rendered controls and
store effects, not HTTP transport headers or browser interactions. Each request
loads unmodified route source in a fresh PHP process and isolated session.

The default suite preserves every original A7/A5 assertion against the exact
workflow preimage. --current-account-guards additionally runs all compatible
account/authorization cases on the current app; only the superseded personal
Send update placement case is historical. Current administrative navigation and
broadcast journeys have their own required real-route suites.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from workflow_source_layer import Layer

APP = Path(__file__).resolve().parents[1] / 'KCMC-Connect-Phase6-Recreated'
PHP = os.environ.get('KCMC_TEST_PHP', 'php')
PHP_RUNNER = r'''<?php
ini_set('session.save_path', $argv[2]);
ini_set('display_errors', '1');
$_SERVER['SCRIPT_NAME'] = '/app/' . $argv[3];
$_SERVER['REQUEST_METHOD'] = $argv[5] === '-' ? 'GET' : 'POST';
$_SERVER['HTTP_HOST'] = 'fixture.example.invalid';
$_SERVER['HTTPS'] = 'on';
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
        self.tmp = tempfile.TemporaryDirectory(prefix='kcmc-owner-ui-cli-')
        self.root = Path(self.tmp.name)
        self.app = self.root / 'app'
        shutil.copytree(app, self.app)
        (self.app / 'config.php').write_text('<?php return ["session_name" => "KCMC_OWNER_UI_TEST"];?>\n')
        self.private = self.root / 'private'; self.private.mkdir(mode=0o700)
        self.sessions = self.root / 'sessions'; self.sessions.mkdir(mode=0o700)
        self.runner = self.root / 'request.php'; self.runner.write_text(PHP_RUNNER)
        password_hash = subprocess.check_output([PHP, '-r', 'echo password_hash("Synthetic-Owner-UI-2031!", PASSWORD_DEFAULT);'], text=True)
        self.initial_users = [dict(id=uid, role=role, active=active, display_name='Synthetic '+uid,
            email=uid+'@example.invalid', email_normalized=uid+'@example.invalid', password_hash=password_hash)
            for uid, role, active in [('owner', 'recovery_admin', True), ('pastor_owner', 'pastor_admin', True),
                ('recovery', 'recovery_admin', True), ('pastor', 'pastor_admin', True), ('member', 'member', True),
                ('prayer', 'prayer_team', True), ('inactive', 'recovery_admin', False)]]
        self.reset()
        self.content = (self.app / 'data/content.json').read_bytes()
    def close(self): self.tmp.cleanup()
    def write(self, name, value): (self.private / name).write_text(json.dumps(value))
    def read(self, name): return json.loads((self.private / name).read_text())
    def reset(self):
        self.write('users.json', {'version': 1, 'users': copy.deepcopy(self.initial_users)})
        self.write('invites.json', {'version': 1, 'invites': []})
        self.write('password-resets.json', {'version': 1, 'resets': []})
        self.write('push-subscriptions.json', {'version': 1, 'subscriptions': []})
    def route(self, route, actor=None, post=None, configured='owner', bad_csrf=False):
        env = {k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(self.private), KCMC_OPERATIONS_OWNER_USER_ID=configured,
            KCMC_SETUP_KEY='', KCMC_PUSH_VAPID_PUBLIC_KEY='A'*88)
        run = subprocess.run([PHP, '-d', 'output_buffering=0', str(self.runner), str(self.app), str(self.sessions), route,
            actor or '-', json.dumps(post) if post is not None else '-', 'bad' if bad_csrf else 'valid'],
            capture_output=True, text=True, env=env, timeout=15)
        if run.returncode != 0: raise AssertionError(run.stderr + '\n' + run.stdout)
        if re.search(r'(?i)Warning:|Fatal error|headers already sent|Deprecated:', run.stderr + run.stdout):
            raise AssertionError(run.stderr + '\n' + run.stdout)
        status = re.search(r'KCMC_ROUTE_STATUS=(\{[^\n]*\})', run.stderr)
        if status is None: raise AssertionError('Real route did not complete: '+run.stderr)
        return json.loads(status.group(1))['status'], run.stdout


class NarrowOwnerRoutes(unittest.TestCase):
    def setUp(self): self.fixture = Fixture(APP)
    def tearDown(self): self.fixture.close()
    def no_content_change(self):
        self.assertEqual((self.fixture.app / 'data/content.json').read_bytes(), self.fixture.content)
    def user(self, uid): return next(u for u in self.fixture.read('users.json')['users'] if u['id'] == uid)
    def test_send_update_link_matches_existing_owner_route_for_every_role_and_config(self):
        for configured in ['owner', 'pastor_owner', '', 'member', 'inactive', 'different-id']:
            for actor in ['owner', 'pastor_owner', 'recovery', 'pastor', 'member', 'prayer']:
                with self.subTest(configured=configured, actor=actor):
                    status, page = self.fixture.route('member/notifications.php', actor, configured=configured)
                    self.assertEqual(status, 200)
                    self.assertIn('Enable notifications', page, 'Ordinary device subscription controls are retained')
                    linked = 'href="/app/admin/push.php"' in page
                    expected = actor == configured and actor in ['owner', 'pastor_owner', 'recovery', 'pastor']
                    self.assertEqual(linked, expected, 'Only the exact configured active administrator gets Send update')
                    send_status, send_page = self.fixture.route('admin/push.php', actor, configured=configured)
                    self.assertEqual(send_status, 200 if expected else 403,
                        'Send update visibility agrees with the unchanged real destination authorization')
                    if not expected: self.assertNotIn('Notify subscribed devices', send_page)
        self.no_content_change()
    def test_inactive_and_anonymous_accounts_never_render_or_reach_owner_sender(self):
        for actor in ['inactive', None]:
            for route in ['member/notifications.php', 'admin/push.php']:
                status, page = self.fixture.route(route, actor, configured='inactive')
                self.assertEqual(status, 302)
                self.assertNotIn('Send update', page)
                self.assertNotIn('Notify subscribed devices', page)
    def test_other_administrators_cannot_disable_or_reset_either_owner_role(self):
        for configured in ['owner', 'pastor_owner']:
            for actor in ['recovery', 'pastor']:
                with self.subTest(configured=configured, actor=actor):
                    self.fixture.reset()
                    before = (self.fixture.private / 'users.json').read_bytes()
                    reset_before = (self.fixture.private / 'password-resets.json').read_bytes()
                    status, users_page = self.fixture.route('admin/users.php', actor, configured=configured)
                    self.assertEqual(status, 200)
                    self.assertIn('Designated owner account', users_page)
                    self.assertNotIn('name="user_id" value="'+configured+'"', users_page,
                        'No owner enable/disable form is offered to another administrator')
                    status, page = self.fixture.route('admin/users.php', actor,
                        {'action':'set_active', 'user_id':configured, 'active':'0'}, configured=configured)
                    self.assertEqual(status, 200)
                    self.assertIn('Another administrator cannot change the designated owner account.', page)
                    self.assertEqual((self.fixture.private / 'users.json').read_bytes(), before)
                    status, reset_page = self.fixture.route('admin/password-resets.php', actor, configured=configured)
                    self.assertEqual(status, 200)
                    self.assertNotIn('name="user_id" value="'+configured+'"', reset_page)
                    self.assertIn('Designated owner account', reset_page)
                    status, reset_page = self.fixture.route('admin/password-resets.php', actor,
                        {'user_id': configured}, configured=configured)
                    self.assertEqual(status, 200)
                    self.assertIn('Another administrator cannot reset the designated owner account.', reset_page)
                    self.assertEqual((self.fixture.private / 'password-resets.json').read_bytes(), reset_before)
                    self.assertEqual((self.fixture.private / 'users.json').read_bytes(), before)
        self.no_content_change()
    def test_crafted_post_cannot_disable_the_designated_owner(self):
        before = (self.fixture.private / 'users.json').read_bytes()
        status, page = self.fixture.route('admin/users.php', 'recovery',
            {'action':'set_active', 'user_id':'owner', 'active':'0'})
        self.assertEqual(status, 200)
        self.assertEqual((self.fixture.private / 'users.json').read_bytes(), before,
            'A recovery administrator cannot disable the configured owner with a valid-CSRF crafted POST')
        self.assertIn('Another administrator cannot change the designated owner account.', page)
    def test_crafted_post_cannot_issue_a_password_reset_for_the_designated_owner(self):
        before = (self.fixture.private / 'password-resets.json').read_bytes()
        status, page = self.fixture.route('admin/password-resets.php', 'recovery', {'user_id':'owner'})
        self.assertEqual(status, 200,
            'A recovery administrator cannot obtain an owner reset link with a valid-CSRF crafted POST')
        self.assertEqual((self.fixture.private / 'password-resets.json').read_bytes(), before)
        self.assertIn('Another administrator cannot reset the designated owner account.', page)
    def test_owner_self_disable_and_administrator_self_reset_policy_is_unchanged(self):
        for actor in ['owner', 'pastor_owner', 'recovery', 'pastor']:
            configured = actor if actor in ['owner', 'pastor_owner'] else 'owner'
            before = (self.fixture.private / 'users.json').read_bytes()
            status, page = self.fixture.route('admin/users.php', actor,
                {'action':'set_active', 'user_id':actor, 'active':'0'}, configured=configured)
            self.assertEqual(status, 200)
            self.assertIn('You cannot disable your own account.', page)
            self.assertEqual((self.fixture.private / 'users.json').read_bytes(), before)
            before_resets = (self.fixture.private / 'password-resets.json').read_bytes()
            status, page = self.fixture.route('admin/password-resets.php', actor,
                {'user_id': actor}, configured=configured)
            self.assertEqual(status, 200)
            self.assertIn('Account Security', page)
            self.assertEqual((self.fixture.private / 'password-resets.json').read_bytes(), before_resets)
        self.no_content_change()
    def test_normal_staff_and_nonowner_administrator_workflows_are_preserved(self):
        for actor, target, permitted in [('owner','member',True), ('recovery','member',True), ('pastor','member',True),
                ('recovery','pastor',True), ('recovery','pastor_owner',True), ('pastor','recovery',False)]:
            with self.subTest(actor=actor, target=target):
                self.fixture.reset()
                before = copy.deepcopy(self.user(target))
                status, _ = self.fixture.route('admin/users.php', actor,
                    {'action':'set_active', 'user_id':target, 'active':'0'})
                self.assertEqual(status, 200)
                after = self.user(target)
                self.assertEqual(after['active'], not permitted)
                self.assertEqual({k:v for k,v in after.items() if k not in ['active','updated_at']},
                    {k:v for k,v in before.items() if k not in ['active','updated_at']})
        for actor, target, permitted in [('owner','member',True), ('pastor','member',True), ('pastor','prayer',True),
                ('recovery','pastor',True), ('recovery','pastor_owner',True), ('pastor','recovery',False)]:
            with self.subTest(reset_actor=actor, target=target):
                self.fixture.reset()
                before = (self.fixture.private / 'users.json').read_bytes()
                status, _ = self.fixture.route('admin/password-resets.php', actor, {'user_id':target})
                self.assertEqual(status, 302 if permitted else 200)
                resets = self.fixture.read('password-resets.json')['resets']
                self.assertEqual(len(resets), int(permitted))
                if permitted:
                    self.assertEqual(resets[0]['user_id'], target)
                    self.assertEqual(resets[0]['created_by'], actor)
                self.assertEqual((self.fixture.private / 'users.json').read_bytes(), before)
        self.no_content_change()
    def test_inactive_actor_and_bad_csrf_cannot_mutate_or_issue_reset(self):
        for actor, bad_csrf in [('inactive', False), ('recovery', True)]:
            for route, post in [('admin/users.php', {'action':'set_active','user_id':'member','active':'0'}),
                    ('admin/password-resets.php', {'user_id':'member'})]:
                self.fixture.reset()
                before_users = (self.fixture.private / 'users.json').read_bytes()
                before_resets = (self.fixture.private / 'password-resets.json').read_bytes()
                status, _ = self.fixture.route(route, actor, post, bad_csrf=bad_csrf)
                self.assertEqual(status, 302 if actor == 'inactive' else 200)
                self.assertEqual((self.fixture.private / 'users.json').read_bytes(), before_users)
                self.assertEqual((self.fixture.private / 'password-resets.json').read_bytes(), before_resets)
    def test_missing_owner_configuration_preserves_existing_account_authority(self):
        before = copy.deepcopy(self.user('owner'))
        status, _ = self.fixture.route('admin/users.php', 'recovery',
            {'action':'set_active','user_id':'owner','active':'0'}, configured='')
        self.assertEqual(status, 200)
        self.assertFalse(self.user('owner')['active'])
        self.assertEqual({k:v for k,v in self.user('owner').items() if k not in ['active','updated_at']},
            {k:v for k,v in before.items() if k not in ['active','updated_at']},
            'This guard does not guess or assign an owner when the existing server setting is missing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--current-account-guards', action='store_true')
    args = parser.parse_args()
    historical = None
    if args.app:
        # Explicit app is used by the exact prior-source negative controls.
        APP = args.app.resolve()
    elif args.current_account_guards:
        print('Current application account and owner authorization route checks', flush=True)
    else:
        historical = tempfile.TemporaryDirectory(prefix='kcmc-owner-ui-historical-')
        APP = Layer(APP.parent).copy_baseline(Path(historical.name) / 'app')
        print('Historical A7/A5 routes: exact workflow preimage, original assertions preserved', flush=True)
    try:
        if args.case:
            suite = unittest.defaultTestLoader.loadTestsFromName(args.case, NarrowOwnerRoutes)
        elif args.current_account_guards:
            names = unittest.defaultTestLoader.getTestCaseNames(NarrowOwnerRoutes)
            suite = unittest.TestSuite(NarrowOwnerRoutes(name) for name in names
                if name != 'test_send_update_link_matches_existing_owner_route_for_every_role_and_config')
        else:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(NarrowOwnerRoutes)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(not result.wasSuccessful())
    finally:
        if historical:
            historical.cleanup()
