<?php
declare(strict_types=1);
$private = sys_get_temp_dir() . '/kcmc-push-' . bin2hex(random_bytes(4));
putenv('KCMC_PRIVATE_DATA_DIR=' . $private);
putenv('KCMC_PUSH_VAPID_PUBLIC_KEY=' . str_repeat('A', 87));
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/push-subscriptions.php';

function check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
    echo "PASS: $message\n";
}

check(kcmc_push_enabled(), 'push is enabled only with a valid configured public key');
$payload = [
    'endpoint' => 'https://push.example.invalid/send/abc123',
    'keys' => [
        'p256dh' => str_repeat('B', 88),
        'auth' => str_repeat('C', 24),
    ],
];
check(kcmc_push_validate_subscription($payload) !== null, 'well-formed HTTPS subscription accepted');
check(kcmc_push_save_subscription('usr_test', $payload), 'valid subscription stored');
check(kcmc_push_active_for_user('usr_test') === 1, 'stored subscription counted for owning user');
check(kcmc_push_active_for_user('usr_other') === 0, 'subscription is user-bound');
check(!kcmc_push_remove_subscription('usr_other', $payload['endpoint']), 'other user cannot revoke subscription');
check(kcmc_push_remove_subscription('usr_test', $payload['endpoint']), 'own subscription can be revoked');
check(kcmc_push_active_for_user('usr_test') === 0, 'revoked subscription is inactive');
$bad = $payload; $bad['endpoint'] = 'http://push.example.invalid/send/abc123';
check(kcmc_push_validate_subscription($bad) === null, 'non-HTTPS push endpoint rejected');
$bad = $payload; $bad['keys']['auth'] = "bad\nvalue";
check(kcmc_push_validate_subscription($bad) === null, 'malformed key material rejected');
@unlink($private . '/push-subscriptions.json');
@unlink($private . '/push-subscriptions.json.lock');
@rmdir($private);
echo "Push subscription PHP contract checks passed.\n";
