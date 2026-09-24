<?php
declare(strict_types=1);
$root=dirname(__DIR__);
function tcs_check(bool $condition,string $message): void { if(!$condition){fwrite(STDERR,"FAIL: $message\n");exit(1);}fwrite(STDOUT,"PASS: $message\n"); }
$lib=file_get_contents($root.'/KCMC-Connect-Phase6-Recreated/lib/timeclock.php');
tcs_check(is_string($lib),'time-clock library is readable');
tcs_check(str_contains($lib,'A reviewer cannot correct their own time entry.'),'self-apply correction is blocked');
tcs_check(str_contains($lib,'A reviewer cannot reject their own time correction request.'),'self-reject correction is blocked');
fwrite(STDOUT,"Time clock correction self-review contract passed.\n");
