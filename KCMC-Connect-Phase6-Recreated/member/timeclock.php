<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/timeclock.php';

kcmc_private_headers();
$user = kcmc_require_login();
$error = '';
$message = '';
[$periodStart, $periodEnd] = kcmc_timeclock_period();

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        http_response_code(403);
        $error = 'Your session expired. Reload and try again.';
    } else {
        $action = (string)($_POST['action'] ?? '');
        try {
            if ($action === 'submit_period') {
                if ((string)($_POST['certify'] ?? '') !== '1') throw new RuntimeException('Review and certify the pay period before submitting it.');
                kcmc_timeclock_submit_period((string)$user['id'], $periodStart, $periodEnd);
                kcmc_audit('timeclock.period_submitted', ['action' => 'submit_period', 'count' => 1]);
                $message = 'Pay period submitted for review.';
            } else {
                kcmc_timeclock_mutate((string)$user['id'], $action, $_POST);
                kcmc_audit('timeclock.' . $action, ['action' => $action, 'count' => 1]);
                $message = match ($action) {
                    'clock_in' => 'Clocked in using the server time.',
                    'break_start' => 'Break started using the server time.',
                    'break_end' => 'Break ended using the server time.',
                    'clock_out' => 'Clocked out and saved today’s work description.',
                    default => 'Time clock updated.',
                };
            }
        } catch (Throwable $e) {
            $error = $e->getMessage();
        }
    }
}

$open = kcmc_timeclock_open_entry((string)$user['id']);
$entries = kcmc_timeclock_period_entries((string)$user['id'], $periodStart, $periodEnd);
usort($entries, fn($a, $b) => strcmp((string)($b['clock_in_at'] ?? ''), (string)($a['clock_in_at'] ?? '')));
$periodRecord = kcmc_timeclock_period_record((string)$user['id'], $periodStart, $periodEnd);
$totalMinutes = array_sum(array_map(fn($e) => (int)($e['net_minutes'] ?? 0), $entries));
$openBreak = false;
if ($open) foreach (($open['breaks'] ?? []) as $b) if (is_array($b) && empty($b['end_at'])) $openBreak = true;
$locked = in_array((string)($periodRecord['status'] ?? ''), ['submitted', 'approved'], true);
function tc_local(string $iso): string { if ($iso === '') return '—'; $d = new DateTimeImmutable($iso); return $d->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('M j, g:i A'); }
function tc_hours(int $minutes): string { return number_format($minutes / 60, 2); }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Time Clock • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.tc-shell{width:min(920px,calc(100% - 28px));margin:24px auto 80px}.tc-card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:20px;margin:16px 0}.tc-actions{display:flex;gap:10px;flex-wrap:wrap}.tc-actions form{margin:0}.tc-table{display:grid;gap:10px}.tc-row{display:grid;grid-template-columns:1fr 1fr .7fr 1.2fr;gap:10px;padding:12px;border:1px solid #e2e8ec;border-radius:12px}.tc-row small{display:block;color:#607080}.tc-form label{display:block;font-weight:700}.tc-form textarea,.tc-form select{width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;font:inherit}.tc-form textarea{min-height:95px}.tc-status{display:inline-block;border-radius:999px;padding:5px 9px;background:#eef2f4;font-weight:800}.tc-total{font-size:1.5rem;font-weight:900}.tc-note{color:#607080}.tc-shell :is(a,button,select,textarea,input):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:700px){.tc-row{grid-template-columns:1fr}.tc-actions{display:grid}.tc-actions form,.tc-actions button{width:100%}}
</style></head><body class="portal-body"><main class="tc-shell">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a><p class="eyebrow">EMPLOYEE TIME</p><h1>Time Clock</h1><p class="portal-lead">Pay period <?=kcmc_h($periodStart)?> through <?=kcmc_h($periodEnd)?>. Punch times are recorded by the KCMC server.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($message): ?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif; ?>
<section class="tc-card"><p class="eyebrow">CURRENT STATUS</p><?php if ($locked): ?><h2>Period <?=kcmc_h(ucfirst((string)$periodRecord['status']))?></h2><p>This pay period is locked while it is <?=kcmc_h((string)$periodRecord['status'])?>.</p><?php elseif (!$open): ?><h2>You are clocked out.</h2><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="clock_in"><button class="btn gold" type="submit">Clock In</button></form><?php else: ?><h2>Clocked in <?=kcmc_h(tc_local((string)$open['clock_in_at']))?></h2><p class="tc-note"><?=$openBreak?'A break is currently running.':'Shift is running.'?></p><div class="tc-actions"><?php if ($openBreak): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="break_end"><button class="btn secondary" type="submit">End Break</button></form><?php else: ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="break_start"><button class="btn secondary" type="submit">Start Break</button></form><?php endif; ?></div><?php if (!$openBreak): ?><form class="tc-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="clock_out"><label>Work category<select name="category" required><option value="">Choose category</option><?php foreach(kcmc_timeclock_categories() as $cat): ?><option><?=kcmc_h($cat)?></option><?php endforeach; ?></select></label><label>What did you work on today?<textarea name="description" maxlength="1000" required></textarea></label><button class="btn gold" type="submit">Clock Out</button></form><?php endif; ?><?php endif; ?></section>
<section class="tc-card"><p class="eyebrow">PAY PERIOD</p><h2>Your time card</h2><p class="tc-total"><?=kcmc_h(tc_hours($totalMinutes))?> hours</p><?php if (!$entries): ?><p>No shifts recorded in this period.</p><?php else: ?><div class="tc-table"><?php foreach($entries as $entry): ?><article class="tc-row"><div><small>Work date</small><strong><?=kcmc_h((string)$entry['work_date'])?></strong></div><div><small>In / Out</small><?=kcmc_h(tc_local((string)$entry['clock_in_at']))?><br><?=kcmc_h(tc_local((string)($entry['clock_out_at']??'')))?></div><div><small>Net</small><strong><?=kcmc_h(tc_hours((int)($entry['net_minutes']??0)))?> h</strong></div><div><small>Work</small><strong><?=kcmc_h((string)($entry['category']??''))?></strong><br><?=kcmc_h((string)($entry['description']??''))?></div></article><?php endforeach; ?></div><?php endif; ?>
<?php if (!$locked && !$open && $entries): ?><form method="post" style="margin-top:18px"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="submit_period"><label class="portal-check"><input type="checkbox" name="certify" value="1" required><span>I reviewed this pay period and certify that the recorded time and work descriptions are complete.</span></label><button class="btn gold" type="submit">Submit Pay Period</button></form><?php endif; ?>
<?php if (($periodRecord['status']??'')==='returned'): ?><p class="portal-alert warning">Returned for review: <?=kcmc_h((string)($periodRecord['return_reason']??''))?></p><?php endif; ?></section>
</main></body></html>
