<?php
declare(strict_types=1);

if (!defined('KCMC_PUSH_SUBSCRIPTIONS')) define('KCMC_PUSH_SUBSCRIPTIONS', KCMC_PRIVATE_DATA . '/push-subscriptions.json');
if (!defined('KCMC_PUSH_VAPID')) define('KCMC_PUSH_VAPID', KCMC_PRIVATE_DATA . '/push-vapid.json');
if (!defined('KCMC_PUSH_NOTICE')) define('KCMC_PUSH_NOTICE', KCMC_PRIVATE_DATA . '/push-notice.json');

function kcmc_push_b64url_encode(string $value): string {
    return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
}

function kcmc_push_b64url_decode(string $value): string|false {
    if (!preg_match('/\A[A-Za-z0-9_-]*\z/', $value)) return false;
    $padding = (4 - (strlen($value) % 4)) % 4;
    return base64_decode(strtr($value . str_repeat('=', $padding), '-_', '+/'), true);
}

function kcmc_push_endpoint_allowed(string $endpoint): bool {
    if (strlen($endpoint) < 20 || strlen($endpoint) > 4096) return false;
    $parts = parse_url($endpoint);
    if (!is_array($parts) || strtolower((string)($parts['scheme'] ?? '')) !== 'https') return false;
    if (!empty($parts['user']) || !empty($parts['pass'])) return false;
    $host = strtolower(rtrim((string)($parts['host'] ?? ''), '.'));
    if ($host === '') return false;
    foreach (['fcm.googleapis.com', 'push.services.mozilla.com', 'push.apple.com', 'notify.windows.com'] as $suffix) {
        if ($host === $suffix || str_ends_with($host, '.' . $suffix)) return true;
    }
    return false;
}

function kcmc_push_clean_subscription(array $subscription, string $userId): ?array {
    $endpoint = trim((string)($subscription['endpoint'] ?? ''));
    $keys = is_array($subscription['keys'] ?? null) ? $subscription['keys'] : [];
    $p256dh = trim((string)($keys['p256dh'] ?? ''));
    $auth = trim((string)($keys['auth'] ?? ''));
    $p256dhRaw = kcmc_push_b64url_decode($p256dh);
    $authRaw = kcmc_push_b64url_decode($auth);
    if (!kcmc_push_endpoint_allowed($endpoint)) return null;
    if ($p256dhRaw === false || strlen($p256dhRaw) !== 65 || ord($p256dhRaw[0]) !== 4) return null;
    if ($authRaw === false || strlen($authRaw) < 16 || strlen($authRaw) > 32) return null;
    return [
        'id' => 'push_' . substr(hash('sha256', $endpoint), 0, 24),
        'user_id' => $userId,
        'endpoint' => $endpoint,
        'p256dh' => $p256dh,
        'auth' => $auth,
    ];
}

function kcmc_push_save_subscription(array $subscription, array $user): bool {
    $userId = trim((string)($user['id'] ?? ''));
    if ($userId === '') return false;
    $clean = kcmc_push_clean_subscription($subscription, $userId);
    if ($clean === null) return false;
    kcmc_update_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []], function (array &$state) use ($clean, $userId): void {
        $now = gmdate('c');
        $subscriptions = array_values(array_filter($state['subscriptions'] ?? [], 'is_array'));
        $found = false;
        foreach ($subscriptions as &$stored) {
            if (($stored['endpoint'] ?? '') !== $clean['endpoint']) continue;
            $stored = array_replace($stored, $clean, ['updated_at' => $now, 'active' => true]);
            $found = true;
            break;
        }
        unset($stored);
        if (!$found) $subscriptions[] = $clean + ['created_at' => $now, 'updated_at' => $now, 'active' => true, 'last_status' => null, 'last_attempt_at' => null];

        $mine = [];
        foreach ($subscriptions as $index => $stored) {
            if (($stored['user_id'] ?? '') === $userId) $mine[] = ['index' => $index, 'at' => (string)($stored['updated_at'] ?? $stored['created_at'] ?? '')];
        }
        if (count($mine) > 5) {
            usort($mine, fn($a, $b) => strcmp($a['at'], $b['at']));
            $remove = array_column(array_slice($mine, 0, count($mine) - 5), 'index');
            $subscriptions = array_values(array_filter($subscriptions, fn($stored, $index) => !in_array($index, $remove, true), ARRAY_FILTER_USE_BOTH));
        }
        $state['version'] = 1;
        $state['subscriptions'] = $subscriptions;
    });
    return true;
}

function kcmc_push_remove_subscription(string $endpoint, array $user): bool {
    $endpoint = trim($endpoint);
    $userId = trim((string)($user['id'] ?? ''));
    if ($endpoint === '' || $userId === '') return false;
    return (bool)kcmc_update_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []], function (array &$state) use ($endpoint, $userId): bool {
        $before = count($state['subscriptions'] ?? []);
        $state['subscriptions'] = array_values(array_filter($state['subscriptions'] ?? [], function ($stored) use ($endpoint, $userId): bool {
            return !is_array($stored) || ($stored['endpoint'] ?? '') !== $endpoint || ($stored['user_id'] ?? '') !== $userId;
        }));
        return count($state['subscriptions']) < $before;
    });
}

function kcmc_push_subscription_count(): int {
    $store = kcmc_read_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]);
    return count(array_filter($store['subscriptions'] ?? [], fn($stored) => is_array($stored) && !empty($stored['active']) && kcmc_push_endpoint_allowed((string)($stored['endpoint'] ?? ''))));
}

function kcmc_push_public_key_from_details(array $details): ?string {
    $ec = is_array($details['ec'] ?? null) ? $details['ec'] : [];
    $x = $ec['x'] ?? null;
    $y = $ec['y'] ?? null;
    if (!is_string($x) || !is_string($y) || strlen($x) !== 32 || strlen($y) !== 32) return null;
    return kcmc_push_b64url_encode("\x04" . $x . $y);
}

function kcmc_push_valid_vapid(array $vapid): bool {
    $privatePem = (string)($vapid['private_key_pem'] ?? '');
    $public = (string)($vapid['public_key'] ?? '');
    $publicRaw = kcmc_push_b64url_decode($public);
    if ($privatePem === '' || !str_contains($privatePem, 'PRIVATE KEY')) return false;
    return $publicRaw !== false && strlen($publicRaw) === 65 && ord($publicRaw[0]) === 4;
}

function kcmc_push_get_vapid(bool $create = false): ?array {
    $stored = kcmc_read_json_store(KCMC_PUSH_VAPID, ['version' => 1]);
    if (kcmc_push_valid_vapid($stored)) return $stored;
    if (!$create) return null;

    return kcmc_update_json_store(KCMC_PUSH_VAPID, ['version' => 1], function (array &$state): array {
        if (kcmc_push_valid_vapid($state)) return $state;
        if (!function_exists('openssl_pkey_new')) throw new RuntimeException('OpenSSL is required for Web Push.');
        $key = openssl_pkey_new(['private_key_type' => OPENSSL_KEYTYPE_EC, 'curve_name' => 'prime256v1']);
        if ($key === false) throw new RuntimeException('Could not generate VAPID key.');
        $privatePem = '';
        if (!openssl_pkey_export($key, $privatePem)) throw new RuntimeException('Could not export VAPID key.');
        $details = openssl_pkey_get_details($key);
        if (!is_array($details)) throw new RuntimeException('Could not inspect VAPID key.');
        $public = kcmc_push_public_key_from_details($details);
        if ($public === null) throw new RuntimeException('Could not derive VAPID public key.');
        $email = (string)(kcmc_config()['church_email'] ?? 'secretary@umckc.org');
        $subject = kcmc_valid_email($email) ? 'mailto:' . kcmc_normalize_email($email) : 'mailto:secretary@umckc.org';
        $state = [
            'version' => 1,
            'subject' => $subject,
            'public_key' => $public,
            'private_key_pem' => $privatePem,
            'created_at' => gmdate('c'),
        ];
        return $state;
    });
}

function kcmc_push_der_length(string $der, int &$offset): int {
    if ($offset >= strlen($der)) throw new RuntimeException('Invalid DER signature.');
    $length = ord($der[$offset++]);
    if (($length & 0x80) === 0) return $length;
    $bytes = $length & 0x7f;
    if ($bytes < 1 || $bytes > 2 || $offset + $bytes > strlen($der)) throw new RuntimeException('Invalid DER signature length.');
    $length = 0;
    for ($i = 0; $i < $bytes; $i++) $length = ($length << 8) | ord($der[$offset++]);
    return $length;
}

function kcmc_push_der_signature_to_raw(string $der): string {
    $offset = 0;
    if (($der[$offset++] ?? '') !== "\x30") throw new RuntimeException('Invalid ECDSA signature sequence.');
    $sequenceLength = kcmc_push_der_length($der, $offset);
    if ($sequenceLength < 1 || $offset + $sequenceLength > strlen($der)) throw new RuntimeException('Invalid ECDSA signature length.');
    $parts = [];
    for ($part = 0; $part < 2; $part++) {
        if (($der[$offset++] ?? '') !== "\x02") throw new RuntimeException('Invalid ECDSA signature integer.');
        $length = kcmc_push_der_length($der, $offset);
        if ($length < 1 || $offset + $length > strlen($der)) throw new RuntimeException('Invalid ECDSA signature integer length.');
        $value = substr($der, $offset, $length);
        $offset += $length;
        $value = ltrim($value, "\x00");
        if (strlen($value) > 32) throw new RuntimeException('ECDSA signature integer is too large.');
        $parts[] = str_pad($value, 32, "\x00", STR_PAD_LEFT);
    }
    return $parts[0] . $parts[1];
}

function kcmc_push_vapid_jwt(string $audience, array $vapid, ?int $now = null): string {
    if (!kcmc_push_valid_vapid($vapid)) throw new RuntimeException('VAPID is not configured.');
    if (!preg_match('#\Ahttps://[A-Za-z0-9.-]+(?::[0-9]+)?\z#', $audience)) throw new RuntimeException('Invalid VAPID audience.');
    $now ??= time();
    $header = kcmc_push_b64url_encode((string)json_encode(['typ' => 'JWT', 'alg' => 'ES256'], JSON_UNESCAPED_SLASHES));
    $claims = kcmc_push_b64url_encode((string)json_encode([
        'aud' => $audience,
        'exp' => $now + 43200,
        'sub' => (string)($vapid['subject'] ?? 'mailto:secretary@umckc.org'),
    ], JSON_UNESCAPED_SLASHES));
    $unsigned = $header . '.' . $claims;
    $key = openssl_pkey_get_private((string)$vapid['private_key_pem']);
    if ($key === false) throw new RuntimeException('VAPID private key is invalid.');
    $der = '';
    if (!openssl_sign($unsigned, $der, $key, OPENSSL_ALGO_SHA256)) throw new RuntimeException('Could not sign VAPID token.');
    return $unsigned . '.' . kcmc_push_b64url_encode(kcmc_push_der_signature_to_raw($der));
}

function kcmc_push_endpoint_origin(string $endpoint): string {
    $parts = parse_url($endpoint);
    if (!is_array($parts) || strtolower((string)($parts['scheme'] ?? '')) !== 'https' || empty($parts['host'])) throw new RuntimeException('Invalid push endpoint.');
    $origin = 'https://' . strtolower((string)$parts['host']);
    if (!empty($parts['port'])) $origin .= ':' . (int)$parts['port'];
    return $origin;
}

function kcmc_push_send_request(string $endpoint, array $vapid): array {
    if (!kcmc_push_endpoint_allowed($endpoint)) return ['ok' => false, 'gone' => false, 'status' => 0, 'error' => 'unsupported_endpoint'];
    try {
        $jwt = kcmc_push_vapid_jwt(kcmc_push_endpoint_origin($endpoint), $vapid);
    } catch (Throwable $e) {
        return ['ok' => false, 'gone' => false, 'status' => 0, 'error' => 'vapid_error'];
    }
    $headers = [
        'TTL: 300',
        'Content-Length: 0',
        'Authorization: vapid t=' . $jwt . ', k=' . (string)$vapid['public_key'],
    ];
    $status = 0;
    $error = '';
    if (function_exists('curl_init')) {
        $ch = curl_init($endpoint);
        if ($ch === false) return ['ok' => false, 'gone' => false, 'status' => 0, 'error' => 'curl_init'];
        $options = [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => '',
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_CONNECTTIMEOUT => 4,
            CURLOPT_TIMEOUT => 8,
            CURLOPT_USERAGENT => 'KCMC-Connect-WebPush/1.0',
        ];
        if (defined('CURLOPT_PROTOCOLS') && defined('CURLPROTO_HTTPS')) $options[CURLOPT_PROTOCOLS] = CURLPROTO_HTTPS;
        curl_setopt_array($ch, $options);
        $response = curl_exec($ch);
        $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        if ($response === false) $error = (string)curl_error($ch);
        curl_close($ch);
    } else {
        $context = stream_context_create(['http' => [
            'method' => 'POST',
            'header' => implode("\r\n", $headers),
            'content' => '',
            'ignore_errors' => true,
            'timeout' => 8,
        ]]);
        @file_get_contents($endpoint, false, $context);
        foreach ($http_response_header ?? [] as $line) {
            if (preg_match('/\AHTTP\/\S+\s+(\d{3})\b/', $line, $m)) { $status = (int)$m[1]; break; }
        }
        if ($status === 0) $error = 'stream_transport_failed';
    }
    return [
        'ok' => $status >= 200 && $status < 300,
        'gone' => $status === 404 || $status === 410,
        'status' => $status,
        'error' => $error === '' ? null : 'transport_error',
    ];
}

function kcmc_push_clean_text(string $value, int $max): string {
    $value = trim((string)preg_replace('/\s+/u', ' ', strip_tags($value)));
    if (function_exists('mb_substr')) return mb_substr($value, 0, $max, 'UTF-8');
    return substr($value, 0, $max);
}

function kcmc_push_valid_target(string $target): bool {
    return preg_match('#\A\./[A-Za-z0-9._~!$&\'()*+,;=:@%/?#-]*\z#', $target) === 1 && !str_contains($target, '\\') && !str_contains($target, '//');
}

function kcmc_push_save_notice(string $title, string $body, string $target, string $actorId): array {
    $title = kcmc_push_clean_text($title, 80);
    $body = kcmc_push_clean_text($body, 180);
    $target = trim($target) === '' ? './' : trim($target);
    if (kcmc_text_length($title) < 3 || kcmc_text_length($body) < 5) throw new InvalidArgumentException('Notification title or message is too short.');
    if (!kcmc_push_valid_target($target)) throw new InvalidArgumentException('Notification link must stay inside KCMC Connect.');
    $notice = [
        'version' => 1,
        'id' => kcmc_random_id('notice'),
        'title' => $title,
        'body' => $body,
        'target' => $target,
        'created_at' => gmdate('c'),
        'created_by' => $actorId,
    ];
    kcmc_update_json_store(KCMC_PUSH_NOTICE, ['version' => 1], function (array &$state) use ($notice): void { $state = $notice; });
    return $notice;
}

function kcmc_push_public_notice(): ?array {
    $notice = kcmc_read_json_store(KCMC_PUSH_NOTICE, ['version' => 1]);
    if (empty($notice['id']) || empty($notice['title']) || empty($notice['body'])) return null;
    return [
        'id' => (string)$notice['id'],
        'title' => (string)$notice['title'],
        'body' => (string)$notice['body'],
        'target' => kcmc_push_valid_target((string)($notice['target'] ?? '')) ? (string)$notice['target'] : './',
        'created_at' => (string)($notice['created_at'] ?? ''),
    ];
}

function kcmc_push_send_all(array $notice, array $vapid): array {
    $store = kcmc_read_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]);
    $subscriptions = array_values(array_filter($store['subscriptions'] ?? [], fn($stored) => is_array($stored) && !empty($stored['active'])));
    $results = [];
    $sent = 0;
    $failed = 0;
    $gone = 0;
    foreach ($subscriptions as $stored) {
        $endpoint = (string)($stored['endpoint'] ?? '');
        $result = kcmc_push_send_request($endpoint, $vapid);
        $results[$endpoint] = $result;
        if (!empty($result['ok'])) $sent++;
        elseif (!empty($result['gone'])) $gone++;
        else $failed++;
    }
    $noticeId = (string)($notice['id'] ?? '');
    kcmc_update_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []], function (array &$state) use ($results, $noticeId): void {
        $now = gmdate('c');
        $updated = [];
        foreach ($state['subscriptions'] ?? [] as $stored) {
            if (!is_array($stored)) continue;
            $endpoint = (string)($stored['endpoint'] ?? '');
            $result = $results[$endpoint] ?? null;
            if (!is_array($result)) { $updated[] = $stored; continue; }
            if (!empty($result['gone'])) continue;
            $stored['last_attempt_at'] = $now;
            $stored['last_status'] = (int)($result['status'] ?? 0);
            if (!empty($result['ok'])) $stored['last_notice_id'] = $noticeId;
            $updated[] = $stored;
        }
        $state['version'] = 1;
        $state['subscriptions'] = $updated;
    });
    return ['total' => count($subscriptions), 'sent' => $sent, 'failed' => $failed, 'gone' => $gone];
}
