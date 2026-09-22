<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/event-create.php';

function event_create_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$valid = kcmc_validate_new_event([
    'title' => 'Community Supper',
    'date' => '2026-10-14',
    'time' => '5:30 PM',
    'end_time' => '7:00 PM',
    'location' => 'Fellowship Hall',
    'description' => 'Dinner and fellowship.',
    'priority' => '80',
    'status' => 'published',
    'expires' => '2026-10-14',
]);
event_create_check(!empty($valid['ok']), 'valid administrator event is accepted');
event_create_check(($valid['event']['priority'] ?? null) === 80, 'priority is normalized to integer');
event_create_check(($valid['event']['status'] ?? '') === 'published', 'visibility status is preserved');
event_create_check(str_starts_with((string)($valid['event']['expires_at'] ?? ''), '2026-10-14T23:59:59'), 'expiry normalizes to local end of day');
event_create_check(!array_key_exists('id', $valid['event']), 'validation does not assign an event ID prematurely');

$badDate = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-02-31', 'priority' => '50', 'status' => 'hidden']);
event_create_check(empty($badDate['ok']), 'invalid calendar date is rejected');
$badStart = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'time' => '17:30', 'priority' => '50', 'status' => 'hidden']);
event_create_check(empty($badStart['ok']), 'invalid start-time format is rejected');
$orphanEnd = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'end_time' => '7:00 PM', 'priority' => '50', 'status' => 'hidden']);
event_create_check(empty($orphanEnd['ok']), 'end time without start time is rejected');
$reversed = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'time' => '7:00 PM', 'end_time' => '6:00 PM', 'priority' => '50', 'status' => 'hidden']);
event_create_check(empty($reversed['ok']), 'end time at or before start is rejected');
$badPriority = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'priority' => '101', 'status' => 'hidden']);
event_create_check(empty($badPriority['ok']), 'priority above 100 is rejected');
$badStatus = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'priority' => '50', 'status' => 'public']);
event_create_check(empty($badStatus['ok']), 'unknown visibility status is rejected');
$badExpiry = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'priority' => '50', 'status' => 'hidden', 'expires' => '2026-10-13']);
event_create_check(empty($badExpiry['ok']), 'expiry before event date is rejected');
$longDescription = kcmc_validate_new_event(['title' => 'Test', 'date' => '2026-10-14', 'priority' => '50', 'status' => 'hidden', 'description' => str_repeat('x', 2001)]);
event_create_check(empty($longDescription['ok']), 'oversized description is rejected');

$events = [
    ['title' => 'Community Supper', 'date' => '2026-10-14'],
    ['title' => 'Youth Night', 'date' => '2026-10-15'],
];
event_create_check(kcmc_event_duplicate_exists($events, ' community supper ', '2026-10-14'), 'duplicate title and date is case-insensitive and whitespace-normalized');
event_create_check(!kcmc_event_duplicate_exists($events, 'Community Supper', '2026-10-15'), 'same title on a different date is allowed');

$page = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/event-create.php');
event_create_check(is_string($page) && str_contains($page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'event creation requires administrator role');
event_create_check(str_contains((string)$page, 'kcmc_private_headers()'), 'event creation is private and no-store');
event_create_check(str_contains((string)$page, 'kcmc_verify_csrf'), 'event creation validates CSRF');
event_create_check(str_contains((string)$page, "kcmc_random_id('event')"), 'event creation assigns a random stable event ID');
event_create_check(str_contains((string)$page, 'kcmc_write_content('), 'event creation writes through standard content writer');
event_create_check(str_contains((string)$page, 'kcmc_prune_content_backups('), 'event creation runs automatic backup retention');
event_create_check(str_contains((string)$page, "kcmc_audit('event.created'"), 'event creation writes a dedicated audit event');

$index = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/index.php');
event_create_check(is_string($index) && str_contains($index, "admin/event-create.php"), 'Publishing Desk exposes an Add Event control');

echo "Event creation contract checks passed.\n";
