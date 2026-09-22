<?php
declare(strict_types=1);

const KCMC_RESTORE_MAX_BYTES = 2097152;

function kcmc_restore_validate_public_content(string $raw): array {
    if ($raw === '' || strlen($raw) > KCMC_RESTORE_MAX_BYTES) {
        return ['ok' => false, 'error' => 'Backup file is empty or exceeds the 2 MB restore limit.', 'data' => null];
    }

    try {
        $data = json_decode($raw, true, 128, JSON_THROW_ON_ERROR);
    } catch (JsonException) {
        return ['ok' => false, 'error' => 'Backup file is not valid JSON.', 'data' => null];
    }
    if (!is_array($data)) return ['ok' => false, 'error' => 'Backup file must contain a JSON object.', 'data' => null];

    $requiredArrays = ['contact', 'announcements', 'bulletin', 'events'];
    foreach ($requiredArrays as $key) {
        if (!array_key_exists($key, $data) || !is_array($data[$key])) {
            return ['ok' => false, 'error' => 'Backup is missing the required public-content section: ' . $key . '.', 'data' => null];
        }
    }
    if (isset($data['meta']) && !is_array($data['meta'])) {
        return ['ok' => false, 'error' => 'Backup metadata is malformed.', 'data' => null];
    }

    $forbiddenTopLevel = [
        'users', 'members', 'invites', 'invitations', 'prayers', 'prayer_requests',
        'passwords', 'password_hashes', 'tokens', 'push_subscriptions', 'subscriptions',
        'setup_key', 'private_data', 'audit_log', 'login_attempts',
    ];
    foreach ($forbiddenTopLevel as $key) {
        if (array_key_exists($key, $data)) {
            return ['ok' => false, 'error' => 'Backup contains a private-data section and cannot be restored as public content.', 'data' => null];
        }
    }

    foreach ($data['announcements'] as $announcement) {
        if (!is_array($announcement)) return ['ok' => false, 'error' => 'Announcement data is malformed.', 'data' => null];
    }
    foreach ($data['events'] as $event) {
        if (!is_array($event)) return ['ok' => false, 'error' => 'Event data is malformed.', 'data' => null];
    }

    return ['ok' => true, 'error' => '', 'data' => $data];
}

function kcmc_restore_public_content(string $raw, string $actor): array {
    $validated = kcmc_restore_validate_public_content($raw);
    if (empty($validated['ok']) || !is_array($validated['data'])) return $validated;

    $data = $validated['data'];
    kcmc_apply_required_public_content($data);
    kcmc_write_content($data, $actor);
    return ['ok' => true, 'error' => '', 'data' => $data];
}
