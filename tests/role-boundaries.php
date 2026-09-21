<?php
declare(strict_types=1);

/**
 * Static authorization regression checks for KCMC's role boundaries.
 *
 * These checks intentionally avoid real prayer data. They verify that route
 * guards remain explicit so a recovery administrator cannot enter confidential
 * prayer workflows while member/prayer/pastor access stays distinct.
 */
$root = dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated';
$bootstrap = file_get_contents($root . '/lib/bootstrap.php');
$users = file_get_contents($root . '/admin/users.php');
$admin = file_get_contents($root . '/admin/index.php');
$prayers = file_get_contents($root . '/admin/prayers.php');
$team = file_get_contents($root . '/member/prayer-team.php');
$submit = file_get_contents($root . '/member/submit-prayer.php');
$member = file_get_contents($root . '/member/index.php');

function verify(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: {$message}\n");
        exit(1);
    }
    echo "PASS: {$message}\n";
}

foreach (['bootstrap' => $bootstrap, 'users' => $users, 'admin' => $admin, 'prayers' => $prayers, 'team' => $team, 'submit' => $submit, 'member' => $member] as $name => $content) {
    verify(is_string($content), "{$name} route source is readable");
}

verify(str_contains($bootstrap, 'function kcmc_require_role(array $roles)'), 'central role guard exists');
verify(str_contains($bootstrap, 'http_response_code(403)'), 'central role guard returns HTTP 403 for unauthorized roles');
verify(str_contains($admin, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'publishing desk is limited to pastor/recovery administrators');
verify(str_contains($users, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'member administration is limited to pastor/recovery administrators');
verify(str_contains($prayers, "kcmc_require_role(['pastor_admin'])"), 'private prayer administration is pastor-only');
verify(str_contains($team, "kcmc_require_role(['prayer_team', 'pastor_admin'])"), 'confidential prayer-team inbox excludes recovery administrators');
verify(str_contains($submit, "kcmc_require_role(['member', 'prayer_team', 'pastor_admin'])"), 'prayer submission excludes recovery administrators');
verify(str_contains($member, "kcmc_has_role(['member', 'prayer_team', 'pastor_admin'], \$user)"), 'member prayer-wall access excludes recovery administrators');
verify(str_contains($users, "if (kcmc_role(\$current) === 'recovery_admin') \$allowed[] = 'recovery_admin';"), 'only recovery administrators can invite another recovery administrator');
verify(str_contains($users, "kcmc_role(\$target) === 'pastor_admin' && kcmc_role(\$current) !== 'recovery_admin'"), 'pastor administrator disablement requires recovery administrator');
verify(str_contains($users, "kcmc_role(\$target) === 'recovery_admin' && kcmc_role(\$current) !== 'recovery_admin'"), 'recovery administrator account changes require recovery administrator');

// The recovery role must never be granted access by broadening a prayer route.
verify(!str_contains($prayers, "['pastor_admin', 'recovery_admin']"), 'private prayer administration does not include recovery administrator');
verify(!str_contains($team, "['prayer_team', 'pastor_admin', 'recovery_admin']"), 'prayer-team inbox does not include recovery administrator');
verify(!str_contains($submit, "['member', 'prayer_team', 'pastor_admin', 'recovery_admin']"), 'prayer submission does not include recovery administrator');

echo "All role-boundary contract checks passed.\n";
