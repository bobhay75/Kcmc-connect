<?php
declare(strict_types=1);

const KCMC_AUDIT_VIEW_MAX_BYTES = 262144;
const KCMC_AUDIT_VIEW_MAX_ROWS = 100;

function kcmc_audit_event_label(string $action): string {
    $labels = [
        'auth.login' => 'Signed in',
        'auth.logout' => 'Signed out',
        'auth.invite_activated' => 'Invitation activated',
        'auth.recovery_admin_created' => 'Recovery administrator created',
        'member.invited' => 'Member invitation created',
        'member.invitation_email_sent' => 'Invitation email accepted',
        'member.invitation_email_failed' => 'Invitation email failed',
        'member.invitation_revoked' => 'Pending invitation revoked',
        'member.status_changed' => 'Account status changed',
        'content.published' => 'Public content published',
        'content.restored' => 'Public content restored',
        'prayer.submitted' => 'Prayer request submitted',
        'prayer.moderated' => 'Prayer request moderated',
        'push.subscription_saved' => 'Push notifications enabled',
        'push.subscription_removed' => 'Push notifications disabled',
        'push.broadcast_attempted' => 'Push broadcast attempted',
    ];
    return $labels[$action] ?? ucwords(str_replace(['.', '_'], ' ', $action));
}

function kcmc_audit_visible_context(array $context): array {
    $allowed = ['role', 'active', 'sent', 'expired', 'failed', 'count', 'content_version', 'audience', 'action', 'bytes', 'reason'];
    $visible = [];
    foreach ($allowed as $key) {
        if (!array_key_exists($key, $context)) continue;
        $value = $context[$key];
        if (is_bool($value)) $value = $value ? 'yes' : 'no';
        if (!is_scalar($value) && $value !== null) continue;
        $text = trim((string)$value);
        if ($text === '') continue;
        $visible[$key] = strlen($text) > 120 ? substr($text, 0, 117) . '...' : $text;
    }
    return $visible;
}

function kcmc_audit_actor_names(array $users): array {
    $map = ['system' => 'System'];
    foreach (($users['users'] ?? []) as $user) {
        if (!is_array($user)) continue;
        $id = trim((string)($user['id'] ?? ''));
        $name = trim((string)($user['display_name'] ?? ''));
        if ($id !== '' && $name !== '') $map[$id] = $name;
    }
    return $map;
}

function kcmc_audit_recent_rows(string $path, array $actorNames, int $limit = 50): array {
    $limit = max(1, min(KCMC_AUDIT_VIEW_MAX_ROWS, $limit));
    if (!is_file($path) || !is_readable($path)) return [];
    $size = (int)@filesize($path);
    if ($size < 1) return [];

    $handle = @fopen($path, 'rb');
    if ($handle === false) return [];
    $start = max(0, $size - KCMC_AUDIT_VIEW_MAX_BYTES);
    if ($start > 0) {
        fseek($handle, $start);
        fgets($handle); // discard a potentially partial first record
    }

    $rows = [];
    while (($line = fgets($handle)) !== false) {
        $decoded = json_decode(trim($line), true);
        if (!is_array($decoded)) continue;
        $at = trim((string)($decoded['at'] ?? ''));
        $action = trim((string)($decoded['action'] ?? ''));
        if ($at === '' || $action === '') continue;
        $actorId = trim((string)($decoded['actor_id'] ?? 'system')) ?: 'system';
        $context = is_array($decoded['context'] ?? null) ? $decoded['context'] : [];
        $rows[] = [
            'at' => $at,
            'action' => $action,
            'label' => kcmc_audit_event_label($action),
            'actor' => $actorNames[$actorId] ?? 'Former or unknown account',
            'context' => kcmc_audit_visible_context($context),
        ];
        if (count($rows) > KCMC_AUDIT_VIEW_MAX_ROWS * 3) $rows = array_slice($rows, -KCMC_AUDIT_VIEW_MAX_ROWS * 2);
    }
    fclose($handle);

    $rows = array_slice($rows, -$limit);
    return array_reverse($rows);
}
