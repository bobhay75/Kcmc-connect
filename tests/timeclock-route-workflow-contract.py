#!/usr/bin/env python3
"""Execute real protected PHP routes with synthetic account/session/private files only."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
PHP = os.environ.get('PHP_BINARY', 'php')
WRAPPER = r'''<?php
$case=json_decode(file_get_contents($argv[1]),true,512,JSON_THROW_ON_ERROR);
putenv('KCMC_PRIVATE_DATA_DIR='.$case['private']);
putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
$_SERVER['SCRIPT_NAME']='/kcmc-connect/'.$case['route'];
$_SERVER['REQUEST_URI']=$_SERVER['SCRIPT_NAME'];
$_SERVER['REQUEST_METHOD']=$case['method'];
require $case['app'].'/lib/bootstrap.php';
ini_set('session.save_path',$case['private']);
$user=kcmc_find_user_by_id($case['login']);
if($user)kcmc_login_user($user);
$_POST=$case['post'];
$_POST['csrf']=$case['bad_csrf']?'forged-token':kcmc_csrf();
require $case['app'].'/'.$case['route'];
'''

class TimeclockRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kcmc-clock-routes-')
        self.private = Path(self.tmp.name)
        self.wrapper = self.private / 'route.php'
        self.wrapper.write_text(WRAPPER)
        self.today = datetime.datetime.now(ZoneInfo('America/Chicago')).date()
        start_month = self.today.replace(day=23)
        if self.today.day < 23:
            start_month = (self.today.replace(day=1)-datetime.timedelta(days=1)).replace(day=23)
        end_month = (start_month.replace(day=28)+datetime.timedelta(days=4)).replace(day=23)-datetime.timedelta(days=1)
        self.start, self.end = str(start_month), str(end_month)
        self.seed()

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self, status=None, running=False, break_open=False):
        now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        self.entry={'id':'recorded','user_id':'owner','work_date':str(self.today),'clock_in_at':(now-datetime.timedelta(hours=2)).isoformat(),'clock_out_at':None if running else now.isoformat(),'net_minutes':0 if running else 120,'status':'open' if running else ('approved' if status=='approved' else 'completed'),'category':'Other','description':'','breaks':([{'start_at':(now-datetime.timedelta(minutes=30)).isoformat(),'end_at':None}] if break_open else []),'corrections':[{'id':'old-evidence','before':{'net_minutes':100},'after':{'net_minutes':120}}]}
        self.historical={'user_id':'owner','start':'2026-07-23','end':'2026-08-22','status':'approved','approved_at':'2026-08-23T12:00:00Z','approved_by':'owner','legacy_evidence':['keep']}
        periods=[self.historical]
        if status:periods.append({'user_id':'owner','start':self.start,'end':self.end,'status':status,'approved_by':'owner' if status=='approved' else None,'approved_at':'2026-10-01T12:00:00Z' if status=='approved' else None,'submitted_at':'2026-10-01T12:00:00Z'})
        self.write_store({'version':1,'entries':[self.entry],'periods':periods,'adjustments':[],'correction_requests':[]})
        (self.private/'users.json').write_text(json.dumps({'version':1,'users':[{'id':'owner','active':True,'role':'recovery_admin','display_name':'Synthetic Owner','password_hash':'$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.'},{'id':'employee','active':True,'role':'member','display_name':'Synthetic Employee','password_hash':'$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.'}]}))

    def write_store(self, value):
        (self.private/'timeclock.json').write_text(json.dumps(value))

    def stored(self):
        return json.loads((self.private/'timeclock.json').read_text())

    def route(self, post=None, route='member/timeclock.php', login='owner', bad_csrf=False):
        fixture=self.private/'case.json'
        fixture.write_text(json.dumps({'private':str(self.private),'app':str(APP),'route':route,'login':login,'method':'POST' if post is not None else 'GET','post':post or {},'bad_csrf':bad_csrf}))
        proc=subprocess.run([PHP,'-n',str(self.wrapper),str(fixture)],text=True,capture_output=True)
        self.assertEqual(proc.returncode,0,proc.stderr + proc.stdout[:2000])
        self.assertEqual(proc.stderr,'')
        self.assertNotIn('Warning:',proc.stdout)
        return proc.stdout

    def test_submitted_and_approved_current_cards_show_and_accept_in_then_out(self):
        for status in ('submitted','approved'):
            with self.subTest(status=status):
                self.seed(status=status)
                html=self.route()
                self.assertIn('>Clock In</button>',html)
                html=self.route({'action':'clock_in','user_id':'employee','reviewer_id':'employee','clock_in_at':'1999-01-01T00:00:00Z'})
                self.assertIn('>Clock Out</button>',html)
                stored=self.stored()
                self.assertEqual(stored['entries'][-1]['user_id'],'owner')
                self.assertNotEqual(stored['entries'][-1]['clock_in_at'],'1999-01-01T00:00:00Z')
                self.assertEqual(stored['entries'][0],self.entry)
                self.assertEqual(stored['periods'][0],self.historical)
                self.assertEqual(stored['periods'][1]['status'],'in_progress')
                html=self.route({'action':'clock_out','user_id':'employee'})
                self.assertIn('>Clock In</button>',html)
                self.assertEqual(self.stored()['entries'][-1]['status'],'completed')
                self.assertEqual(self.stored()['entries'][-1]['category'],'Other')
                self.assertEqual(self.stored()['entries'][-1]['description'],'')
                self.assertEqual(self.stored()['periods'][0],self.historical)

    def test_clock_out_visible_and_works_with_open_break(self):
        self.seed(status='submitted',running=True,break_open=True)
        self.assertIn('>Clock Out</button>',self.route())
        self.route({'action':'clock_out'})
        entry=self.stored()['entries'][0]
        self.assertEqual(entry['clock_out_at'],entry['breaks'][0]['end_at'])
        self.assertEqual(entry['status'],'completed')
        self.assertGreaterEqual(entry['net_minutes'],89)
        self.assertLessEqual(entry['net_minutes'],90)

    def test_employee_forged_submit_and_bad_csrf_do_not_change_store(self):
        for post,bad_csrf in [({'action':'submit_period','certify':'1','user_id':'employee'},False),({'action':'clock_in'},True)]:
            with self.subTest(post=post):
                self.seed()
                before=(self.private/'timeclock.json').read_bytes()
                html=self.route(post,bad_csrf=bad_csrf)
                self.assertEqual((self.private/'timeclock.json').read_bytes(),before)
                self.assertTrue('administrator time-card review' in html or 'session expired' in html)

    def test_owner_self_review_ignores_forged_actor(self):
        self.seed(status='submitted')
        self.route({'action':'approve','user_id':'owner','reviewer_id':'employee','start':self.start,'end':self.end},route='admin/timecards.php')
        self.assertEqual(self.stored()['periods'][1]['status'],'approved')
        self.assertEqual(self.stored()['periods'][1]['approved_by'],'owner')
        self.assertEqual(self.stored()['periods'][0],self.historical)

    def test_non_owner_cannot_use_admin_review_route(self):
        self.seed(status='submitted')
        before=(self.private/'timeclock.json').read_bytes()
        html=self.route({'action':'approve','user_id':'owner','reviewer_id':'owner','start':self.start,'end':self.end},route='admin/timecards.php',login='employee')
        self.assertIn('Payroll review access is restricted.',html)
        self.assertEqual((self.private/'timeclock.json').read_bytes(),before)

    def test_open_and_previously_approved_entries_have_no_adjustment_form(self):
        for status,running in [('in_progress',True),('approved',False)]:
            with self.subTest(status=status,running=running):
                self.seed(status=status,running=running)
                html=self.route(route='admin/timecards.php')
                self.assertNotIn('class="adjust-form" method="post"',html)

    def test_admin_fallback_and_cli_use_same_live_private_store(self):
        old=self.stored()
        old['entries']=[dict(self.entry,work_date='2026-08-22')]
        old['periods']=[]
        self.write_store(old)
        html=self.route(route='admin/timecards.php')
        self.assertIn('2026-07-23 through 2026-08-22',html)
        queued=self.stored()
        self.assertEqual(queued['periods'][0]['status'],'submitted')
        self.assertEqual(queued['periods'][0]['total_minutes'],120)
        before=(self.private/'timeclock.json').read_bytes()
        env=dict(os.environ,KCMC_PRIVATE_DATA_DIR=str(self.private))
        diagnose=subprocess.run([PHP,'-n',str(APP/'admin/timeclock-period-close.php'),'--diagnose'],text=True,capture_output=True,env=env)
        self.assertEqual(diagnose.returncode,0,diagnose.stderr)
        fingerprint=json.loads(diagnose.stdout)['fingerprint']
        proc=subprocess.run([PHP,'-n',str(APP/'admin/timeclock-period-close.php'),'--run','--expect-store',fingerprint],text=True,capture_output=True,env=env)
        self.assertEqual(proc.returncode,0,proc.stderr + proc.stdout[:2000])
        self.assertIn('updated=0 channel=off mail_accepted=0',proc.stdout)
        self.assertEqual((self.private/'timeclock.json').read_bytes(),before)

if __name__=='__main__':
    unittest.main()
