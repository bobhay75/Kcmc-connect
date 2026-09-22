<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/event-rsvp.php';
require_once __DIR__ . '/../lib/inbox-follow-up.php';
require_once __DIR__ . '/../lib/private-csv.php';

kcmc_require_role(['pastor_admin', 'recovery_admin']);
$status = kcmc_csv_status_filter($_GET['status'] ?? 'all');
$rows = kcmc_csv_filter_rows(kcmc_event_rsvp_recent(500), $status);
$export = [];
foreach ($rows as $row) {
    $export[] = [
        (string)($row['event'] ?? ''),
        (string)($row['event_date'] ?? ''),
        (string)($row['name'] ?? ''),
        (string)($row['email'] ?? ''),
        (string)($row['message'] ?? ''),
        (string)($row['submitted_at'] ?? ''),
        kcmc_inbox_status_label(kcmc_inbox_status($row['status'] ?? null)),
    ];
}

kcmc_csv_download(
    'kcmc-event-rsvps-' . gmdate('Y-m-d') . '-' . $status . '.csv',
    ['Event', 'Event Date', 'Name', 'Email', 'Note', 'Received UTC', 'Follow-up'],
    $export
);
