<?php
declare(strict_types=1);

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';

function expect_same(mixed $expected, mixed $actual, string $message): void {
    if ($expected !== $actual) {
        fwrite(STDERR, "FAIL: {$message}\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true) . "\n");
        exit(1);
    }
}

$_SERVER['SCRIPT_NAME'] = '/kcmc-connect/member/login.php';
$_COOKIE = [];

expect_same(false, kcmc_session_cookie_present(), 'Anonymous public visits must not look authenticated.');
expect_same(null, kcmc_current_user_if_session(), 'Anonymous public visits must not start a member lookup.');
expect_same(PHP_SESSION_NONE, session_status(), 'Anonymous public visits must not create a PHP session.');

$announcements = [
    ['id' => 'backpack-blessing-2026', 'priority' => 200, 'status' => 'hidden'],
    ['id' => 'sep-news-16', 'priority' => 100, 'status' => 'published'],
    ['id' => 'lower-priority', 'priority' => 20, 'status' => 'published'],
];
expect_same(1, kcmc_featured_announcement_index($announcements), 'Publishing must skip retired announcements.');
$announcements[] = ['id' => 'owner-announcement', 'priority' => 10, 'status' => 'hidden'];
expect_same(3, kcmc_featured_announcement_index($announcements), 'The stable owner announcement must remain editable.');

$content = ['events' => []];
expect_same(true, kcmc_apply_required_public_content($content), 'Required public content must be added once.');
expect_same(false, kcmc_apply_required_public_content($content), 'Required public content migration must be idempotent.');

expect_same('/kcmc-connect/admin/', kcmc_safe_next('/kcmc-connect/admin/'), 'Local redirects must remain available.');
expect_same('/kcmc-connect/member/', kcmc_safe_next('https://example.com/steal'), 'External redirects must be rejected.');

$safeAudit = kcmc_sanitize_audit_context([
    'role' => 'member',
    'message' => 'private prayer',
    'nested' => ['token_hash' => 'secret', 'action' => 'approved'],
]);
expect_same(['role' => 'member', 'nested' => ['action' => 'approved']], $safeAudit, 'Audit context must remove sensitive fields recursively.');

expect_same(false, kcmc_can_view_private_prayers(['role' => 'recovery_admin']), 'Recovery administrators must not read prayer content.');
expect_same(true, kcmc_can_view_private_prayers(['role' => 'pastor_admin']), 'Pastor administrators must retain prayer access.');

echo "KCMC PHP behavior checks passed.\n";
