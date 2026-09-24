<?php
declare(strict_types=1);

function push_self_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$page = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/push.php');
push_self_check(is_string($page), 'push administration page is readable');
push_self_check(str_contains((string)$page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'push page remains administrator-only');
push_self_check(str_contains((string)$page, 'kcmc_private_headers()'), 'push page remains private/no-store');
push_self_check(str_contains((string)$page, 'kcmc_verify_csrf'), 'push sends remain CSRF protected');
push_self_check(str_contains((string)$page, "in_array(\$scope, ['self', 'broadcast'], true)"), 'push page accepts only self-test and broadcast scopes');
push_self_check(str_contains((string)$page, "(string)(\$subscription['user_id'] ?? '') === \$currentUserId"), 'self-test subscriptions are bound to the signed-in account ID');
push_self_check(str_contains((string)$page, "array_slice(\$mySubscriptions, 0, 5)"), 'self-test is bounded to five signed-in-account devices');
push_self_check(str_contains((string)$page, "array_slice(\$allSubscriptions, 0, 200)"), 'broadcast retains the 200-subscription bound');
push_self_check(str_contains((string)$page, "time() - (int)\$_SESSION['push_last_send_at'] < 30"), 'self-test and broadcast share the 30-second send guard');
push_self_check(str_contains((string)$page, "(string)(\$_POST['confirm_send'] ?? '') !== '1'"), 'both push actions require explicit confirmation');
push_self_check(str_contains((string)$page, 'kcmc_push_send_empty($subscription)'), 'self-test reuses the existing payloadless VAPID sender');
push_self_check(str_contains((string)$page, "kcmc_push_deactivate_endpoint((string)\$subscription['endpoint'], 'gone')"), 'expired self-test endpoints use the established deactivation path');
push_self_check(str_contains((string)$page, "push.self_test_attempted"), 'self-test emits a distinct audit event');
push_self_check(str_contains((string)$page, "push.broadcast_attempted"), 'broadcast audit event remains intact');
push_self_check(str_contains((string)$page, 'Test my subscribed device'), 'UI offers signed-in-device verification before broadcast');
push_self_check(str_contains((string)$page, 'Final mobile acceptance'), 'UI gives the owner an explicit final mobile acceptance checklist');
push_self_check(str_contains((string)$page, 'No broadcast is required for acceptance.'), 'release acceptance does not require a church-wide broadcast');
push_self_check(str_contains((string)$page, 'background delivery or notification tap behavior'), 'UI states the real-device-only verification boundary');
push_self_check(str_contains((string)$page, 'send_scope" value="self"'), 'self-test form posts the self scope explicitly');
push_self_check(str_contains((string)$page, 'send_scope" value="broadcast"'), 'broadcast form posts the broadcast scope explicitly');
push_self_check(str_contains((string)$page, 'Signed-in account subscriptions:'), 'UI reports only a count for signed-in-account subscriptions');
push_self_check(!str_contains((string)$page, 'p256dh') && !str_contains((string)$page, "['auth']"), 'push page does not render subscription cryptographic key material');
echo "Push self-test contract checks passed.\n";
