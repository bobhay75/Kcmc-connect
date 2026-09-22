<?php
declare(strict_types=1);

$root = dirname(__DIR__);
$endpoint = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/audit-export.php');
$auditPage = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/audit.php');
$csvLib = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/lib/private-csv.php');

function audit_csv_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: $message\n");
        exit(1);
    }
    fwrite(STDOUT, "PASS: $message\n");
}

audit_csv_check(is_string($endpoint), 'audit export endpoint exists');
audit_csv_check(str_contains($endpoint, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'export requires administrator role');
audit_csv_check(str_contains($endpoint, 'kcmc_audit_recent_rows'), 'export reuses privacy-minimized audit rows');
audit_csv_check(str_contains($endpoint, 'KCMC_AUDIT_VIEW_MAX_ROWS'), 'export is bounded to the audit-view row limit');
audit_csv_check(str_contains($endpoint, 'kcmc_csv_download'), 'export uses private CSV download helper');
audit_csv_check(str_contains($endpoint, "['Timestamp UTC', 'Event', 'Actor', 'Visible context']"), 'export columns are explicitly allow-listed');

foreach (['ip_hash', 'actor_id', 'token_hash', 'push endpoint', 'prayer text', 'password_hash'] as $forbidden) {
    audit_csv_check(!str_contains(strtolower($endpoint), strtolower($forbidden)), 'endpoint omits private field marker: ' . $forbidden);
}

audit_csv_check(is_string($csvLib) && str_contains($csvLib, "['=', '+', '-', '@']"), 'shared CSV helper neutralizes spreadsheet formula prefixes');
audit_csv_check(is_string($auditPage) && str_contains($auditPage, 'audit-export.php'), 'Audit History links to CSV export');
audit_csv_check(str_contains($auditPage, 'Download CSV'), 'Audit History exposes clear export control');

fwrite(STDOUT, "Audit CSV export contract passed.\n");
