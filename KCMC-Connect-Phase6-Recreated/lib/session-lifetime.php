<?php
declare(strict_types=1);

const KCMC_SESSION_IDLE_SECONDS = 1800;
const KCMC_SESSION_ABSOLUTE_SECONDS = 43200;
const KCMC_SESSION_REGENERATE_SECONDS = 900;

/** Bind only a freshly authenticated account snapshot, never a legacy session. */
function kcmc_session_credential_tag(array $user, string $nonce): ?string {
    $id = $user['id'] ?? null;
    $hash = $user['password_hash'] ?? null;
    if (!is_string($id) || $id === '' || !is_string($hash) || (password_get_info($hash)['algo'] ?? null) === null) return null;
    return hash_hmac('sha256', "kcmc-session-credential-v1\0" . $id . "\0" . $hash, $nonce);
}

function kcmc_session_bind_credentials(array &$session, array $user): void {
    $nonce = bin2hex(random_bytes(32));
    $tag = kcmc_session_credential_tag($user, $nonce);
    if ($tag === null) throw new LogicException('A valid authenticated account is required.');
    // The password hash stays in users.json; sessions contain only a random
    // nonce and a keyed fingerprint that changes with the stored credential.
    $session['kcmc_auth_credential_nonce'] = $nonce;
    $session['kcmc_auth_credential_tag'] = $tag;
}

function kcmc_session_credentials_match(array $session, array $user): bool {
    $nonce = $session['kcmc_auth_credential_nonce'] ?? null;
    $tag = $session['kcmc_auth_credential_tag'] ?? null;
    if (!is_string($nonce) || !preg_match('/\A[a-f0-9]{64}\z/', $nonce)
        || !is_string($tag) || !preg_match('/\A[a-f0-9]{64}\z/', $tag)) return false;
    $expected = kcmc_session_credential_tag($user, $nonce);
    return $expected !== null && hash_equals($expected, $tag);
}

function kcmc_session_initialize_auth(array &$session, int $now): void {
    $session['kcmc_auth_started_at'] = $now;
    $session['kcmc_auth_last_activity_at'] = $now;
    $session['kcmc_auth_last_regenerated_at'] = $now;
}

function kcmc_session_lifetime_state(array $session, int $now, bool $recordActivity = true): array {
    $started = (int)($session['kcmc_auth_started_at'] ?? 0);
    $lastActivity = (int)($session['kcmc_auth_last_activity_at'] ?? 0);
    $lastRegenerated = (int)($session['kcmc_auth_last_regenerated_at'] ?? 0);

    if ($started <= 0 || $lastActivity <= 0) {
        return ['status' => 'initialize', 'regenerate' => false];
    }
    if ($started > $now + 300 || $lastActivity > $now + 300 || $lastRegenerated > $now + 300) {
        return ['status' => 'invalid_clock', 'regenerate' => false];
    }
    if (($now - $started) >= KCMC_SESSION_ABSOLUTE_SECONDS) {
        return ['status' => 'absolute_expired', 'regenerate' => false];
    }
    if (($now - $lastActivity) >= KCMC_SESSION_IDLE_SECONDS) {
        return ['status' => 'idle_expired', 'regenerate' => false];
    }

    $regenerate = $recordActivity && ($lastRegenerated <= 0 || ($now - $lastRegenerated) >= KCMC_SESSION_REGENERATE_SECONDS);
    return ['status' => 'active', 'regenerate' => $regenerate];
}

function kcmc_session_apply_lifetime(array &$session, int $now, bool $recordActivity = true): array {
    $state = kcmc_session_lifetime_state($session, $now, $recordActivity);
    if ($state['status'] === 'initialize') {
        kcmc_session_initialize_auth($session, $now);
        return ['status' => 'active', 'regenerate' => false, 'initialized' => true];
    }
    if ($state['status'] !== 'active') return $state + ['initialized' => false];
    if ($recordActivity) $session['kcmc_auth_last_activity_at'] = $now;
    return $state + ['initialized' => false];
}

function kcmc_session_mark_regenerated(array &$session, int $now): void {
    $session['kcmc_auth_last_regenerated_at'] = $now;
}

function kcmc_session_audit_expiration(string $userId, string $reason, int $now): void {
    if ($userId === '' || !defined('KCMC_AUDIT_LOG') || !function_exists('kcmc_ensure_private_storage')) return;
    $reason = in_array($reason, ['idle_expired', 'absolute_expired', 'invalid_clock', 'credentials_changed'], true) ? $reason : 'expired';
    kcmc_ensure_private_storage();
    $record = [
        'at' => gmdate('c', $now),
        'action' => 'auth.session_expired',
        'actor_id' => $userId,
        'ip_hash' => hash('sha256', (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown')),
        'context' => ['reason' => $reason],
    ];
    @file_put_contents(KCMC_AUDIT_LOG, json_encode($record, JSON_UNESCAPED_SLASHES) . PHP_EOL, FILE_APPEND | LOCK_EX);
    @chmod(KCMC_AUDIT_LOG, 0640);
}
