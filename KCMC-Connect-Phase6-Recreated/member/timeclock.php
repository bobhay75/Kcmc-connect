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
            if ($action === 'request_correction') {
                kcmc_timeclock_request_correction((string)$user['id'], trim((string)($_POST['entry_id'] ?? '')), (string)($_POST['reason'] ?? ''));
                kcmc_audit('timeclock.correction_requested', ['action' => 'request_correction', 'count' => 1]);
                $message = 'Correction request sent for administrator review.';
            } else {
                if (!in_array($action, ['clock_in', 'clock_out', 'break_start', 'break_end'], true)) throw new RuntimeException('That action belongs in administrator time-card review.');
                kcmc_timeclock_mutate((string)$user['id'], $action, $_POST);
                kcmc_audit('timeclock.' . $action, ['action' => $action, 'count' => 1]);
                $message = match ($action) {
                    'clock_in' => 'Clocked in using the server time.',
                    'break_start' => 'Break started using the server time.',
                    'break_end' => 'Break ended using the server time.',
                    'clock_out' => 'Clocked out using the server time.',
                    default => 'Time clock updated.',
                };
            }
        } catch (Throwable $e) { $error = $e->getMessage(); }
    }
}

$open = kcmc_timeclock_open_entry((string)$user['id']);
$entries = kcmc_timeclock_period_entries((string)$user['id'], $periodStart, $periodEnd);
usort($entries, fn($a, $b) => strcmp((string)($b['clock_in_at'] ?? ''), (string)($a['clock_in_at'] ?? '')));
$periodRecord = kcmc_timeclock_period_record((string)$user['id'], $periodStart, $periodEnd);
$totalMinutes = array_sum(array_map(fn($entry) => (int)($entry['net_minutes'] ?? 0), $entries));
$correctionRequests = kcmc_timeclock_correction_requests_for((string)$user['id']);
$pendingByEntry = [];
foreach ($correctionRequests as $request) if (($request['status'] ?? '') === 'pending') $pendingByEntry[(string)($request['entry_id'] ?? '')] = $request;
$openBreak = false;
if ($open) foreach (($open['breaks'] ?? []) as $break) if (is_array($break) && empty($break['end_at'])) $openBreak = true;
$recentEntries = kcmc_timeclock_entries_for((string)$user['id']);
usort($recentEntries, fn($a, $b) => strcmp((string)($b['clock_in_at'] ?? ''), (string)($a['clock_in_at'] ?? '')));
$recentEntries = array_slice($recentEntries, 0, 50);
function tc_local(string $iso): string { if ($iso === '') return '—'; $d = new DateTimeImmutable($iso); return $d->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('M j, g:i A'); }
function tc_hours(int $minutes): string { return number_format($minutes / 60, 2); }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Time Clock • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.tc-shell{width:min(920px,calc(100% - 28px));margin:24px auto 80px}.tc-card{background:var(--kcmc-panel, #fff);color:var(--kcmc-text, #17324c);border:1px solid var(--kcmc-line, #dce3e7);border-radius:18px;padding:20px;margin:16px 0}.tc-actions{display:flex;gap:10px;flex-wrap:wrap}.tc-actions form{margin:0}.tc-table{display:grid;gap:10px}.tc-row{display:grid;grid-template-columns:1fr 1fr .7fr 1.2fr;gap:10px;padding:12px;border:1px solid var(--kcmc-line, #e2e8ec);border-radius:12px}.tc-row small{display:block;color:var(--kcmc-muted, #607080)}.tc-form label{display:block;font-weight:700}.tc-form textarea,.tc-form select{width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;font:inherit}.tc-form textarea{min-height:95px}.tc-total{font-size:1.5rem;font-weight:900}.tc-note{color:var(--kcmc-muted, #607080)}.tc-adjusted{display:inline-block;margin-top:4px;border-radius:999px;padding:3px 7px;background:var(--kcmc-warning-bg, #fff3d6);color:var(--kcmc-warning, #77510c);font-size:.8rem;font-weight:800}.tc-correction{grid-column:1/-1;border-top:1px solid var(--kcmc-line, #e2e8ec);padding-top:10px}.tc-correction summary{cursor:pointer;font-weight:800}.tc-correction textarea{width:100%;box-sizing:border-box;min-height:75px;padding:10px;margin:8px 0;font:inherit}.tc-request-list{display:grid;gap:10px}.tc-request{border:1px solid var(--kcmc-line, #e2e8ec);border-radius:12px;padding:12px}.tc-request p{margin:.35rem 0}.tc-request-head{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.tc-shell :is(a,button,select,textarea,input,summary):focus-visible{outline:3px solid var(--kcmc-gold, #174d75);outline-offset:3px}@media(max-width:700px){.tc-row{grid-template-columns:1fr}.tc-actions{display:grid}.tc-actions form,.tc-actions button{width:100%}.tc-correction{grid-column:1}}

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
</head><body class="portal-body"><?php echo kcmc_screen_navigation('member/', true); ?><main class="tc-shell">
<nav class="tc-actions" aria-label="Page navigation"><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← My account</a><a class="portal-back" href="<?=kcmc_h(kcmc_url('index.php'))?>">Home</a></nav><p class="eyebrow">STAFF TIME CLOCK</p><h1>Clock In / Clock Out</h1><p class="portal-lead">Pay period <?=kcmc_h($periodStart)?> through <?=kcmc_h($periodEnd)?>. Punch times are recorded by the KCMC server.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($message): ?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif; ?>
<section class="tc-card"><p class="eyebrow">CURRENT STATUS</p>
<?php if (!$open): ?><h2>You are clocked out.</h2><p class="tc-note">Start your shift here. Your clock-in time is recorded by the KCMC server.</p><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="clock_in"><button class="btn gold" type="submit">Clock In</button></form>
<?php else: ?><h2>Clocked in <?=kcmc_h(tc_local((string)$open['clock_in_at']))?></h2><p class="tc-note"><?=$openBreak?'A break is currently running. Clocking out also ends the break.':'Shift is running.'?></p>
<form class="tc-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="clock_out"><details><summary>Add work details (optional)</summary><label>Work category<select name="category"><option value="">Other</option><?php foreach(kcmc_timeclock_categories() as $category): ?><option><?=kcmc_h($category)?></option><?php endforeach; ?></select></label><label>Work note<textarea name="description" maxlength="1000"></textarea></label></details><button class="btn gold" type="submit">Clock Out</button></form>
<div class="tc-actions" style="margin-top:12px"><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="<?=$openBreak?'break_end':'break_start'?>"><button class="btn secondary" type="submit"><?=$openBreak?'End Break':'Start Break'?></button></form></div>
<?php endif; ?>
<?php if (in_array((string)($periodRecord['status']??''), ['submitted','approved','in_progress'], true)): ?><p class="tc-note">Your earlier time-card review does not stop you from clocking in or out. New punches are included in administrator review.</p><?php endif; ?>
<p class="tc-note">Administrators handle pay-period turn-in and approval. You can request a correction with a reason below.</p></section>
<section class="tc-card"><p class="eyebrow">PAY PERIOD</p><h2>Current pay-period total</h2><p class="tc-total"><?=kcmc_h(tc_hours($totalMinutes))?> hours</p><?php if (!$recentEntries): ?><p>No shifts recorded yet.</p><?php else: ?><h3>Recent shifts</h3><div class="tc-table"><?php foreach($recentEntries as $entry): $entryId=(string)($entry['id']??'');$correctionCount=kcmc_timeclock_entry_correction_count($entry); ?><article class="tc-row"><div><small>Work date</small><strong><?=kcmc_h((string)$entry['work_date'])?></strong><?php if($correctionCount>0): ?><br><small><?=kcmc_h((string)$correctionCount)?> approved correction<?= $correctionCount===1?'':'s' ?></small><?php endif; ?></div><div><small>In / Out</small><?=kcmc_h(tc_local((string)$entry['clock_in_at']))?><br><?=kcmc_h(tc_local((string)($entry['clock_out_at']??'')))?></div><div><small>Net</small><strong><?=kcmc_h(tc_hours((int)($entry['net_minutes']??0)))?> h</strong><br><small>Break <?=kcmc_h((string)kcmc_timeclock_break_minutes($entry))?> min</small><?php if (!empty($entry['adjustment_count'])): ?><span class="tc-adjusted">Supervisor adjusted <?=kcmc_h((string)$entry['adjustment_count'])?>×</span><?php endif; ?></div><div><small>Work</small><strong><?=kcmc_h((string)($entry['category']??''))?></strong><br><?=kcmc_h((string)($entry['description']??''))?></div><?php if(($entry['status']??'')!=='open'): ?><details class="tc-correction"><summary>Request a correction</summary><?php if(isset($pendingByEntry[$entryId])): ?><p class="tc-note">A correction request for this shift is already pending administrator review.</p><?php else: ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="request_correction"><input type="hidden" name="entry_id" value="<?=kcmc_h($entryId)?>"><label>What needs to be corrected?<textarea name="reason" minlength="5" maxlength="500" required placeholder="Example: I clocked out late; actual end time was about 5:15 PM."></textarea></label><button class="btn secondary" type="submit">Send Correction Request</button></form><?php endif; ?></details><?php endif; ?></article><?php endforeach; ?></div><?php endif; ?>
<?php if (($periodRecord['status']??'')==='returned'): ?><p class="portal-alert warning">Administrator review note: <?=kcmc_h((string)($periodRecord['return_reason']??''))?></p><?php endif; ?></section>
<?php if($correctionRequests): ?><section class="tc-card"><p class="eyebrow">CORRECTIONS</p><h2>Your correction requests</h2><div class="tc-request-list"><?php foreach(array_slice($correctionRequests,0,20) as $request): ?><article class="tc-request"><div class="tc-request-head"><strong><?=kcmc_h(ucfirst((string)($request['status']??'pending')))?></strong><time datetime="<?=kcmc_h((string)($request['requested_at']??''))?>"><?=kcmc_h(tc_local((string)($request['requested_at']??'')))?></time></div><p><?=kcmc_h((string)($request['reason']??''))?></p><?php if(!empty($request['resolution_reason'])): ?><p class="tc-note">Administrator response: <?=kcmc_h((string)$request['resolution_reason'])?></p><?php endif; ?></article><?php endforeach; ?></div></section><?php endif; ?>
</main></body></html>
