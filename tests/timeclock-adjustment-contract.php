<?php
declare(strict_types=1);
$root = dirname(__DIR__);
require_once $root . '/KCMC-Connect-Phase6-Recreated/lib/timeclock.php';

function tca_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
    fwrite(STDOUT, "PASS: $message\n");
}

tca_check(kcmc_timeclock_hours_to_minutes('0') === 0, 'zero-hour adjustment is valid');
tca_check(kcmc_timeclock_hours_to_minutes('1.25') === 75, 'decimal hours convert to minutes');
tca_check(kcmc_timeclock_hours_to_minutes('24') === 1440, '24-hour upper bound is valid');
tca_check(kcmc_timeclock_hours_to_minutes('-1') === null, 'negative hours are rejected');
tca_check(kcmc_timeclock_hours_to_minutes('24.01') === null, 'hours above 24 are rejected');
tca_check(kcmc_timeclock_hours_to_minutes('abc') === null, 'non-numeric hours are rejected');

$lib = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/lib/timeclock.php');
$admin = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/timecards.php');
$member = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/member/timeclock.php');

foreach ([$lib,$admin,$member] as $source) tca_check(is_string($source), 'time-clock adjustment source is readable');
tca_check(str_contains($lib, "'adjustments'=>[]"), 'private time-clock store includes immutable adjustment collection');
tca_check(str_contains($lib, 'previous_net_minutes'), 'adjustment history preserves previous minutes');
tca_check(str_contains($lib, 'new_net_minutes'), 'adjustment history preserves corrected minutes');
tca_check(str_contains($lib, "'reason'=>\$reason"), 'adjustment history stores required private reason');
tca_check(str_contains($lib, "'adjusted_by'=>\$reviewerId"), 'adjustment history records supervisor identity');
tca_check(str_contains($lib, 'A reviewer cannot adjust their own time entry.'), 'supervisor cannot adjust own time');
tca_check(str_contains($lib, 'Approved time is locked.'), 'approved time cannot be adjusted');
tca_check(str_contains($lib, "(\$entry['status']??'')==='open'"), 'open shifts cannot be adjusted');
tca_check(str_contains($lib, "\$s['adjustments'][]=\$record"), 'adjustment history is append-only');
tca_check(str_contains($admin, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'adjustment UI remains administrator-only');
tca_check(str_contains($admin, 'kcmc_verify_csrf'), 'adjustment POST requires CSRF');
tca_check(str_contains($admin, "'timeclock.entry_adjusted'"), 'adjustment emits privacy-safe audit event');
tca_check(str_contains($admin, 'Save adjustment'), 'administrator has explicit adjustment control');
tca_check(str_contains($admin, '>Reason<'), 'administrator must supply adjustment reason');
tca_check(str_contains($member, 'Supervisor adjusted'), 'employee can see that a shift was adjusted');
tca_check(!str_contains($admin, "kcmc_audit('timeclock.entry_adjusted', ['reason'"), 'private reason is not copied into audit context');

fwrite(STDOUT, "Time clock adjustment contract passed.\n");
