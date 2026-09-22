<?php
declare(strict_types=1);
$private = sys_get_temp_dir() . '/kcmc-push-delivery-' . bin2hex(random_bytes(4));
if (!mkdir($private, 0700, true) && !is_dir($private)) throw new RuntimeException('Could not create temp directory');
putenv('KCMC_PRIVATE_DATA_DIR=' . $private . '/data');
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/push-subscriptions.php';

function delivery_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
    echo "PASS: $message\n";
}
function b64url_decode_test(string $value): string|false {
    $padding = str_repeat('=', (4 - strlen($value) % 4) % 4);
    return base64_decode(strtr($value . $padding, '-_', '+/'), true);
}

$key = openssl_pkey_new(['private_key_type' => OPENSSL_KEYTYPE_EC, 'curve_name' => 'prime256v1']);
delivery_check($key !== false, 'temporary P-256 VAPID key generated');
$pem = '';
delivery_check(openssl_pkey_export($key, $pem), 'temporary VAPID private key exported');
$keyFile = $private . '/vapid-private.pem';
file_put_contents($keyFile, $pem);
chmod($keyFile, 0600);
$details = openssl_pkey_get_details($key);
delivery_check(is_array($details) && isset($details['ec']['x'], $details['ec']['y']), 'OpenSSL exposes P-256 public coordinates');
$x = (string)$details['ec']['x'];
$y = (string)$details['ec']['y'];
$public = kcmc_push_b64url("\x04" . str_pad($x, 32, "\0", STR_PAD_LEFT) . str_pad($y, 32, "\0", STR_PAD_LEFT));
putenv('KCMC_PUSH_VAPID_PUBLIC_KEY=' . $public);
putenv('KCMC_PUSH_VAPID_PRIVATE_KEY_FILE=' . $keyFile);
putenv('KCMC_PUSH_VAPID_SUBJECT=mailto:push@example.com');

delivery_check(kcmc_push_key_material() !== null, 'configured public and private VAPID keys match');
delivery_check(kcmc_push_subject() === 'mailto:push@example.com', 'VAPID subject validated');
$now = 1700000000;
$endpoint = 'https://example.com/push/test';
$jwt = kcmc_push_vapid_token($endpoint, $now);
delivery_check(is_string($jwt) && substr_count($jwt, '.') === 2, 'ES256 VAPID JWT created');
$parts = explode('.', (string)$jwt);
$claimsRaw = b64url_decode_test($parts[1]);
$signatureRaw = b64url_decode_test($parts[2]);
$claims = is_string($claimsRaw) ? json_decode($claimsRaw, true) : null;
delivery_check(is_array($claims) && ($claims['aud'] ?? '') === 'https://example.com', 'VAPID audience is push endpoint origin');
delivery_check(($claims['exp'] ?? 0) === $now + 43200, 'VAPID expiry is twelve hours');
delivery_check(($claims['sub'] ?? '') === 'mailto:push@example.com', 'VAPID subject included');
delivery_check(is_string($signatureRaw) && strlen($signatureRaw) === 64, 'ES256 signature is JOSE 64-byte R||S form');

$subscription = [
    'endpoint' => $endpoint,
    'keys' => ['p256dh' => str_repeat('B', 88), 'auth' => str_repeat('C', 24)],
    'active' => true,
];
$captured = null;
$sent = kcmc_push_send_empty($subscription, function (array $request) use (&$captured): array {
    $captured = $request;
    return ['status' => 201, 'error' => ''];
}, $now);
delivery_check(!empty($sent['sent']) && empty($sent['expired']), 'HTTP 201 is accepted as successful push handoff');
delivery_check(is_array($captured) && in_array('TTL: 300', $captured['headers'] ?? [], true), 'push request includes mandatory TTL');
$authHeader = '';
foreach (($captured['headers'] ?? []) as $header) if (str_starts_with($header, 'Authorization: vapid ')) $authHeader = $header;
delivery_check(str_contains($authHeader, 't=') && str_contains($authHeader, 'k=' . $public), 'push request carries VAPID token and public key');
$gone = kcmc_push_send_empty($subscription, fn(array $request): array => ['status' => 410, 'error' => ''], $now);
delivery_check(empty($gone['sent']) && !empty($gone['expired']), 'HTTP 410 marks a subscription expired');
putenv('KCMC_PUSH_VAPID_PUBLIC_KEY=' . str_repeat('A', 87));
delivery_check(kcmc_push_key_material() === null, 'mismatched VAPID public/private keys fail closed');

@unlink($keyFile);
@unlink($private . '/data/push-subscriptions.json');
@unlink($private . '/data/push-subscriptions.json.lock');
@rmdir($private . '/data');
@rmdir($private);
echo "Push delivery PHP contract checks passed.\n";
