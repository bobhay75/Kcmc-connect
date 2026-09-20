<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
define('KCMC_ROOT',__DIR__.'/../KCMC-Connect-Phase6-Recreated');
require KCMC_ROOT.'/lib/invitation-delivery.php';
function kcmc_h(string $v): string { return htmlspecialchars($v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
$token=str_repeat('a',64);
$record=['email'=>'dana@example.invalid','display_name'=>'Dana Example','role'=>'pastor_admin','created_by'=>'test_admin',
    'token_hash'=>hash('sha256',$token),'used_at'=>null,'expires_at'=>'2031-01-08T00:00:00Z'];
$current=['id'=>'test_admin'];
$base='https://bobsome1.com/kcmc-connect/member/activate.php';
$delivery=kcmc_invitation_delivery(['invites'=>[$record]],$base.'?token='.$token,'dana@example.invalid','test_admin',$base,strtotime('2031-01-01T00:00:00Z'));
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invitation delivery — synthetic preview</title><style>
body{margin:0;padding:24px;background:#07121c;color:#eef5f8;font:16px/1.5 system-ui,sans-serif}main{max-width:900px;margin:auto}*{box-sizing:border-box}.portal-card{padding:24px;border-radius:18px}.eyebrow{font-size:.78rem;font-weight:750;color:#d6ad62;letter-spacing:.12em}.btn{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border:1px solid #647d8d;border-radius:30px;text-decoration:none;background:transparent;color:#fff}.gold{background:#d6ad62;color:#18212a}a{color:inherit}
<?php readfile(KCMC_ROOT.'/admin/invitation-delivery.css'); ?>
</style></head><body><main><p>TEST PREVIEW • fictitious recipient • no message will be sent</p><?php require KCMC_ROOT.'/admin/invitation-delivery.php'; ?></main><script><?php readfile(KCMC_ROOT.'/admin/invitation-delivery.js'); ?></script></body></html>
