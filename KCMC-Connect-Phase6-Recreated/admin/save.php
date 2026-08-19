<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_require_owner();
if ($_SERVER['REQUEST_METHOD']!=='POST' || !kcmc_verify_csrf($_POST['csrf']??null)) { http_response_code(403); exit('Invalid request'); }
$data=kcmc_content();
$data['contact']['phone']=trim((string)($_POST['contact_phone']??''));
$data['contact']['email']=trim((string)($_POST['contact_email']??''));
$data['contact']['office_hours']=trim((string)($_POST['contact_hours']??''));
$data['contact']['address']=trim((string)($_POST['contact_address']??''));
$a=$data['announcements'][0]??['id'=>'owner-announcement'];
$a['title']=trim((string)($_POST['announcement_title']??''));
$a['body']=trim((string)($_POST['announcement_body']??''));
$a['priority']=max(0,min(100,(int)($_POST['announcement_priority']??50)));
$a['status']=($_POST['announcement_status']??'hidden')==='published'?'published':'hidden';
$exp=trim((string)($_POST['announcement_expires']??'')); $a['expires_at']=$exp?date('c',strtotime($exp)):'';
$data['announcements'][0]=$a;
$data['bulletin']['title']=trim((string)($_POST['bulletin_title']??''));
$data['bulletin']['date']=trim((string)($_POST['bulletin_date']??''));
$data['bulletin']['welcome']=trim((string)($_POST['bulletin_welcome']??''));
$data['bulletin']['notes']=array_values(array_filter(array_map('trim',preg_split('/\R/',(string)($_POST['bulletin_notes']??'')))));
$postedEvents=$_POST['events']??[];
foreach($postedEvents as $i=>$p){ if(!isset($data['events'][$i]))continue; $data['events'][$i]['title']=trim((string)($p['title']??''));$data['events'][$i]['date']=trim((string)($p['date']??''));$data['events'][$i]['time']=trim((string)($p['time']??''));$data['events'][$i]['priority']=max(0,min(100,(int)($p['priority']??50)));$data['events'][$i]['status']=($p['status']??'hidden')==='published'?'published':'hidden';$ex=trim((string)($p['expires']??''));$data['events'][$i]['expires_at']=$ex?date('c',strtotime($ex.' 23:59:59')):''; }
kcmc_write_content($data,'owner');
header('Location: /admin/?msg='.rawurlencode('Published successfully. Backup created automatically.'));
