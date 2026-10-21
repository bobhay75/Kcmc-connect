<?php
declare(strict_types=1);
// Isolated in-memory stores and injected transport: never send mail or read private production data.
const KCMC_PRIVATE_DATA='/__kcmc_isolated_welcome_test__';
$stores=[];$config=[];
function kcmc_content():array{return ['contact'=>[]];}
function kcmc_config():array{global $config;return $config;}
function kcmc_read_json_store(string $p,array $default):array{global $stores;return $stores[$p]??$default;}
function kcmc_update_json_store(string $p,array $default,callable $fn):mixed{global $stores;$state=$stores[$p]??$default;$result=$fn($state);$stores[$p]=$state;return $result;}
function check(bool $ok,string $label):void{if(!$ok)throw new RuntimeException($label);}
$root=$argv[1]??'';
require $root.'/lib/visitor-welcome.php';
require $root.'/lib/invitation-mailer.php';
require __DIR__.'/payload/lib/connection-welcome.php';
foreach(['KCMC_VISITOR_WELCOME_MAIL_ENABLED','KCMC_INVITATION_MAIL_ENABLED','KCMC_INVITATION_FROM','KCMC_INVITATION_FROM_NAME'] as $key)putenv($key);
check(!kcmc_connection_welcome_settings()['ready'],'No default sender enablement');
$config=['invitation_mail_enabled'=>true,'invitation_from'=>'office@example.org','invitation_from_name'=>'KCMC'];
check(kcmc_connection_welcome_settings()['ready'],'Configured invitation sender reused');
$config=['invitation_mail_enabled'=>true,'invitation_from'=>"office@example.org\r\nBcc: x"];
check(!kcmc_connection_welcome_settings()['ready'],'Unsafe configured sender rejected');
$config=[];
$row=['kind'=>'visit','name'=>'Jane Visitor','email'=>'jane@example.org','service'=>'9:15 AM — Traditional Worship','message'=>'PRIVATE NOTE DO NOT COPY'];
$id=static fn(int $n):string=>'connection_'.str_pad(dechex($n),24,'0',STR_PAD_LEFT);
$count=0;$messages=[];
$transport=static function($to,$subject,$body,$headers,$envelope)use(&$count,&$messages):bool{$count++;$messages[]=[$to,$subject,quoted_printable_decode($body),$headers,$envelope];return true;};
$ready=['ready'=>true,'from'=>'welcome@example.org','from_name'=>'KCMC Connect'];
check(kcmc_connection_welcome_send($id(1),$row,$transport,['ready'=>false],100000)['status']==='not_configured','Unconfigured sender must fail closed');
check($count===0,'No unconfigured mail');
check(kcmc_connection_welcome_send($id(2),$row,$transport,$ready,100001)['status']==='accepted','Welcome handoff');
check($count===1,'One handoff');
check(!str_contains($messages[0][2],$row['message']),'No visitor notes in automatic email');
check(str_contains($messages[0][2],'welcome-kit.php'),'Welcome package linked');
check($messages[0][3]['Auto-Submitted']==='auto-generated','Automatic mail header');
check(kcmc_connection_welcome_send($id(2),$row,$transport,$ready,100002)['status']==='accepted'&&$count===1,'Same request cannot resend');
$row['kind']='groups';
check(kcmc_connection_welcome_send($id(3),$row,$transport,$ready,100003)['status']==='suppressed'&&$count===1,'Same recipient suppressed across connection types');
$row['email']='group@example.org';
check(kcmc_connection_welcome_send($id(4),$row,$transport,$ready,100004)['status']==='accepted','Group signup welcome');
$row['kind']='serve';$row['email']='serve@example.org';
check(kcmc_connection_welcome_send($id(5),$row,$transport,$ready,100005)['status']==='accepted','Volunteer signup welcome');
$row['email']="bad@example.org\r\nBcc: other@example.org";
$before=$count;
check(kcmc_connection_welcome_send($id(6),$row,$transport,$ready,100006)['status']==='unavailable'&&$count===$before,'Header injection rejected');
$row['email']='failure@example.org';
$failed=static function()use(&$count):bool{$count++;throw new RuntimeException('transport failed');};
check(kcmc_connection_welcome_send($id(7),$row,$failed,$ready,100007)['status']==='unavailable','Transport failure recorded');
$before=$count;kcmc_connection_welcome_send($id(7),$row,$transport,$ready,100008);check($count===$before,'No retry after failed handoff');
check(kcmc_welcome_draft_save($id(2),'Welcome','Message',0,'admin')['ok'],'Draft saved');
check(!kcmc_welcome_draft_save($id(2),'Overwrite','Wrong',0,'admin')['ok'],'Concurrent draft overwrite blocked');
check(kcmc_welcome_draft_read($id(2),$row)['body']==='Message','Saved draft preserved');
check(!kcmc_welcome_draft_save($id(2),"Welcome\nBcc: x",'Message',1,'admin')['ok'],'Unsafe subject rejected');
$source=file_get_contents(__DIR__.'/payload/admin/welcome.php');
check(strpos($source,'kcmc_require_role')<strpos($source,'kcmc_connection_recent'),'Role check precedes private reads');
check(str_contains($source,'kcmc_verify_csrf'),'Draft mutation has CSRF check');
echo "PASS: welcome deduplication, sender fallback, transport failure, privacy and draft conflict checks. No emails sent.\n";
