#!/usr/bin/env python3
"""Actual PHP route with isolated stores and a synthetic transport, never the network.

Only the transport argument of the route's existing sender call is substituted in
a temporary copy. Signing, filtering, CSRF, counts, deactivation and rendering use
the actual runtime. The provider callback returns fixed statuses and writes only
synthetic call IDs. This does not prove provider connectivity or device receipt.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
PHP = os.environ.get('KCMC_TEST_PHP', 'php')
RUNNER = r'''<?php
ini_set('session.save_path', $argv[2]);
$_SERVER['SCRIPT_NAME'] = '/app/admin/push.php';
$_SERVER['REQUEST_METHOD'] = $argv[4] === '-' ? 'GET' : 'POST';
$_SERVER['HTTP_HOST'] = 'fixture.example.invalid';
$_SERVER['HTTPS'] = 'on';
register_shutdown_function(static function (): void { fwrite(STDERR, "\nROUTE_STATUS=" . (http_response_code() ?: 200) . "\n"); });
function fixture_push_transport(array $request): array {
    $state = json_decode(file_get_contents($GLOBALS['argv'][7]), true);
    $state[] = $request['url'];
    file_put_contents($GLOBALS['argv'][7], json_encode($state));
    $statuses = explode(',', $GLOBALS['argv'][6]);
    $status = (int)$statuses[min(count($state) - 1, count($statuses) - 1)];
    return ['status' => $status, 'error' => $status === 0 ? 'RAW_ERROR_SECRET_ENDPOINT_AND_TOKEN' : ''];
}
require $argv[1] . '/lib/bootstrap.php';
if ($argv[3] !== '-') kcmc_login_user(kcmc_find_user_by_id($argv[3]));
if ($argv[4] !== '-') {
    $_POST = ['send_scope' => $argv[4], 'confirm_send' => '1', 'csrf' => $argv[5] === 'bad' ? 'bad' : ($_SESSION['csrf'] ?? '')];
}
require $argv[1] . '/admin/push.php';
'''
KEYGEN = r'''$key=openssl_pkey_new(['private_key_type'=>OPENSSL_KEYTYPE_EC,'curve_name'=>'prime256v1']); openssl_pkey_export($key,$pem); file_put_contents($argv[1],$pem); chmod($argv[1],0600); $e=openssl_pkey_get_details($key)['ec']; echo rtrim(strtr(base64_encode("\x04".str_pad($e['x'],32,"\0",STR_PAD_LEFT).str_pad($e['y'],32,"\0",STR_PAD_LEFT)),'+/','-_'),'=');'''


class PushDiagnosticsRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kcmc-push-diagnostics-')
        self.root = Path(self.tmp.name)
        self.app = self.root / 'app'; shutil.copytree(APP, self.app)
        self.private = self.root / 'private'; self.private.mkdir(mode=0o700)
        self.sessions = self.root / 'sessions'; self.sessions.mkdir(mode=0o700)
        self.calls = self.root / 'transport.json'; self.calls.write_text('[]')
        self.runner = self.root / 'route.php'; self.runner.write_text(RUNNER)
        (self.app / 'config.php').write_text('<?php return ["session_name" => "KCMC_PUSH_DIAGNOSTICS"];')
        page = self.app / 'admin/push.php'; text = page.read_text()
        self.assertEqual(text.count('kcmc_push_send_empty($subscription)'), 1)
        page.write_text(text.replace('kcmc_push_send_empty($subscription)', "kcmc_push_send_empty($subscription, 'fixture_push_transport')"))
        self.keyfile = self.root / 'server-only-key.pem'
        self.public = subprocess.check_output([PHP, '-r', KEYGEN, str(self.keyfile)], text=True)
        password = subprocess.check_output([PHP, '-r', 'echo password_hash("Synthetic-Only-2031!", PASSWORD_DEFAULT);'], text=True)
        users = [dict(id=uid, role=role, active=True, display_name=uid, email=uid+'@example.invalid', password_hash=password)
            for uid, role in [('owner','recovery_admin'), ('other','recovery_admin'), ('member','member')]]
        (self.private / 'users.json').write_text(json.dumps({'version': 1, 'users': users}))
        self.subscriptions = [dict(user_id=uid, endpoint='https://93.184.216.34/synthetic-'+uid, active=True,
            keys={'p256dh':'B'*88, 'auth':'C'*24}) for uid in ['owner', 'other']]
        self.store = self.private / 'push-subscriptions.json'
        self.store.write_text(json.dumps({'version': 1, 'subscriptions': self.subscriptions}))
        self.content = (self.app / 'data/content.json').read_bytes()

    def tearDown(self):
        self.assertEqual((self.app / 'data/content.json').read_bytes(), self.content)
        self.tmp.cleanup()

    def route(self, scope='self', actor='owner', status=401, bad_csrf=False, config=None):
        env = {k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(self.private), KCMC_OPERATIONS_OWNER_USER_ID='owner',
            KCMC_PUSH_VAPID_PUBLIC_KEY=self.public, KCMC_PUSH_VAPID_PRIVATE_KEY_FILE=str(self.keyfile),
            KCMC_PUSH_VAPID_SUBJECT='mailto:private-contact@example.invalid')
        if config: env.update(config)
        run = subprocess.run([PHP, '-d', 'output_buffering=0', str(self.runner), str(self.app), str(self.sessions),
            actor or '-', scope or '-', 'bad' if bad_csrf else 'valid', str(status), str(self.calls)],
            capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertNotRegex(run.stderr + run.stdout, r'Warning:|Fatal error|Deprecated:|headers already sent')
        match = re.search(r'ROUTE_STATUS=(\d+)', run.stderr); self.assertIsNotNone(match)
        output = run.stdout
        for secret in [self.public, str(self.keyfile), 'private-contact@example.invalid', 'synthetic-owner', 'synthetic-other',
                'RAW_ERROR_SECRET_ENDPOINT_AND_TOKEN', 'BEGIN PRIVATE KEY', 'p256dh', 'Authorization: vapid']:
            self.assertNotIn(secret, output)
        return int(match.group(1)), output

    def test_provider_authentication_failure_is_an_error_with_safe_actionable_reason(self):
        status, page = self.route(status=403)
        self.assertEqual(status, 200)
        self.assertIn('0 accepted by the push service', page)
        self.assertIn('No notification was accepted', page)
        self.assertIn('rejected authentication (HTTP 403)', page)
        self.assertNotIn('portal-alert success', page)
        self.assertEqual(json.loads(self.calls.read_text()), [self.subscriptions[0]['endpoint']], 'Self-test does not target the other account')

    def test_transport_failure_never_exposes_raw_curl_error(self):
        _, page = self.route(status=0)
        self.assertIn('outbound HTTPS and certificate trust', page)
        self.assertNotIn('portal-alert success', page)

    def test_provider_rate_limit_is_reported_without_automatic_retry(self):
        _, page = self.route(status=429)
        self.assertIn('rate limit was reached (HTTP 429)', page)
        self.assertEqual(len(json.loads(self.calls.read_text())), 1)

    def test_accepted_transport_is_distinguished_from_actual_device_receipt(self):
        _, page = self.route(status=201)
        self.assertIn('portal-alert success', page)
        self.assertIn('1 accepted by the push service', page)
        self.assertIn('Device display and tap behavior still need to be checked', page)

    def test_synthetic_partial_broadcast_uses_warning_and_keeps_safe_failure_counts(self):
        _, page = self.route(scope='broadcast', status='201,429')
        self.assertIn('1 accepted by the push service', page)
        self.assertIn('1 failed', page)
        self.assertIn('rate limit was reached (HTTP 429)', page)
        self.assertNotIn('portal-alert success', page)
        self.assertEqual(json.loads(self.calls.read_text()), [s['endpoint'] for s in self.subscriptions])

    def test_expired_subscription_is_deactivated_only_for_the_targeted_account(self):
        _, page = self.route(status=410)
        self.assertNotIn('portal-alert success', page)
        self.assertIn('1 expired subscriptions removed', page)
        subscriptions = json.loads(self.store.read_text())['subscriptions']
        self.assertFalse(subscriptions[0]['active'])
        self.assertTrue(subscriptions[1]['active'])

    def test_missing_private_key_has_specific_safe_guidance_and_sends_nothing(self):
        _, page = self.route(config={'KCMC_PUSH_VAPID_PRIVATE_KEY_FILE': str(self.root / 'missing-secret-key.pem')})
        self.assertIn('private key file is missing, unreadable or inside the public app', page)
        self.assertNotIn('missing-secret-key.pem', page)
        self.assertEqual(json.loads(self.calls.read_text()), [])

    def test_mismatched_key_pair_has_specific_guidance_without_replacing_keys(self):
        before = self.keyfile.read_bytes()
        _, page = self.route(config={'KCMC_PUSH_VAPID_PUBLIC_KEY':'A'*87})
        self.assertIn('VAPID key pair is invalid or does not match', page)
        self.assertEqual(self.keyfile.read_bytes(), before)
        self.assertEqual(json.loads(self.calls.read_text()), [])

    def test_unsubscribed_account_gets_explicit_error_without_a_send(self):
        self.store.write_text(json.dumps({'version':1, 'subscriptions':[self.subscriptions[1]]}))
        _, page = self.route()
        self.assertIn('This signed-in account has no active subscribed devices', page)
        self.assertEqual(json.loads(self.calls.read_text()), [])

    def test_csrf_and_owner_gate_prevent_provider_calls(self):
        _, page = self.route(bad_csrf=True)
        self.assertIn('Please reload and try again', page)
        for actor in ['other', 'member', None]:
            status, _ = self.route(actor=actor)
            self.assertEqual(status, 302 if actor is None else 403)
        self.assertEqual(json.loads(self.calls.read_text()), [])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--app', type=Path, default=APP)
    args = parser.parse_args(); APP = args.app.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PushDiagnosticsRoutes))
    raise SystemExit(not result.wasSuccessful())
