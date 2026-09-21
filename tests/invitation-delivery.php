<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/invitation-delivery.php';
$now = strtotime('2031-01-01T00:00:00Z');
$base = 'https://bobsome1.com/kcmc-connect/member/activate.php';
$token = str_repeat('a', 64); // synthetic, never a real invitation
$link = $base . '?token=' . $token;
$email = 'dana@example.invalid';
$record = ['email'=>$email,'display_name'=>'Dana Example','role'=>'pastor_admin','created_by'=>'test_admin',
    'token_hash'=>hash('sha256',$token),'expires_at'=>'2031-01-08T00:00:00Z','used_at'=>null];
$store = ['version'=>1,'invites'=>[$record]];
$passed = 0;
function verify(bool $test, string $name): void { global $passed; if (!$test) throw new RuntimeException('FAIL: '.$name); $passed++; echo "PASS: $name\n"; }
function card(array $state, ?string $url = null, ?string $address = null, ?string $creator = null, ?string $origin = null, ?int $time = null): ?array {
    global $link,$email,$base,$now;
    return kcmc_invitation_delivery($state,$url??$link,$address??$email,$creator??'test_admin',$origin??$base,$time??$now);
}
$d = card($store);
verify($d !== null && $d['name']==='Dana Example' && $d['email']===$email,'correct live record and recipient are bound');
verify($d['role']==='Pastor administrator','role label comes from stored role');
verify(str_contains($d['message'],$link) && str_contains($d['message'],$email),'copyable email includes exact link and recipient');
verify(str_contains($d['message'],'at least 12 characters'),'email explains recipient-owned password setup');
parse_str((string)parse_url($d['gmail_url'],PHP_URL_QUERY),$query);
verify($query['to']===$email && $query['su']===$d['subject'],'Gmail compose has correct recipient and subject');
verify(!isset($query['body']) && !str_contains($d['gmail_url'],$token) && !str_contains($d['email_url'],$token),'compose URLs do not contain activation token or email body');
verify(parse_url($d['gmail_url'],PHP_URL_HOST)==='mail.google.com','Gmail destination is fixed');
verify(card($store,null,'other@example.invalid')===null,'wrong recipient refused');
verify(card($store,null,null,'other_admin')===null,'wrong creator refused');
verify(card($store,$base.'?token='.str_repeat('b',64))===null,'unknown token refused');
foreach (['superseded','2031-01-01T00:00:00Z'] as $used) {
    $s=$store;$s['invites'][0]['used_at']=$used;verify(card($s)===null,'used/superseded token refused: '.$used);
}
foreach (['2031-01-01T00:00:00Z','2030-12-31T23:59:59Z','not-a-date',''] as $expiry) {
    $s=$store;$s['invites'][0]['expires_at']=$expiry;verify(card($s)===null,'invalid or expired invitation refused: '.$expiry);
}
foreach (['https://evil.example/activate.php?token='.$token,$link.'&extra=1',$link.'#x',$base.'?token=',$base.'?token='.strtoupper($token),$base.'?token[]=x'] as $url) {
    verify(card($store,$url)===null,'noncanonical or foreign activation link refused');
}
verify(card($store,'https://evil.example/activate.php?token='.$token,null,null,'https://evil.example/activate.php')===null,'untrusted Host cannot define a delivery destination');
verify(card($store,str_replace('https:','http:',$link),null,null,str_replace('https:','http:',$base))===null,'insecure production delivery refused');
$local='http://127.0.0.1:9876/kcmc-connect/member/activate.php';
verify(card($store,$local.'?token='.$token,null,null,$local)!==null,'explicit localhost is available for isolated tests');
$s=$store;$s['invites'][]=$record;verify(card($s)===null,'ambiguous duplicate hash refused');
foreach (['missing','unknown'] as $role) {
    $s=$store;if($role==='missing')unset($s['invites'][0]['role']);else $s['invites'][0]['role']=$role;
    verify(card($s)===null,'unknown or missing role refused');
}
foreach ([[],['invites'=>null],['invites'=>['bad',null]],['invites'=>[['token_hash'=>[]]]]] as $s) verify(card($s)===null,'malformed store fails closed');
$s=$store;$s['invites'][0]['display_name']="Dana\nBcc: attacker@example.invalid";verify(card($s)===null,'recipient control-character injection refused');
$before=serialize($store);card($store);verify(serialize($store)===$before,'helper does not mutate invitation state');
function kcmc_h(string $value): string { return htmlspecialchars($value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
define('KCMC_ROOT',__DIR__.'/../KCMC-Connect-Phase6-Recreated');
$current=['id'=>'test_admin'];$delivery=$d;
ob_start();require KCMC_ROOT.'/admin/invitation-delivery.php';$html=ob_get_clean();
verify(str_contains($html,'Invitation ready — not emailed'),'unsent delivery card reports that nothing was emailed');
$inviteSendSuccess=true;
ob_start();require KCMC_ROOT.'/admin/invitation-delivery.php';$sentHtml=ob_get_clean();
verify(str_contains($sentHtml,'Invitation email submitted') && str_contains($sentHtml,'does not prove inbox delivery'),'server-submitted card reports transport acceptance without claiming inbox delivery');
verify(!str_contains($sentHtml,'Nothing has been emailed.'),'server-submitted card does not contradict successful mail handoff');
unset($inviteSendSuccess);
verify(str_contains($html,'type="button"') && !str_contains($html,'type="submit"') && !str_contains($html,'<form'),'delivery controls cannot submit invitation creation');
verify(str_contains($html,'readonly') && str_contains($html,'<noscript>'),'manual-copy and no-JavaScript fallback available');
verify(str_contains($html,'rel="noopener noreferrer"') && str_contains($html,'referrerpolicy="no-referrer"'),'external Gmail links have safe new-tab and referrer attributes');
$s=$store;$s['invites'][0]['display_name']='<img src=x onerror=alert(1)>';$delivery=card($s);
ob_start();require KCMC_ROOT.'/admin/invitation-delivery.php';$html=ob_get_clean();
verify(!str_contains($html,'<img src=x') && str_contains($html,'&lt;img'),'all rendered invitation metadata is HTML escaped');
$users=file_get_contents(KCMC_ROOT.'/admin/users.php');
verify(strpos($users,"kcmc_require_role(['pastor_admin', 'recovery_admin'])") < strpos($users,"'/../lib/invitation-delivery.php'"),'authorization runs before delivery metadata read');
verify(str_contains($users,"unset(\$_SESSION['invite_link'], \$_SESSION['invite_email'], \$_SESSION['invite_send_status'], \$_SESSION['invite_send_success'])"),'invitation and send-result flash data are one-request scoped');
verify(str_contains($users,"name=\"send_email\" value=\"1\""),'app-sent invitation requires an explicit checkbox');
verify(str_contains($users,"kcmc_send_invitation_email(\$sendDelivery)"),'explicit send path uses the server-side invitation mailer');
verify(str_contains($users,"member.invitation_email_sent") && str_contains($users,"member.invitation_email_failed"),'server mail outcomes create audit events');
$javascript=file_get_contents(KCMC_ROOT.'/admin/invitation-delivery.js');
verify(!preg_match('/fetch\s*\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|readText\s*\(|window\.open|location\./',$javascript),'delivery JS has no network, local token storage, clipboard reads or current-URL dependency');
verify(str_contains($users,"if ((string)(\$_POST['send_email'] ?? '') === '1')"),'server send occurs only after explicit form opt-in');
verify(str_contains($users,"if (!\$mailReady)"),'unconfigured server mail fails closed to manual delivery');
verify(str_contains($users,"if (\$sendDelivery === null)"),'recipient-bound delivery validation must pass before server send');
echo "Invitation delivery PHP checks passed: $passed\n";
