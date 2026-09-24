<?php
declare(strict_types=1);
$root=dirname(__DIR__);
function tcr_check(bool $condition,string $message): void { if(!$condition){fwrite(STDERR,"FAIL: $message\n");exit(1);}fwrite(STDOUT,"PASS: $message\n"); }
$lib=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/lib/timeclock.php');
$admin=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/admin/timecards.php');
$workflow=file_get_contents($root.'/.github/workflows/timeclock-mvp.yml');
tcr_check(is_string($lib)&&is_string($admin)&&is_string($workflow),'release sources are readable');
tcr_check(str_contains($lib,'correction_count'),'corrected periods are tracked');
tcr_check(str_contains($admin,'Original correction evidence is preserved privately.'),'administrator UI states evidence boundary');
tcr_check(str_contains($workflow,'timeclock-correction-contract.php'),'CI runs correction contract');
tcr_check(str_contains($workflow,'timeclock-correction-ui-contract.php'),'CI runs correction UI contract');
fwrite(STDOUT,"Time clock correction release contract passed.\n");
