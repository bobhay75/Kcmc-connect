<?php
declare(strict_types=1);

const KCMC_PUSH_SUBSCRIPTIONS = KCMC_PRIVATE_DATA . '/push-subscriptions.json';

function kcmc_push_b64url(string $value): string {
    return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
}

function kcmc_push_public_key(): string {
    $cfg = kcmc_config();
    $configured = trim((string)($cfg['push_vapid_public_key'] ?? ''));
    $env = getenv('KCMC_PUSH_VAPID_PUBLIC_KEY');
    if (is_string($env) && trim($env) !== '') $configured = trim($env);
    return preg_match('/\A[A-Za-z0-9_-]{80,120}\z/', $configured) ? $configured : '';
}

function kcmc_push_subject(): string {
    $cfg = kcmc_config();
    $subject = trim((string)($cfg['push_vapid_subject'] ?? ''));
    $env = getenv('KCMC_PUSH_VAPID_SUBJECT');
    if (is_string($env) && trim($env) !== '') $subject = trim($env);
    if (strlen($subject) > 300) return '';
    if (str_starts_with($subject, 'mailto:')) {
        return filter_var(substr($subject, 7), FILTER_VALIDATE_EMAIL) ? $subject : '';
    }
    if (!filter_var($subject, FILTER_VALIDATE_URL)) return '';
    $parts = parse_url($subject);
    return is_array($parts) && ($parts['scheme'] ?? '') === 'https' && !empty($parts['host']) ? $subject : '';
}

function kcmc_push_private_key_file(): string {
    $cfg = kcmc_config();
    $path = trim((string)($cfg['push_vapid_private_key_file'] ?? ''));
    $env = getenv('KCMC_PUSH_VAPID_PRIVATE_KEY_FILE');
    if (is_string($env) && trim($env) !== '') $path = trim($env);
    if ($path === '') return '';
    $real = realpath($path);
    if ($real === false || !is_file($real) || !is_readable($real)) return '';
    $root = realpath(KCMC_ROOT);
    if ($root !== false && ($real === $root || str_starts_with($real, $root . DIRECTORY_SEPARATOR))) return '';
    return $real;
}

function kcmc_push_key_material(): ?array {
    $public = kcmc_push_public_key();
    $file = kcmc_push_private_key_file();
    if ($public === '' || $file === '') return null;
    $pem = @file_get_contents($file);
    if (!is_string($pem) || $pem === '') return null;
    $key = @openssl_pkey_get_private($pem);
    if ($key === false) return null;
    $details = openssl_pkey_get_details($key);
    if (!is_array($details) || ($details['type'] ?? null) !== OPENSSL_KEYTYPE_EC) return null;
    $ec = $details['ec'] ?? null;
    if (!is_array($ec) || !in_array((string)($ec['curve_name'] ?? ''), ['prime256v1', 'secp256r1'], true)) return null;
    $x = $ec['x'] ?? null;
    $y = $ec['y'] ?? null;
    if (!is_string($x) || !is_string($y) || strlen($x) > 32 || strlen($y) > 32) return null;
    $derived = kcmc_push_b64url("\x04" . str_pad($x, 32, "\0", STR_PAD_LEFT) . str_pad($y, 32, "\0", STR_PAD_LEFT));
    if (!hash_equals($public, $derived)) return null;
    return ['private' => $key, 'public' => $public];
}

function kcmc_push_enabled(): bool {
    return kcmc_push_public_key() !== '';
}

function kcmc_push_delivery_ready(): bool {
    return function_exists('curl_init') && function_exists('openssl_sign') && kcmc_push_subject() !== '' && kcmc_push_key_material() !== null;
}

function kcmc_push_validate_subscription(array $payload): ?array {
    $endpoint = trim((string)($payload['endpoint'] ?? ''));
    $keys = $payload['keys'] ?? null;
    $p256dh = is_array($keys) ? trim((string)($keys['p256dh'] ?? '')) : '';
    $auth = is_array($keys) ? trim((string)($keys['auth'] ?? '')) : '';
    if ($endpoint === '' || strlen($endpoint) > 2048 || !filter_var($endpoint, FILTER_VALIDATE_URL)) return null;
    $parts = parse_url($endpoint);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || empty($parts['host']) || isset($parts['user']) || isset($parts['pass'])) return null;
    if (isset($parts['port']) && (int)$parts['port'] !== 443) return null;
    if (!preg_match('/\A[A-Za-z0-9_-]{40,200}\z/', $p256dh)) return null;
    if (!preg_match('/\A[A-Za-z0-9_-]{12,80}\z/', $auth)) return null;
    return ['endpoint' => $endpoint, 'keys' => ['p256dh' => $p256dh, 'auth' => $auth]];
}

function kcmc_push_save_subscription(string $userId, array $payload): bool {
    $subscription = kcmc_push_validate_subscription($payload);
    if ($userId === '' || $subscription === null) return false;
    return (bool)kcmc_update_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []], function (array &$state) use ($userId, $subscription): bool {
        if (!isset($state['subscriptions']) || !is_array($state['subscriptions'])) $state['subscriptions'] = [];
        $now = gmdate('c');
        foreach ($state['subscriptions'] as &$stored) {
            if (!is_array($stored) || ($stored['endpoint'] ?? '') !== $subscription['endpoint']) continue;
            $stored = array_merge($stored, $subscription, ['user_id' => $userId, 'active' => true, 'updated_at' => $now]);
            unset($stored);
            return true;
        }
        unset($stored);
        $state['subscriptions'][] = $subscription + [
            'user_id' => $userId,
            'active' => true,
            'created_at' => $now,
            'updated_at' => $now,
        ];
        return true;
    });
}

function kcmc_push_remove_subscription(string $userId, string $endpoint): bool {
    $endpoint = trim($endpoint);
    if ($userId === '' || $endpoint === '' || strlen($endpoint) > 2048) return false;
    return (bool)kcmc_update_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []], function (array &$state) use ($userId, $endpoint): bool {
        if (!isset($state['subscriptions']) || !is_array($state['subscriptions'])) return false;
        $changed = false;
        foreach ($state['subscriptions'] as &$stored) {
            if (!is_array($stored) || ($stored['user_id'] ?? '') !== $userId || ($stored['endpoint'] ?? '') !== $endpoint || empty($stored['active'])) continue;
            $stored['active'] = false;
            $stored['updated_at'] = gmdate('c');
            $stored['revoked_at'] = gmdate('c');
            $changed = true;
        }
        unset($stored);
        return $changed;
    });
}

function kcmc_push_deactivate_endpoint(string $endpoint, string $reason): bool {
    $reason = in_array($reason, ['expired', 'gone', 'invalid'], true) ? $reason : 'invalid';
    return (bool)kcmc_update_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []], function (array &$state) use ($endpoint, $reason): bool {
        if (!isset($state['subscriptions']) || !is_array($state['subscriptions'])) return false;
        $changed = false;
        foreach ($state['subscriptions'] as &$stored) {
            if (!is_array($stored) || ($stored['endpoint'] ?? '') !== $endpoint || empty($stored['active'])) continue;
            $stored['active'] = false;
            $stored['updated_at'] = gmdate('c');
            $stored['revoked_at'] = gmdate('c');
            $stored['revoke_reason'] = $reason;
            $changed = true;
        }
        unset($stored);
        return $changed;
    });
}

function kcmc_push_active_for_user(string $userId): int {
    if ($userId === '') return 0;
    $state = kcmc_read_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]);
    $count = 0;
    foreach (($state['subscriptions'] ?? []) as $stored) {
        if (is_array($stored) && ($stored['user_id'] ?? '') === $userId && !empty($stored['active'])) $count++;
    }
    return $count;
}

function kcmc_push_active_subscriptions(): array {
    $state = kcmc_read_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]);
    return array_values(array_filter($state['subscriptions'] ?? [], static function ($stored): bool {
        return is_array($stored) && !empty($stored['active']) && kcmc_push_validate_subscription($stored) !== null;
    }));
}

function kcmc_push_der_length(string $der, int &$offset): ?int {
    if ($offset >= strlen($der)) return null;
    $first = ord($der[$offset++]);
    if (($first & 0x80) === 0) return $first;
    $bytes = $first & 0x7f;
    if ($bytes < 1 || $bytes > 4 || $offset + $bytes > strlen($der)) return null;
    $length = 0;
    for ($i = 0; $i < $bytes; $i++) $length = ($length << 8) | ord($der[$offset++]);
    return $length;
}

function kcmc_push_der_to_jose(string $der): ?string {
    $offset = 0;
    if (($der[$offset++] ?? '') !== "\x30") return null;
    $seqLength = kcmc_push_der_length($der, $offset);
    if ($seqLength === null || $offset + $seqLength !== strlen($der) || ($der[$offset++] ?? '') !== "\x02") return null;
    $rLength = kcmc_push_der_length($der, $offset);
    if ($rLength === null || $rLength < 1 || $offset + $rLength > strlen($der)) return null;
    $r = substr($der, $offset, $rLength); $offset += $rLength;
    if (($der[$offset++] ?? '') !== "\x02") return null;
    $sLength = kcmc_push_der_length($der, $offset);
    if ($sLength === null || $sLength < 1 || $offset + $sLength !== strlen($der)) return null;
    $s = substr($der, $offset, $sLength);
    $r = ltrim($r, "\0"); $s = ltrim($s, "\0");
    if ($r === '' || $s === '' || strlen($r) > 32 || strlen($s) > 32) return null;
    return str_pad($r, 32, "\0", STR_PAD_LEFT) . str_pad($s, 32, "\0", STR_PAD_LEFT);
}

function kcmc_push_vapid_token(string $endpoint, ?int $now = null): ?string {
    $parts = parse_url($endpoint);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || empty($parts['host'])) return null;
    $port = isset($parts['port']) ? (int)$parts['port'] : 443;
    if ($port !== 443) return null;
    $material = kcmc_push_key_material();
    $subject = kcmc_push_subject();
    if ($material === null || $subject === '') return null;
    $audience = 'https://' . $parts['host'];
    $issued = $now ?? time();
    $header = kcmc_push_b64url((string)json_encode(['typ' => 'JWT', 'alg' => 'ES256'], JSON_UNESCAPED_SLASHES));
    $claims = kcmc_push_b64url((string)json_encode(['aud' => $audience, 'exp' => $issued + 43200, 'sub' => $subject], JSON_UNESCAPED_SLASHES));
    $input = $header . '.' . $claims;
    $der = '';
    if (!openssl_sign($input, $der, $material['private'], OPENSSL_ALGO_SHA256)) return null;
    $raw = kcmc_push_der_to_jose($der);
    return $raw === null ? null : $input . '.' . kcmc_push_b64url($raw);
}

function kcmc_push_public_ipv4(string $host): string {
    if (filter_var($host, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
        return filter_var($host, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4 | FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) ? $host : '';
    }
    $addresses = @gethostbynamel($host);
    if (!is_array($addresses)) return '';
    foreach ($addresses as $address) {
        if (filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4 | FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) return $address;
    }
    return '';
}

function kcmc_push_send_empty(array $stored, ?callable $transport = null, ?int $now = null): array {
    $subscription = kcmc_push_validate_subscription($stored);
    if ($subscription === null || !kcmc_push_delivery_ready()) return ['sent' => false, 'expired' => false, 'status' => 0, 'reason' => 'not_ready'];
    $endpoint = $subscription['endpoint'];
    $parts = parse_url($endpoint);
    $host = is_array($parts) ? (string)($parts['host'] ?? '') : '';
    $ip = $host !== '' ? kcmc_push_public_ipv4($host) : '';
    if ($ip === '') return ['sent' => false, 'expired' => false, 'status' => 0, 'reason' => 'unresolvable_endpoint'];
    $jwt = kcmc_push_vapid_token($endpoint, $now);
    if ($jwt === null) return ['sent' => false, 'expired' => false, 'status' => 0, 'reason' => 'vapid_failed'];
    $headers = [
        'TTL: 300',
        'Urgency: normal',
        'Content-Length: 0',
        'Authorization: vapid t=' . $jwt . ', k=' . kcmc_push_public_key(),
    ];
    $request = ['url' => $endpoint, 'headers' => $headers, 'resolve' => $host . ':443:' . $ip];
    if ($transport !== null) {
        $result = $transport($request);
        $status = is_array($result) ? (int)($result['status'] ?? 0) : 0;
        $error = is_array($result) ? (string)($result['error'] ?? '') : 'transport_failed';
    } else {
        $ch = curl_init($endpoint);
        if ($ch === false) return ['sent' => false, 'expired' => false, 'status' => 0, 'reason' => 'curl_init_failed'];
        $options = [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => '',
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => 10,
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_MAXREDIRS => 0,
            CURLOPT_USERAGENT => 'KCMC-Connect-WebPush/1.0',
            CURLOPT_RESOLVE => [$request['resolve']],
        ];
        if (defined('CURLOPT_PROTOCOLS') && defined('CURLPROTO_HTTPS')) $options[CURLOPT_PROTOCOLS] = CURLPROTO_HTTPS;
        curl_setopt_array($ch, $options);
        curl_exec($ch);
        $error = curl_error($ch);
        $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        curl_close($ch);
    }
    $sent = in_array($status, [201, 202], true);
    $expired = in_array($status, [404, 410], true);
    return ['sent' => $sent, 'expired' => $expired, 'status' => $status, 'reason' => $sent ? '' : ($error !== '' ? 'transport_error' : 'http_' . $status)];
}
