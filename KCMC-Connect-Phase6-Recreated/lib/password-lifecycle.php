<?php
declare(strict_types=1);

const KCMC_PASSWORD_RESETS = KCMC_PRIVATE_DATA . '/password-resets.json';
const KCMC_PASSWORD_RESET_TTL = 3600;

function kcmc_password_policy_error(string $password, string $confirm, string $currentHash = ''): string {
    if (strlen($password) < 12) return 'Use at least 12 characters.';
    if ($password !== $confirm) return 'Passwords do not match.';
    if ($currentHash !== '' && password_verify($password, $currentHash)) return 'Choose a password different from the current password.';
    return '';
}

function kcmc_can_issue_password_reset(array $actor, array $target): bool {
    if (empty($actor['active']) || empty($target['active'])) return false;
    $actorId = (string)($actor['id'] ?? '');
    $targetId = (string)($target['id'] ?? '');
    if ($actorId === '' || $targetId === '' || hash_equals($actorId, $targetId)) return false;
    $actorRole = kcmc_role($actor);
    $targetRole = kcmc_role($target);
    if ($actorRole === 'recovery_admin') return true;
    return $actorRole === 'pastor_admin' && in_array($targetRole, ['member', 'prayer_team'], true);
}

function kcmc_create_password_reset(array $target, string $createdBy, ?int $now = null): ?array {
    $now ??= time();
    $userId = trim((string)($target['id'] ?? ''));
    $email = kcmc_normalize_email((string)($target['email'] ?? ''));
    if ($userId === '' || $createdBy === '' || empty($target['active']) || !kcmc_valid_email($email)) return null;

    $token = bin2hex(random_bytes(32));
    $record = [
        'id' => kcmc_random_id('reset'),
        'user_id' => $userId,
        'email_normalized' => $email,
        'token_hash' => hash('sha256', $token),
        'created_at' => gmdate('c', $now),
        'expires_at' => gmdate('c', $now + KCMC_PASSWORD_RESET_TTL),
        'created_by' => $createdBy,
        'used_at' => null,
    ];

    kcmc_update_json_store(KCMC_PASSWORD_RESETS, ['version' => 1, 'resets' => []], function (array &$state) use ($record, $userId): void {
        if (!isset($state['resets']) || !is_array($state['resets'])) $state['resets'] = [];
        foreach ($state['resets'] as &$old) {
            if (!is_array($old) || ($old['user_id'] ?? '') !== $userId || !empty($old['used_at'])) continue;
            $old['used_at'] = 'superseded';
        }
        unset($old);
        $state['resets'][] = $record;
    });

    return ['token' => $token, 'record' => $record];
}

function kcmc_find_password_reset(string $token, ?int $now = null): ?array {
    $token = trim($token);
    if (!preg_match('/\A[a-f0-9]{64}\z/', $token)) return null;
    $now ??= time();
    $needle = hash('sha256', $token);
    $store = kcmc_read_json_store(KCMC_PASSWORD_RESETS, ['version' => 1, 'resets' => []]);
    foreach (($store['resets'] ?? []) as $record) {
        if (!is_array($record) || !empty($record['used_at'])) continue;
        $storedHash = (string)($record['token_hash'] ?? '');
        if (strlen($storedHash) !== strlen($needle) || !hash_equals($storedHash, $needle)) continue;
        $expires = strtotime((string)($record['expires_at'] ?? ''));
        if ($expires === false || $expires <= $now) return null;
        return $record;
    }
    return null;
}

function kcmc_claim_password_reset(string $token, ?int $now = null): ?array {
    $token = trim($token);
    if (!preg_match('/\A[a-f0-9]{64}\z/', $token)) return null;
    $now ??= time();
    $needle = hash('sha256', $token);
    return kcmc_update_json_store(KCMC_PASSWORD_RESETS, ['version' => 1, 'resets' => []], function (array &$state) use ($needle, $now): ?array {
        if (!isset($state['resets']) || !is_array($state['resets'])) return null;
        foreach ($state['resets'] as &$record) {
            if (!is_array($record) || !empty($record['used_at'])) continue;
            $storedHash = (string)($record['token_hash'] ?? '');
            if (strlen($storedHash) !== strlen($needle) || !hash_equals($storedHash, $needle)) continue;
            $expires = strtotime((string)($record['expires_at'] ?? ''));
            if ($expires === false || $expires <= $now) return null;
            $record['used_at'] = gmdate('c', $now);
            $claimed = $record;
            unset($record);
            return $claimed;
        }
        unset($record);
        return null;
    });
}

function kcmc_revoke_password_resets_for_user(string $userId, string $reason = 'revoked'): int {
    $userId = trim($userId);
    if ($userId === '') return 0;
    $reason = preg_match('/\A[a-z_]{3,40}\z/', $reason) ? $reason : 'revoked';
    return (int)kcmc_update_json_store(KCMC_PASSWORD_RESETS, ['version' => 1, 'resets' => []], function (array &$state) use ($userId, $reason): int {
        if (!isset($state['resets']) || !is_array($state['resets'])) return 0;
        $count = 0;
        foreach ($state['resets'] as &$record) {
            if (!is_array($record) || ($record['user_id'] ?? '') !== $userId || !empty($record['used_at'])) continue;
            $record['used_at'] = $reason;
            $count++;
        }
        unset($record);
        return $count;
    });
}

function kcmc_password_reset_delivery(array $target, string $link): ?array {
    $email = kcmc_normalize_email((string)($target['email'] ?? ''));
    $name = trim((string)($target['display_name'] ?? 'KCMC member'));
    if (!kcmc_valid_email($email) || $name === '' || strlen($name) > 160) return null;
    $parts = parse_url($link);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || empty($parts['host']) || isset($parts['user']) || isset($parts['pass'])) return null;
    $message = "Hello {$name},\n\nA KCMC Connect administrator created a one-time password reset link for your account. This link expires in one hour and stops working after it is used.\n\n{$link}\n\nIf you were not expecting this reset, do not use the link and contact the KCMC church office.\n";
    return [
        'email' => $email,
        'subject' => 'KCMC Connect password reset',
        'message' => $message,
        'link' => $link,
    ];
}
