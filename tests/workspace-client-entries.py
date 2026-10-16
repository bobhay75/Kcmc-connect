#!/usr/bin/env python3
"""Real-PHP navigation/auth checks with isolated synthetic account/work stores."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('account_routes',ROOT/'tests/member-account-routes.py')
routes=importlib.util.module_from_spec(spec);spec.loader.exec_module(routes)
TASK='teamtask_'+'a'*24

class WorkspaceEntries(unittest.TestCase):
    def setUp(self): self.f=routes.Fixture(routes.APP)
    def tearDown(self): self.f.close()
    def workspace(self, assignee='member'):
        task=dict(id=TASK,revision=1,title='PRIVATE ASSIGNMENT TEXT',body='PRIVATE THREAD CONTEXT',assigned_to=assignee,created_by='owner',updated_by='owner',created_at=1792000000,updated_at=1792000000,blocked=False,priority='normal',status='open',publication_id='',start_date='',due_date='')
        state=dict(version=1,revision=1,tasks={TASK:task},comments={},preferences={},nonces={})
        path=self.f.private/'team-workspace.json';path.write_text(json.dumps(state));path.chmod(0o600);return path
    def test_missing_workspace_never_creates_store_or_clutters_personal_account(self):
        path=self.f.private/'team-workspace.json'
        for actor in ['owner','pastor','recovery','member','prayer']:
            status,page=self.f.route('member/index.php',actor)
            self.assertEqual(status,200);self.assertNotIn('member/work.php',page)
            self.assertEqual(page.count('<strong>Prayer &amp; Care</strong>'),int(actor in ['owner','pastor','member','prayer']))
            self.assertNotIn('Earlier prayer requests',page);self.assertNotIn('member/prayers.php',page)
        self.assertFalse(path.exists());self.assertFalse(Path(str(path)+'.lock').exists())
    def test_work_link_is_only_for_current_explicit_assignee_and_reads_no_task_text_into_account(self):
        path=self.workspace();before=path.read_bytes()
        for actor in ['owner','pastor','recovery','member','prayer']:
            status,page=self.f.route('member/index.php',actor)
            self.assertEqual(status,200);self.assertEqual('member/work.php' in page,actor=='member')
            self.assertNotIn('PRIVATE ASSIGNMENT TEXT',page);self.assertNotIn('PRIVATE THREAD CONTEXT',page)
        self.assertEqual(path.read_bytes(),before)
        state=json.loads(before);state['tasks'][TASK]['assigned_to']='prayer';path.write_text(json.dumps(state))
        self.assertNotIn('member/work.php',self.f.route('member/index.php','member')[1])
        self.assertIn('member/work.php',self.f.route('member/index.php','prayer')[1])
    def test_corrupt_workspace_does_not_break_account_or_rewrite_corrupt_bytes(self):
        path=self.workspace();path.write_text('{corrupt synthetic workspace')
        before=path.read_bytes()
        status,page=self.f.route('member/index.php','member')
        self.assertEqual(status,200);self.assertNotIn('member/work.php',page);self.assertEqual(path.read_bytes(),before)
    def test_admin_link_uses_existing_publisher_capability(self):
        for actor in ['owner','pastor','recovery','prayer']:
            status,page=self.f.route('admin/home.php',actor)
            self.assertEqual(status,200);self.assertEqual('Open Team workspace' in page,actor!='prayer')
            self.assertEqual('href="/app/member/work.php"' in page,actor!='prayer')
        self.assertEqual(self.f.route('admin/home.php','member')[0],403)
    def test_admin_hub_is_grouped_link_rows_with_exact_role_targets(self):
        publishing={'member/work.php','admin/','admin/users.php','admin/password-resets.php','admin/rsvps.php','admin/connections.php'}
        prayer={'admin/prayer-inbox.php','admin/prayers.php','admin/prayer-care.php'}
        owner={'admin/timecards.php','admin/payroll-setup.php','admin/push.php','admin/operations.php'}
        expected={'owner':publishing|prayer|owner,'pastor':publishing|prayer,'recovery':publishing,'prayer':{'admin/prayer-inbox.php'}}
        for actor,targets in expected.items():
            with self.subTest(actor=actor):
                status,page=self.f.route('admin/home.php',actor);self.assertEqual(status,200)
                rows=re.findall(r'<a class="admin-link" href="/app/([^"]*)" aria-label="Open ([^"]+)">',page)
                self.assertEqual({href for href,label in rows},targets)
                self.assertEqual(len(rows),len(targets))
                groups=re.findall(r'<nav class="admin-links" aria-label="([^"]+)">',page)
                self.assertLessEqual(len(groups),3);self.assertEqual(len(groups),len(set(groups)))
                self.assertNotIn('class="portal-card admin-tool"',page)
                self.assertEqual(routes.page_control_links(page), [
                    ('← Back', '/app/member/'), ('Home', '/app/'),
                    ('My account', '/app/member/'), ('Time clock', '/app/member/timeclock.php')])
                if actor=='prayer':self.assertEqual(groups,['People &amp; care'])
    def test_authenticated_work_shell_and_no_embedded_private_state(self):
        path=self.workspace();before=path.read_bytes()
        for actor in ['owner','pastor','recovery','member','prayer']:
            status,page=self.f.route('member/work.php',actor)
            self.assertEqual(status,200);self.assertIn('id="workspace"',page)
            self.assertIn('data-api="/app/api/team-workspace.php"',page);self.assertIn('data-csrf="',page)
            self.assertIn('href="/app/member/">← My account',page);self.assertIn('href="/app/">Home',page)
            self.assertNotIn('PRIVATE ASSIGNMENT TEXT',page);self.assertNotIn('PRIVATE THREAD CONTEXT',page)
            self.assertNotIn('alice@example',page)
        self.assertEqual(path.read_bytes(),before)
        for actor in [None,'inactive']:
            status,page=self.f.route('member/work.php',actor)
            self.assertEqual(status,302);self.assertNotIn('id="workspace"',page)
    def test_history_is_contextual_disclosure_and_keeps_existing_route(self):
        for actor in ['owner','pastor','member','prayer']:
            status,page=self.f.route('member/prayer-care.php',actor)
            self.assertEqual(status,200)
            self.assertRegex(page,r'<details class="care-section"><summary>Earlier prayer requests</summary>')
            self.assertIn('href="/app/member/prayers.php">Open earlier prayer requests',page)
            self.assertNotIn('SECRET OTHER PRAYER',page)
        self.assertNotIn('Open earlier prayer requests',self.f.route('admin/prayer-care.php','owner')[1])

if __name__=='__main__':unittest.main(verbosity=2)
