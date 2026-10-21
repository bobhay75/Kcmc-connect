<?php
declare(strict_types=1);
if(!function_exists('kcmc_visitor_welcome_claim'))require_once __DIR__.'/visitor-welcome.php';
if(!function_exists('kcmc_invitation_mail_settings'))require_once __DIR__.'/invitation-mailer.php';
require_once __DIR__.'/welcome-drafts.php';
function kcmc_connection_welcome_settings(): array {
    $settings=kcmc_visitor_welcome_settings();
    if(!empty($settings['ready']))return $settings;
    $invitation=kcmc_invitation_mail_settings();
    if(!empty($invitation['ready']))return ['ready'=>true,'from'=>$invitation['from'],'from_name'=>$invitation['from_name']];
    return ['ready'=>false,'from'=>'','from_name'=>'KCMC Connect'];
}
function kcmc_connection_welcome_send(string $id,array $row,?callable $transport=null,?array $override=null,?int $now=null): array {
    $email=strtolower(trim((string)($row['email']??'')));
    if(!in_array($row['kind']??'',['visit','serve','groups'],true)||!preg_match('/\Aconnection_[a-f0-9]{24}\z/',$id)||!kcmc_visitor_welcome_email_valid($email))return ['status'=>'unavailable'];
    $settings=$override??kcmc_connection_welcome_settings();$now??=time();
    try{$claim=kcmc_visitor_welcome_claim($id,$email,!empty($settings['ready']),$now);}catch(Throwable){return ['status'=>'unavailable'];}
    if(empty($claim['send']))return ['status'=>(string)$claim['status']];
    $message=kcmc_welcome_draft_default($row);
    $message['body'].="\n\nThis automatic welcome responds to your KCMC signup. It does not subscribe you to a mailing list.";
    $headers=['From'=>'"'.addcslashes((string)$settings['from_name'],'\\"').'" <'.$settings['from'].'>','Reply-To'=>$settings['from'],'MIME-Version'=>'1.0','Content-Type'=>'text/plain; charset=UTF-8','Content-Transfer-Encoding'=>'quoted-printable','Auto-Submitted'=>'auto-generated','X-Auto-Response-Suppress'=>'All'];
    $sender=$transport??static function(string $to,string $subject,string $body,array $headers,string $envelope):bool{return mail($to,$subject,$body,$headers,$envelope);};
    try{$sent=$sender($email,'=?UTF-8?B?'.base64_encode($message['subject']).'?=',quoted_printable_encode(str_replace("\n","\r\n",$message['body'])),$headers,'-f'.$settings['from'])===true;}catch(Throwable){$sent=false;}
    $status=$sent?'accepted':'unavailable';
    try{kcmc_update_json_store(KCMC_VISITOR_WELCOME_STATE,[],static function(array &$state)use($id,$status):void{if(isset($state['deliveries'][$id]))$state['deliveries'][$id]['status']=$status;});}catch(Throwable){}
    return ['status'=>$status];
}
