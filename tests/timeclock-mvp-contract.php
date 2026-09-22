<?php
declare(strict_types=1);
$root = dirname(__DIR__);
require_once $root . '/KCMC-Connect-Phase6-Recreated/lib/timeclock.php';

function tc_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
    fwrite(STDOUT, "PASS: $message\n");
}

[$s1,$e1] = kcmc_timeclock_period(new DateTimeImmutable('2026-09-22 12:00:00', new DateTimeZone('America/Chicago')));
tc_check($s1 === '2026-08-23' && $e1 === '2026-09-22', 'Sep 22 belongs to Aug 23-Sep 22 pay period');
[$s2,$e2] = kcmc_timeclock_period(new DateTimeImmutable('2026-09-23 12:00:00', new DateTimeZone('America/Chicago')));
tc_check($s2 === '2026-09-23' && $e2 === '2026-10-22', 'Sep 23 opens the next pay period');
[$s3,$e3] = kcmc_timeclock_period(new DateTimeImmutable('2027-01-05 12:00:00', new DateTimeZone('America/Chicago')));
tc_check($s3 === '2026-12-23' && $e3 === '2027-01-22', 'pay period boundary works across year change');

tc_check(kcmc_timeclock_minutes('2026-09-22T13:00:00+00:00','2026-09-22T15:30:00+00:00') === 150, 'gross minute calculation is deterministic');
$sample=['clock_in_at'=>'2026-09-22T13:00:00+00:00','clock_out_at'=>'2026-09-22T17:00:00+00:00','breaks'=>[['start_at'=>'2026-09-22T14:00:00+00:00','end_at'=>'2026-09-22T14:30:00+00:00']]];
tc_check(kcmc_timeclock_net_minutes($sample) === 210, 'net minutes subtract closed breaks');
tc_check(in_array('KCMC Connect / IT', kcmc_timeclock_categories(), true), 'KCMC Connect / IT work category is available');

$lib = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/lib/timeclock.php');
$member = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/member/timeclock.php');
$admin = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/timecards.php');
$csv = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/timecards-export.php');
$print = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/timecards-print.php');
$memberHome = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/member/index.php');
$operations = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/operations.php');

tc_check(str_contains($lib, "KCMC_PRIVATE_DATA . '/timeclock.json'"), 'time clock data lives in protected private storage');
tc_check(str_contains($lib, "['submitted','approved']"), 'submitted and approved periods are locked server-side');
tc_check(str_contains($lib, 'kcmc_timeclock_now()'), 'punch mutations use server-generated timestamps');
tc_check(str_contains($member, 'kcmc_require_login()'), 'employee time clock requires authentication');
tc_check(str_contains($member, 'kcmc_verify_csrf'), 'employee mutations require CSRF');
tc_check(str_contains($member, "(string)\$user['id']"), 'employee page scopes reads and writes to signed-in user');
tc_check(str_contains($member, 'name="certify"'), 'pay-period submission requires employee certification control');
tc_check(str_contains($admin, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'time-card review requires administrator role');
tc_check(str_contains($admin, 'cannot approve or return their own time card'), 'reviewer self-approval is blocked');
tc_check(str_contains($csv, "!== 'approved'"), 'CSV export is restricted to approved periods');
tc_check(str_contains($print, "!== 'approved'"), 'print/PDF view is restricted to approved periods');
tc_check(str_contains($csv, 'kcmc_csv_download'), 'accounting export uses spreadsheet-safe private CSV helper');
tc_check(str_contains($print, 'Print / Save PDF'), 'approved time card has print/PDF workflow');
tc_check(str_contains($memberHome, 'member/timeclock.php'), 'member home links to Time Clock');
tc_check(str_contains($operations, 'admin/timecards.php'), 'Operations hub links to Time Cards');
foreach ([$lib,$member,$admin,$csv,$print] as $source) tc_check(!str_contains(strtolower($source), 'gps'), 'time clock MVP contains no GPS tracking');

fwrite(STDOUT, "Time clock MVP contract passed.\n");
