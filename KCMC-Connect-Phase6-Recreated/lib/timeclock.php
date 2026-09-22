<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';

define('KCMC_TIMECLOCK', KCMC_PRIVATE_DATA . '/timeclock.json');

function kcmc_timeclock_store(): array {
    return kcmc_read_json_store(KCMC_TIMECLOCK, ['version'=>1,'entries'=>[]]);
}
function kcmc_timeclock_now(): string { return gmdate('c'); }
function kcmc_timeclock_categories(): array { return ['Office / Administration','Maintenance / Facilities','Media / Worship','KCMC Connect / IT','Events / Outreach','Other']; }
function kcmc_timeclock_entries_for(string $userId): array {
    return array_values(array_filter(kcmc_timeclock_store()['entries']??[], fn($e)=>is_array($e)&&($e['user_id']??'')===$userId));
}
function kcmc_timeclock_open_entry(string $userId): ?array {
    foreach (array_reverse(kcmc_timeclock_entries_for($userId)) as $e) if (($e['status']??'')==='open') return $e;
    return null;
}
function kcmc_timeclock_minutes(string $start,string $end): int { return max(0,(int)floor((strtotime($end)-strtotime($start))/60)); }
function kcmc_timeclock_net_minutes(array $e): int {
    if (empty($e['clock_out_at'])) return 0;
    $gross=kcmc_timeclock_minutes((string)$e['clock_in_at'],(string)$e['clock_out_at']); $break=0;
    foreach (($e['breaks']??[]) as $b) if (is_array($b)&&!empty($b['start_at'])&&!empty($b['end_at'])) $break+=kcmc_timeclock_minutes((string)$b['start_at'],(string)$b['end_at']);
    return max(0,$gross-$break);
}
function kcmc_timeclock_mutate(string $userId,string $action,array $input=[]): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK,['version'=>1,'entries'=>[]],function(array &$s) use($userId,$action,$input): array {
        $now=kcmc_timeclock_now(); $idx=null;
        foreach ($s['entries'] as $i=>$e) if (is_array($e)&&($e['user_id']??'')===$userId&&($e['status']??'')==='open') $idx=$i;
        if ($action==='clock_in') {
            if ($idx!==null) throw new RuntimeException('You are already clocked in.');
            $e=['id'=>kcmc_random_id('time'),'user_id'=>$userId,'work_date'=>kcmc_local_date_value($now),'clock_in_at'=>$now,'clock_out_at'=>null,'breaks'=>[],'category'=>'','description'=>'','status'=>'open','created_at'=>$now,'updated_at'=>$now];
            $s['entries'][]=$e; kcmc_audit('timeclock.clock_in',['entry_id'=>$e['id']]); return $e;
        }
        if ($idx===null) throw new RuntimeException('No open shift.');
        $e=&$s['entries'][$idx]; $breakIndex=null;
        foreach (($e['breaks']??[]) as $i=>$b) if (is_array($b)&&empty($b['end_at'])) $breakIndex=$i;
        if ($action==='break_start') { if($breakIndex!==null) throw new RuntimeException('A break is already open.'); $e['breaks'][]=['start_at'=>$now,'end_at'=>null]; }
        elseif ($action==='break_end') { if($breakIndex===null) throw new RuntimeException('No open break.'); $e['breaks'][$breakIndex]['end_at']=$now; }
        elseif ($action==='clock_out') {
            if($breakIndex!==null) throw new RuntimeException('End the break before clocking out.');
            $category=trim((string)($input['category']??'')); $description=trim((string)($input['description']??''));
            if(!in_array($category,kcmc_timeclock_categories(),true)) throw new RuntimeException('Choose a valid work category.');
            if($description===''||kcmc_text_length($description)>1000) throw new RuntimeException('Enter a work description (maximum 1000 characters).');
            $e['clock_out_at']=$now; $e['category']=$category; $e['description']=$description; $e['status']='completed'; $e['net_minutes']=kcmc_timeclock_net_minutes($e);
        } else throw new RuntimeException('Unsupported time-clock action.');
        $e['updated_at']=$now; kcmc_audit('timeclock.'.$action,['entry_id'=>$e['id']]); return $e;
    });
}
function kcmc_timeclock_period(?DateTimeImmutable $date=null): array {
    $tz=new DateTimeZone(KCMC_LOCAL_TIMEZONE); $d=($date??new DateTimeImmutable('now',$tz))->setTimezone($tz); $day=(int)$d->format('j');
    if($day>=23){$start=$d->modify('first day of this month')->setDate((int)$d->format('Y'),(int)$d->format('n'),23);$end=$start->modify('+1 month')->setDate((int)$start->modify('+1 month')->format('Y'),(int)$start->modify('+1 month')->format('n'),22);}else{$end=$d->setDate((int)$d->format('Y'),(int)$d->format('n'),22);$prev=$d->modify('-1 month');$start=$prev->setDate((int)$prev->format('Y'),(int)$prev->format('n'),23);}
    return [$start->format('Y-m-d'),$end->format('Y-m-d')];
}
