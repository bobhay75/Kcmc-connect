<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/timeclock.php';

kcmc_private_headers();
$reviewer = kcmc_require_role(['pastor_admin', 'recovery_admin']);
$error = '';
$message = '';

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        http_response_code(403);
        $error = 'Your session expired. Reload and try again.';
    } else {
        $action = (string)($_POST['action'] ?? '');
        try {
            if ($action === 'adjust_entry') {
                $entryId = trim((string)($_POST['entry_id'] ?? ''));
                $hours = trim((string)($_POST['adjusted_hours'] ?? ''));
                $minutes = kcmc_timeclock_hours_to_minutes($hours);
                if ($minutes === null) throw new RuntimeException('Adjusted time must be a number between 0 and 24 hours.');
                $record = kcmc_timeclock_adjust_entry(
                    $entryId,
                    (string)$reviewer['id'],
                    $minutes,
                    (string)($_POST['reason'] ?? '')
                );
                kcmc_audit('timeclock.entry_adjusted', ['action' => 'adjust_entry', 'count' => 1]);
                $message = 'Time entry adjusted from ' . number_format(((int)$record['previous_net_minutes']) / 60, 2) . ' to ' . number_format(((int)$record['new_net_minutes']) / 60, 2) . ' hours.';
            } else {
                $userId = trim((string)($_POST['user_id'] ?? ''));
                $start = trim((string)($_POST['start'] ?? ''));
                $end = trim((string)($_POST['end'] ?? ''));
                if ($userId === (string)$reviewer['id']) {
                    throw new RuntimeException('A reviewer cannot approve or return their own time card.');
                }
                if (!kcmc_find_user_by_id($userId)) throw new RuntimeException('Employee account not found.');
                $record = kcmc_timeclock_review_period($userId, $start, $end, (string)$reviewer['id'], $action, (string)($_POST['reason'] ?? ''));
                kcmc_audit('timeclock.period_reviewed', ['action' => $action, 'status' => (string)$record['status'], 'count' => 1]);
                $message = $action === 'approve' ? 'Time card approved.' : 'Time card returned to the employee.';
            }
        } catch (Throwable $e) {
            $error = $e->getMessage();
        }
    }
}

$store = kcmc_timeclock_store();
$periods = array_values(array_filter($store['periods'] ?? [], 'is_array'));
usort($periods, fn($a, $b) => strcmp((string)($b['submitted_at'] ?? ''), (string)($a['submitted_at'] ?? '')));
$names = [];
foreach (kcmc_users() as $u) $names[(string)$u['id']] = (string)($u['display_name'] ?? 'Employee');
function tca_hours(int $minutes): string { return number_format($minutes / 60, 2); }
function tca_adjustments(array $store, string $entryId): array {
    $rows = array_values(array_filter($store['adjustments'] ?? [], fn($a) => is_array($a) && ($a['entry_id'] ?? '') === $entryId));
    usort($rows, fn($a, $b) => strcmp((string)($b['adjusted_at'] ?? ''), (string)($a['adjusted_at'] ?? '')));
    return $rows;
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Time Cards • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.tc-admin{width:min(1100px,calc(100% - 28px));margin:24px auto 80px}.tc-list{display:grid;gap:14px}.tc-card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:20px}.tc-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.tc-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.tc-meta div{background:#f5f8fa;border-radius:12px;padding:10px}.tc-meta small,.shift-row small{display:block;color:#607080}.tc-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}.tc-actions form{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end}.tc-actions label{font-weight:700}.tc-actions input,.adjust-form input{padding:9px;border:1px solid #cbd5dc;border-radius:8px;min-width:180px}.status{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2f4;font-weight:800}.status.approved{background:#e6f3e7;color:#215b2d}.status.submitted{background:#fff3d6;color:#77510c}.status.returned{background:#fbe4e4;color:#7d2525}.shift-list{display:grid;gap:10px;margin:18px 0}.shift-row{border:1px solid #e2e8ec;border-radius:12px;padding:14px}.shift-main{display:grid;grid-template-columns:1fr 1.2fr .7fr 2fr;gap:10px}.adjust-form{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-top:12px;padding-top:12px;border-top:1px solid #edf0f2}.adjust-form label{font-weight:700}.adjustment-history{margin:10px 0 0;padding-left:18px;color:#536273}.tc-admin :is(a,button,input):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:720px){.tc-meta{grid-template-columns:1fr 1fr}.tc-actions,.tc-actions form,.adjust-form{display:grid;width:100%}.tc-actions input,.tc-actions button,.tc-actions a,.adjust-form input,.adjust-form button{width:100%;box-sizing:border-box}.shift-main{grid-template-columns:1fr}}
</style></head><body class="portal-body"><main class="tc-admin">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/operations.php'))?>">← Operations</a><p class="eyebrow">PAYROLL TURN-IN</p><h1>Employee Time Cards</h1><p class="portal-lead">Review submitted KCMC time cards. Approved periods are locked. Supervisor time adjustments preserve an immutable before/after record and require a reason.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?><?php if ($message): ?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif; ?>
<?php if (!$periods): ?><section class="tc-card"><p>No employee pay periods have been submitted yet.</p></section><?php else: ?><section class="tc-list">
<?php foreach($periods as $period):
    $uid=(string)($period['user_id']??'');$start=(string)($period['start']??'');$end=(string)($period['end']??'');$status=(string)($period['status']??'submitted');
    $entries=kcmc_timeclock_period_entries($uid,$start,$end);$minutes=array_sum(array_map(fn($e)=>(int)($e['net_minutes']??0),$entries));
?>
<article class="tc-card"><div class="tc-head"><div><h2><?=kcmc_h($names[$uid]??'Former or unknown employee')?></h2><p><?=kcmc_h($start)?> through <?=kcmc_h($end)?></p></div><span class="status <?=kcmc_h($status)?>"><?=kcmc_h(ucfirst($status))?></span></div>
<div class="tc-meta"><div><small>Shifts</small><strong><?=count($entries)?></strong></div><div><small>Total hours</small><strong><?=kcmc_h(tca_hours($minutes))?></strong></div><div><small>Submitted</small><strong><?=kcmc_h((string)($period['submitted_at']??'—'))?></strong></div><div><small>Approved</small><strong><?=kcmc_h((string)($period['approved_at']??'—'))?></strong></div></div>
<?php if ($status==='returned'): ?><p class="portal-alert warning">Return reason: <?=kcmc_h((string)($period['return_reason']??''))?></p><?php endif; ?>
<div class="shift-list"><?php foreach($entries as $entry): $entryId=(string)($entry['id']??'');$history=tca_adjustments($store,$entryId); ?>
<section class="shift-row"><div class="shift-main"><div><small>Work date</small><strong><?=kcmc_h((string)($entry['work_date']??''))?></strong></div><div><small>Category</small><?=kcmc_h((string)($entry['category']??''))?></div><div><small>Net hours</small><strong><?=kcmc_h(tca_hours((int)($entry['net_minutes']??0)))?></strong><?php if (!empty($entry['adjustment_count'])): ?><br><small>Adjusted <?=kcmc_h((string)$entry['adjustment_count'])?>×</small><?php endif; ?></div><div><small>Work description</small><?=kcmc_h((string)($entry['description']??''))?></div></div>
<?php if ($history): ?><ul class="adjustment-history"><?php foreach($history as $adjustment): ?><li><?=kcmc_h(tca_hours((int)($adjustment['previous_net_minutes']??0)))?> → <?=kcmc_h(tca_hours((int)($adjustment['new_net_minutes']??0)))?> h · <?=kcmc_h((string)($adjustment['reason']??''))?> · <?=kcmc_h($names[(string)($adjustment['adjusted_by']??'')]??'Administrator')?> · <?=kcmc_h((string)($adjustment['adjusted_at']??''))?></li><?php endforeach; ?></ul><?php endif; ?>
<?php if ($status!=='approved' && $uid !== (string)$reviewer['id'] && $entryId!==''): ?><form class="adjust-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="adjust_entry"><input type="hidden" name="entry_id" value="<?=kcmc_h($entryId)?>"><label>Adjusted hours<input type="number" name="adjusted_hours" min="0" max="24" step="0.01" value="<?=kcmc_h(tca_hours((int)($entry['net_minutes']??0)))?>" required></label><label>Reason<input name="reason" maxlength="500" placeholder="Missed punch, corrected duration…" required></label><button class="btn secondary" type="submit">Save adjustment</button></form><?php endif; ?>
</section><?php endforeach; ?></div>
<div class="tc-actions"><?php if ($status==='submitted'): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="approve"><button class="btn gold" type="submit">Approve</button></form><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="return"><label>Return reason<input name="reason" maxlength="500" required></label><button class="btn secondary" type="submit">Return</button></form><?php endif; ?><?php if ($status==='approved'): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards-export.php?user='.rawurlencode($uid).'&start='.rawurlencode($start).'&end='.rawurlencode($end)))?>">Download CSV</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards-print.php?user='.rawurlencode($uid).'&start='.rawurlencode($start).'&end='.rawurlencode($end)))?>">Print time card</a><?php endif; ?></div>
</article><?php endforeach; ?></section><?php endif; ?>
</main></body></html>
