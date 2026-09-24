<?php
declare(strict_types=1);
$root = dirname(__DIR__);
function tcu_check(bool $condition,string $message): void { if(!$condition){fwrite(STDERR,"FAIL: $message\n");exit(1);}fwrite(STDOUT,"PASS: $message\n"); }
$member=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/member/timeclock.php');
$admin=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/admin/timecards.php');
tcu_check(is_string($member)&&is_string($admin),'correction UI sources are readable');
tcu_check(str_contains($member,'Request a correction'),'employee correction disclosure is present');
tcu_check(str_contains($member,'minlength="5"')&&str_contains($member,'maxlength="500"'),'employee correction reason is bounded');
tcu_check(str_contains($admin,'datetime-local'),'administrator can enter corrected local punch times');
tcu_check(str_contains($admin,'Unpaid break minutes'),'administrator can correct break duration');
tcu_check(str_contains($admin,'Administrator correction reason'),'administrator reason is required');
tcu_check(str_contains($admin,'@media(max-width:720px)'),'correction review has phone layout');
tcu_check(str_contains($admin,'correction-mark'),'corrected periods are visibly marked');
fwrite(STDOUT,"Time clock correction UI contract passed.\n");
