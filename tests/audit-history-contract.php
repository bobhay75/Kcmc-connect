<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/audit-history.php';

function audit_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$actors = kcmc_audit_actor_names(['users' => [
    ['id' => 'u1', 'display_name' => 'Pastor One', 'email' => 'hidden@example.com'],
    ['id' => 'u2', 'display_name' => 'Admin Two', 'email' => 'also-hidden@example.com'],
]]);
audit_check(($actors['u1'] ?? '') === 'Pastor One' && ($actors['system'] ?? '') === 'System', 'actor map uses display names and system label');

$visible = kcmc_audit_visible_context([
    'role' => 'pastor_admin',
    'sent' => 2,
    'password' => 'secret',
    'token_hash' => 'secret-hash',
    'endpoint_hash' => 'endpoint-hash',
    'prayer_id' => 'prayer-secret-id',
]);
audit_check(($visible['role'] ?? '') === 'pastor_admin' && ($visible['sent'] ?? '') === '2', 'allow-listed operational context is retained');
audit_check(!isset($visible['password'], $visible['token_hash'], $visible['endpoint_hash'], $visible['prayer_id']), 'sensitive and internal identifiers are excluded from visible context');

$tmp = tempnam(sys_get_temp_dir(), 'kcmc-audit-');
if ($tmp === false) { fwrite(STDERR, "FAIL: could not create temp audit file\n"); exit(1); }
$records = [
    ['at' => '2026-09-22T18:00:00Z', 'action' => 'auth.login', 'actor_id' => 'u1', 'ip_hash' => 'hidden-ip', 'context' => ['role' => 'pastor_admin']],
    ['at' => '2026-09-22T18:05:00Z', 'action' => 'member.invited', 'actor_id' => 'u2', 'ip_hash' => 'hidden-ip-2', 'context' => ['role' => 'member', 'invite_id' => 'hidden-invite']],
    ['at' => '2026-09-22T18:10:00Z', 'action' => 'push.broadcast_attempted', 'actor_id' => 'u2', 'context' => ['sent' => 3, 'expired' => 1, 'failed' => 0]],
];
file_put_contents($tmp, "not-json\n" . implode("\n", array_map(fn($r) => json_encode($r, JSON_UNESCAPED_SLASHES), $records)) . "\n");
$rows = kcmc_audit_recent_rows($tmp, $actors, 2);
audit_check(count($rows) === 2, 'requested audit row limit is enforced');
audit_check(($rows[0]['action'] ?? '') === 'push.broadcast_attempted', 'newest audit event is displayed first');
audit_check(($rows[1]['actor'] ?? '') === 'Admin Two', 'actor ID resolves to display name');
audit_check(!array_key_exists('ip_hash', $rows[0]), 'IP hashes are absent from returned rows');
audit_check(!isset($rows[1]['context']['invite_id']), 'internal invitation identifiers are omitted');
@unlink($tmp);

audit_check(kcmc_audit_event_label('content.published') === 'Public content published', 'known events receive friendly labels');
audit_check(kcmc_audit_event_label('custom.event_name') === 'Custom Event Name', 'unknown events receive readable fallback labels');

$page = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/audit.php');
audit_check(is_string($page), 'audit page source is readable');
audit_check(str_contains($page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'audit page requires an administrator role');
audit_check(str_contains($page, 'kcmc_private_headers()'), 'audit page uses private no-store headers');
audit_check(str_contains($page, 'kcmc_audit_recent_rows(KCMC_AUDIT_LOG'), 'audit page reads only through bounded audit helper');
audit_check(!preg_match('/ip_hash|password_hash|token_hash|KCMC_PRAYERS|push-subscriptions\.json/', $page), 'audit page source does not expose sensitive raw fields or private stores');

$member = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/index.php');
audit_check(is_string($member) && str_contains($member, 'admin/audit.php'), 'administrator home links to audit history');

echo "Audit history contract checks passed.\n";
