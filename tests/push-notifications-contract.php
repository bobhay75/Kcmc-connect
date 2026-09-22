<?php
declare(strict_types=1);

$tmp = sys_get_temp_dir() . '/kcmc-push-' . bin2hex(random_bytes(6));
putenv('KCMC_PRIVATE_DATA_DIR=' . $tmp);
$_SERVER['SCRIPT_NAME'] = '/kcmc-connect/member/notifications.php';

require dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated/lib/push.php';

function verify_push(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: {$message}\n");
        exit(1);
    }
}

try {
    $vapid = kcmc_push_get_vapid(true);
    verify_push(is_array($vapid) && kcmc_push_valid_vapid($vapid), 'VAPID keypair was not generated.');
    verify_push(is_file(KCMC_PUSH_VAPID), 'VAPID keypair was not persisted in private storage.');
    $publicRaw = kcmc_push_b64url_decode((string)$vapid['public_key']);
    verify_push(is_string($publicRaw) && strlen($publicRaw) === 65 && ord($publicRaw[0]) === 4, 'VAPID public key is not an uncompressed P-256 point.');

    $jwt = kcmc_push_vapid_jwt('https://fcm.googleapis.com', $vapid, 1700000000);
    $parts = explode('.', $jwt);
    verify_push(count($parts) === 3, 'VAPID JWT is malformed.');
    $signature = kcmc_push_b64url_decode($parts[2]);
    verify_push(is_string($signature) && strlen($signature) === 64, 'VAPID JWT does not contain a raw ES256 signature.');

    verify_push(kcmc_push_endpoint_allowed('https://fcm.googleapis.com/fcm/send/example'), 'FCM endpoint should be accepted.');
    verify_push(kcmc_push_endpoint_allowed('https://updates.push.services.mozilla.com/wpush/v2/example'), 'Mozilla endpoint should be accepted.');
    verify_push(kcmc_push_endpoint_allowed('https://web.push.apple.com/Q/example'), 'Apple endpoint should be accepted.');
    verify_push(!kcmc_push_endpoint_allowed('https://example.com/push'), 'Arbitrary HTTPS endpoint must be rejected to prevent SSRF.');
    verify_push(!kcmc_push_endpoint_allowed('http://fcm.googleapis.com/fcm/send/example'), 'Non-HTTPS push endpoint must be rejected.');

    $subscription = [
        'endpoint' => 'https://fcm.googleapis.com/fcm/send/test-endpoint',
        'keys' => [
            'p256dh' => kcmc_push_b64url_encode("\x04" . str_repeat("\x01", 64)),
            'auth' => kcmc_push_b64url_encode(str_repeat("\x02", 16)),
        ],
    ];
    $user = ['id' => 'usr_test'];
    verify_push(kcmc_push_save_subscription($subscription, $user), 'Valid subscription was not saved.');
    verify_push(kcmc_push_subscription_count() === 1, 'Saved subscription is not counted.');
    $stored = kcmc_read_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]);
    verify_push(($stored['subscriptions'][0]['user_id'] ?? '') === 'usr_test', 'Subscription is not bound to the authenticated user.');

    $notice = kcmc_push_save_notice('Sunday update', 'Worship begins at the usual times this Sunday.', './#events', 'usr_admin');
    verify_push(($notice['target'] ?? '') === './#events', 'Same-app notification target was not saved.');
    $publicNotice = kcmc_push_public_notice();
    verify_push(is_array($publicNotice) && ($publicNotice['title'] ?? '') === 'Sunday update', 'Public notice could not be read.');
    verify_push(!array_key_exists('created_by', $publicNotice), 'Public notice leaked the administrator identifier.');
    verify_push(!array_key_exists('private_key_pem', $publicNotice), 'Public notice leaked VAPID key material.');

    verify_push(kcmc_push_remove_subscription($subscription['endpoint'], $user), 'Subscription could not be removed by its owner.');
    verify_push(kcmc_push_subscription_count() === 0, 'Removed subscription remains active.');

    echo "KCMC Web Push contract checks passed.\n";
} finally {
    if (is_dir($tmp)) {
        $files = array_reverse(glob($tmp . '/*') ?: []);
        foreach ($files as $file) @unlink($file);
        @rmdir($tmp);
    }
}
