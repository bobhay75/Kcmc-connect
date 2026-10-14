<?php
declare(strict_types=1);
require_once __DIR__.'/../KCMC-Connect-Phase6-Recreated/lib/event-calendar.php';
function calendar_check(bool $ok,string $name):void{if(!$ok)throw new RuntimeException($name);echo "PASS: $name\n";}
$zone=new DateTimeZone('America/Chicago');
$now=new DateTimeImmutable('2026-10-14 12:00:00',$zone);
$weekly=['id'=>'weekly','title'=>'Study','date'=>'2026-10-14','time'=>'5:17 PM','end_time'=>'6:00 PM','repeat'=>'weekly','status'=>'published','expires_at'=>'','location'=>'KCMC'];
$one=['id'=>'one','title'=>'One-time','date'=>'2026-10-22','time'=>'8:30 AM','status'=>'published'];
$outside=['id'=>'trunk','title'=>'Trunk or Treat','date'=>'2026-10-31','time'=>'4:30 PM','end_time'=>'6:30 PM'];
$items=[$weekly,$one,$outside];$original=$items;
$week=kcmc_event_calendar($items,'next-week',$now);
calendar_check(array_column($week['events'],'date')===['2026-10-21','2026-10-22'],'next week projects weekly dates and filters one-time dates');
calendar_check($week['events'][1]===$one&&$items===$original,'one-time records and input remain byte-equivalent');
calendar_check($week['events'][0]['time']==='5:17 PM'&&$week['events'][0]['end_time']==='6:00 PM','weekly clock times and location preserved');
calendar_check($week['range']==='Oct 18–Oct 24, 2026','Sunday to Saturday range');
foreach(['2026-10-18'=>'2026-10-28','2026-10-31'=>'2026-11-04','2027-03-13'=>'2027-03-17','2026-12-31'=>'2027-01-06'] as $day=>$date){
 $view=kcmc_event_calendar([$weekly],'next-week',new DateTimeImmutable($day,$zone));
 calendar_check($view['events'][0]['date']===$date,'Sunday boundary, DST or year rollover: '.$day);
}
foreach([
 ['status'=>'hidden'],['deleted_at'=>'2026-10-01'],['id'=>'backpack-blessing-2026'],
 ['starts_at'=>'2026-10-19T00:00:00-05:00'],['expires_at'=>'2026-10-13T23:59:59-05:00'],
 ['repeat_until'=>'2026-10-20'],['date'=>'2026-02-31'],['date'=>'2026-11-04']
] as $override){calendar_check(kcmc_event_calendar([array_replace($weekly,$override)],'next-week',$now)['events']===[],'excluded unavailable series: '.json_encode($override));}
calendar_check(count(kcmc_event_calendar([array_replace($weekly,['repeat_until'=>'2026-10-21'])],'next-week',$now)['events'])===1,'inclusive weekly end date');
$edges=[array_replace($one,['date'=>'2026-10-18']),array_replace($one,['id'=>'sat','date'=>'2026-10-24']),array_replace($one,['id'=>'after','date'=>'2026-10-25'])];
calendar_check(count(kcmc_event_calendar($edges,'next-week',$now)['events'])===2,'Sunday and Saturday included, following Sunday excluded');
$upcoming=kcmc_active_items($items);usort($upcoming,'kcmc_compare_event_start');
foreach([null,'upcoming','<script>',[],['next-week']] as $invalid){calendar_check(kcmc_event_calendar($items,$invalid,$now)['events']===$upcoming,'default and malformed requests retain existing Upcoming behavior');}
calendar_check(kcmc_event_calendar([],'next-week',$now)['events']===[],'empty week supported');

$legacy=array_replace($weekly,['id'=>'griefshare-0902','title'=>'GriefShare begins','time'=>'9:30 AM','end_time'=>'']);
$current=array_replace($legacy,['id'=>'griefshare-20261014','title'=>'GriefShare']);
$pair=[$legacy,$current];$saved=$pair;
calendar_check(array_column(kcmc_event_calendar($pair,'next-week',$now)['events'],'id')===['griefshare-20261014'],'known duplicate weekly GriefShare shows once');
calendar_check($pair===$saved,'deduplication does not modify source records');
foreach(['upcoming','next-week'] as $view){
 $dynamic=array_map(fn($e)=>array_replace($e,['date'=>date('Y-m-d')]),$pair);
 calendar_check(count(kcmc_event_calendar($dynamic,$view)['events'])===1,'deduplicate in '.$view);
}
calendar_check(count(kcmc_event_calendar([$legacy,array_replace($current,['status'=>'hidden'])],'next-week',$now)['events'])===1,'hidden replacement does not hide legacy');
calendar_check(kcmc_event_calendar([$legacy,array_replace($current,['deleted_at'=>'2026-10-13'])],'next-week',$now)['events'][0]['id']==='griefshare-0902','deleted replacement does not hide legacy');
foreach(['time'=>'10:00 AM','location'=>'Other room','end_time'=>'11:00 AM','id'=>'unrelated-series'] as $field=>$value){
 calendar_check(count(kcmc_event_calendar([$legacy,array_replace($current,[$field=>$value])],'next-week',$now)['events'])===2,'different occurrence preserved: '.$field);
}
$once=array_replace($legacy,['repeat'=>'','date'=>'2026-10-21']);
calendar_check(count(kcmc_event_calendar([$once,$current],'next-week',$now)['events'])===2,'legacy one-time event is never suppressed');
