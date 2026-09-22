<?php
declare(strict_types=1);

const KCMC_PUSH_SUBSCRIPTIONS = KCMC_PRIVATE_DATA . '/push-subscriptions.json';

function kcmc_push_public_key(): string {
    $cfg = kcmc_config();
    $configured = trim((string)($cfg['push_vapid_public_key'] ?? ''));
    $env = getenv('KCMC_PUSH_VAPID_PUBLIC_KEY');
    if (is_string($env) && trim($env) !== '') $configured = trim($env);
    return preg_match('/\A[A-Za-z0-9_-]{80,120}\z/', $configured) ? $configured : '';
}

function kcmc_push_enabled(): bool {
    return kcmc_push_public_key() !== '';
}

function kcmc_push_validate_subscription(array $payload): ?array {
    $endpoint = trim((string)($payload['endpoint'] ?? ''));
    $keys = $payload['keys'] ?? null;
    $p256dh = is_array($keys) ? trim((string)($keys['p256dh'] ?? '')) : '';
    $auth = is_array($keys) ? trim((string)($keys['auth'] ?? '')) : '';
    if ($endpoint === '' || strlen($endpoint) > 2048 || !filter_var($endpoint, FILTER_VALIDATE_URL)) return null;
    $parts = parse_url($endpoint);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || empty($parts['host']) || isset($parts['user']) || isset($parts['pass'])) return null;
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

function kcmc_push_active_for_user(string $userId): int {
    if ($userId === '') return 0;
    $state = kcmc_read_json_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]);
    $count = 0;
    foreach (($state['subscriptions'] ?? []) as $stored) {
        if (is_array($stored) && ($stored['user_id'] ?? '') === $userId && !empty($stored['active'])) $count++;
    }
    return $count;
}
