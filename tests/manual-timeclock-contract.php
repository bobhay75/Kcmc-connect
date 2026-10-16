<?php
declare(strict_types=1);

// Exercise the real time store with synthetic accounts and isolated private data.
$library=$argv[1]??dirname(__DIR__).'/KCMC-Connect-Phase6-Recreated/lib/timeclock.php';
$private=sys_get_temp_dir().'/kcmc-manual-clock-'.bin2hex(random_bytes(8));
putenv('KCMC_PRIVATE_DATA_DIR='.$private);
putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
require $library;
$assertions=0;

function mt_check(bool $condition,string $message): void {
 global $assertions;
 if(!$condition)throw new RuntimeException($message);
 $assertions++;echo 'PASS: '.$message."\n";
}
function mt_entry(string $id,string $date='2026-10-01',int $minutes=120,string $status='completed',string $user='owner'): array {
 $in=(new DateTimeImmutable($date.' 08:00:00',new DateTimeZone(KCMC_LOCAL_TIMEZONE)))->setTimezone(new DateTimeZone('UTC'));
 return ['id'=>$id,'user_id'=>$user,'work_date'=>$date,'clock_in_at'=>$in->format(DATE_ATOM),'clock_out_at'=>$status==='open'?null:$in->modify('+'.$minutes.' minutes')->format(DATE_ATOM),'net_minutes'=>$minutes,'status'=>$status,'category'=>'Other','description'=>'Synthetic recorded work','breaks'=>[],'corrections'=>[['id'=>'historic-correction','before'=>['net_minutes'=>60],'after'=>['net_minutes'=>$minutes]]]];
}
function mt_period(string $status='approved',string $start='2026-09-23',string $end='2026-10-22'): array {
 return ['user_id'=>'owner','start'=>$start,'end'=>$end,'status'=>$status,'submitted_at'=>'2026-10-01T13:00:00Z','approved_at'=>'2026-10-02T13:00:00Z','approved_by'=>'historic-reviewer','returned_at'=>'2026-10-03T13:00:00Z','return_reason'=>'Historic follow-up reason','review_history'=>[['status'=>'submitted','approved_by'=>'previous-reviewer','reason'=>'Historic attribution']],'review_required'=>true,'custom_evidence'=>['keep'=>'period evidence']];
}
function mt_seed(array $entries,array $periods=[]): array {
 if(!is_dir(KCMC_PRIVATE_DATA))mkdir(KCMC_PRIVATE_DATA,0700,true);
 if(is_file(KCMC_TIMECLOCK.'.lock'))unlink(KCMC_TIMECLOCK.'.lock');
 $store=['version'=>1,'entries'=>$entries,'periods'=>$periods,'adjustments'=>[['id'=>'historic-adjustment','entry_id'=>'old','reason'=>'Preserve this reason']],'correction_requests'=>[],'custom_evidence'=>['keep'=>'store evidence']];
 file_put_contents(KCMC_TIMECLOCK,"\n ".json_encode($store,JSON_UNESCAPED_SLASHES)."\n");
 file_put_contents(KCMC_USERS,json_encode(['version'=>1,'users'=>[['id'=>'owner','role'=>'recovery_admin','active'=>true],['id'=>'reviewer','role'=>'pastor_admin','active'=>true]]]));
 return $store;
}
function mt_rejected_without_write(callable $action,string $message,bool $retired=false,bool $untouchedLock=true): void {
 $exists=is_file(KCMC_TIMECLOCK);$raw=$exists?file_get_contents(KCMC_TIMECLOCK):null;
 clearstatcache(true,KCMC_TIMECLOCK);$before=$exists?stat(KCMC_TIMECLOCK):null;
 $lock=file_exists(KCMC_TIMECLOCK.'.lock');$caught=false;
 try{$action();}catch(RuntimeException $error){$caught=!$retired||$error->getMessage()==='Time cards do not need submission or approval. Recorded time is available directly.';}
 clearstatcache(true,KCMC_TIMECLOCK);$after=is_file(KCMC_TIMECLOCK)?stat(KCMC_TIMECLOCK):null;
 mt_check($caught&&($exists?file_get_contents(KCMC_TIMECLOCK)===$raw&&$before['ino']===$after['ino']&&$before['mtime']===$after['mtime']:!file_exists(KCMC_PRIVATE_DATA))&&(!$untouchedLock||file_exists(KCMC_TIMECLOCK.'.lock')===$lock),$message);
}
function mt_attribution(array $period): array {
 return array_intersect_key($period,array_flip(['status','submitted_at','approved_at','approved_by','returned_at','return_reason','review_history','custom_evidence']));
}

try {
 foreach(['submit','approve','return','unknown'] as $action){
  mt_rejected_without_write(fn()=>$action==='submit'?kcmc_timeclock_submit_period('owner','invalid','invalid'):kcmc_timeclock_review_period('owner','invalid','invalid','owner',$action),'retired '.$action.' refuses before creating private storage',true);
 }
 foreach(['current','submitted','returned','approved'] as $status){
  $later=mt_entry('later','2026-10-02',90,$status==='current'?'completed':$status);
  $earlier=mt_entry('earlier','2026-10-01',120,$status==='current'?'completed':$status);
  $open=mt_entry('open','2026-10-03',999,'open');
  $missingOut=mt_entry('missing-out','2026-10-04',777);$missingOut['clock_out_at']=null;
  $period=$status==='current'?[]:[mt_period($status)];
  mt_seed([$later,mt_entry('other-account','2026-10-01',600,'completed','reviewer'),$open,mt_entry('outside','2026-09-22',400),$earlier,$missingOut],$period);
  $raw=file_get_contents(KCMC_TIMECLOCK);$inode=fileinode(KCMC_TIMECLOCK);
  $report=kcmc_timeclock_period_report('owner','2026-09-23','2026-10-22');
  mt_check($report!==null&&$report['total_minutes']===210&&$report['completed_shifts']===2&&$report['open_shifts']===2,$status.' card reports completed time without approval and excludes unfinished minutes');
  mt_check(array_column($report['entries'],'id')===['earlier','later','open','missing-out']&&array_column($report['completed_entries'],'id')===['earlier','later'],$status.' report sorts own in-period shifts and separates unfinished records');
  mt_check(file_get_contents(KCMC_TIMECLOCK)===$raw&&fileinode(KCMC_TIMECLOCK)===$inode&&!file_exists(KCMC_TIMECLOCK.'.lock'),$status.' report performs no private-data or lock writes');
  foreach(['submit','approve','return'] as $action)mt_rejected_without_write(fn()=>$action==='submit'?kcmc_timeclock_submit_period('owner','2026-09-23','2026-10-22'):kcmc_timeclock_review_period('owner','2026-09-23','2026-10-22','reviewer',$action),'retired '.$action.' preserves '.$status.' records and their inode',true);
 }
 mt_check(kcmc_timeclock_period_report('missing','2026-09-23','2026-10-22')===null,'a period with no recorded shifts has no report');
 foreach([['','2026-09-23','2026-10-22'],['owner','2026-09-24','2026-10-22'],['owner','2026-09-23','2026-10-23'],['owner','2026-02-30','2026-03-22'],['owner',"2026-09-23\0",'2026-10-22']] as $arguments)mt_check(kcmc_timeclock_period_report(...$arguments)===null,'invalid user or canonical pay-period boundaries return no report');

 $closed=mt_entry('closed-cutoff','2026-10-22',125);$next=mt_entry('next-period','2026-10-23',60);
 $seed=mt_seed([$closed,$next]);
 mt_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T04:59:59Z'))===0,'period-end totals wait until Chicago midnight after the 22nd');
 mt_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T05:00:00Z'))===1,'the closed period is recorded automatically without submission');
 $store=kcmc_timeclock_store();$summary=$store['periods'][0];
 mt_check($summary['status']==='recorded'&&$summary['total_minutes']===125&&$summary['review_required']===false&&!isset($summary['approved_by'])&&!isset($summary['submitted_at']),'a new closed summary records totals without inventing approval or submission');
 mt_check($store['entries']===$seed['entries']&&$store['adjustments']===$seed['adjustments']&&$store['custom_evidence']===$seed['custom_evidence'],'period-end aggregation preserves shift statuses and unrelated private evidence');
 $raw=file_get_contents(KCMC_TIMECLOCK);$inode=fileinode(KCMC_TIMECLOCK);
 mt_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T05:15:00Z'))===0&&file_get_contents(KCMC_TIMECLOCK)===$raw&&fileinode(KCMC_TIMECLOCK)===$inode,'repeated period-end aggregation preserves bytes and inode');
 $open=mt_entry('overnight','2026-10-22',999,'open');mt_seed([$closed,$open]);
 kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:00:00Z'));$store=kcmc_timeclock_store();
 mt_check($store['periods'][0]['status']==='needs_attention'&&$store['periods'][0]['open_shifts']===1&&$store['periods'][0]['total_minutes']===125&&$store['entries'][1]===$open,'unfinished shifts remain open and flagged without invented punches or minutes');
 $store['entries'][1]['clock_out_at']='2026-10-23T06:00:00Z';$store['entries'][1]['status']='completed';$store['entries'][1]['net_minutes']=1020;file_put_contents(KCMC_TIMECLOCK,json_encode($store));
 kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:01:00Z'));$store=kcmc_timeclock_store();
 mt_check($store['periods'][0]['status']==='recorded'&&$store['periods'][0]['total_minutes']===1145,'finishing an overnight shift refreshes its original period directly');
 foreach(['submitted','approved','returned'] as $status){
  $period=mt_period($status);mt_seed([$closed],[$period]);kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-10-23T06:00:00Z'));$stored=kcmc_timeclock_store();
  mt_check(mt_attribution($stored['periods'][0])===mt_attribution($period)&&$stored['periods'][0]['total_minutes']===125&&$stored['periods'][0]['review_required']===false&&$stored['entries'][0]===$closed,'legacy '.$status.' attribution survives while closed-period actual totals refresh');
 }
 mt_seed([mt_entry('dst','2026-11-22',45)]);
 mt_check(kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-11-23T05:59:59Z'))===0&&kcmc_timeclock_close_due_periods(new DateTimeImmutable('2026-11-23T06:00:00Z'))===1,'period closure follows Chicago daylight-saving time');

 [$start,$end]=kcmc_timeclock_period();$today=kcmc_timeclock_local_date(kcmc_timeclock_now());
 foreach(['submitted','approved','returned'] as $status){
  $period=mt_period($status,$start,$end);$old=mt_entry('previous',$today,120,$status);mt_seed([$old],[$period]);
  $in=kcmc_timeclock_mutate('owner','clock_in',['clock_in_at'=>'1999-01-01T00:00:00Z']);$store=kcmc_timeclock_store();
  mt_check($in['status']==='open'&&abs(time()-strtotime($in['clock_in_at']))<5&&mt_attribution($store['periods'][0])===mt_attribution($period)&&$store['periods'][0]['review_required']===false&&$store['entries'][0]===$old,'manual punch bypasses '.$status.' approval state and preserves historical attribution');
  $out=kcmc_timeclock_mutate('owner','clock_out');
  mt_check($out['status']==='completed'&&$out['category']==='Other'&&$out['description']===''&&!empty($out['clock_out_at']),'Clock Out works without approval, category or work note after '.$status.' history');
 }

 $period=mt_period();$entry=mt_entry('adjust-approved');$entry['status']='approved';$seed=mt_seed([$entry],[$period]);
 $adjustment=kcmc_timeclock_adjust_entry('adjust-approved','owner',150,'Corrected the recorded duration.');$store=kcmc_timeclock_store();
 mt_check($adjustment['previous_net_minutes']===120&&$adjustment['new_net_minutes']===150&&$adjustment['adjusted_by']==='owner'&&$store['adjustments'][0]===$seed['adjustments'][0]&&count($store['adjustments'])===2,'owner can adjust historically approved time with retained original adjustment history');
 mt_check($store['entries'][0]['corrections']===$entry['corrections']&&mt_attribution($store['periods'][0])===mt_attribution($period)&&$store['periods'][0]['total_minutes']===150,'adjustment preserves correction and approval evidence while recomputing actual totals');
 mt_seed([mt_entry('reviewer-own','2026-10-01',120,'approved','reviewer')]);
 mt_rejected_without_write(fn()=>kcmc_timeclock_adjust_entry('reviewer-own','reviewer',150,'Please change the duration.'),'removing approvals does not expand ordinary reviewer self-adjustment permissions',false,false);

 mt_seed([$entry],[$period]);$request=kcmc_timeclock_request_correction('owner','adjust-approved','Please correct the end time.');
 $correction=kcmc_timeclock_apply_correction($request['id'],'owner',['clock_in'=>'2026-10-01T08:00','clock_out'=>'2026-10-01T11:00','break_minutes'=>'15','category'=>'Other','description'=>'Corrected recorded work','correction_reason'=>'Corrected using the actual end time.']);$store=kcmc_timeclock_store();
 mt_check($correction['request']['status']==='applied'&&$correction['request']['resolved_by']==='owner'&&$correction['entry']['net_minutes']===165&&count($correction['entry']['corrections'])===2&&$correction['entry']['corrections'][0]===$entry['corrections'][0],'correction requests still apply with reasons, actor and before/after evidence');
 mt_check(mt_attribution($store['periods'][0])===mt_attribution($period)&&$store['periods'][0]['total_minutes']===165&&$store['periods'][0]['correction_count']===1,'correction updates actual totals without needing or fabricating approval');
 echo 'Manual time clock: '.$assertions." assertions passed.\n";
} finally {
 foreach(glob(KCMC_PRIVATE_DATA.'/*')?:[] as $path)if(is_file($path))unlink($path);
 if(is_dir(KCMC_PRIVATE_DATA))rmdir(KCMC_PRIVATE_DATA);
}
