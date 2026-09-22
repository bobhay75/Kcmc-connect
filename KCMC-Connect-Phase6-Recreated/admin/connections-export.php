<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/connection-intake.php';
require_once __DIR__ . '/../lib/inbox-follow-up.php';
require_once __DIR__ . '/../lib/private-csv.php';

kcmc_require_role(['pastor_admin', 'recovery_admin']);
$status = kcmc_csv_status_filter($_GET['status'] ?? 'all');
$rows = kcmc_csv_filter_rows(kcmc_connection_recent(500), $status);
$labels = ['visit' => 'Plan a Visit', 'serve' => 'Serve', 'groups' => 'Find Your People'];
$export = [];
foreach ($rows as $row) {
    $kind = (string)($row['kind'] ?? '');
    $detail = trim((string)($row['service'] ?? '')) ?: trim((string)($row['interest'] ?? ''));
    $export[] = [
        $labels[$kind] ?? ucfirst($kind),
        (string)($row['name'] ?? ''),
        (string)($row['email'] ?? ''),
        (string)($row['phone'] ?? ''),
        $detail,
        (string)($row['message'] ?? ''),
        (string)($row['submitted_at'] ?? ''),
        kcmc_inbox_status_label(kcmc_inbox_status($row['status'] ?? null)),
    ];
}

kcmc_csv_download(
    'kcmc-connections-' . gmdate('Y-m-d') . '-' . $status . '.csv',
    ['Type', 'Name', 'Email', 'Phone', 'Service / Interest', 'Note', 'Received UTC', 'Follow-up'],
    $export
);
