<?php
declare(strict_types=1);

function kcmc_health_item(string $id, string $label, string $status, string $detail): array {
    if (!in_array($status, ['pass', 'warn', 'fail'], true)) $status = 'fail';
    return ['id' => $id, 'label' => $label, 'status' => $status, 'detail' => $detail];
}

function kcmc_health_read_store(string $path, array $default): array {
    if (!is_file($path) || !is_readable($path)) return $default;
    $raw = @file_get_contents($path);
    if (!is_string($raw) || trim($raw) === '') return $default;
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : $default;
}

function kcmc_health_pending_invite_count(array $store, ?int $now = null): int {
    $now ??= time();
    $count = 0;
    foreach (($store['invites'] ?? []) as $invite) {
        if (!is_array($invite) || !empty($invite['used_at'])) continue;
        $expires = strtotime((string)($invite['expires_at'] ?? ''));
        if ($expires !== false && $expires > $now) $count++;
    }
    return $count;
}

function kcmc_health_role_counts(array $store): array {
    $counts = ['member' => 0, 'prayer_team' => 0, 'pastor_admin' => 0, 'recovery_admin' => 0, 'active_total' => 0, 'disabled_total' => 0];
    foreach (($store['users'] ?? []) as $user) {
        if (!is_array($user)) continue;
        if (empty($user['active'])) {
            $counts['disabled_total']++;
            continue;
        }
        $counts['active_total']++;
        $role = (string)($user['role'] ?? 'member');
        if (array_key_exists($role, $counts)) $counts[$role]++;
    }
    return $counts;
}

function kcmc_health_active_push_count(array $store): int {
    $count = 0;
    foreach (($store['subscriptions'] ?? []) as $subscription) {
        if (is_array($subscription) && !empty($subscription['active'])) $count++;
    }
    return $count;
}

function kcmc_health_latest_backup(): ?array {
    if (!is_dir(KCMC_BACKUPS) || !is_readable(KCMC_BACKUPS)) return null;
    $matches = glob(KCMC_BACKUPS . '/content-*.json') ?: [];
    $latestPath = '';
    $latestMtime = 0;
    foreach ($matches as $path) {
        if (!is_file($path)) continue;
        $mtime = (int)@filemtime($path);
        if ($mtime > $latestMtime) {
            $latestMtime = $mtime;
            $latestPath = $path;
        }
    }
    return $latestPath === '' ? null : ['mtime' => $latestMtime, 'name' => basename($latestPath)];
}

function kcmc_release_health_snapshot(?int $now = null): array {
    $now ??= time();
    $checks = [];

    $phpOk = version_compare(PHP_VERSION, '8.1.0', '>=');
    $checks[] = kcmc_health_item('php', 'PHP runtime', $phpOk ? 'pass' : 'fail', 'PHP ' . PHP_VERSION . ($phpOk ? ' meets the 8.1+ requirement.' : ' is below the 8.1 minimum.'));
    $checks[] = kcmc_health_item('https', 'HTTPS request', kcmc_is_https() ? 'pass' : 'fail', kcmc_is_https() ? 'This administrator request is protected by HTTPS.' : 'This administrator request is not reporting HTTPS.');

    $contentOk = is_file(KCMC_DATA) && is_readable(KCMC_DATA);
    $contentValid = false;
    if ($contentOk) {
        $raw = @file_get_contents(KCMC_DATA);
        $decoded = is_string($raw) ? json_decode($raw, true) : null;
        $contentValid = is_array($decoded);
    }
    $checks[] = kcmc_health_item('content', 'Public content store', $contentOk && $contentValid ? 'pass' : 'fail', $contentOk && $contentValid ? 'content.json is readable and valid JSON.' : 'content.json is missing, unreadable or invalid.');

    $privateExists = is_dir(KCMC_PRIVATE_DATA);
    $privateReadable = $privateExists && is_readable(KCMC_PRIVATE_DATA);
    $privateWritable = $privateExists && is_writable(KCMC_PRIVATE_DATA);
    $checks[] = kcmc_health_item('private_storage', 'Private data storage', $privateReadable && $privateWritable ? 'pass' : 'fail', $privateReadable && $privateWritable ? 'Private storage is readable and writable.' : 'Private storage is missing or lacks required access.');

    $backupExists = is_dir(KCMC_BACKUPS);
    $backupWritable = $backupExists && is_writable(KCMC_BACKUPS);
    $latestBackup = kcmc_health_latest_backup();
    if (!$backupWritable) {
        $checks[] = kcmc_health_item('backups', 'Backup storage', 'fail', 'Backup storage is missing or not writable.');
    } elseif ($latestBackup === null) {
        $checks[] = kcmc_health_item('backups', 'Backup storage', 'warn', 'Backup storage is writable, but no automatic content backup is present yet.');
    } else {
        $ageHours = max(0, (int)floor(($now - (int)$latestBackup['mtime']) / 3600));
        $checks[] = kcmc_health_item('backups', 'Backup storage', 'pass', 'Backup storage is writable. Latest automatic content backup is about ' . $ageHours . ' hour' . ($ageHours === 1 ? '' : 's') . ' old.');
    }

    $config = kcmc_config();
    $setupKeyPresent = trim((string)($config['setup_key'] ?? '')) !== '';
    $checks[] = kcmc_health_item('setup_key', 'Recovery setup key', $setupKeyPresent ? 'fail' : 'pass', $setupKeyPresent ? 'A recovery setup key is still active and should be removed after first-account setup.' : 'No recovery setup key is active.');

    $mailSettings = kcmc_invitation_mail_settings();
    if (!empty($mailSettings['ready'])) {
        $checks[] = kcmc_health_item('invitation_mail', 'Invitation email', 'pass', 'Direct invitation email is configured with a validated sender.');
    } elseif (!empty($mailSettings['enabled'])) {
        $checks[] = kcmc_health_item('invitation_mail', 'Invitation email', 'fail', 'Direct invitation email is enabled but its sender configuration is invalid.');
    } else {
        $checks[] = kcmc_health_item('invitation_mail', 'Invitation email', 'warn', 'Direct invitation email is disabled; manual recipient-checked delivery remains available.');
    }

    $pushPublic = kcmc_push_public_key() !== '';
    $pushReady = kcmc_push_delivery_ready();
    if ($pushReady) {
        $checks[] = kcmc_health_item('push_delivery', 'Web Push delivery', 'pass', 'VAPID public/private key material, subject, cURL and OpenSSL are ready.');
    } elseif ($pushPublic) {
        $checks[] = kcmc_health_item('push_delivery', 'Web Push delivery', 'fail', 'A VAPID public key is configured, but the complete server delivery path is not ready.');
    } else {
        $checks[] = kcmc_health_item('push_delivery', 'Web Push delivery', 'warn', 'Web Push is not configured on this server.');
    }

    $workerOk = is_file(KCMC_ROOT . '/sw.js') && is_readable(KCMC_ROOT . '/sw.js');
    $manifestOk = is_file(KCMC_ROOT . '/manifest.webmanifest') && is_readable(KCMC_ROOT . '/manifest.webmanifest');
    $checks[] = kcmc_health_item('pwa', 'PWA files', $workerOk && $manifestOk ? 'pass' : 'fail', $workerOk && $manifestOk ? 'Service worker and web-app manifest are present.' : 'Service worker or web-app manifest is missing.');

    $users = kcmc_health_read_store(KCMC_USERS, ['version' => 1, 'users' => []]);
    $roles = kcmc_health_role_counts($users);
    $accountStatus = $roles['active_total'] > 0 && ($roles['pastor_admin'] + $roles['recovery_admin']) > 0 ? 'pass' : 'fail';
    $checks[] = kcmc_health_item('accounts', 'Administrator accounts', $accountStatus, $roles['active_total'] . ' active account(s): ' . $roles['pastor_admin'] . ' Pastor administrator(s), ' . $roles['recovery_admin'] . ' Recovery administrator(s), ' . $roles['prayer_team'] . ' prayer-team account(s), ' . $roles['member'] . ' member account(s).');

    $invites = kcmc_health_read_store(KCMC_INVITES, ['version' => 1, 'invites' => []]);
    $pendingInvites = kcmc_health_pending_invite_count($invites, $now);
    $checks[] = kcmc_health_item('pending_invites', 'Pending invitations', 'pass', $pendingInvites . ' current unexpired invitation(s) await activation.');

    $pushStore = defined('KCMC_PUSH_SUBSCRIPTIONS') ? kcmc_health_read_store(KCMC_PUSH_SUBSCRIPTIONS, ['version' => 1, 'subscriptions' => []]) : ['subscriptions' => []];
    $activePush = kcmc_health_active_push_count($pushStore);
    $pushSubscriptionStatus = $pushReady && $activePush < 1 ? 'warn' : 'pass';
    $checks[] = kcmc_health_item('push_subscriptions', 'Push subscriptions', $pushSubscriptionStatus, $activePush . ' active browser subscription(s) stored.');

    $auditReadable = is_file(KCMC_AUDIT_LOG) && is_readable(KCMC_AUDIT_LOG);
    $checks[] = kcmc_health_item('audit', 'Audit log', $auditReadable ? 'pass' : 'warn', $auditReadable ? 'The private audit log is present and readable.' : 'No readable audit log is present yet.');

    $summary = ['pass' => 0, 'warn' => 0, 'fail' => 0];
    foreach ($checks as $check) $summary[$check['status']]++;
    $overall = $summary['fail'] > 0 ? 'fail' : ($summary['warn'] > 0 ? 'warn' : 'pass');

    return [
        'overall' => $overall,
        'summary' => $summary,
        'checks' => $checks,
        'metrics' => [
            'active_accounts' => $roles['active_total'],
            'disabled_accounts' => $roles['disabled_total'],
            'pending_invites' => $pendingInvites,
            'active_push_subscriptions' => $activePush,
        ],
        'generated_at' => gmdate('c', $now),
    ];
}
