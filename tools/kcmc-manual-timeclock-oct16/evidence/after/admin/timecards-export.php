<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/payroll.php';
require_once __DIR__ . '/../lib/timeclock.php';
require_once __DIR__ . '/../lib/private-csv.php';

kcmc_private_headers();
kcmc_require_payroll_reviewer();
$userId = trim((string)($_GET['user'] ?? ''));
$start = trim((string)($_GET['start'] ?? ''));
$end = trim((string)($_GET['end'] ?? ''));
$report = kcmc_timeclock_period_report($userId, $start, $end);
if ($report === null) { http_response_code(404); exit('Recorded time card not found.'); }
$entries = $report['entries'];
$rows = [];
foreach ($entries as $entry) {
    $unfinished = ($entry['status'] ?? '') === 'open' || empty($entry['clock_out_at']);
    $gross = !$unfinished ? kcmc_timeclock_minutes((string)$entry['clock_in_at'], (string)$entry['clock_out_at']) : 0;
    $net = $unfinished ? 0 : (int)($entry['net_minutes'] ?? 0);
    $rows[] = [
        'Work Date' => (string)($entry['work_date'] ?? ''),
        'Clock In UTC' => (string)($entry['clock_in_at'] ?? ''),
        'Clock Out UTC' => (string)($entry['clock_out_at'] ?? ''),
        'Status' => $unfinished ? 'Unfinished - excluded from total' : 'Completed',
        'Break Minutes' => $unfinished ? '' : max(0, $gross - $net),
        'Net Hours' => $unfinished ? '' : number_format($net / 60, 2, '.', ''),
        'Category' => (string)($entry['category'] ?? ''),
        'Work Description' => (string)($entry['description'] ?? ''),
    ];
}
$total = (int)$report['total_minutes'];
$rows[] = ['Work Date'=>'TOTAL','Clock In UTC'=>'','Clock Out UTC'=>'','Status'=>'Completed shifts only','Break Minutes'=>'','Net Hours'=>number_format($total/60,2,'.',''),'Category'=>'','Work Description'=>''];
kcmc_csv_download('kcmc-timecard-' . $start . '-to-' . $end . '.csv', ['Work Date','Clock In UTC','Clock Out UTC','Status','Break Minutes','Net Hours','Category','Work Description'], $rows);
