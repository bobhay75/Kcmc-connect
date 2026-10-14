<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/public-presentation.php';
function check_post(bool $ok, string $label): void { if (!$ok) throw new RuntimeException($label); echo "PASS: $label\n"; }
$event = ['id'=>'test-event','title'=>'Study','date'=>'2026-10-14','time'=>'5:17 PM','end_time'=>'6:00 PM','status'=>'published','expires_at'=>'2026-10-14T23:59:59-05:00'];
$data = ['contact'=>['email'=>'unchanged@example.org'],'events'=>[$event], 'announcements'=>[['id'=>'a','body'=>'Keep this','status'=>'published']], 'bulletin'=>['notes'=>['Keep this too']]];
$weekly = kcmc_change_post($data,'events','test-event','repeat',['repeat'=>'weekly']);
check_post($weekly['events'][0]['expires_at']==='', 'ongoing weekly series clears one-off expiry');
check_post($weekly['events'][0]['time']===$event['time'] && $weekly['contact']===$data['contact'] && $weekly['announcements']===$data['announcements'] && $weekly['bulletin']===$data['bulletin'], 'weekly setting preserves time and unrelated content');
$zone = new DateTimeZone('America/Chicago');
foreach (['2026-10-14'=>'2026-10-14','2026-10-15'=>'2026-10-21','2026-11-01'=>'2026-11-04','2027-03-14'=>'2027-03-17'] as $today=>$expected) {
    $next=kcmc_next_weekly_occurrence($weekly['events'][0],new DateTimeImmutable($today,$zone));
    check_post($next['date']===$expected && $next['time']==='5:17 PM','next date across week and DST: '.$today);
}
$bounded=kcmc_change_post($data,'events','test-event','repeat',['repeat'=>'weekly','repeat_until'=>'2026-10-21']);
check_post(kcmc_next_weekly_occurrence($bounded['events'][0],new DateTimeImmutable('2026-10-21',$zone))!==null, 'last weekly date included');
check_post(kcmc_next_weekly_occurrence($bounded['events'][0],new DateTimeImmutable('2026-10-22',$zone))===null, 'series stops after last date');
$once=kcmc_change_post($weekly,'events','test-event','repeat',['repeat'=>'']);
check_post($once===$data, 'switching to Once restores original expiry and fields');
check_post(kcmc_next_weekly_occurrence($event)===$event, 'one-off event unchanged');
$deleted=kcmc_change_post($weekly,'events','test-event','delete');
check_post(count($deleted['events'])===1 && !empty($deleted['events'][0]['deleted_at']), 'delete retains recoverable record');
check_post(kcmc_active_items($deleted['events'])===[], 'deleted weekly event cannot reappear');
check_post(kcmc_public_content_view($deleted)['events']===[], 'trash excluded from public payload');
$restored=kcmc_change_post($deleted,'events','test-event','restore');
check_post($restored['events'][0]['status']==='hidden' && !isset($restored['events'][0]['deleted_at']), 'restored post stays hidden pending editorial review');
$ann=kcmc_change_post($data,'announcements','a','delete');
check_post(kcmc_active_items($ann['announcements'])===[] && $ann['events']===$data['events'], 'announcement deletion is scoped');
foreach ([['events','test-event','repeat',['repeat'=>'daily']],['events','test-event','repeat',['repeat'=>'weekly','repeat_until'=>'2026-02-31']],['events','test-event','repeat',['repeat'=>'weekly','repeat_until'=>'2026-10-13']],['users','a','delete',[]],['events','missing','delete',[]]] as $bad) {
    try { kcmc_change_post($data,...$bad); throw new RuntimeException('Invalid action accepted'); } catch (InvalidArgumentException $e) { echo "PASS: invalid post action rejected\n"; }
}
$source=file_get_contents(__DIR__.'/../KCMC-Connect-Phase6-Recreated/admin/posts.php');
check_post(str_contains($source,"kcmc_require_role(['pastor_admin', 'recovery_admin'])") && str_contains($source,'kcmc_verify_csrf') && str_contains($source,"['confirm']") && str_contains($source,'hash_equals'), 'mutations require editorial role CSRF confirmation and version check');
