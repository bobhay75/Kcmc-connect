<?php
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/backup-retention.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
function kcmc_publish_fail(string $message, int $status): never {
    http_response_code($status);
    if (str_contains((string)($_SERVER['HTTP_ACCEPT'] ?? ''), 'application/json')) {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['ok'=>false, 'error'=>$message], JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
    } else {
        header('Content-Type: text/html; charset=utf-8');
        $copy = $_POST; unset($copy['csrf']);
        require_once __DIR__ . '/../lib/screen-navigation.php';
        echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Publishing • KCMC Connect</title><link rel="stylesheet" href="' . kcmc_h(kcmc_url('styles.css?v=3.0.0')) . '">' . kcmc_screen_assets() . '</head><body class="portal-body">' . kcmc_screen_navigation('admin/', true) . '<main class="portal-shell portal-narrow"><h1>Changes were not published</h1><p role="alert">' . kcmc_h($message) . '</p><details><summary>Copy your unsaved input before reloading</summary><textarea readonly rows="18" cols="70">' . kcmc_h(json_encode($copy, JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES) ?: '') . '</textarea></details></main></body></html>';
    }
    exit;
}
if ($_SERVER['REQUEST_METHOD']!=='POST' || !is_string($_POST['csrf']??null) || !kcmc_verify_csrf($_POST['csrf'])) { kcmc_publish_fail('Invalid request. Your changes were not published.', 403); }
if ((string)($_POST['confirm_publish'] ?? '') !== '1') { kcmc_publish_fail('Review the changes and confirm that they are ready to publish.', 422); }
$version = is_string($_POST['version'] ?? null) ? $_POST['version'] : '';
if (!preg_match('/\A[a-f0-9]{64}\z/', $version)) kcmc_publish_fail('This editor is out of date. Copy your changes before opening the latest version.', 428);
if (!hash_equals($version, hash_file('sha256', KCMC_DATA) ?: '')) kcmc_publish_fail('Content changed. Your edits are still here. Open the latest version in another tab to compare before publishing.', 409);
$data=kcmc_content();
$contactEmail=kcmc_normalize_email((string)($_POST['contact_email']??''));
if(!kcmc_valid_email($contactEmail)){kcmc_publish_fail('Enter a valid church contact email.', 422);}
$data['contact']['phone']=trim((string)($_POST['contact_phone']??''));
$data['contact']['email']=$contactEmail;
$data['contact']['office_hours']=trim((string)($_POST['contact_hours']??''));
$data['contact']['address']=trim((string)($_POST['contact_address']??''));
$announcements=is_array($data['announcements']??null)?$data['announcements']:[];
$requestedAnnouncementId=(string)($_POST['announcement_id']??'');
foreach($announcements as $savedAnnouncement){if(is_array($savedAnnouncement)&&($savedAnnouncement['id']??'')===$requestedAnnouncementId&&!empty($savedAnnouncement['deleted_at'])){kcmc_publish_fail('This announcement was deleted. Your input is still here; review the latest Publishing Desk.', 409);}}
$announcementIndex=null;
foreach($announcements as $i=>$announcement){
    if(is_array($announcement)&&empty($announcement['deleted_at'])&&($announcement['id']??'')===$requestedAnnouncementId&&!in_array($requestedAnnouncementId,KCMC_RETIRED_CONTENT_IDS,true)){$announcementIndex=(int)$i;break;}
}
if($announcementIndex===null)$announcementIndex=kcmc_featured_announcement_index($announcements);
if($announcementIndex===null){$announcements[]=['id'=>'owner-announcement'];$announcementIndex=array_key_last($announcements);}
$a=$announcements[$announcementIndex];
$a['title']=trim((string)($_POST['announcement_title']??''));
$a['body']=trim((string)($_POST['announcement_body']??''));
$a['priority']=max(0,min(100,(int)($_POST['announcement_priority']??50)));
$a['status']=($_POST['announcement_status']??'hidden')==='published'?'published':'hidden';
$exp=trim((string)($_POST['announcement_expires']??'')); $a['expires_at']=kcmc_local_datetime_iso($exp);
$announcements[$announcementIndex]=$a;
$data['announcements']=$announcements;
$data['bulletin']['title']=trim((string)($_POST['bulletin_title']??''));
$data['bulletin']['date']=trim((string)($_POST['bulletin_date']??''));
$data['bulletin']['welcome']=trim((string)($_POST['bulletin_welcome']??''));
$data['bulletin']['notes']=array_values(array_filter(array_map('trim',preg_split('/\R/',(string)($_POST['bulletin_notes']??'')))));
$postedEvents=$_POST['events']??[];
foreach($postedEvents as $i=>$p){
    if(!isset($data['events'][$i]) || !empty($data['events'][$i]['deleted_at']))continue;
    $data['events'][$i]['title']=trim((string)($p['title']??''));
    $data['events'][$i]['date']=trim((string)($p['date']??''));
    $data['events'][$i]['time']=trim((string)($p['time']??''));
    if(array_key_exists('end_time',$p))$data['events'][$i]['end_time']=trim((string)$p['end_time']);
    if(array_key_exists('location',$p))$data['events'][$i]['location']=trim((string)$p['location']);
    if(array_key_exists('description',$p))$data['events'][$i]['description']=trim((string)$p['description']);
    $data['events'][$i]['priority']=max(0,min(100,(int)($p['priority']??50)));
    $status=($p['status']??'hidden')==='published'?'published':'hidden';
    $date=$data['events'][$i]['date'];
    $startMinutes=kcmc_event_time_minutes($data['events'][$i]['time']);
    $endMinutes=kcmc_event_time_minutes((string)($data['events'][$i]['end_time']??''));
    if($status==='published' && !kcmc_valid_event_date($date)){
        kcmc_publish_fail('Each published event must have a valid date.', 422);
    }
    if($data['events'][$i]['time']!=='' && $startMinutes===null){
        kcmc_publish_fail('Event start time must use a format such as 4:30 PM.', 422);
    }
    if((string)($data['events'][$i]['end_time']??'')!=='' && $endMinutes===null){
        kcmc_publish_fail('Event end time must use a format such as 6:30 PM.', 422);
    }
    if($startMinutes!==null && $endMinutes!==null && $endMinutes<=$startMinutes){
        kcmc_publish_fail('Event end time must be later than the start time.', 422);
    }
    $data['events'][$i]['status']=$status;
    $ex=trim((string)($p['expires']??''));
    $data['events'][$i]['expires_at']=kcmc_local_datetime_iso($ex,true);
}
try { $savedVersion = kcmc_write_content($data,(string)$user['display_name'],$version,true); }
catch (RuntimeException $e) { kcmc_publish_fail('Content changed or storage is unavailable. Your input is still here. Review the latest version before trying again.', 409); }
$rotation=kcmc_prune_content_backups(KCMC_BACKUPS);
kcmc_audit('content.published', ['content_version' => '3.0.0']);
if(($rotation['removed']??0)>0||($rotation['failed']??0)>0)kcmc_audit('content.backups_rotated',['removed'=>(int)($rotation['removed']??0),'failed'=>(int)($rotation['failed']??0),'kept'=>(int)($rotation['kept']??0)]);
if (str_contains((string)($_SERVER['HTTP_ACCEPT'] ?? ''), 'application/json')) {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok'=>true, 'version'=>$savedVersion]);
} else header('Location: ' . kcmc_url('admin/?msg=' . rawurlencode('Published successfully. Backup created automatically.')));
