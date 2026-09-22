<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

define('KCMC_TIMECLOCK', KCMC_PRIVATE_DATA . '/timeclock.json');

function kcmc_timeclock_categories(): array { return ['Office / Administration','Maintenance / Facilities','Media / Worship','KCMC Connect / IT','Events / Outreach','Other']; }
function kcmc_timeclock_period_start_day(): int { $cfg=kcmc_config(); return max(1,min(28,(int)($cfg['timeclock_period_start_day']??23))); }
function kcmc_timeclock_now(): string { return gmdate('c'); }
function kcmc_timeclock_store(): array { return kcmc_read_json_store(KCMC_TIMECLOCK,['version'=>1,'entries'=>[],'periods'=>[],'adjustments'=>[]]); }
function kcmc_timeclock_local_date(string $iso): string { $d=new DateTimeImmutable($iso); return $d->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('Y-m-d'); }
function kcmc_timeclock_minutes(string $start,string $end): int { $a=strtotime($start);$b=strtotime($end); return ($a===false||$b===false)?0:max(0,(int)floor(($b-$a)/60)); }
function kcmc_timeclock_net_minutes(array $entry): int { if(empty($entry['clock_out_at']))return 0; $gross=kcmc_timeclock_minutes((string)$entry['clock_in_at'],(string)$entry['clock_out_at']);$break=0;foreach(($entry['breaks']??[]) as $b)if(is_array($b)&&!empty($b['start_at'])&&!empty($b['end_at']))$break+=kcmc_timeclock_minutes((string)$b['start_at'],(string)$b['end_at']);return max(0,$gross-$break); }
function kcmc_timeclock_hours_to_minutes(string $hours): ?int { $hours=trim($hours);if($hours===''||!is_numeric($hours))return null;$value=(float)$hours;if(!is_finite($value)||$value<0||$value>24)return null;return (int)round($value*60); }
function kcmc_timeclock_period(?DateTimeImmutable $date=null): array { $tz=new DateTimeZone(KCMC_LOCAL_TIMEZONE);$d=($date??new DateTimeImmutable('now',$tz))->setTimezone($tz);$startDay=kcmc_timeclock_period_start_day();$day=(int)$d->format('j');if($day>=$startDay){$start=$d->setDate((int)$d->format('Y'),(int)$d->format('n'),$startDay);}else{$p=$d->modify('-1 month');$start=$p->setDate((int)$p->format('Y'),(int)$p->format('n'),$startDay);} $end=$start->modify('+1 month -1 day');return [$start->format('Y-m-d'),$end->format('Y-m-d')]; }
function kcmc_timeclock_entries_for(string $userId): array { return array_values(array_filter(kcmc_timeclock_store()['entries']??[],fn($e)=>is_array($e)&&($e['user_id']??'')===$userId)); }
function kcmc_timeclock_open_entry(string $userId): ?array { foreach(array_reverse(kcmc_timeclock_entries_for($userId)) as $e)if(($e['status']??'')==='open')return $e; return null; }
function kcmc_timeclock_period_entries(string $userId,string $start,string $end): array { return array_values(array_filter(kcmc_timeclock_entries_for($userId),fn($e)=>($e['work_date']??'')>=$start&&($e['work_date']??'')<=$end)); }
function kcmc_timeclock_period_record(string $userId,string $start,string $end): ?array { foreach(kcmc_timeclock_store()['periods']??[] as $p)if(is_array($p)&&($p['user_id']??'')===$userId&&($p['start']??'')===$start&&($p['end']??'')===$end)return $p; return null; }
function kcmc_timeclock_period_total(string $userId,string $start,string $end): int { return array_sum(array_map(fn($e)=>(int)($e['net_minutes']??0),kcmc_timeclock_period_entries($userId,$start,$end))); }
function kcmc_timeclock_adjustments_for_entry(string $entryId): array { $rows=array_values(array_filter(kcmc_timeclock_store()['adjustments']??[],fn($a)=>is_array($a)&&($a['entry_id']??'')===$entryId));usort($rows,fn($a,$b)=>strcmp((string)($b['adjusted_at']??''),(string)($a['adjusted_at']??'')));return $rows; }
function kcmc_timeclock_mutate(string $userId,string $action,array $input=[]): array {
 return kcmc_update_json_store(KCMC_TIMECLOCK,['version'=>1,'entries'=>[],'periods'=>[],'adjustments'=>[]],function(array &$s)use($userId,$action,$input):array{
  $s['entries']=is_array($s['entries']??null)?$s['entries']:[];$s['periods']=is_array($s['periods']??null)?$s['periods']:[];$now=kcmc_timeclock_now();$today=kcmc_timeclock_local_date($now);[$ps,$pe]=kcmc_timeclock_period(new DateTimeImmutable($now));
  foreach($s['periods'] as $p)if(is_array($p)&&($p['user_id']??'')===$userId&&($p['start']??'')===$ps&&($p['end']??'')===$pe&&in_array((string)($p['status']??''),['submitted','approved'],true))throw new RuntimeException('This pay period is locked while it is awaiting review or approved.');
  $idx=null;foreach($s['entries'] as $i=>$e)if(is_array($e)&&($e['user_id']??'')===$userId&&($e['status']??'')==='open')$idx=$i;
  if($action==='clock_in'){if($idx!==null)throw new RuntimeException('You are already clocked in.');$e=['id'=>kcmc_random_id('time'),'user_id'=>$userId,'work_date'=>$today,'clock_in_at'=>$now,'clock_out_at'=>null,'breaks'=>[],'category'=>'','description'=>'','status'=>'open','created_at'=>$now,'updated_at'=>$now,'net_minutes'=>0];$s['entries'][]=$e;return $e;}
  if($idx===null)throw new RuntimeException('No open shift.');$e=&$s['entries'][$idx];$breakIdx=null;foreach(($e['breaks']??[]) as $i=>$b)if(is_array($b)&&empty($b['end_at']))$breakIdx=$i;
  if($action==='break_start'){if($breakIdx!==null)throw new RuntimeException('A break is already open.');$e['breaks'][]=['start_at'=>$now,'end_at'=>null];}
  elseif($action==='break_end'){if($breakIdx===null)throw new RuntimeException('No open break.');$e['breaks'][$breakIdx]['end_at']=$now;}
  elseif($action==='clock_out'){if($breakIdx!==null)throw new RuntimeException('End the break before clocking out.');$category=trim((string)($input['category']??''));$description=trim((string)($input['description']??''));if(!in_array($category,kcmc_timeclock_categories(),true))throw new RuntimeException('Choose a valid work category.');if($description===''||kcmc_text_length($description)>1000)throw new RuntimeException('Enter a work description up to 1000 characters.');$e['clock_out_at']=$now;$e['category']=$category;$e['description']=$description;$e['status']='completed';$e['net_minutes']=kcmc_timeclock_net_minutes($e);}
  else throw new RuntimeException('Unsupported time-clock action.');$e['updated_at']=$now;return $e;
 });
}
function kcmc_timeclock_submit_period(string $userId,string $start,string $end): array {
 return kcmc_update_json_store(KCMC_TIMECLOCK,['version'=>1,'entries'=>[],'periods'=>[],'adjustments'=>[]],function(array &$s)use($userId,$start,$end):array{
  $entries=[];foreach(($s['entries']??[]) as $i=>&$e){if(!is_array($e)||($e['user_id']??'')!==$userId||($e['work_date']??'')<$start||($e['work_date']??'')>$end)continue;if(($e['status']??'')==='open')throw new RuntimeException('Clock out before submitting this period.');if(trim((string)($e['description']??''))===''||!in_array((string)($e['category']??''),kcmc_timeclock_categories(),true))throw new RuntimeException('Every completed shift needs a category and description.');$entries[]=$i;}unset($e);if(!$entries)throw new RuntimeException('There are no completed shifts in this pay period.');
  $now=kcmc_timeclock_now();$found=null;foreach(($s['periods']??[]) as $i=>$p)if(is_array($p)&&($p['user_id']??'')===$userId&&($p['start']??'')===$start&&($p['end']??'')===$end)$found=$i;if($found!==null&&in_array((string)($s['periods'][$found]['status']??''),['submitted','approved'],true))throw new RuntimeException('This pay period is already submitted or approved.');$record=['user_id'=>$userId,'start'=>$start,'end'=>$end,'status'=>'submitted','submitted_at'=>$now,'approved_at'=>null,'approved_by'=>null,'returned_at'=>null,'return_reason'=>null];if($found===null)$s['periods'][]=$record;else$s['periods'][$found]=array_replace($s['periods'][$found],$record);foreach($entries as $i)$s['entries'][$i]['status']='submitted';return $record;
 });
}
function kcmc_timeclock_review_period(string $userId,string $start,string $end,string $reviewerId,string $action,string $reason=''): array {
 return kcmc_update_json_store(KCMC_TIMECLOCK,['version'=>1,'entries'=>[],'periods'=>[],'adjustments'=>[]],function(array &$s)use($userId,$start,$end,$reviewerId,$action,$reason):array{
  $idx=null;foreach(($s['periods']??[]) as $i=>$p)if(is_array($p)&&($p['user_id']??'')===$userId&&($p['start']??'')===$start&&($p['end']??'')===$end)$idx=$i;if($idx===null||($s['periods'][$idx]['status']??'')!=='submitted')throw new RuntimeException('That pay period is not awaiting review.');$now=kcmc_timeclock_now();if($action==='approve'){$s['periods'][$idx]['status']='approved';$s['periods'][$idx]['approved_at']=$now;$s['periods'][$idx]['approved_by']=$reviewerId;}elseif($action==='return'){$reason=trim($reason);if($reason===''||kcmc_text_length($reason)>500)throw new RuntimeException('Enter a return reason up to 500 characters.');$s['periods'][$idx]['status']='returned';$s['periods'][$idx]['returned_at']=$now;$s['periods'][$idx]['return_reason']=$reason;}else throw new RuntimeException('Unsupported review action.');foreach(($s['entries']??[]) as &$e)if(is_array($e)&&($e['user_id']??'')===$userId&&($e['work_date']??'')>=$start&&($e['work_date']??'')<=$end)$e['status']=$s['periods'][$idx]['status']==='approved'?'approved':'completed';unset($e);return $s['periods'][$idx];
 });
}
function kcmc_timeclock_adjust_entry(string $entryId,string $reviewerId,int $newMinutes,string $reason): array {
 $entryId=trim($entryId);$reviewerId=trim($reviewerId);$reason=trim($reason);
 if($entryId===''||$reviewerId==='')throw new RuntimeException('The time entry could not be identified.');
 if($newMinutes<0||$newMinutes>1440)throw new RuntimeException('Adjusted time must be between 0 and 24 hours.');
 if($reason===''||kcmc_text_length($reason)>500)throw new RuntimeException('Enter an adjustment reason up to 500 characters.');
 return kcmc_update_json_store(KCMC_TIMECLOCK,['version'=>1,'entries'=>[],'periods'=>[],'adjustments'=>[]],function(array &$s)use($entryId,$reviewerId,$newMinutes,$reason):array{
  $s['entries']=is_array($s['entries']??null)?$s['entries']:[];$s['periods']=is_array($s['periods']??null)?$s['periods']:[];$s['adjustments']=is_array($s['adjustments']??null)?$s['adjustments']:[];
  $idx=null;foreach($s['entries'] as $i=>$entry)if(is_array($entry)&&($entry['id']??'')===$entryId){$idx=$i;break;}if($idx===null)throw new RuntimeException('Time entry not found.');
  $entry=&$s['entries'][$idx];$userId=(string)($entry['user_id']??'');if($userId===$reviewerId)throw new RuntimeException('A reviewer cannot adjust their own time entry.');if(($entry['status']??'')==='open')throw new RuntimeException('An open shift cannot be adjusted.');if(($entry['status']??'')==='approved')throw new RuntimeException('Approved time is locked.');
  $workDate=(string)($entry['work_date']??'');foreach($s['periods'] as $period){if(!is_array($period)||($period['user_id']??'')!==$userId)continue;if($workDate<(string)($period['start']??'')||$workDate>(string)($period['end']??''))continue;if(($period['status']??'')==='approved')throw new RuntimeException('Approved time is locked.');}
  $previous=(int)($entry['net_minutes']??0);if($previous===$newMinutes)throw new RuntimeException('The adjusted time is unchanged.');$now=kcmc_timeclock_now();$record=['id'=>kcmc_random_id('adjustment'),'entry_id'=>$entryId,'user_id'=>$userId,'previous_net_minutes'=>$previous,'new_net_minutes'=>$newMinutes,'reason'=>$reason,'adjusted_at'=>$now,'adjusted_by'=>$reviewerId];$s['adjustments'][]=$record;$entry['net_minutes']=$newMinutes;$entry['adjusted_at']=$now;$entry['adjusted_by']=$reviewerId;$entry['adjustment_count']=max(0,(int)($entry['adjustment_count']??0))+1;$entry['updated_at']=$now;return $record;
 });
}
