<?php
declare(strict_types=1);
$tmp = sys_get_temp_dir() . '/kcmc-welcome-' . bin2hex(random_bytes(6));
mkdir($tmp, 0700, true);
putenv('KCMC_PRIVATE_DATA_DIR=' . $tmp);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/visitor-welcome.php';
function welcome_check(bool $ok, string $label): void {
    if (!$ok) throw new RuntimeException('FAIL: ' . $label);
    echo 'PASS: ' . $label . PHP_EOL;
}
$settings = ['visitor_welcome_mail_enabled' => true, 'visitor_welcome_from' => 'welcome@example.invalid',
    'visitor_welcome_base_url' => 'https://church.example.invalid/app/'];
$visit = ['kind'=>'visit', 'name'=>'Sam Guest', 'email'=>'sam@example.invalid',
    'service'=>'10:30 AM — Contemporary Worship', 'message'=>'PRIVATE NOTE https://do-not-reflect.invalid', 'phone'=>'555-private'];
$next = static fn(int $i): string => 'connection_' . str_pad(dechex($i), 24, '0', STR_PAD_LEFT);
$captured = [];
$accept = static function (...$args) use (&$captured): bool { $captured[] = $args; return true; };
$now = 2100000000;
try {
    welcome_check(!kcmc_visitor_welcome_settings([])['ready'], 'visitor receipts are disabled by default');
    welcome_check(!kcmc_visitor_welcome_settings(['invitation_mail_enabled'=>true,'invitation_from'=>'a@example.invalid'])['ready'], 'staff invitation enablement does not enable visitor emails');
    welcome_check(kcmc_visitor_welcome_settings($settings)['ready'], 'explicit visitor settings accept an authorized mailbox');
    foreach (["bad@example.invalid\r\nBcc: attack@example.invalid", '-fother@example.invalid', 'a;cmd@example.invalid', 'a b@example.invalid'] as $bad) {
        welcome_check(!kcmc_visitor_welcome_settings(array_replace($settings, ['visitor_welcome_from'=>$bad]))['ready'], 'unsafe sender is rejected');
    }
    foreach (['http://church.example.invalid/', 'https://user@church.example.invalid/', 'https://church.example.invalid/?token=x', 'https://church.example.invalid/#fragment', 'https://church.example.invalid/ evil'] as $bad) {
        welcome_check(!kcmc_visitor_welcome_settings(array_replace($settings, ['visitor_welcome_base_url'=>$bad]))['ready'], 'unsafe or token-bearing base URL is rejected');
    }
    $disabled = kcmc_visitor_welcome_send($next(1), $visit, $accept, [], $now);
    welcome_check($disabled['status']==='not_configured' && count($captured)===0, 'disabled receipts never invoke transport');
    $result = kcmc_visitor_welcome_send($next(2), $visit, $accept, $settings, $now);
    welcome_check($result['status']==='accepted' && count($captured)===1, 'configured visit is handed off immediately');
    [$to,$subject,$encoded,$headers,$envelope] = $captured[0];
    $body = quoted_printable_decode($encoded);
    welcome_check($to===$visit['email'] && $envelope==='-fwelcome@example.invalid', 'one intended recipient with aligned envelope sender');
    welcome_check($headers['Reply-To']==='secretary@umckc.org', 'visitor replies go to the published church office');
    welcome_check(!isset($headers['Cc']) && !isset($headers['Bcc']), 'no copying or leaking visitor details to other recipients');
    welcome_check($headers['Auto-Submitted']==='auto-generated', 'automatic-response loop suppression is set');
    welcome_check(str_contains($body, 'Hi Sam,') && str_contains($body, $visit['service']), 'receipt greets visitor and confirms the chosen service');
    foreach (['#events','#partner','#serve','bulletin.php','#visit','maps.app.goo.gl','Launch Kids','417-739-4395'] as $value) {
        welcome_check(str_contains($body,$value), 'receipt contains next step ' . $value);
    }
    welcome_check(!str_contains($body,'PRIVATE NOTE') && !str_contains($body,'do-not-reflect') && !str_contains($body,'555-private'), 'private notes and phone are not reflected into mail');
    welcome_check(str_contains($body,'does not create an account or subscribe'), 'receipt does not enroll anyone in ongoing messages');
    $injected=$visit; $injected['name']='https://malicious.invalid Attack';
    welcome_check(!str_contains(kcmc_visitor_welcome_message($injected,kcmc_visitor_welcome_settings($settings))['body'],'malicious.invalid'), 'untrusted name cannot become a reflected advertising URL');
    kcmc_visitor_welcome_send($next(2),$visit,$accept,$settings,$now+1);
    welcome_check(count($captured)===1, 'same saved request never sends twice');
    $result=kcmc_visitor_welcome_send($next(3),$visit,$accept,$settings,$now+1801);
    welcome_check($result['status']==='suppressed' && count($captured)===1, 'recipient limit blocks repeat mail even after intake duplicate window');
    $other=$visit; $other['email']='other@example.invalid';
    $result=kcmc_visitor_welcome_send($next(4),$other,static fn()=>false,$settings,$now);
    welcome_check($result['status']==='unavailable','transport rejection is not reported as delivered');
    $throwing=$visit; $throwing['email']='exception@example.invalid';
    $result=kcmc_visitor_welcome_send($next(5),$throwing,static function(){throw new RuntimeException('synthetic');},$settings,$now);
    welcome_check($result['status']==='unavailable','transport exception produces safe follow-up status');
    $result=kcmc_visitor_welcome_send($next(6),$visit,$accept,$settings,$now+86401);
    welcome_check($result['status']==='accepted' && count($captured)===2,'later legitimate visit may receive a receipt after 24 hours');
    $nonvisit=$visit; $nonvisit['kind']='groups';
    welcome_check(kcmc_visitor_welcome_send($next(7),$nonvisit,$accept,$settings,$now)['status']==='not_applicable','group interest does not receive a visit receipt');
    $invalid=$visit; $invalid['service']='arbitrary service';
    welcome_check(kcmc_visitor_welcome_send($next(8),$invalid,$accept,$settings,$now)['status']==='unavailable','mailer independently checks the service allowlist');
    $state=file_get_contents(KCMC_VISITOR_WELCOME_STATE);
    welcome_check(!str_contains($state,'@') && !str_contains($state,'Sam') && !str_contains($state,'PRIVATE NOTE'), 'delivery ledger contains no email addresses, names or notes');
    welcome_check(kcmc_visitor_welcome_states()[$next(2)]['status']==='accepted','staff can read persisted delivery state');
    welcome_check(str_contains(kcmc_visitor_welcome_status_label('accepted'),'not confirmed'),'staff label distinguishes server acceptance from inbox delivery');
    welcome_check(str_contains(kcmc_visitor_welcome_confirmation('unavailable'),'still saved'),'failed email does not imply the visit request was lost');
    file_put_contents(KCMC_VISITOR_WELCOME_STATE,'{broken');
    $fresh=$visit; $fresh['email']='fresh@example.invalid';
    welcome_check(kcmc_visitor_welcome_send($next(9),$fresh,$accept,$settings,$now)['status']==='unavailable' && count($captured)===2,'corrupt delivery state fails closed without sending');
    $api=file_get_contents(__DIR__.'/../KCMC-Connect-Phase6-Recreated/api/connection.php');
    welcome_check(strpos($api,"if (!empty(\$result['duplicate']))") < strpos($api,'$welcome ='), 'duplicate requests return before mail logic');
    welcome_check(strpos($api,"if (empty(\$result['stored']))") < strpos($api,'$welcome ='), 'failed saves return before mail logic');
    welcome_check(str_contains($api,"kcmc_audit(\$auditAction, ['count' => 1]);"),'audit remains aggregate-only');
} finally {
    foreach (glob($tmp.'/*') as $file) unlink($file);
    rmdir($tmp);
}
echo "Visitor welcome contract passed; no real mail sent.\n";
