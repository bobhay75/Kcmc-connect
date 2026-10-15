#!/usr/bin/env python3
"""Execute the real JSON route with synthetic accounts, sessions and private stores.

Ordinary cases replace only the PHP input stream with a supplied JSON request.
The contention case adds a read-only observer at the actual mutator entry in its
temporary copy, then holds the real workspace lock while probing the native PHP
session lock. No authorization or persistence behavior is replaced. The fixture
opens no socket, contacts no production service, and does not prove HTTP transport
headers/browser behavior. Each request is a fresh PHP process.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
PHP = os.environ.get('KCMC_TEST_PHP', os.environ.get('PHP_BINARY', 'php'))
RUNNER = r'''<?php
declare(strict_types=1);
$case = json_decode(file_get_contents($argv[1]), true, 512, JSON_THROW_ON_ERROR);
ini_set('session.save_path', $case['sessions']);
ini_set('display_errors', '1');
$_SERVER['SCRIPT_NAME'] = '/app/api/team-workspace.php';
$_SERVER['REQUEST_URI'] = $_SERVER['SCRIPT_NAME'];
$_SERVER['HTTP_HOST'] = 'fixture.example.invalid';
$_SERVER['HTTPS'] = 'on';
$_SERVER['REQUEST_METHOD'] = $case['method'];
$_SERVER['CONTENT_TYPE'] = 'application/json';
$_GET = $case['query'];
require $case['app'] . '/lib/bootstrap.php';
if ($case['actor'] !== null) {
    kcmc_login_user(kcmc_find_user_by_id($case['actor']));
    $_COOKIE[session_name()] = session_id();
    $_SESSION['kcmc_auth_last_activity_at'] = time() - 120;
}
if ($case['expired'] && isset($_SESSION)) $_SESSION['kcmc_auth_last_activity_at'] = time() - 1900;
$before = $_SESSION['kcmc_auth_last_activity_at'] ?? null;
$GLOBALS['fixture_team_mutation_probe'] = $case['mutation_probe'] ?? null;
$payload = $case['payload'];
if (is_array($payload)) $payload['csrf'] = $case['bad_csrf'] ? 'invalid-csrf' : ($_SESSION['csrf'] ?? 'anonymous-invalid');
$GLOBALS['fixture_team_input'] = $case['raw'] !== null ? $case['raw'] : ($payload === null ? '' : json_encode($payload, JSON_THROW_ON_ERROR));
$_SERVER['CONTENT_LENGTH'] = (string)strlen($GLOBALS['fixture_team_input']);
final class FixtureTeamInput {
    public $context;
    private int $offset = 0;
    public function stream_open(string $path, string $mode, int $options, ?string &$opened_path): bool { return $path === 'php://input'; }
    public function stream_read(int $count): string { $part = substr($GLOBALS['fixture_team_input'], $this->offset, $count); $this->offset += strlen($part); return $part; }
    public function stream_eof(): bool { return $this->offset >= strlen($GLOBALS['fixture_team_input']); }
    public function stream_stat(): array { return ['size' => strlen($GLOBALS['fixture_team_input'])]; }
    public function stream_tell(): int { return $this->offset; }
    public function stream_seek(int $offset, int $whence): bool { if ($whence !== SEEK_SET || $offset < 0) return false; $this->offset = $offset; return true; }
}
stream_wrapper_unregister('php');
stream_wrapper_register('php', FixtureTeamInput::class);
register_shutdown_function(static function () use ($before): void {
    fwrite(STDERR, "\nTEAM_ROUTE_META=" . json_encode([
        'status' => http_response_code() ?: 200,
        'session_status' => session_status(),
        'last_activity_before' => $before,
        'last_activity_after' => $_SESSION['kcmc_auth_last_activity_at'] ?? null,
    ]) . "\n");
});
require $case['app'] . '/api/team-workspace.php';
'''


class TeamWorkspaceRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kcmc-team-route-')
        self.root = Path(self.tmp.name)
        self.app = self.root / 'app'
        shutil.copytree(APP, self.app)
        (self.app / 'config.php').write_text('<?php return ["session_name" => "KCMC_TEAM_ROUTE_TEST"];')
        self.private = self.root / 'private'; self.private.mkdir(mode=0o700)
        self.sessions = self.root / 'sessions'; self.sessions.mkdir(mode=0o700)
        self.runner = self.root / 'request.php'; self.runner.write_text(RUNNER)
        password = subprocess.check_output([PHP, '-r', 'echo password_hash("Synthetic-Team-Only-2031!", PASSWORD_DEFAULT);'], text=True)
        self.users = [dict(id=uid, active=active, role=role, display_name='Synthetic ' + uid,
            email=uid + '@example.invalid', password_hash=password)
            for uid, role, active in [('owner', 'recovery_admin', True), ('pastor', 'pastor_admin', True),
                ('alice', 'member', True), ('bob', 'member', True), ('prayer', 'prayer_team', True),
                ('inactive', 'member', False)]]
        self.write('users.json', {'version': 1, 'users': self.users})
        self.write('publications.json', {'version': 2, 'projects': [
            {'id': 'pub_aaaaaaaaaaaaaaaaaaaaaaaa', 'name': 'DRAFT TITLE SENTINEL', 'pages': [{'items': [
                {'type': 'text', 'text': 'PRIVATE DRAFT BODY SENTINEL'}]}], 'updated': '2026-10-15T12:00:00Z'}]})
        for name in ['prayers.json', 'timeclock.json', 'invites.json']:
            (self.private / name).write_bytes(('UNRELATED PRIVATE SENTINEL ' + name).encode())
        self.protected = {p.name: p.read_bytes() for p in self.private.iterdir()}
        self.content = (self.app / 'data/content.json').read_bytes()

    def tearDown(self):
        self.assertEqual((self.app / 'data/content.json').read_bytes(), self.content)
        for name, original in self.protected.items():
            self.assertEqual((self.private / name).read_bytes(), original, name + ' changed')
        self.tmp.cleanup()

    def write(self, name, value):
        (self.private / name).write_text(json.dumps(value))

    def route(self, actor='owner', payload=None, query=None, method=None, raw=None, bad_csrf=False, expired=False):
        case = self.root / 'case.json'
        case.write_text(json.dumps(dict(app=str(self.app), sessions=str(self.sessions), actor=actor,
            payload=payload, query=query or {}, method=method or ('POST' if payload is not None or raw is not None else 'GET'),
            raw=raw, bad_csrf=bad_csrf, expired=expired)))
        env = {k: v for k, v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(self.private), KCMC_OPERATIONS_OWNER_USER_ID='owner')
        result = subprocess.run([PHP, '-d', 'output_buffering=0', str(self.runner), str(case)],
            capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotRegex(result.stderr + result.stdout, r'Warning:|Fatal error|Deprecated:|headers already sent')
        match = re.search(r'TEAM_ROUTE_META=(\{[^\n]*\})', result.stderr)
        self.assertIsNotNone(match, result.stderr)
        meta = json.loads(match.group(1))
        try:
            body = json.loads(result.stdout)
        except ValueError:
            self.fail('Route response is not JSON: ' + result.stdout[:2000])
        self.assertIsInstance(body, dict)
        for private_value in ['PRIVATE DRAFT BODY SENTINEL', 'password_hash', 'example.invalid', 'UNRELATED PRIVATE SENTINEL']:
            self.assertNotIn(private_value, result.stdout)
        return meta['status'], body, meta

    def create(self, actor='owner', **fields):
        task = dict(title='Synthetic assigned task', body='Synthetic task details', assigned_to='alice',
            start_date='', due_date='', priority='normal', status='open', blocked=False, publication_id='')
        task.update(fields)
        status, body, _ = self.route(actor, {'action': 'create', 'task': task})
        self.assertEqual(status, 200, body)
        self.assertTrue(body['ok'])
        return body['task']

    def test_json_authentication_expiration_and_inactive_accounts(self):
        for actor, expired in [(None, False), ('inactive', False), ('alice', True)]:
            with self.subTest(actor=actor, expired=expired):
                status, body, _ = self.route(actor=actor, expired=expired)
                self.assertEqual(status, 401)
                self.assertFalse(body['ok'])
                self.assertNotIn('tasks', body)
        self.assertFalse((self.private / 'team-workspace.json').exists())

    def test_passive_poll_releases_session_without_extending_idle_deadline(self):
        status, body, meta = self.route('alice')
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(meta['session_status'], 1, 'Polling must release the PHP session lock')
        self.assertEqual(meta['last_activity_before'], meta['last_activity_after'])
        self.assertFalse((self.private / 'team-workspace.json').exists(), 'A fresh read must not initialize a store')

    def test_contended_post_releases_session_before_the_actual_workspace_mutator(self):
        task = self.create()
        library = self.app / 'lib/team-workspace.php'
        source = library.read_text()
        anchor = 'function kcmc_team_mutate(array $user,string $action,array $input,?int $now=null): array {'
        self.assertEqual(source.count(anchor), 1)
        # Observe the exact boundary without replacing the mutator or route.
        observer = r'''
    if (is_string($GLOBALS['fixture_team_mutation_probe'] ?? null)) {
        file_put_contents($GLOBALS['fixture_team_mutation_probe'], json_encode([
            'session_status'=>session_status(), 'session_id'=>session_id(),
        ], JSON_THROW_ON_ERROR));
    }
'''
        library.write_text(source.replace(anchor, anchor + observer, 1))
        probe = self.root / 'mutation-boundary.json'
        case = self.root / 'contended-case.json'
        case.write_text(json.dumps(dict(app=str(self.app), sessions=str(self.sessions), actor='alice',
            payload={'action':'status', 'task_id':task['id'], 'revision':task['revision'], 'status':'in_progress'},
            query={}, method='POST', raw=None, bad_csrf=False, expired=False, mutation_probe=str(probe))))
        env = {k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(self.private), KCMC_OPERATIONS_OWNER_USER_ID='owner')
        lock_path = self.private / 'team-workspace.json.lock'
        with lock_path.open('r+') as workspace_lock:
            fcntl.flock(workspace_lock, fcntl.LOCK_EX)
            process = subprocess.Popen([PHP, '-d', 'output_buffering=0', str(self.runner), str(case)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            try:
                deadline = time.monotonic() + 10
                boundary = None
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        boundary = json.loads(probe.read_text())
                        break
                    except (FileNotFoundError, json.JSONDecodeError):
                        time.sleep(0.01)
                self.assertIsNotNone(boundary, 'The real route must reach the actual mutator while the workspace is contended')
                self.assertIsNone(process.poll(), 'The actual writer remains blocked on the workspace lock held by this fixture')
                self.assertEqual(boundary['session_status'], 1, 'The mutation must start with PHP_SESSION_NONE')
                session_file = self.sessions / ('sess_' + boundary['session_id'])
                native_probe = r'''$h=fopen($argv[1],'r+');if(!$h)exit(2);$free=flock($h,LOCK_EX|LOCK_NB);echo $free?'UNLOCKED':'LOCKED';if($free)flock($h,LOCK_UN);fclose($h);'''
                result = subprocess.check_output([PHP, '-r', native_probe, str(session_file)], text=True, env=env, timeout=5)
                self.assertEqual(result, 'UNLOCKED', 'An independent PHP request can acquire the same browser session while its writer waits')
            finally:
                fcntl.flock(workspace_lock, fcntl.LOCK_UN)
                try:
                    output, error = process.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate()
                    raise
        self.assertEqual(process.returncode, 0, error + output)
        self.assertNotRegex(error + output, r'Warning:|Fatal error|Deprecated:|headers already sent')
        self.assertEqual(json.loads(output)['task']['status'], 'in_progress')
        metadata = re.search(r'TEAM_ROUTE_META=(\{[^\n]*\})', error)
        self.assertIsNotNone(metadata)
        metadata = json.loads(metadata.group(1))
        self.assertEqual(metadata['session_status'], 1, 'Audit must also leave the session closed')
        self.assertGreater(metadata['last_activity_after'], metadata['last_activity_before'], 'An explicit authenticated POST still records user activity')

    def test_assignment_filter_and_no_draft_or_account_directory_for_members(self):
        assigned = self.create(publication_id='pub_aaaaaaaaaaaaaaaaaaaaaaaa')
        self.create(title='OTHER TASK SENTINEL', assigned_to='bob')
        self.create(title='UNASSIGNED TASK SENTINEL', assigned_to='')
        status, member, _ = self.route('alice')
        self.assertEqual(status, 200)
        self.assertEqual([task['id'] for task in member['tasks']], [assigned['id']])
        self.assertFalse(member['can_manage'])
        self.assertEqual(member['users'], [])
        self.assertEqual(member['publications'], [])
        self.assertNotIn('publication_id', member['tasks'][0])
        self.assertNotIn('DRAFT TITLE SENTINEL', json.dumps(member))
        _, pastor, _ = self.route('pastor')
        self.assertTrue(pastor['can_manage'])
        self.assertEqual(len(pastor['tasks']), 3)
        self.assertTrue(any(user['id'] == 'alice' for user in pastor['users']))
        for user in pastor['users']:
            self.assertEqual(set(user), {'id', 'name'})
        for actor in ['bob', 'prayer']:
            _, page, _ = self.route(actor)
            self.assertNotIn(assigned['id'], json.dumps(page))

    def test_member_can_change_only_assigned_status_and_comment_with_server_actor(self):
        task = self.create()
        status, body, _ = self.route('alice', {'action': 'status', 'task_id': task['id'],
            'revision': task['revision'], 'status': 'in_progress', 'actor_id': 'owner', 'updated_at': 1})
        self.assertEqual(status, 200, body)
        self.assertEqual(body['task']['status'], 'in_progress')
        stored = json.loads((self.private / 'team-workspace.json').read_text())
        self.assertEqual(stored['tasks'][task['id']]['updated_by'], 'alice')
        self.assertNotIn('publication_id', body['task'])
        self.assertNotEqual(body['task']['updated_at'], 1)
        payload = {'action': 'comment', 'context': {'kind': 'task', 'id': task['id']},
            'body': '<script>synthetic plaintext</script>', 'parent_id': '', 'nonce': 'route_comment_nonce_01',
            'author_id': 'owner', 'created_at': 1}
        status, comment, _ = self.route('alice', payload)
        self.assertEqual(status, 200, comment)
        self.assertEqual(comment['comment']['author_id'], 'alice')
        self.assertEqual(comment['comment']['body'], payload['body'])
        self.assertNotEqual(comment['comment']['created_at'], 1)
        status, thread, _ = self.route('alice', query={'action': 'thread', 'kind': 'task', 'id': task['id']})
        self.assertEqual(status, 200)
        self.assertEqual(len(thread['comments']), 1)

    def test_forged_manage_actions_and_other_task_mutations_preserve_exact_store(self):
        alice = self.create()
        bob = self.create(assigned_to='bob')
        before = (self.private / 'team-workspace.json').read_bytes()
        original = dict(title='Escalated', body='', assigned_to='alice', start_date='', due_date='',
            priority='high', status='done', blocked=False, publication_id='')
        requests = [
            {'action': 'create', 'task': original},
            {'action': 'update', 'task_id': alice['id'], 'revision': alice['revision'], 'task': original},
            {'action': 'status', 'task_id': bob['id'], 'revision': bob['revision'], 'status': 'done'},
            {'action': 'comment', 'context': {'kind': 'task', 'id': bob['id']}, 'body': 'Denied comment', 'parent_id': '', 'nonce': 'denied_comment_nonce'},
            {'action': 'comment', 'context': {'kind': 'publication', 'id': 'pub_aaaaaaaaaaaaaaaaaaaaaaaa'}, 'body': 'Denied draft comment', 'parent_id': '', 'nonce': 'denied_publish_nonce'},
        ]
        for payload in requests:
            with self.subTest(action=payload['action']):
                status, body, _ = self.route('alice', payload)
                self.assertIn(status, [403, 404])
                self.assertFalse(body['ok'])
                self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)
        status, body, _ = self.route('alice', query={'action': 'thread', 'kind': 'publication', 'id': 'pub_aaaaaaaaaaaaaaaaaaaaaaaa'})
        self.assertIn(status, [403, 404])
        self.assertNotIn('DRAFT TITLE SENTINEL', json.dumps(body))

    def test_csrf_method_invalid_json_and_size_limits_never_mutate(self):
        task = self.create()
        before = (self.private / 'team-workspace.json').read_bytes()
        payload = {'action': 'status', 'task_id': task['id'], 'revision': task['revision'], 'status': 'done'}
        for kwargs, statuses in [({'payload': payload, 'bad_csrf': True}, [400, 403]),
                ({'method': 'DELETE'}, [405]), ({'raw': '{broken'}, [400, 422]),
                ({'raw': '[]'}, [400, 403, 422]), ({'raw': 'x' * 32769}, [413])]:
            with self.subTest(kwargs=list(kwargs)):
                status, body, _ = self.route('alice', **kwargs)
                self.assertIn(status, statuses)
                self.assertFalse(body['ok'])
                self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)

    def test_stale_task_and_preferences_are_409_without_dropping_changes(self):
        task = self.create()
        payload = {'action': 'status', 'task_id': task['id'], 'revision': task['revision'], 'status': 'done'}
        self.assertEqual(self.route('alice', payload)[0], 200)
        before = (self.private / 'team-workspace.json').read_bytes()
        status, body, _ = self.route('alice', dict(payload, status='open'))
        self.assertEqual(status, 409)
        self.assertFalse(body['ok'])
        self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)
        prefs = {'action': 'preferences', 'revision': 0,
            'preferences': {'view': 'board', 'sort': 'due', 'statusfilter': 'open'}}
        self.assertEqual(self.route('alice', prefs)[0], 200)
        before = (self.private / 'team-workspace.json').read_bytes()
        self.assertEqual(self.route('alice', prefs)[0], 409)
        self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)

    def test_idempotent_comment_does_not_duplicate_or_add_mutation_audit(self):
        task = self.create()
        payload = {'action': 'comment', 'context': {'kind': 'task', 'id': task['id']},
            'body': 'Synthetic retry text', 'parent_id': '', 'nonce': 'retry_route_nonce_01'}
        status, first, _ = self.route('alice', payload)
        self.assertEqual(status, 200, first)
        before = (self.private / 'team-workspace.json').read_bytes()
        audit = (self.private / 'audit.ndjson').read_bytes()
        status, second, _ = self.route('alice', payload)
        self.assertEqual(status, 200)
        self.assertTrue(second['duplicate'])
        self.assertEqual(first['comment']['id'], second['comment']['id'])
        self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)
        self.assertEqual((self.private / 'audit.ndjson').read_bytes(), audit)
        self.assertNotIn(payload['body'], audit.decode())
        self.assertNotIn('Synthetic assigned task', audit.decode())

    def test_publication_threads_and_cross_context_parent_validation_use_real_route(self):
        task = self.create()
        publication = {'action': 'comment', 'context': {'kind': 'publication', 'id': 'pub_aaaaaaaaaaaaaaaaaaaaaaaa'},
            'body': 'Synthetic publisher discussion', 'parent_id': '', 'nonce': 'publication_route_nonce_01'}
        status, result, _ = self.route('pastor', publication)
        self.assertEqual(status, 200, result)
        status, thread, _ = self.route('owner', query={'action': 'thread', 'kind': 'publication', 'id': 'pub_aaaaaaaaaaaaaaaaaaaaaaaa'})
        self.assertEqual(status, 200)
        self.assertEqual(thread['context']['label'], 'DRAFT TITLE SENTINEL')
        self.assertEqual([c['id'] for c in thread['comments']], [result['comment']['id']])
        before = (self.private / 'team-workspace.json').read_bytes()
        status, body, _ = self.route('alice', {'action': 'comment', 'context': {'kind': 'task', 'id': task['id']},
            'body': 'Cross-context forged reply', 'parent_id': result['comment']['id'], 'nonce': 'cross_context_route_nonce'})
        self.assertEqual(status, 422)
        self.assertFalse(body['ok'])
        self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)
        status, body, _ = self.route('owner', query={'action': 'thread', 'kind': 'publication', 'id': 'pub_bbbbbbbbbbbbbbbbbbbbbbbb'})
        self.assertEqual(status, 404)
        self.assertFalse(body['ok'])
        status, body, _ = self.route('pastor', dict(publication, body='Changed retry body'))
        self.assertEqual(status, 409)
        self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)

    def test_deactivated_assignee_cannot_read_or_write_with_a_fresh_bound_session(self):
        task = self.create()
        before = (self.private / 'team-workspace.json').read_bytes()
        accounts = json.loads(json.dumps(self.users))
        next(user for user in accounts if user['id'] == 'alice')['active'] = False
        self.write('users.json', {'version': 1, 'users': accounts})
        try:
            for payload in [None, {'action': 'status', 'task_id': task['id'], 'revision': task['revision'], 'status': 'done'}]:
                status, body, _ = self.route('alice', payload)
                self.assertEqual(status, 401)
                self.assertFalse(body['ok'])
                self.assertEqual((self.private / 'team-workspace.json').read_bytes(), before)
        finally:
            (self.private / 'users.json').write_bytes(self.protected['users.json'])

    def test_corrupt_json_and_schema_return_503_without_replacing_bytes(self):
        self.create()
        for corrupt in [b'{not JSON', b'{"version":1,"revision":0,"tasks":"wrong","comments":[],"preferences":[],"nonces":[]}']:
            with self.subTest(corrupt=corrupt):
                (self.private / 'team-workspace.json').write_bytes(corrupt)
                for kwargs in [{}, {'payload': {'action': 'preferences', 'revision': 0,
                        'preferences': {'view': 'board', 'sort': 'due', 'statusfilter': 'all'}}}]:
                    status, body, _ = self.route('alice', **kwargs)
                    self.assertEqual(status, 503, body)
                    self.assertFalse(body['ok'])
                    self.assertEqual((self.private / 'team-workspace.json').read_bytes(), corrupt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=APP)
    args = parser.parse_args()
    APP = args.app.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TeamWorkspaceRoutes))
    raise SystemExit(not result.wasSuccessful())
