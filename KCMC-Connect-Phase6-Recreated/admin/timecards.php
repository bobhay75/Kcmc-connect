<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/payroll.php';
require_once __DIR__ . '/../lib/timeclock.php';

kcmc_private_headers();
$reviewer = kcmc_require_payroll_reviewer();
$workHome = kcmc_can_publish($reviewer) || kcmc_can_view_private_prayers($reviewer);
$backPath = $workHome ? 'admin/home.php' : 'member/';
$backLabel = $workHome ? '← Admin home' : '← Account home';
$error = '';
$message = '';
try {
    $closed = kcmc_timeclock_close_due_periods();
    if ($closed > 0) kcmc_audit('timeclock.periods_queued', ['action' => 'period_end', 'count' => $closed]);
} catch (Throwable $errorDuringClosure) {
    $error = 'Automatic period-end totals could not be prepared. Existing punches are preserved; try again or review the server task.';
}

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        http_response_code(403);
        $error = 'Your session expired. Reload and try again.';
    } else {
        $action = (string)($_POST['action'] ?? '');
        try {
            if ($action === 'adjust_entry') {
                $entryId = trim((string)($_POST['entry_id'] ?? ''));
                $minutes = kcmc_timeclock_hours_to_minutes(trim((string)($_POST['adjusted_hours'] ?? '')));
                if ($minutes === null) throw new RuntimeException('Adjusted time must be a number between 0 and 24 hours.');
                $record = kcmc_timeclock_adjust_entry($entryId, (string)$reviewer['id'], $minutes, (string)($_POST['reason'] ?? ''));
                kcmc_audit('timeclock.entry_adjusted', ['action' => 'adjust_entry', 'count' => 1]);
                $message = 'Time entry adjusted from ' . number_format(((int)$record['previous_net_minutes']) / 60, 2) . ' to ' . number_format(((int)$record['new_net_minutes']) / 60, 2) . ' hours.';
            } elseif ($action === 'apply_correction') {
                kcmc_timeclock_apply_correction(trim((string)($_POST['request_id'] ?? '')), (string)$reviewer['id'], $_POST);
                kcmc_audit('timeclock.correction_applied', ['action' => 'apply_correction', 'count' => 1]);
                $message = 'Correction applied. The original and corrected values were preserved in private correction history.';
            } elseif ($action === 'reject_correction') {
                kcmc_timeclock_reject_correction(trim((string)($_POST['request_id'] ?? '')), (string)$reviewer['id'], (string)($_POST['reason'] ?? ''));
                kcmc_audit('timeclock.correction_rejected', ['action' => 'reject_correction', 'count' => 1]);
                $message = 'Correction request rejected with an administrator response.';
            } else {
                $userId = trim((string)($_POST['user_id'] ?? ''));
                $start = trim((string)($_POST['start'] ?? ''));
                $end = trim((string)($_POST['end'] ?? ''));
                if ($action !== 'submit_period' && $userId === (string)$reviewer['id'] && !kcmc_is_designated_owner($reviewer)) throw new RuntimeException('A reviewer cannot approve or return their own time card.');
                if (!kcmc_find_user_by_id($userId)) throw new RuntimeException('Employee account not found.');
                $record = $action === 'submit_period'
                    ? kcmc_timeclock_submit_period($userId, $start, $end)
                    : kcmc_timeclock_review_period($userId, $start, $end, (string)$reviewer['id'], $action, (string)($_POST['reason'] ?? ''));
                kcmc_audit('timeclock.period_reviewed', ['action' => $action, 'status' => (string)$record['status'], 'count' => 1]);
                $message = match ($action) { 'submit_period' => 'Time card prepared for administrator review.', 'approve' => 'Time card approved.', default => 'Time card returned for administrator follow-up.' };
            }
        } catch (Throwable $e) { $error = $e->getMessage(); }
    }
}

$store = kcmc_timeclock_store();
$periods = array_values(array_filter($store['periods'] ?? [], 'is_array'));
$knownPeriods = [];
foreach ($periods as $period) $knownPeriods[(string)($period['user_id']??'').'|'.(string)($period['start']??'')] = true;
foreach (($store['entries']??[]) as $entry) {
    if (!is_array($entry) || empty($entry['user_id']) || empty($entry['work_date'])) continue;
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', (string)$entry['work_date'], new DateTimeZone(KCMC_LOCAL_TIMEZONE));
    if ($date === false || $date->format('Y-m-d') !== $entry['work_date']) continue;
    [$start,$end] = kcmc_timeclock_period($date);
    $key = (string)$entry['user_id'].'|'.$start;
    if (isset($knownPeriods[$key])) continue;
    $periods[] = ['user_id'=>(string)$entry['user_id'],'start'=>$start,'end'=>$end,'status'=>'in_progress'];
    $knownPeriods[$key] = true;
}
usort($periods, fn($a, $b) => strcmp((string)($b['submitted_at'] ?? ''), (string)($a['submitted_at'] ?? '')));
$pendingCorrections = kcmc_timeclock_pending_corrections();
$names = [];
foreach (kcmc_users() as $u) $names[(string)$u['id']] = (string)($u['display_name'] ?? 'Employee');
function tca_hours(int $minutes): string { return number_format($minutes / 60, 2); }
function tca_adjustments(array $store, string $entryId): array { $rows=array_values(array_filter($store['adjustments']??[],fn($a)=>is_array($a)&&($a['entry_id']??'')===$entryId));usort($rows,fn($a,$b)=>strcmp((string)($b['adjusted_at']??''),(string)($a['adjusted_at']??'')));return $rows; }
function tca_entry(array $store, string $entryId): ?array { foreach(($store['entries']??[]) as $entry)if(is_array($entry)&&($entry['id']??'')===$entryId)return $entry;return null; }
function tca_local_input(string $iso): string { if($iso==='')return '';$d=new DateTimeImmutable($iso);return $d->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('Y-m-d\TH:i'); }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Time Cards • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.tc-admin{width:min(1100px,calc(100% - 28px));margin:24px auto 80px}.tc-list{display:grid;gap:14px}.tc-card{background:var(--kcmc-panel, #fff);color:var(--kcmc-text, #17324c);border:1px solid var(--kcmc-line, #dce3e7);border-radius:18px;padding:20px}.tc-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.tc-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.tc-meta div{background:var(--kcmc-panel-muted, #f5f8fa);border-radius:12px;padding:10px}.tc-meta small,.shift-row small{display:block;color:var(--kcmc-muted, #607080)}.tc-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}.tc-actions form{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end}.tc-actions label,.adjust-form label,.correction-form label{font-weight:700}.tc-actions input,.adjust-form input,.correction-form input,.correction-form select,.correction-form textarea{padding:9px;border:1px solid var(--kcmc-control-line, #cbd5dc);border-radius:8px}.status{display:inline-block;padding:5px 9px;border-radius:999px;background:var(--kcmc-panel-muted, #eef2f4);font-weight:800}.status.approved{background:var(--kcmc-success-bg, #e6f3e7);color:var(--kcmc-success, #215b2d)}.status.submitted,.status.pending{background:var(--kcmc-warning-bg, #fff3d6);color:var(--kcmc-warning, #77510c)}.status.returned,.status.rejected{background:var(--kcmc-error-bg, #fbe4e4);color:var(--kcmc-error, #7d2525)}.shift-list{display:grid;gap:10px;margin:18px 0}.shift-row{border:1px solid var(--kcmc-line, #e2e8ec);border-radius:12px;padding:14px}.shift-main{display:grid;grid-template-columns:1fr 1.2fr .7fr 2fr;gap:10px}.adjust-form{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-top:12px;padding-top:12px;border-top:1px solid var(--kcmc-line, #edf0f2)}.adjustment-history{margin:10px 0 0;padding-left:18px;color:var(--kcmc-muted, #536273)}.correction-list{display:grid;gap:14px;margin:16px 0 26px}.correction-card{border:1px solid var(--kcmc-gold, #e3c36a);background:var(--kcmc-warning-bg, #fffaf0);border-radius:16px;padding:16px}.correction-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}.correction-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.correction-form label{display:grid;gap:5px}.correction-form .wide{grid-column:1/-1}.correction-form textarea{min-height:82px;resize:vertical}.correction-actions{display:flex;gap:10px;flex-wrap:wrap;grid-column:1/-1}.correction-actions form{display:flex;gap:8px;flex-wrap:wrap}.correction-mark{display:inline-block;margin-left:6px;border-radius:999px;padding:3px 7px;background:var(--kcmc-info-bg, #e8eef8);color:var(--kcmc-info, #284c7a);font-size:.8rem;font-weight:800}.tc-admin :is(a,button,input,select,textarea):focus-visible{outline:3px solid var(--kcmc-gold, #174d75);outline-offset:3px}@media(max-width:720px){.tc-meta,.correction-grid,.correction-form{grid-template-columns:1fr}.tc-actions,.tc-actions form,.adjust-form,.correction-actions,.correction-actions form{display:grid;width:100%}.tc-actions input,.tc-actions button,.tc-actions a,.adjust-form input,.adjust-form button,.correction-form input,.correction-form select,.correction-form textarea,.correction-form button,.correction-actions input,.correction-actions button{width:100%;box-sizing:border-box}.shift-main{grid-template-columns:1fr}.correction-form .wide{grid-column:1}}

/* KCMC_READABILITY_FIX_V1_20261001 BEGIN */

body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) {color:var(--kcmc-text, #17324c);--ink:var(--kcmc-text, #17324c);--muted:var(--kcmc-muted, #536273);--line:var(--kcmc-muted, #607080);color-scheme:light}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) .eyebrow {color:var(--kcmc-gold, #715017)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) :is(.portal-fine,.portal-lead,.muted,.tc-note,.audit-time,.health-meta) {color:var(--kcmc-muted, #536273)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) .btn.secondary {color:var(--kcmc-text, #17324c);background:var(--kcmc-panel, #fff);border-color:var(--kcmc-muted, #536273)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) .portal-link-button {color:var(--kcmc-gold, #174d75)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) :is(input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]),select,textarea) {color:var(--kcmc-text, #17324c);background:var(--kcmc-panel, #fff);border:1px solid var(--kcmc-muted, #607080);caret-color:var(--kcmc-text, #17324c)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) :is(input,textarea)::placeholder {color:var(--kcmc-muted, #536273);opacity:1}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) .portal-alert.warning {color:var(--kcmc-warning, #77510c);background:var(--kcmc-warning-bg, #fff3d6);border-color:var(--kcmc-warning, #a06b12)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) .portal-alert.error {color:var(--kcmc-error, #7d2525);background:var(--kcmc-error-bg, #fbe4e4);border-color:var(--kcmc-error-line, #a33434)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) .portal-alert.success {color:var(--kcmc-success, #215b2d);background:var(--kcmc-success-bg, #e6f3e7);border-color:var(--kcmc-success, #2b7a46)}
body.portal-body :is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card) :is(a,button,input,select,textarea,summary):focus-visible {outline:3px solid var(--kcmc-gold, #174d75);outline-offset:3px}
body.portal-body .audit-toolbar .audit-time {color:#c5d4dc}
/* KCMC_READABILITY_FIX_V1_20261001 END */
</style><?php require_once __DIR__ . '/../lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
</head><body class="portal-body"><?php echo kcmc_screen_navigation('admin/home.php', true); ?><main class="tc-admin">
<nav class="tc-actions" aria-label="Page navigation"><a class="portal-back" href="<?=kcmc_h(kcmc_url($backPath))?>"><?=kcmc_h($backLabel)?></a><a class="portal-back" href="<?=kcmc_h(kcmc_url('index.php'))?>">Home</a></nav><p class="eyebrow">PAYROLL TURN-IN</p><h1>Employee Time Cards</h1><p class="portal-lead">Review employee totals, prepare or approve time cards, and handle correction requests. Closed pay periods enter this private review queue automatically when this screen or the scheduled period-end task runs. No payroll email is sent from this screen.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?><?php if ($message): ?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif; ?>

<?php if($pendingCorrections): ?><section class="tc-card"><p class="eyebrow">CORRECTION REQUESTS</p><h2>Pending employee corrections</h2><div class="correction-list"><?php foreach($pendingCorrections as $request): $entry=tca_entry($store,(string)($request['entry_id']??'')); if(!$entry)continue; $uid=(string)($request['user_id']??''); ?>
<article class="correction-card"><div class="tc-head"><div><strong><?=kcmc_h($names[$uid]??'Former or unknown employee')?></strong><p><?=kcmc_h((string)($request['reason']??''))?></p></div><span class="status pending">Pending</span></div>
<div class="correction-grid"><div><small>Recorded work date</small><strong><?=kcmc_h((string)($entry['work_date']??''))?></strong></div><div><small>Recorded net hours</small><strong><?=kcmc_h(tca_hours((int)($entry['net_minutes']??0)))?></strong></div><div><small>Recorded category</small><?=kcmc_h((string)($entry['category']??''))?></div><div><small>Requested</small><?=kcmc_h((string)($request['requested_at']??''))?></div></div>
<form class="correction-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="apply_correction"><input type="hidden" name="request_id" value="<?=kcmc_h((string)$request['id'])?>"><label>Corrected clock in<input type="datetime-local" name="clock_in" value="<?=kcmc_h(tca_local_input((string)($entry['clock_in_at']??'')))?>" required></label><label>Corrected clock out<input type="datetime-local" name="clock_out" value="<?=kcmc_h(tca_local_input((string)($entry['clock_out_at']??'')))?>" required></label><label>Unpaid break minutes<input type="number" name="break_minutes" min="0" max="1440" step="1" value="<?=kcmc_h((string)kcmc_timeclock_break_minutes($entry))?>" required></label><label>Work category<select name="category" required><?php foreach(kcmc_timeclock_categories() as $category): ?><option<?=$category===(string)($entry['category']??'')?' selected':''?>><?=kcmc_h($category)?></option><?php endforeach; ?></select></label><label class="wide">Work description (optional)<textarea name="description" maxlength="1000"><?=kcmc_h((string)($entry['description']??''))?></textarea></label><label class="wide">Administrator correction reason<textarea name="correction_reason" minlength="5" maxlength="500" required></textarea></label><div class="correction-actions"><button class="btn gold" type="submit">Apply correction</button></div></form>
<form class="correction-actions" method="post" style="margin-top:10px"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="reject_correction"><input type="hidden" name="request_id" value="<?=kcmc_h((string)$request['id'])?>"><input name="reason" minlength="5" maxlength="500" placeholder="Reason for rejecting request" required><button class="btn secondary" type="submit">Reject request</button></form></article><?php endforeach; ?></div></section><?php endif; ?>

<?php if (!$periods): ?><section class="tc-card"><p>No employee shifts have been recorded yet.</p></section><?php else: ?><section class="tc-list">
<?php foreach($periods as $period): $uid=(string)($period['user_id']??'');$start=(string)($period['start']??'');$end=(string)($period['end']??'');$status=(string)($period['status']??'submitted');$entries=kcmc_timeclock_period_entries($uid,$start,$end);$minutes=array_sum(array_map(fn($e)=>(int)($e['net_minutes']??0),$entries));$openCount=count(array_filter($entries,fn($e)=>($e['status']??'')==='open'||empty($e['clock_out_at']))); ?>
<article class="tc-card"><div class="tc-head"><div><h2><?=kcmc_h($names[$uid]??'Former or unknown employee')?></h2><p><?=kcmc_h($start)?> through <?=kcmc_h($end)?><?php if(!empty($period['correction_count'])): ?><span class="correction-mark"><?=kcmc_h((string)$period['correction_count'])?> correction<?=((int)$period['correction_count']===1?'':'s')?></span><?php endif; ?></p></div><span class="status <?=kcmc_h($status)?>"><?=kcmc_h(ucfirst(str_replace('_',' ',$status)))?></span></div>
<div class="tc-meta"><div><small>Shifts</small><strong><?=count($entries)?></strong></div><div><small>Total hours</small><strong><?=kcmc_h(tca_hours($minutes))?></strong></div><div><small>Submitted</small><strong><?=kcmc_h((string)($period['submitted_at']??'—'))?></strong></div><div><small>Approved</small><strong><?=kcmc_h((string)($period['approved_at']??'—'))?></strong></div></div>
<?php if ($openCount): ?><p class="portal-alert warning"><?=kcmc_h((string)$openCount)?> shift(s) still open. Recorded totals include completed shifts only; no clock-out time has been invented.</p><?php endif; ?>
<?php if (!empty($period['review_required'])): ?><p class="portal-alert warning">New punches were recorded after an earlier review. Prepare this card again before approval; prior review attribution is retained in private history.</p><?php endif; ?>
<?php if ($status==='returned'): ?><p class="portal-alert warning">Return reason: <?=kcmc_h((string)($period['return_reason']??''))?></p><?php endif; ?>
<div class="shift-list"><?php foreach($entries as $entry): $entryId=(string)($entry['id']??'');$history=tca_adjustments($store,$entryId);$correctionCount=kcmc_timeclock_entry_correction_count($entry); ?>
<section class="shift-row"><div class="shift-main"><div><small>Work date</small><strong><?=kcmc_h((string)($entry['work_date']??''))?></strong><?php if($correctionCount): ?><br><small><?=kcmc_h((string)$correctionCount)?> approved correction<?= $correctionCount===1?'':'s' ?></small><?php endif; ?></div><div><small>Category</small><?=kcmc_h((string)($entry['category']??''))?></div><div><small>Net hours</small><strong><?=kcmc_h(tca_hours((int)($entry['net_minutes']??0)))?></strong><?php if (!empty($entry['adjustment_count'])): ?><br><small>Adjusted <?=kcmc_h((string)$entry['adjustment_count'])?>×</small><?php endif; ?></div><div><small>Work description</small><?=kcmc_h((string)($entry['description']??''))?></div></div>
<?php if ($history): ?><ul class="adjustment-history"><?php foreach($history as $adjustment): ?><li><?=kcmc_h(tca_hours((int)($adjustment['previous_net_minutes']??0)))?> → <?=kcmc_h(tca_hours((int)($adjustment['new_net_minutes']??0)))?> h · <?=kcmc_h((string)($adjustment['reason']??''))?> · <?=kcmc_h($names[(string)($adjustment['adjusted_by']??'')]??'Administrator')?> · <?=kcmc_h((string)($adjustment['adjusted_at']??''))?></li><?php endforeach; ?></ul><?php endif; ?>
<?php if ($status!=='approved' && !in_array((string)($entry['status']??''), ['open','approved'], true) && ($uid !== (string)$reviewer['id'] || kcmc_is_designated_owner($reviewer)) && $entryId!==''): ?><form class="adjust-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="adjust_entry"><input type="hidden" name="entry_id" value="<?=kcmc_h($entryId)?>"><label>Adjusted hours<input type="number" name="adjusted_hours" min="0" max="24" step="0.01" value="<?=kcmc_h(tca_hours((int)($entry['net_minutes']??0)))?>" required></label><label>Reason<input name="reason" maxlength="500" placeholder="Missed punch, corrected duration…" required></label><button class="btn secondary" type="submit">Save adjustment</button></form><?php endif; ?>
</section><?php endforeach; ?></div>
<div class="tc-actions"><?php if (in_array($status,['in_progress','returned','needs_attention'],true) && !$openCount): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="submit_period"><button class="btn secondary" type="submit">Prepare for review</button></form><?php endif; ?><?php if ($status==='submitted' && !$openCount && ($uid !== (string)$reviewer['id'] || kcmc_is_designated_owner($reviewer))): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="approve"><button class="btn gold" type="submit">Approve</button></form><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="return"><label>Return reason<input name="reason" maxlength="500" required></label><button class="btn secondary" type="submit">Return</button></form><?php endif; ?><?php if ($status==='approved'): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards-export.php?user='.rawurlencode($uid).'&start='.rawurlencode($start).'&end='.rawurlencode($end)))?>">Download CSV</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards-print.php?user='.rawurlencode($uid).'&start='.rawurlencode($start).'&end='.rawurlencode($end)))?>">Print time card</a><?php endif; ?></div>
</article><?php endforeach; ?></section><?php endif; ?>
</main></body></html>
