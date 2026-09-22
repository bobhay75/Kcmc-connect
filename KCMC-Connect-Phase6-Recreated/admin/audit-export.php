<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/audit-history.php';
require_once __DIR__ . '/../lib/private-csv.php';

kcmc_require_role(['pastor_admin', 'recovery_admin']);
$userStore = kcmc_users_store();
$actorNames = kcmc_audit_actor_names($userStore);
$rows = kcmc_audit_recent_rows(KCMC_AUDIT_LOG, $actorNames, KCMC_AUDIT_VIEW_MAX_ROWS);

$export = [];
foreach ($rows as $row) {
    if (!is_array($row)) continue;
    $contextParts = [];
    foreach (($row['context'] ?? []) as $key => $value) {
        $contextParts[] = ucwords(str_replace('_', ' ', (string)$key)) . ': ' . (string)$value;
    }
    $export[] = [
        'Timestamp UTC' => (string)($row['at'] ?? ''),
        'Event' => (string)($row['label'] ?? ''),
        'Actor' => (string)($row['actor'] ?? ''),
        'Visible context' => implode('; ', $contextParts),
    ];
}

kcmc_csv_download(
    'kcmc-audit-history-' . gmdate('Y-m-d-His') . '.csv',
    ['Timestamp UTC', 'Event', 'Actor', 'Visible context'],
    $export
);
