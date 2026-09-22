<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/timeclock.php';
require_once __DIR__ . '/../lib/private-csv.php';

kcmc_require_role(['pastor_admin', 'recovery_admin']);
$userId = trim((string)($_GET['user'] ?? ''));
$start = trim((string)($_GET['start'] ?? ''));
$end = trim((string)($_GET['end'] ?? ''));
$period = kcmc_timeclock_period_record($userId, $start, $end);
if (!$period || ($period['status'] ?? '') !== 'approved') { http_response_code(404); exit('Approved time card not found.'); }
$employee = kcmc_find_user_by_id($userId);
$name = trim((string)($employee['display_name'] ?? 'Employee'));
$entries = kcmc_timeclock_period_entries($userId, $start, $end);
usort($entries, fn($a,$b)=>strcmp((string)($a['clock_in_at']??''),(string)($b['clock_in_at']??'')));
$rows = [];
foreach ($entries as $entry) {
    $gross = !empty($entry['clock_out_at']) ? kcmc_timeclock_minutes((string)$entry['clock_in_at'], (string)$entry['clock_out_at']) : 0;
    $net = (int)($entry['net_minutes'] ?? 0);
    $rows[] = [
        'Work Date' => (string)($entry['work_date'] ?? ''),
        'Clock In UTC' => (string)($entry['clock_in_at'] ?? ''),
        'Clock Out UTC' => (string)($entry['clock_out_at'] ?? ''),
        'Break Minutes' => max(0, $gross - $net),
        'Net Hours' => number_format($net / 60, 2, '.', ''),
        'Category' => (string)($entry['category'] ?? ''),
        'Work Description' => (string)($entry['description'] ?? ''),
    ];
}
$total = array_sum(array_map(fn($e)=>(int)($e['net_minutes']??0),$entries));
$rows[] = ['Work Date'=>'TOTAL','Clock In UTC'=>'','Clock Out UTC'=>'','Break Minutes'=>'','Net Hours'=>number_format($total/60,2,'.',''),'Category'=>'','Work Description'=>''];
kcmc_csv_download('kcmc-timecard-' . $start . '-to-' . $end . '.csv', ['Work Date','Clock In UTC','Clock Out UTC','Break Minutes','Net Hours','Category','Work Description'], $rows);
