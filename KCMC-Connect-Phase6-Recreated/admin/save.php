<?php
require_once __DIR__ . '/../lib/bootstrap.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
if ($_SERVER['REQUEST_METHOD']!=='POST' || !kcmc_verify_csrf($_POST['csrf']??null)) { http_response_code(403); exit('Invalid request'); }
$data=kcmc_content();
$contactEmail=kcmc_normalize_email((string)($_POST['contact_email']??''));
if(!kcmc_valid_email($contactEmail)){http_response_code(422);exit('Enter a valid church contact email.');}
$data['contact']['phone']=trim((string)($_POST['contact_phone']??''));
$data['contact']['email']=$contactEmail;
$data['contact']['office_hours']=trim((string)($_POST['contact_hours']??''));
$data['contact']['address']=trim((string)($_POST['contact_address']??''));
$announcements=is_array($data['announcements']??null)?$data['announcements']:[];
$requestedAnnouncementId=(string)($_POST['announcement_id']??'');
$announcementIndex=null;
foreach($announcements as $i=>$announcement){
    if(is_array($announcement)&&($announcement['id']??'')===$requestedAnnouncementId&&!in_array($requestedAnnouncementId,KCMC_RETIRED_CONTENT_IDS,true)){$announcementIndex=(int)$i;break;}
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
    if(!isset($data['events'][$i]))continue;
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
        http_response_code(422);
        exit('Each published event must have a valid date.');
    }
    if($data['events'][$i]['time']!=='' && $startMinutes===null){
        http_response_code(422);
        exit('Event start time must use a format such as 4:30 PM.');
    }
    if((string)($data['events'][$i]['end_time']??'')!=='' && $endMinutes===null){
        http_response_code(422);
        exit('Event end time must use a format such as 6:30 PM.');
    }
    if($startMinutes!==null && $endMinutes!==null && $endMinutes<=$startMinutes){
        http_response_code(422);
        exit('Event end time must be later than the start time.');
    }
    $data['events'][$i]['status']=$status;
    $ex=trim((string)($p['expires']??''));
    $data['events'][$i]['expires_at']=kcmc_local_datetime_iso($ex,true);
}
kcmc_write_content($data,(string)$user['display_name']);
kcmc_audit('content.published', ['content_version' => '3.0.0']);
header('Location: ' . kcmc_url('admin/?msg=' . rawurlencode('Published successfully. Backup created automatically.')));
