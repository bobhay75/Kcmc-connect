<?php
declare(strict_types=1);
$root=dirname(__DIR__);
$library=$argv[1]??$root.'/KCMC-Connect-Phase6-Recreated/lib/timeclock.php';
$private=sys_get_temp_dir().'/kcmc-clock-workflow-'.bin2hex(random_bytes(8));
putenv('KCMC_PRIVATE_DATA_DIR='.$private);
putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
require $library;
$count=0;
function wf_check(bool $ok,string $message): void { global $count; if(!$ok)throw new RuntimeException($message);$count++;echo 'PASS: '.$message."\n"; }
function wf_seed(array $entries=[],array $periods=[]): void {
 if(!is_dir(KCMC_PRIVATE_DATA))mkdir(KCMC_PRIVATE_DATA,0700,true);
 file_put_contents(KCMC_TIMECLOCK,json_encode(['version'=>1,'entries'=>$entries,'periods'=>$periods,'adjustments'=>[],'correction_requests'=>[],'legacy'=>['keep'=>'unchanged evidence']]));
 file_put_contents(KCMC_USERS,json_encode(['version'=>1,'users'=>[['id'=>'owner','role'=>'recovery_admin','active'=>true],['id'=>'reviewer','role'=>'pastor_admin','active'=>true],['id'=>'inactive-owner','role'=>'recovery_admin','active'=>false],['id'=>'member-owner','role'=>'member','active'=>true]]]));
}
function wf_entry(string $id,string $user,string $date,int $minutes=120,string $status='completed'): array {
 $start=(new DateTimeImmutable($date.' 08:00:00',new DateTimeZone(KCMC_LOCAL_TIMEZONE)))->setTimezone(new DateTimeZone('UTC'));
 return ['id'=>$id,'user_id'=>$user,'work_date'=>$date,'clock_in_at'=>$start->format(DATE_ATOM),'clock_out_at'=>$status==='open'?null:$start->modify('+'.$minutes.' minutes')->format(DATE_ATOM),'breaks'=>[],'category'=>'Other','description'=>'','status'=>$status,'net_minutes'=>$status==='open'?0:$minutes,'corrections'=>[['id'=>'old-evidence','before'=>['net_minutes'=>90],'after'=>['net_minutes'=>$minutes]]]];
}
function wf_denied(callable $callback,string $message): void { $raw=file_get_contents(KCMC_TIMECLOCK);$caught=false;try{$callback();}catch(RuntimeException $e){$caught=true;}wf_check($caught&&file_get_contents(KCMC_TIMECLOCK)===$raw,$message); }
function wf_record(string $uid,string $start,string $end,string $status='submitted'): array {return ['user_id'=>$uid,'start'=>$start,'end'=>$end,'status'=>$status,'submitted_at'=>'2026-10-01T12:00:00+00:00','approved_at'=>$status==='approved'?'2026-10-02T12:00:00+00:00':null,'approved_by'=>$status==='approved'?'reviewer':null,'legacy'=>['keep'=>'review attribution']];}
try {
 [$start,$end]=kcmc_timeclock_period();$today=kcmc_timeclock_local_date(kcmc_timeclock_now());
 $old=wf_entry('old','owner',$today,120,'submitted');$historic=wf_record('owner','2026-08-23','2026-09-22','approved');
 wf_seed([$old],[wf_record('owner',$start,$end),$historic]);
 $in=kcmc_timeclock_mutate('owner','clock_in',['clock_in_at'=>'1999-01-01T00:00:00Z']);$stored=kcmc_timeclock_store();
 wf_check($in['status']==='open'&&$in['work_date']===$today&&abs(time()-strtotime($in['clock_in_at']))<5,'prematurely submitted current period still permits a server-time Clock In');
 wf_check($stored['periods'][0]['status']==='in_progress'&&$stored['periods'][0]['review_required']===true&&$stored['periods'][0]['review_history'][0]['status']==='submitted','new punch marks earlier snapshot for review and retains its attribution');
 wf_check($stored['entries'][0]===$old&&$stored['periods'][1]===$historic&&$stored['legacy']===['keep'=>'unchanged evidence'],'punch preserves old shifts, approved historical card, and unrelated store evidence');
 wf_denied(fn()=>kcmc_timeclock_mutate('owner','clock_in'),'duplicate Clock In is refused without changing stored records');
 $out=kcmc_timeclock_mutate('owner','clock_out');
 wf_check($out['status']==='completed'&&$out['category']==='Other'&&$out['description']===''&&!empty($out['clock_out_at']),'Clock Out requires no work category or note');
 wf_denied(fn()=>kcmc_timeclock_mutate('owner','clock_out'),'second Clock Out is refused without changing stored records');
 wf_seed([$old],[wf_record('owner',$start,$end,'approved'),$historic]);
 kcmc_timeclock_mutate('owner','clock_in');$stored=kcmc_timeclock_store();
 wf_check($stored['periods'][0]['status']==='in_progress'&&$stored['periods'][0]['approved_by']===null&&$stored['periods'][0]['review_history'][0]['approved_by']==='reviewer'&&$stored['periods'][1]===$historic,'new current-period punch supersedes early approval while retaining its history and all historical approvals');
 $open=wf_entry('running','owner',$today,0,'open');$open['clock_in_at']=gmdate(DATE_ATOM,time()-125*60);$open['breaks']=[['start_at'=>gmdate(DATE_ATOM,time()-30*60),'end_at'=>null]];
 wf_seed([$open]);$out=kcmc_timeclock_mutate('owner','clock_out');
 wf_check($out['breaks'][0]['end_at']===$out['clock_out_at']&&$out['net_minutes']>=94&&$out['net_minutes']<=95,'Clock Out ends an open break using the same server time and subtracts break minutes');
 wf_seed([wf_entry('own-shift','owner',$today)]);
 wf_denied(fn()=>kcmc_timeclock_request_correction('owner','own-shift',' '),'employee correction requires a meaningful reason');
 wf_denied(fn()=>kcmc_timeclock_request_correction('other','own-shift','Please fix the end time.'),'employee cannot request correction of another account shift');
 $request=kcmc_timeclock_request_correction('owner','own-shift','Please fix the end time.');
 wf_check($request['status']==='pending'&&$request['reason']==='Please fix the end time.','employee can request a correction with its reason preserved');
 wf_denied(fn()=>kcmc_timeclock_request_correction('owner','own-shift','Another duplicate reason.'),'duplicate pending employee correction is refused');
 $correct=kcmc_timeclock_apply_correction($request['id'],'owner',['clock_in'=>$today.'T08:00','clock_out'=>$today.'T10:30','category'=>'Other','description'=>'','break_minutes'=>'10','correction_reason'=>'Owner reviewed test punches.']);
 wf_check($correct['request']['resolved_by']==='owner'&&$correct['entry']['net_minutes']===140&&count($correct['entry']['corrections'])===2,'designated owner can resolve own correction with mandatory reason and preserved before/after evidence');
 $request=kcmc_timeclock_request_correction('owner','own-shift','Please double-check this test.');$rejected=kcmc_timeclock_reject_correction($request['id'],'owner','Confirmed original punch is correct.');
 wf_check($rejected['status']==='rejected'&&$rejected['resolved_by']==='owner'&&kcmc_timeclock_store()['correction_requests'][1]['status']==='rejected','designated owner can respond to own correction request and rejection persists');
 wf_seed([wf_entry('review-shift','owner',$today,120,'submitted')],[wf_record('owner',$start,$end)]);
 $approved=kcmc_timeclock_review_period('owner',$start,$end,'owner','approve');
 wf_check($approved['status']==='approved'&&$approved['approved_by']==='owner','configured active administrator owner can approve own time card');
 wf_seed([wf_entry('review-shift','owner',$today,120,'submitted')],[wf_record('owner',$start,$end)]);
 $returned=kcmc_timeclock_review_period('owner',$start,$end,'owner','return','Testing the return workflow.');
 wf_check($returned['status']==='returned'&&$returned['return_reason']==='Testing the return workflow.','configured owner can return own card with a reason');
 wf_seed([wf_entry('review-shift','reviewer',$today,120,'submitted')],[wf_record('reviewer',$start,$end)]);
 wf_denied(fn()=>kcmc_timeclock_review_period('reviewer',$start,$end,'reviewer','approve'),'ordinary administrator still cannot approve own card');
 foreach(['inactive-owner','member-owner'] as $id){putenv('KCMC_OPERATIONS_OWNER_USER_ID='.$id);wf_seed([wf_entry('review-shift',$id,$today,120,'submitted')],[wf_record($id,$start,$end)]);wf_denied(fn()=>kcmc_timeclock_review_period($id,$start,$end,$id,'approve'),'inactive or non-administrator configured identity does not gain owner self-review: '.$id);}putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
 wf_seed([wf_entry('review-shift','owner',$today,120,'submitted'),wf_entry('still-open','owner',$today,0,'open')],[wf_record('owner',$start,$end)]);
 wf_denied(fn()=>kcmc_timeclock_review_period('owner',$start,$end,'owner','approve'),'administrator cannot approve an open shift or erase its open state');
 wf_seed([wf_entry('no-notes','owner',$today)]);$submitted=kcmc_timeclock_submit_period('owner',$start,$end);
 wf_check($submitted['status']==='submitted'&&$submitted['total_minutes']===120&&$submitted['submission_source']==='administrator','administrator can prepare a card with optional work notes and summed totals');
 wf_denied(fn()=>kcmc_timeclock_submit_period('owner','2026-09-24','2026-10-22'),'overlapping or arbitrary period boundaries are refused');
 wf_seed([wf_entry('cutoff','owner','2026-10-22',125)]);
 wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T04:59:59Z'))===0&&kcmc_timeclock_store()['periods']===[],'Chicago period stays open through 11:59:59 PM on the 22nd');
 wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T05:00:00Z'))===1,'closed period enters administrator queue at Chicago midnight on the 23rd');
 $stored=kcmc_timeclock_store();wf_check($stored['periods'][0]['status']==='submitted'&&$stored['periods'][0]['total_minutes']===125&&$stored['periods'][0]['completed_shifts']===1&&$stored['entries'][0]['status']==='submitted','period-end queue stores added minutes, completed count, and submitted shift state');
 $raw=file_get_contents(KCMC_TIMECLOCK);$ino=fileinode(KCMC_TIMECLOCK);
 wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T05:05:00Z'))===0&&file_get_contents(KCMC_TIMECLOCK)===$raw&&fileinode(KCMC_TIMECLOCK)===$ino,'repeated cutoff is idempotent without duplicate periods or record replacement');
 $overnight=wf_entry('overnight','owner','2026-10-22',0,'open');wf_seed([wf_entry('closed','owner','2026-10-22',120),$overnight,wf_entry('next-period','owner','2026-10-23',60)]);
 kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:00:00Z'));$stored=kcmc_timeclock_store();
 wf_check($stored['periods'][0]['status']==='needs_attention'&&$stored['periods'][0]['total_minutes']===120&&$stored['periods'][0]['open_shifts']===1&&$stored['entries'][1]===$overnight&&count($stored['periods'])===1,'cutoff flags overnight/open shifts without fabricating a clock-out or including the new period');
 $stored['entries'][1]['status']='completed';$stored['entries'][1]['clock_out_at']='2026-10-23T06:00:00+00:00';$stored['entries'][1]['net_minutes']=1020;file_put_contents(KCMC_TIMECLOCK,json_encode($stored));
 wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:01:00Z'))===1&&kcmc_timeclock_store()['periods'][0]['total_minutes']===1140&&kcmc_timeclock_store()['periods'][0]['status']==='submitted','a resolved overnight shift is queued once with its full actual minutes assigned to original work date');
 wf_seed([wf_entry('queued-correction','owner','2026-10-22',120)]);
 kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:00:00Z'));
 $request=kcmc_timeclock_request_correction('owner','queued-correction','Correct the recorded end time.');
 kcmc_timeclock_apply_correction($request['id'],'owner',['clock_in'=>'2026-10-22T08:00','clock_out'=>'2026-10-22T11:00','category'=>'Other','description'=>'','break_minutes'=>'15','correction_reason'=>'Reviewed the actual end time.']);
 $stored=kcmc_timeclock_store();wf_check($stored['periods'][0]['total_minutes']===165&&$stored['periods'][0]['correction_count']===1&&$stored['correction_requests'][0]['status']==='applied','queued card recomputes corrected totals and persists period correction marker under the store lock');
 wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:05:00Z'))===0&&kcmc_timeclock_store()['periods'][0]['total_minutes']===165,'cutoff retry retains corrected aggregate without duplicate submission');
 $approved=wf_record('owner','2026-09-23','2026-10-22','approved');$returned=wf_record('reviewer','2026-09-23','2026-10-22','returned');wf_seed([wf_entry('approved-old','owner','2026-10-21'),wf_entry('returned-old','reviewer','2026-10-21')],[$approved,$returned]);
 wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:00:00Z'))===0&&kcmc_timeclock_store()['periods']===[$approved,$returned],'cutoff never silently reopens approved historical cards or resubmits returned cards');
 wf_seed([wf_entry('dst','owner','2026-11-22',45)]);wf_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-11-23T05:59:59Z'))===0&&kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-11-23T06:00:00Z'))===1,'cutoff follows Chicago daylight-saving offset instead of a fixed UTC hour');
 [$ys,$ye]=kcmc_timeclock_period(new DateTimeImmutable('2027-01-01T12:00:00-06:00'));wf_check($ys==='2026-12-23'&&$ye==='2027-01-22','pay periods retain the 23rd-to-22nd boundary across year rollover');
 $member=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/member/timeclock.php');$admin=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/admin/timecards.php');
 wf_check(!str_contains($member,'name="certify"')&&!str_contains($member,'value="submit_period"')&&str_contains($member,'value="clock_in"')&&str_contains($member,'value="clock_out"'),'employee screen offers punching and corrections, with no submission or approval controls');
 wf_check(str_contains($admin,"kcmc_timeclock_close_due_periods()")&&str_contains($admin,'value="submit_period"')&&str_contains($admin,'kcmc_is_designated_owner($reviewer)'),'administrator screen owns period preparation, automatic queue fallback, and designated-owner review override');
 echo 'Time clock employee workflow: '.$count." assertions passed.\n";
} finally {
 foreach(glob(KCMC_PRIVATE_DATA.'/*')?:[] as $path)if(is_file($path))unlink($path);
 if(is_dir(KCMC_PRIVATE_DATA))rmdir(KCMC_PRIVATE_DATA);
}
