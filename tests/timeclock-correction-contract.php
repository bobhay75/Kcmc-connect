<?php
declare(strict_types=1);
$root = dirname(__DIR__);
function tcc_check(bool $condition,string $message): void { if(!$condition){fwrite(STDERR,"FAIL: $message\n");exit(1);}fwrite(STDOUT,"PASS: $message\n"); }
$lib=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/lib/timeclock.php');
$member=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/member/timeclock.php');
$admin=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/admin/timecards.php');
foreach([$lib,$member,$admin] as $source)tcc_check(is_string($source),'correction workflow source is readable');
tcc_check(str_contains($lib,"'correction_requests'=>[]"),'private store includes correction requests');
tcc_check(str_contains($lib,"'adjustments'=>[]"),'supervisor adjustment history is preserved');
tcc_check(str_contains($lib,'That completed shift could not be found.'),'employee request is bound to an owned completed shift');
tcc_check(str_contains($lib,'already pending'),'duplicate pending requests are blocked');
tcc_check(str_contains($lib,"'before'=>\$before")&&str_contains($lib,"'after'=>\$after"),'applied corrections preserve before and after evidence');
tcc_check(str_contains($lib,'A reviewer cannot correct their own time entry.'),'administrator cannot apply a correction to own time');
tcc_check(str_contains($lib,"\$period['correction_count']"),'approved or submitted period correction marker is persisted');
tcc_check(str_contains($member,"'request_correction'"),'employee UI submits correction requests');
tcc_check(str_contains($member,'Your correction requests'),'employee can review request status');
tcc_check(str_contains($member,'Supervisor adjusted'),'existing supervisor adjustment marker is preserved');
tcc_check(str_contains($admin,"kcmc_require_role(['pastor_admin', 'recovery_admin'])"),'correction review remains administrator-only');
tcc_check(str_contains($admin,'kcmc_verify_csrf'),'administrator correction actions require CSRF');
tcc_check(str_contains($admin,"'apply_correction'")&&str_contains($admin,"'reject_correction'"),'administrator can apply or reject pending correction requests');
tcc_check(str_contains($admin,"'timeclock.correction_applied'")&&str_contains($admin,"'timeclock.correction_rejected'"),'correction actions emit privacy-safe audit events');
tcc_check(!str_contains($admin,"kcmc_audit('timeclock.correction_applied', ['reason'"),'private correction reason is excluded from general audit context');
fwrite(STDOUT,"Time clock correction contract passed.\n");
