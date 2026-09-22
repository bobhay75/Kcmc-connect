<?php
declare(strict_types=1);

$tmp = sys_get_temp_dir() . '/kcmc-private-csv-' . bin2hex(random_bytes(5));
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) throw new RuntimeException('Could not create CSV test storage.');
putenv('KCMC_PRIVATE_DATA_DIR=' . $tmp);

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/connection-intake.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/event-rsvp.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/inbox-follow-up.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/private-csv.php';

function csv_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

foreach (['=SUM(A1:A2)', '+cmd', '-2+3', '@hyperlink'] as $dangerous) {
    csv_check(str_starts_with(kcmc_csv_safe_cell($dangerous), "'"), 'spreadsheet formula-like cell is neutralized: ' . $dangerous[0]);
}
csv_check(kcmc_csv_safe_cell('Normal text') === 'Normal text', 'ordinary CSV cell remains unchanged');
csv_check(kcmc_csv_safe_cell("Line 1\r\nLine 2") === "Line 1\nLine 2", 'CSV cell normalizes line endings');

csv_check(kcmc_csv_status_filter('CONTACTED') === 'contacted', 'CSV status filter normalizes allowed status');
csv_check(kcmc_csv_status_filter('anything') === 'all', 'unknown CSV status falls back to all');
$sample = [
    ['id'=>'a'],
    ['id'=>'b','status'=>'contacted'],
    ['id'=>'c','status'=>'closed'],
];
csv_check(count(kcmc_csv_filter_rows($sample, 'all')) === 3, 'all-status CSV includes every bounded row');
csv_check(count(kcmc_csv_filter_rows($sample, 'new')) === 1, 'legacy missing status exports as New');
csv_check(count(kcmc_csv_filter_rows($sample, 'contacted')) === 1, 'Contacted filter selects only contacted rows');

$connectionExport = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/connections-export.php');
csv_check(is_string($connectionExport) && str_contains($connectionExport, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'connection CSV requires administrator role');
csv_check(str_contains((string)$connectionExport, 'kcmc_connection_recent(500)'), 'connection CSV is bounded to newest 500 rows');
csv_check(str_contains((string)$connectionExport, 'kcmc_csv_status_filter'), 'connection CSV supports validated follow-up filtering');
csv_check(str_contains((string)$connectionExport, 'kcmc_csv_download'), 'connection CSV uses centralized private download writer');
csv_check(!str_contains((string)$connectionExport, "['id']") && !str_contains((string)$connectionExport, 'status_updated_at'), 'connection CSV excludes private row IDs and internal status timestamps');

$rsvpExport = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/rsvps-export.php');
csv_check(is_string($rsvpExport) && str_contains($rsvpExport, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'RSVP CSV requires administrator role');
csv_check(str_contains((string)$rsvpExport, 'kcmc_event_rsvp_recent(500)'), 'RSVP CSV is bounded to newest 500 rows');
csv_check(str_contains((string)$rsvpExport, 'kcmc_csv_status_filter'), 'RSVP CSV supports validated follow-up filtering');
csv_check(!str_contains((string)$rsvpExport, "['id']") && !str_contains((string)$rsvpExport, 'status_updated_at'), 'RSVP CSV excludes private row IDs and internal status timestamps');

$helper = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/private-csv.php');
csv_check(is_string($helper) && str_contains($helper, "kcmc_private_headers()"), 'CSV download applies private/no-store headers');
csv_check(str_contains((string)$helper, "Content-Type: text/csv; charset=UTF-8"), 'CSV download sets explicit text/csv content type');
csv_check(str_contains((string)$helper, 'Content-Disposition: attachment'), 'CSV download forces attachment disposition');
csv_check(str_contains((string)$helper, "\\xEF\\xBB\\xBF"), 'CSV download writes UTF-8 BOM for spreadsheet compatibility');
csv_check(str_contains((string)$helper, "['=', '+', '-', '@']"), 'CSV helper explicitly neutralizes formula-leading characters');

foreach (glob($tmp . '/*') ?: [] as $path) @unlink($path);
@rmdir($tmp);
putenv('KCMC_PRIVATE_DATA_DIR');
echo "Private inbox CSV contract checks passed.\n";
