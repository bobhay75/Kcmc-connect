<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/timeclock.php';

kcmc_private_headers();
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
$total = array_sum(array_map(fn($e)=>(int)($e['net_minutes']??0),$entries));
$categoryTotals=[];foreach($entries as $entry){$cat=(string)($entry['category']??'Other');$categoryTotals[$cat]=($categoryTotals[$cat]??0)+(int)($entry['net_minutes']??0);}ksort($categoryTotals);
function tcp_local(string $iso): string { if($iso==='')return '—';$d=new DateTimeImmutable($iso);return $d->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('M j, Y g:i A'); }
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>KCMC Time Card • <?=kcmc_h($name)?></title><style>
body{font-family:Arial,sans-serif;color:#111;margin:28px}h1,h2{margin:.3em 0}.meta{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:18px 0}.meta div{border:1px solid #bbb;padding:10px}table{width:100%;border-collapse:collapse;margin-top:18px;font-size:13px}th,td{border:1px solid #bbb;padding:8px;vertical-align:top;text-align:left}.totals{margin-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:18px}.box{border:1px solid #bbb;padding:12px}.actions{margin:0 0 18px}@media print{.actions{display:none}body{margin:.4in}a{color:#000;text-decoration:none}}@media(max-width:700px){.meta,.totals{grid-template-columns:1fr}table{font-size:11px}}
</style></head><body><div class="actions"><a href="<?=kcmc_h(kcmc_url('admin/timecards.php'))?>">← Time Cards</a> <button onclick="window.print()">Print / Save PDF</button></div><h1>Kimberling City Methodist Church</h1><h2>Approved Employee Time Card</h2><div class="meta"><div><strong>Employee</strong><br><?=kcmc_h($name)?></div><div><strong>Pay period</strong><br><?=kcmc_h($start)?> through <?=kcmc_h($end)?></div><div><strong>Submitted</strong><br><?=kcmc_h((string)($period['submitted_at']??'—'))?></div><div><strong>Approved</strong><br><?=kcmc_h((string)($period['approved_at']??'—'))?></div></div><table><thead><tr><th>Date</th><th>Clock In</th><th>Clock Out</th><th>Break</th><th>Net</th><th>Category</th><th>Description</th></tr></thead><tbody><?php foreach($entries as $entry):$gross=!empty($entry['clock_out_at'])?kcmc_timeclock_minutes((string)$entry['clock_in_at'],(string)$entry['clock_out_at']):0;$net=(int)($entry['net_minutes']??0);?><tr><td><?=kcmc_h((string)$entry['work_date'])?></td><td><?=kcmc_h(tcp_local((string)$entry['clock_in_at']))?></td><td><?=kcmc_h(tcp_local((string)($entry['clock_out_at']??'')))?></td><td><?=max(0,$gross-$net)?> min</td><td><?=number_format($net/60,2)?> h</td><td><?=kcmc_h((string)($entry['category']??''))?></td><td><?=kcmc_h((string)($entry['description']??''))?></td></tr><?php endforeach; ?></tbody></table><div class="totals"><div class="box"><strong>Category totals</strong><?php foreach($categoryTotals as $cat=>$minutes):?><p><?=kcmc_h($cat)?>: <?=number_format($minutes/60,2)?> h</p><?php endforeach; ?></div><div class="box"><strong>Total net hours</strong><p style="font-size:1.5rem"><?=number_format($total/60,2)?> hours</p><p>Employee certification: <?=kcmc_h((string)($period['submitted_at']??'—'))?></p><p>Reviewer approval: <?=kcmc_h((string)($period['approved_at']??'—'))?></p></div></div></body></html>
