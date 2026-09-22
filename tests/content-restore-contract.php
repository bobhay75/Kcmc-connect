<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/content-restore.php';

function restore_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$valid = json_encode([
    'meta' => ['version' => '3.0.0'],
    'contact' => ['email' => 'secretary@example.com'],
    'announcements' => [],
    'bulletin' => ['title' => 'Sunday'],
    'events' => [],
    'news' => ['title' => 'News'],
], JSON_UNESCAPED_SLASHES);
$result = kcmc_restore_validate_public_content((string)$valid);
restore_check(!empty($result['ok']) && is_array($result['data']), 'valid KCMC public backup is accepted');

$badJson = kcmc_restore_validate_public_content('{bad');
restore_check(empty($badJson['ok']), 'malformed JSON is rejected');

$missing = kcmc_restore_validate_public_content((string)json_encode(['contact' => [], 'announcements' => [], 'bulletin' => []]));
restore_check(empty($missing['ok']) && str_contains((string)$missing['error'], 'events'), 'missing required public section is rejected');

$private = kcmc_restore_validate_public_content((string)json_encode([
    'contact' => [], 'announcements' => [], 'bulletin' => [], 'events' => [],
    'prayers' => [['message' => 'private']],
]));
restore_check(empty($private['ok']) && str_contains((string)$private['error'], 'private-data'), 'private-data section is rejected');

$oversize = kcmc_restore_validate_public_content(str_repeat('A', KCMC_RESTORE_MAX_BYTES + 1));
restore_check(empty($oversize['ok']), 'oversized restore payload is rejected');

$malformedEvent = kcmc_restore_validate_public_content((string)json_encode([
    'contact' => [], 'announcements' => [], 'bulletin' => [], 'events' => ['bad-row'],
]));
restore_check(empty($malformedEvent['ok']), 'malformed event row is rejected');

$page = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/restore.php');
restore_check(is_string($page), 'restore page source is readable');
restore_check(str_contains($page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'restore requires an administrator role');
restore_check(str_contains($page, 'kcmc_verify_csrf'), 'restore requires CSRF validation');
restore_check(str_contains($page, "!== 'RESTORE'"), 'restore requires explicit typed confirmation');
restore_check(str_contains($page, 'is_uploaded_file'), 'restore requires a verified HTTP upload');
restore_check(str_contains($page, "kcmc_audit('content.restored'"), 'successful restore is audited');
restore_check(!preg_match('/KCMC_USERS|KCMC_INVITES|KCMC_PRAYERS|KCMC_PUSH_SUBSCRIPTIONS/', $page), 'restore page does not access private data stores');

$member = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/index.php');
restore_check(is_string($member) && str_contains($member, 'admin/restore.php'), 'administrator home links to content restore');

echo "Guarded content restore contract checks passed.\n";
