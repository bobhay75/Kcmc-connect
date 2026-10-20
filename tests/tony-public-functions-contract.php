<?php
declare(strict_types=1);
require_once __DIR__.'/../KCMC-Connect-Phase6-Recreated/lib/public-features.php';
function verify_public(bool $value,string $label): void {if(!$value)throw new RuntimeException($label);echo "PASS: $label\n";}
$urls=['front-porch'=>'https://www.facebook.com/Church/videos/111/','traditional'=>'https://www.facebook.com/watch/?v=222','contemporary'=>'https://facebook.com/Church/videos/333/?tracking=anything'];
$services=kcmc_worship_services(['worship_streams'=>$urls]);
verify_public(count($services)===3 && count(array_unique(array_column($services,'stream_url')))===3,'three services retain distinct direct video destinations');
foreach($services as $service)verify_public(is_file(__DIR__.'/../KCMC-Connect-Phase6-Recreated/'.$service['image']),'service photo exists: '.$service['id']);
verify_public(kcmc_service_stream_url('https://www.facebook.com/watch/?v=111')===kcmc_service_stream_url($urls['front-porch']),'equivalent video URLs canonicalize before duplicate comparison');
$urls['traditional']='https://facebook.com/watch/?v=111';
$duplicates=kcmc_worship_services(['worship_streams'=>$urls]);
verify_public($duplicates[0]['stream_url']==='' && $duplicates[1]['stream_url']==='','duplicate recording is never labeled as two services');
foreach(['https://evil.invalid/videos/123','https://facebook.com@evil.invalid/videos/123','https://www.facebook.com/Church/live_videos','javascript:alert(1)','https://www.facebook.com/watch/?v[]=1','http://facebook.com/watch/?v=123',[],null] as $bad)verify_public(kcmc_service_stream_url($bad)==='','unsafe or generic service destination rejected');
$now=new DateTimeImmutable('2026-10-20T12:00:00-05:00');
$make=static fn($id,$title,$date,$extra=[])=>array_merge(['id'=>$id,'title'=>$title,'date'=>$date,'time'=>'4:30 PM','status'=>'published'],$extra);
$items=[$make('staff','Staff meeting','2026-10-21'),$make('preschool','Quest Preschool','2026-10-21'),$make('study','Bible study','2026-10-22'),$make('trunk-or-treat-2026','Trunk or Treat','2026-10-31'),$make('richard-french-lasagna-20261114','Lasagna Dinner','2026-11-14'),$make('hidden','Hidden community event','2026-10-30',['public_event'=>true,'status'=>'hidden']),$make('expired','Expired event','2026-10-10',['public_event'=>true]),$make('embargo','Embargoed event','2026-11-01',['public_event'=>true,'starts_at'=>'2026-11-01T00:00:00-06:00'])];
// Active-items uses real time; dates intentionally cover this October review.
$highlight=kcmc_public_event_calendar($items,null,null,$now);
verify_public(array_column($highlight['events'],'id')===['trunk-or-treat-2026','richard-french-lasagna-20261114'],'Trunk or Treat leads public highlights without meetings, classes or hidden records');
$calendar=kcmc_public_event_calendar($items,null,'calendar',$now);
verify_public(in_array('study',array_column($calendar['events'],'id'),true) && !in_array('staff',array_column($calendar['events'],'id'),true),'full calendar keeps programs while excluding staff meetings');
$next=kcmc_public_event_calendar($items,'next-week',null,$now);
verify_public(array_column($next['events'],'id')===['trunk-or-treat-2026'],'next-week highlights include Trunk or Treat');
foreach(['2026-10-20'=>true,'2026-10-25'=>true,'2026-10-13'=>false,'2026-11-01'=>false,''=>false,'2026-02-31'=>false] as $date=>$expected)verify_public(kcmc_bulletin_is_current(['date'=>$date],$now)===$expected,'bulletin freshness: '.($date?:'undated'));
verify_public(!kcmc_bulletin_is_current(['date'=>'2026-10-20'],$now->modify('+7 days')),'issue expires without silently changing the published date');
echo "Public function contract complete.\n";
