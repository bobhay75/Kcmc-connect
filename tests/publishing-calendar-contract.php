<?php
declare(strict_types=1);

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';

function expect_same(mixed $expected, mixed $actual, string $message): void {
    if ($expected !== $actual) {
        fwrite(STDERR, "FAIL: {$message}\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true) . "\n");
        exit(1);
    }
}

foreach ([
    '2026-09-20' => true,
    '2026-02-28' => true,
    '2026-02-29' => false,
    '2026-13-01' => false,
    '2026-9-20' => false,
    '' => false,
] as $date => $expected) {
    expect_same($expected, kcmc_valid_event_date($date), "Event date validation for {$date}.");
}

foreach ([
    '' => null,
    '8:00 AM' => 480,
    '12:00 PM' => 720,
    '12:00 AM' => 0,
    '5:17 PM' => 1037,
    '1:05 pm' => 785,
    '13:00 PM' => null,
    '5:60 PM' => null,
    '5 PM' => null,
    '17:00' => null,
] as $time => $expected) {
    expect_same($expected, kcmc_event_time_minutes($time), "Event time parsing for {$time}.");
}

// Keep visibility fixtures relative to the runtime clock so this contract does
// not start failing merely because the calendar date advanced.
$now = time();
$content = [
    'events' => [
        [
            'id' => 'published',
            'date' => date('Y-m-d', $now),
            'time' => '8:00 AM',
            'status' => 'published',
            'expires_at' => gmdate('c', $now + 86400),
        ],
        [
            'id' => 'expired',
            'date' => date('Y-m-d', $now - 172800),
            'time' => '8:00 AM',
            'status' => 'published',
            'expires_at' => gmdate('c', $now - 86400),
        ],
        [
            'id' => 'hidden',
            'date' => date('Y-m-d', $now + 86400),
            'time' => '8:00 AM',
            'status' => 'hidden',
        ],
    ],
];
$active = kcmc_active_items($content['events']);
$activeIds = array_map(static fn(array $event): string => (string)$event['id'], $active);
expect_same(['published'], $activeIds, 'Only currently published, unexpired events are public.');

$repo = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/save.php');
if (!is_string($repo)) {
    fwrite(STDERR, "FAIL: Could not read Publishing Desk save route.\n");
    exit(1);
}
foreach ([
    "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
    "kcmc_verify_csrf",
    "kcmc_valid_event_date",
    "kcmc_event_time_minutes",
    "Event end time must be later than the start time.",
    'kcmc_local_datetime_iso($ex,true)',
] as $needle) {
    if (!str_contains($repo, $needle)) {
        fwrite(STDERR, "FAIL: Publishing Desk contract missing: {$needle}\n");
        exit(1);
    }
}

echo "KCMC Publishing Desk and calendar contract checks passed.\n";
