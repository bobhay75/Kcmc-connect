<?php
declare(strict_types=1);
$private=sys_get_temp_dir().'/kcmc-payroll-'.bin2hex(random_bytes(8));
putenv('KCMC_PRIVATE_DATA_DIR='.$private);putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
putenv('KCMC_PAYROLL_FROM=payroll-sender@example.test');
require dirname(__DIR__).'/KCMC-Connect-Phase6-Recreated/lib/payroll.php';
$count=0;
function pa_check(bool $ok,string $message):void{global $count;if(!$ok)throw new RuntimeException($message);$count++;echo 'PASS: '.$message."\n";}
function pa_deny(callable $action,string $message):void{$failed=false;try{$action();}catch(RuntimeException $error){$failed=true;}pa_check($failed,$message);}
function pa_write_users(array $users):void{file_put_contents(KCMC_USERS,json_encode(['version'=>1,'users'=>$users]));}
function pa_store(array $value):void{file_put_contents(KCMC_TIMECLOCK,json_encode($value));chmod(KCMC_TIMECLOCK,0640);}
function pa_seed_period(int $minutes=120):void{
 pa_store(['version'=>1,'entries'=>[['id'=>'closed','user_id'=>'worker','work_date'=>'2026-08-22','clock_in_at'=>'2026-08-22T13:00:00Z','clock_out_at'=>'2026-08-22T15:00:00Z','net_minutes'=>$minutes,'status'=>'submitted','category'=>'Other','description'=>'PRIVATE description should not be emailed','corrections'=>[]]],'periods'=>[['user_id'=>'worker','start'=>'2026-07-23','end'=>'2026-08-22','status'=>'submitted','correction_count'=>0]],'adjustments'=>[],'correction_requests'=>[['reason'=>'PRIVATE correction reason should not be emailed']],'legacy'=>['keep'=>'existing data']]);
}
try{
 mkdir($private,0750);chmod($private,0750);
 $users=[['id'=>'owner','display_name'=>'Owner','email'=>'owner@example.test','role'=>'recovery_admin','active'=>true],['id'=>'payroll','display_name'=>'Chosen Reviewer','email'=>'payroll@example.test','role'=>'member','active'=>true],['id'=>'named-mike','display_name'=>'Mike Cahill','email'=>'mike@example.test','role'=>'member','active'=>true],['id'=>'worker','display_name'=>'Worker','email'=>'worker@example.test','role'=>'member','active'=>true],['id'=>'inactive','display_name'=>'Inactive','email'=>'inactive@example.test','role'=>'member','active'=>false]];
 pa_write_users($users);$roles=file_get_contents(KCMC_USERS);$owner=$users[0];$reviewer=$users[1];
 pa_check(kcmc_payroll_settings()===kcmc_payroll_default_settings()&&!is_file(KCMC_PAYROLL_SETTINGS),'payroll defaults to off with no selected account and creates no settings file');
 pa_check(kcmc_can_review_payroll($owner)&&!kcmc_can_review_payroll($reviewer)&&!kcmc_can_review_payroll($users[2]),'owner retains access; no recipient is inferred from name or existing membership');
 pa_deny(fn()=>kcmc_payroll_save_settings($reviewer,['channel'=>'queue','reviewer_id'=>'payroll']),'ordinary account cannot configure its own payroll capability');
 pa_check(!is_file(KCMC_PAYROLL_SETTINGS),'denied delegation leaves settings absent');
 foreach(['missing','inactive',''] as $id)pa_deny(fn()=>kcmc_payroll_save_settings($owner,['channel'=>'queue','reviewer_id'=>$id]),'queue requires an explicitly selected active account: '.$id);
 $settings=kcmc_payroll_save_settings($owner,['channel'=>'queue','reviewer_id'=>'payroll']);
 pa_check(kcmc_can_review_payroll($reviewer)&&!kcmc_can_review_payroll($users[2]),'explicit queue selection grants only the chosen account payroll access');
 pa_check(!kcmc_can_publish($reviewer)&&!kcmc_can_view_private_prayers($reviewer)&&file_get_contents(KCMC_USERS)===$roles,'payroll selection changes no stored roles, publishing, or confidential prayer access');
 $users[1]['active']=false;pa_write_users($users);pa_check(!kcmc_can_review_payroll($reviewer),'account deactivation immediately revokes delegated payroll access');$users[1]['active']=true;pa_write_users($users);
 kcmc_payroll_save_settings($owner,['channel'=>'off']);pa_check(!kcmc_can_review_payroll($reviewer)&&kcmc_can_review_payroll($owner),'turning payroll off revokes delegation and preserves owner access');
 $identity=kcmc_payroll_store_identity();pa_check(!$identity['store_exists']&&!is_file(KCMC_TIMECLOCK)&&preg_match('/\A[a-f0-9]{64}\z/',$identity['fingerprint'])===1,'store identity is read-only and works before the first time-clock record');
 pa_deny(fn()=>kcmc_payroll_expect_store(str_repeat('0',64)),'a mismatched web/CLI store fingerprint is refused');
 $now=kcmc_timeclock_now();kcmc_timeclock_mutate('worker','clock_in');kcmc_timeclock_mutate('worker','clock_out');
 pa_check(kcmc_payroll_store_identity()['fingerprint']===$identity['fingerprint'],'normal atomic Clock In/Out writes do not invalidate the store fingerprint');
 chmod($private,0700);pa_check(kcmc_payroll_store_identity()['fingerprint']!==$identity['fingerprint'],'directory mode change invalidates the reviewed fingerprint');chmod($private,0750);
 chmod($private,0770);pa_deny(fn()=>kcmc_payroll_store_identity(),'group-writable private directory is refused');chmod($private,0750);
 $php=kcmc_payroll_cli_candidates()[0]??'';$line=kcmc_payroll_cron_line($php);
 pa_check(str_contains($line,'*/15 * * * *')&&str_contains($line,'--run --expect-store')&&str_contains($line,$identity['fingerprint'])&&str_contains($line,"KCMC_PRIVATE_DATA_DIR='".$private."'"),'cron preview pins the actual web store, uses Chicago-independent frequent execution, and does not install a schedule');
 pa_check(kcmc_payroll_shell_quote("a'b\$c`d")==="'a'\"'\"'b\$c`d'",'cron arguments use POSIX shell quoting even for apostrophes and shell syntax');
 pa_deny(fn()=>kcmc_payroll_shell_quote("bad\npath"),'newline injection into generated cron arguments is refused');
 foreach(['http://example.test/admin/timecards.php','https://a:b@example.test/admin/timecards.php','https://example.test/admin/timecards.php?x=1','https://example.test/admin/timecards.php#fragment'] as $url)pa_check(!kcmc_payroll_valid_review_url($url),'unsafe or ambiguous review URL is refused: '.$url);
 putenv('KCMC_PAYROLL_FROM=');pa_deny(fn()=>kcmc_payroll_save_settings($owner,['channel'=>'email','reviewer_id'=>'payroll','review_url'=>'https://example.test/admin/timecards.php']),'email cannot be enabled without the separate configured payroll sender');putenv('KCMC_PAYROLL_FROM=payroll-sender@example.test');
 $enabled=kcmc_payroll_save_settings($owner,['channel'=>'email','reviewer_id'=>'payroll','review_url'=>'https://example.test/admin/timecards.php']);$today=kcmc_timeclock_local_date(gmdate(DATE_ATOM));
 pa_check($enabled['email_activation_date']===$today,'first email activation begins on the owner-save Chicago date');
 $saved=$enabled;$saved['email_activation_date']='2026-08-22';file_put_contents(KCMC_PAYROLL_SETTINGS,json_encode($saved));
 $same=kcmc_payroll_save_settings($owner,['channel'=>'email','reviewer_id'=>'payroll','review_url'=>'https://example.test/admin/timecards.php']);
 pa_check($same['email_activation_date']==='2026-08-22','saving the same active email reviewer preserves the original activation cutoff');
 $switched=kcmc_payroll_save_settings($owner,['channel'=>'email','reviewer_id'=>'named-mike','review_url'=>'https://example.test/admin/timecards.php']);
 pa_check($switched['email_activation_date']===$today,'switching the explicitly selected email reviewer resets cutoff to today');
 kcmc_payroll_save_settings($owner,['channel'=>'off']);
 $reenabled=kcmc_payroll_save_settings($owner,['channel'=>'email','reviewer_id'=>'payroll','review_url'=>'https://example.test/admin/timecards.php']);
 pa_check($reenabled['email_activation_date']===$today,'turning email off and on starts a new activation cutoff');
 $legacy=$reenabled;unset($legacy['email_activation_date']);file_put_contents(KCMC_PAYROLL_SETTINGS,json_encode($legacy));
 pa_deny(fn()=>kcmc_payroll_handoff($identity['fingerprint'],static fn()=>true),'legacy email settings missing activation refuse transport until owner re-saves');
 $legacy['email_activation_date']='2026-02-30';file_put_contents(KCMC_PAYROLL_SETTINGS,json_encode($legacy));
 pa_deny(fn()=>kcmc_payroll_handoff($identity['fingerprint'],static fn()=>true),'invalid activation date refuses transport instead of guessing a cutoff');
 $repaired=kcmc_payroll_save_settings($owner,['channel'=>'email','reviewer_id'=>'payroll','review_url'=>'https://example.test/admin/timecards.php']);
 pa_check($repaired['email_activation_date']===$today,'owner re-save establishes a valid cutoff for legacy or malformed settings');
 $saved=$repaired;$saved['email_activation_date']='2026-09-22';file_put_contents(KCMC_PAYROLL_SETTINGS,json_encode($saved));pa_seed_period();$border=kcmc_timeclock_store();$later=$border['entries'][0];$later['id']='cutoff-date';$later['work_date']='2026-09-22';$border['entries'][]=$later;$border['periods'][]=['user_id'=>'worker','start'=>'2026-08-23','end'=>'2026-09-22','status'=>'submitted'];pa_store($border);$borderSent=[];
 kcmc_payroll_handoff($identity['fingerprint'],static function($to,$subject,$body,$headers)use(&$borderSent):bool{$borderSent[]=$subject;return true;});
 pa_check(count($borderSent)===1&&str_contains($borderSent[0],'2026-08-23 through 2026-09-22'),'email excludes historical periods before activation and includes a period ending exactly at cutoff');
 $saved['email_activation_date']='2026-08-22';file_put_contents(KCMC_PAYROLL_SETTINGS,json_encode($saved));pa_seed_period();$sent=[];
 $transport=static function($to,$subject,$body,$headers)use(&$sent):bool{$sent[]=compact('to','subject','body','headers');return true;};
 $result=kcmc_payroll_handoff($identity['fingerprint'],$transport);$stored=kcmc_timeclock_store();
 pa_check(count($sent)===1&&$sent[0]['to']==='payroll@example.test'&&str_contains($sent[0]['body'],'Worker: 2.00 hours')&&$result['accepted']===1,'explicit email handoff sends added closed-period totals only to the selected account through injected transport');
 pa_check(!str_contains($sent[0]['body'],'PRIVATE')&&!str_contains($sent[0]['body'],'correction reason'),'email excludes work descriptions and confidential correction reasons');
 pa_check($stored['payroll_deliveries'][0]['status']==='accepted'&&$stored['payroll_deliveries'][0]['reason']==='accepted_by_mail_transport'&&$stored['legacy']===['keep'=>'existing data'],'mail transport acceptance is persisted separately from actual inbox delivery and existing records are retained');
 $raw=file_get_contents(KCMC_TIMECLOCK);$inode=fileinode(KCMC_TIMECLOCK);kcmc_payroll_handoff($identity['fingerprint'],$transport);clearstatcache(true,KCMC_TIMECLOCK);
 pa_check(count($sent)===1&&file_get_contents(KCMC_TIMECLOCK)===$raw&&fileinode(KCMC_TIMECLOCK)===$inode,'retry of the same accepted revision does not resend or replace unchanged records');
 $stored=kcmc_timeclock_store();$stored['entries'][0]['net_minutes']=150;$stored['periods'][0]['correction_count']=1;pa_store($stored);$result=kcmc_payroll_handoff($identity['fingerprint'],$transport);
 pa_check(count($sent)===2&&str_contains($sent[1]['body'],'Worker: 2.50 hours')&&count(kcmc_timeclock_store()['payroll_deliveries'])===2,'changed corrected totals create a new versioned notice without losing old delivery evidence');
 $stored=kcmc_timeclock_store();$stored['periods'][0]['status']='approved';pa_store($stored);kcmc_payroll_handoff($identity['fingerprint'],$transport);pa_check(count($sent)===2,'approval status alone does not spam a second totals notification');
 pa_seed_period(180);$failures=0;$failedTransport=static function()use(&$failures):bool{$failures++;return false;};$result=kcmc_payroll_handoff($identity['fingerprint'],$failedTransport);kcmc_payroll_handoff($identity['fingerprint'],$failedTransport);
 pa_check($failures===1&&$result['failed']===1&&kcmc_timeclock_store()['payroll_deliveries'][0]['status']==='failed','transport failure is preserved for owner review and is never blindly retried');
 $stored=kcmc_timeclock_store();$stored['payroll_deliveries'][0]['status']='sending';pa_store($stored);kcmc_payroll_handoff($identity['fingerprint'],$failedTransport);
 pa_check($failures===1&&kcmc_timeclock_store()['payroll_deliveries'][0]['status']==='sending','a claimed attempt interrupted around transport remains uncertain and is never automatically duplicated');
 pa_seed_period();$stored=kcmc_timeclock_store();$stored['payroll_deliveries']='preserve malformed delivery evidence';pa_store($stored);$raw=file_get_contents(KCMC_TIMECLOCK);pa_deny(fn()=>kcmc_payroll_handoff($identity['fingerprint'],$transport),'malformed delivery history requires review rather than being discarded');pa_check(file_get_contents(KCMC_TIMECLOCK)===$raw,'refusal preserves malformed history exactly');
 $users[1]['active']=false;pa_write_users($users);$before=count($sent);$result=kcmc_payroll_handoff($identity['fingerprint'],$transport);pa_check(!$result['ready']&&count($sent)===$before,'disabled recipient prevents any email handoff');
 echo 'Payroll automation: '.$count." assertions passed; no real mail or crontab operation.\n";
}finally{
 foreach(glob($private.'/*')?:[] as $path)if(is_file($path)||is_link($path))unlink($path);
 if(is_dir($private))rmdir($private);
}
