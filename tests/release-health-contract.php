<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/release-health.php';

function health_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$now = strtotime('2026-09-22T20:00:00Z');
$invites = [
    'invites' => [
        ['email' => 'one@example.com', 'used_at' => null, 'expires_at' => '2026-09-23T20:00:00Z'],
        ['email' => 'two@example.com', 'used_at' => null, 'expires_at' => '2026-09-21T20:00:00Z'],
        ['email' => 'three@example.com', 'used_at' => 'revoked', 'expires_at' => '2026-09-24T20:00:00Z'],
        ['email' => 'four@example.com', 'used_at' => null, 'expires_at' => '2026-09-25T20:00:00Z'],
    ],
];
health_check(kcmc_health_pending_invite_count($invites, $now) === 2, 'only current unused invitations are counted');

$users = [
    'users' => [
        ['role' => 'member', 'active' => true],
        ['role' => 'prayer_team', 'active' => true],
        ['role' => 'pastor_admin', 'active' => true],
        ['role' => 'recovery_admin', 'active' => true],
        ['role' => 'member', 'active' => false],
    ],
];
$roles = kcmc_health_role_counts($users);
health_check($roles['active_total'] === 4, 'active account total is correct');
health_check($roles['disabled_total'] === 1, 'disabled account total is correct');
health_check($roles['pastor_admin'] === 1 && $roles['recovery_admin'] === 1, 'administrator role counts are correct');

$push = ['subscriptions' => [
    ['active' => true, 'endpoint' => 'https://push.example/1'],
    ['active' => false, 'endpoint' => 'https://push.example/2'],
    ['active' => true, 'endpoint' => 'https://push.example/3'],
]];
health_check(kcmc_health_active_push_count($push) === 2, 'only active push subscriptions are counted');

$item = kcmc_health_item('test', 'Test', 'unexpected', 'detail');
health_check($item['status'] === 'fail', 'unknown health status fails closed');

$page = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/health.php');
health_check(is_string($page), 'health dashboard source is readable');
health_check(str_contains($page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'dashboard requires an administrator role');
health_check(str_contains($page, 'kcmc_private_headers()'), 'dashboard uses private no-store headers');
health_check(str_contains($page, 'No passwords, tokens, invitation links, prayer content or private-key material'), 'dashboard states its privacy boundary');
health_check(!preg_match('/token_hash|password_hash|KCMC_PRAYERS|push_vapid_private_key_file/', $page), 'dashboard source does not read sensitive content fields');
health_check(str_contains($page, "admin/push.php") && str_contains($page, "admin/users.php") && str_contains($page, "admin/backup.php"), 'dashboard links to operational follow-up controls');

$member = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/index.php');
health_check(is_string($member) && str_contains($member, "admin/health.php"), 'administrator home links to release health');

echo "Release health contract checks passed.\n";
