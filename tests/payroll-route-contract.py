#!/usr/bin/env python3
"""Actual owner/recipient routes and store-bound CLI, with isolated fake accounts only."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('clock_routes',Path(__file__).with_name('timeclock-route-workflow-contract.py'))
CLOCK=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLOCK)
PHP,APP=shutil.which(CLOCK.PHP) or CLOCK.PHP,CLOCK.APP

class PayrollRoutes(unittest.TestCase):
    setUp=CLOCK.TimeclockRoutes.setUp
    tearDown=CLOCK.TimeclockRoutes.tearDown
    seed=CLOCK.TimeclockRoutes.seed
    write_store=CLOCK.TimeclockRoutes.write_store
    stored=CLOCK.TimeclockRoutes.stored
    route=CLOCK.TimeclockRoutes.route

    def save_queue(self):
        html=self.route({'action':'save','channel':'queue','reviewer_id':'employee','php_cli':PHP},route='admin/payroll-setup.php')
        self.assertIn('Payroll settings saved.',html)
        return html

    def cli(self,*arguments,private=None):
        env=dict(os.environ,KCMC_PRIVATE_DATA_DIR=str(private or self.private))
        return subprocess.run([PHP,'-n',str(APP/'admin/timeclock-period-close.php'),*arguments],text=True,capture_output=True,env=env)

    def test_owner_selection_is_explicit_and_does_not_change_user_roles(self):
        before=(self.private/'users.json').read_bytes()
        html=self.save_queue()
        self.assertIn('*/15 * * * *',html)
        self.assertIn('--run --expect-store',html)
        self.assertEqual((self.private/'users.json').read_bytes(),before)
        settings=json.loads((self.private/'payroll-settings.json').read_text())
        self.assertEqual(settings['reviewer_id'],'employee')
        self.assertEqual(settings['channel'],'queue')
        self.assertEqual(settings['updated_by'],'owner')
        payroll_page=self.route(route='admin/timecards.php',login='employee')
        self.assertIn('Employee Time Cards',payroll_page)
        self.assertIn('href="/kcmc-connect/member/">My account</a>',payroll_page)
        self.assertIn('class="screen-back" href="/kcmc-connect/member/"',payroll_page)
        self.assertNotIn('href="/kcmc-connect/admin/home.php"',payroll_page)
        html=self.route(route='admin/index.php',login='employee')
        self.assertIn('Access denied.',html)

    def test_selected_payroll_member_can_approve_other_card_with_own_actor_id(self):
        self.seed(status='submitted')
        self.save_queue()
        self.route({'action':'approve','user_id':'owner','reviewer_id':'owner','start':self.start,'end':self.end},route='admin/timecards.php',login='employee')
        self.assertEqual(self.stored()['periods'][1]['status'],'approved')
        self.assertEqual(self.stored()['periods'][1]['approved_by'],'employee')

    def test_selected_payroll_member_cannot_approve_own_or_configure_capabilities(self):
        self.seed(status='submitted')
        stored=self.stored()
        stored['entries'][0]['user_id']='employee'
        stored['periods'][1]['user_id']='employee'
        self.write_store(stored)
        self.save_queue()
        before=(self.private/'timeclock.json').read_bytes()
        html=self.route({'action':'approve','user_id':'employee','reviewer_id':'owner','start':self.start,'end':self.end},route='admin/timecards.php',login='employee')
        self.assertIn('A reviewer cannot approve or return their own time card.',html)
        self.assertEqual((self.private/'timeclock.json').read_bytes(),before)
        settings=(self.private/'payroll-settings.json').read_bytes()
        html=self.route({'action':'save','channel':'email','reviewer_id':'employee','php_cli':PHP},route='admin/payroll-setup.php',login='employee')
        self.assertIn('Access denied.',html)
        self.assertEqual((self.private/'payroll-settings.json').read_bytes(),settings)

    def test_recipient_can_export_approved_totals_but_disabled_channel_revokes_access(self):
        self.seed(status='approved')
        self.save_queue()
        # The wrapper preserves ordinary GET query handling used by these routes.
        original=CLOCK.WRAPPER
        try:
            CLOCK.WRAPPER=original.replace("$_POST=$case['post'];", "$_GET=['user'=>'owner','start'=>'"+self.start+"','end'=>'"+self.end+"'];\n$_POST=$case['post'];")
            self.wrapper.write_text(CLOCK.WRAPPER)
            csv=self.route(route='admin/timecards-export.php',login='employee')
            self.assertIn('TOTAL',csv)
            self.assertIn('2.00',csv)
            html=self.route(route='admin/timecards-print.php',login='employee')
            self.assertIn('Approved Employee Time Card',html)
        finally:
            CLOCK.WRAPPER=original
            self.wrapper.write_text(original)
        self.route({'action':'save','channel':'off','php_cli':PHP},route='admin/payroll-setup.php')
        self.assertIn('Payroll review access is restricted.',self.route(route='admin/timecards.php',login='employee'))
        self.assertIn('Employee Time Cards',self.route(route='admin/timecards.php',login='owner'))

    def test_diagnose_is_read_only_and_missing_or_wrong_expectation_prevents_any_run(self):
        before={path.name:path.read_bytes() for path in self.private.iterdir() if path.is_file()}
        diagnosis=self.cli('--diagnose')
        self.assertEqual(diagnosis.returncode,0,diagnosis.stderr)
        identity=json.loads(diagnosis.stdout)
        self.assertEqual(identity['timeclock_path'],str(self.private/'timeclock.json'))
        self.assertEqual(before,{path.name:path.read_bytes() for path in self.private.iterdir() if path.is_file()})
        for arguments in [(),('--run',),('--run','--expect-store','0'*64)]:
            with self.subTest(arguments=arguments):
                result=self.cli(*arguments)
                self.assertEqual(result.returncode,1)
                self.assertIn('refused:',result.stderr)
                self.assertEqual(before,{path.name:path.read_bytes() for path in self.private.iterdir() if path.is_file()})

    def test_web_fingerprint_survives_punches_and_runner_uses_same_private_store(self):
        self.save_queue()
        identity=json.loads(self.cli('--diagnose').stdout)
        self.route({'action':'clock_in'},login='employee')
        self.route({'action':'clock_out'},login='employee')
        self.assertEqual(json.loads(self.cli('--diagnose').stdout)['fingerprint'],identity['fingerprint'])
        result=self.cli('--run','--expect-store',identity['fingerprint'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('channel=queue mail_accepted=0',result.stdout)
        receipt=json.loads((self.private/'payroll-run-status.json').read_text())
        self.assertEqual(receipt['store_fingerprint'],identity['fingerprint'])
        self.assertEqual(receipt['channel'],'queue')
        with tempfile.TemporaryDirectory(prefix='kcmc-wrong-payroll-store-') as other:
            os.chmod(other,0o750)
            wrong=self.cli('--run','--expect-store',identity['fingerprint'],private=other)
            self.assertEqual(wrong.returncode,1)
            self.assertEqual(list(Path(other).iterdir()),[])

    def test_store_diagnosis_refuses_symlinks_hardlinks_and_unsafe_metadata(self):
        with tempfile.TemporaryDirectory(prefix='kcmc-payroll-alias-') as other:
            alias=Path(other)/'private'
            alias.symlink_to(self.private,target_is_directory=True)
            result=self.cli('--diagnose',private=alias)
            self.assertEqual(result.returncode,1)
            self.assertIn('without symlinks',result.stderr)
        os.chmod(self.private,0o770)
        result=self.cli('--diagnose')
        self.assertEqual(result.returncode,1)
        os.chmod(self.private,0o750)
        os.link(self.private/'timeclock.json',self.private/'second-timeclock-link')
        result=self.cli('--diagnose')
        self.assertEqual(result.returncode,1)
        self.assertIn('metadata requires review',result.stderr)

    def test_concurrent_runners_claim_one_revision_once_using_fake_transport_only(self):
        self.seed(status='submitted')
        value=self.stored()
        value['entries'][0]['work_date']='2026-08-22'
        value['periods']=[{'user_id':'owner','start':'2026-07-23','end':'2026-08-22','status':'submitted'}]
        self.write_store(value)
        users=json.loads((self.private/'users.json').read_text())
        users['users'][1]['email']='payroll@example.test'
        (self.private/'users.json').write_text(json.dumps(users))
        (self.private/'payroll-settings.json').write_text(json.dumps({'version':1,'channel':'email','reviewer_id':'employee','review_url':'https://example.test/admin/timecards.php','email_activation_date':'2026-08-22'}))
        os.chmod(self.private,0o750)
        expected=json.loads(self.cli('--diagnose').stdout)['fingerprint']
        worker=self.private/'worker.php'
        worker.write_text("""<?php
require $argv[1].'/lib/payroll.php';
$result=kcmc_payroll_handoff($argv[2],static function()use($argv):bool{
    file_put_contents($argv[3],"sent\n",FILE_APPEND|LOCK_EX);usleep(200000);return true;
});
echo json_encode($result);
""")
        env=dict(os.environ,KCMC_PRIVATE_DATA_DIR=str(self.private),KCMC_PAYROLL_FROM='sender@example.test')
        command=[PHP,'-n',str(worker),str(APP),expected,str(self.private/'sent.log')]
        processes=[subprocess.Popen(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env) for _ in range(2)]
        results=[process.communicate(timeout=10) for process in processes]
        for process,(stdout,stderr) in zip(processes,results):
            self.assertEqual(process.returncode,0,stderr+stdout)
            self.assertEqual(stderr,'')
        self.assertEqual((self.private/'sent.log').read_text().splitlines(),['sent'])
        self.assertEqual(len(self.stored()['payroll_deliveries']),1)
        self.assertEqual(self.stored()['payroll_deliveries'][0]['status'],'accepted')

    def test_composed_recipient_navigation_is_scoped_default_off_and_revocable(self):
        original_app=CLOCK.APP
        CLOCK.APP=Path(os.environ.get('KCMC_NAV_TEST_APP',str(APP)))
        try:
            self.seed(status='submitted')
            before=(self.private/'users.json').read_bytes()
            default=self.route(route='member/index.php',login='employee')
            self.assertNotIn('href="/kcmc-connect/admin/timecards.php"',default)
            self.assertNotIn('href="/kcmc-connect/admin/home.php"',default)
            self.save_queue()
            selected=self.route(route='member/index.php',login='employee')
            self.assertIn('href="/kcmc-connect/admin/timecards.php"',selected)
            self.assertIn('Payroll review',selected)
            for forbidden in ('admin/home.php','admin/index.php','admin/users.php','admin/prayer-inbox.php','admin/prayers.php','admin/operations.php'):
                self.assertNotIn('href="/kcmc-connect/'+forbidden+'"',selected)
            self.assertEqual((self.private/'users.json').read_bytes(),before)
            self.assertIn('Access denied.',self.route(route='admin/prayer-inbox.php',login='employee'))
            self.assertIn('Access denied.',self.route(route='admin/index.php',login='employee'))
            self.route({'action':'save','channel':'off','php_cli':PHP},route='admin/payroll-setup.php')
            revoked=self.route(route='member/index.php',login='employee')
            self.assertNotIn('href="/kcmc-connect/admin/timecards.php"',revoked)
            self.assertNotIn('href="/kcmc-connect/admin/home.php"',revoked)
            self.assertEqual((self.private/'users.json').read_bytes(),before)
        finally:
            CLOCK.APP=original_app

    def test_persistent_php_worker_refuses_externally_replaced_private_directory(self):
        location=self.private/'isolated-private'
        location.mkdir(mode=0o750)
        os.chmod(location,0o750)
        worker=self.private/'identity-worker.php'
        worker.write_text("""<?php
require $argv[1].'/lib/payroll.php';
$first=kcmc_payroll_store_identity();echo json_encode($first)."\n";flush();
fgets(STDIN);
try{kcmc_payroll_expect_store($first['fingerprint']);echo "WRONG_DIRECTORY_ACCEPTED\n";}
catch(RuntimeException $error){echo "DIRECTORY_REPLACEMENT_REFUSED\n";}
""")
        env=dict(os.environ,KCMC_PRIVATE_DATA_DIR=str(location))
        process=subprocess.Popen([PHP,'-n',str(worker),str(APP)],text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        first=json.loads(process.stdout.readline())
        original=location.stat().st_ino
        location.rename(self.private/'original-private')
        location.mkdir(mode=0o750)
        os.chmod(location,0o750)
        self.assertNotEqual(location.stat().st_ino,original)
        stdout,stderr=process.communicate('continue\n',timeout=10)
        self.assertEqual(process.returncode,0,stderr+stdout)
        self.assertEqual(stderr,'')
        self.assertEqual(stdout.strip(),'DIRECTORY_REPLACEMENT_REFUSED')
        self.assertEqual(list(location.iterdir()),[])

    def test_composed_selected_pastor_discovers_payroll_in_existing_hub_only(self):
        original_app=CLOCK.APP
        CLOCK.APP=Path(os.environ.get('KCMC_NAV_TEST_APP',str(APP)))
        try:
            self.seed(status='submitted')
            users=json.loads((self.private/'users.json').read_text())
            users['users'][1]['role']='pastor_admin'
            (self.private/'users.json').write_text(json.dumps(users))
            before=(self.private/'users.json').read_bytes()
            default=self.route(route='admin/home.php',login='employee')
            self.assertIn('Publishing',default)
            self.assertNotIn('href="/kcmc-connect/admin/timecards.php"',default)
            self.save_queue()
            account=self.route(route='member/index.php',login='employee')
            self.assertIn('href="/kcmc-connect/admin/home.php"',account)
            self.assertNotIn('href="/kcmc-connect/admin/timecards.php"',account)
            hub=self.route(route='admin/home.php',login='employee')
            self.assertIn('href="/kcmc-connect/admin/timecards.php"',hub)
            self.assertNotIn('href="/kcmc-connect/admin/payroll-setup.php"',hub)
            self.assertNotIn('href="/kcmc-connect/admin/operations.php"',hub)
            self.assertEqual((self.private/'users.json').read_bytes(),before)
            owner=self.route(route='admin/home.php',login='owner')
            self.assertIn('href="/kcmc-connect/admin/payroll-setup.php"',owner)
            self.route({'action':'save','channel':'off','php_cli':PHP},route='admin/payroll-setup.php')
            revoked=self.route(route='admin/home.php',login='employee')
            self.assertNotIn('href="/kcmc-connect/admin/timecards.php"',revoked)
            self.assertIn('Publishing',revoked)
        finally:
            CLOCK.APP=original_app

if __name__=='__main__':unittest.main()
