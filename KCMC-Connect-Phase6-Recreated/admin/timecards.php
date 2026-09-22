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
        $userId = trim((string)($_POST['user_id'] ?? ''));
        $start = trim((string)($_POST['start'] ?? ''));
        $end = trim((string)($_POST['end'] ?? ''));
        $action = (string)($_POST['action'] ?? '');
        if ($userId === (string)$reviewer['id']) {
            $error = 'A reviewer cannot approve or return their own time card.';
        } elseif (!kcmc_find_user_by_id($userId)) {
            $error = 'Employee account not found.';
        } else {
            try {
                $record = kcmc_timeclock_review_period($userId, $start, $end, (string)$reviewer['id'], $action, (string)($_POST['reason'] ?? ''));
                kcmc_audit('timeclock.period_reviewed', ['action' => $action, 'status' => (string)$record['status'], 'count' => 1]);
                $message = $action === 'approve' ? 'Time card approved.' : 'Time card returned to the employee.';
            } catch (Throwable $e) {
                $error = $e->getMessage();
            }
        }
    }
}

$store = kcmc_timeclock_store();
$periods = array_values(array_filter($store['periods'] ?? [], 'is_array'));
usort($periods, fn($a, $b) => strcmp((string)($b['submitted_at'] ?? ''), (string)($a['submitted_at'] ?? '')));
$names = [];
foreach (kcmc_users() as $u) $names[(string)$u['id']] = (string)($u['display_name'] ?? 'Employee');
function tca_hours(int $minutes): string { return number_format($minutes / 60, 2); }
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Time Cards • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.tc-admin{width:min(1050px,calc(100% - 28px));margin:24px auto 80px}.tc-list{display:grid;gap:14px}.tc-card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:20px}.tc-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.tc-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.tc-meta div{background:#f5f8fa;border-radius:12px;padding:10px}.tc-meta small{display:block;color:#607080}.tc-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}.tc-actions form{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end}.tc-actions label{font-weight:700}.tc-actions input{padding:9px;border:1px solid #cbd5dc;border-radius:8px;min-width:220px}.status{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2f4;font-weight:800}.status.approved{background:#e6f3e7;color:#215b2d}.status.submitted{background:#fff3d6;color:#77510c}.status.returned{background:#fbe4e4;color:#7d2525}.tc-admin :is(a,button,input):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:720px){.tc-meta{grid-template-columns:1fr 1fr}.tc-actions,.tc-actions form{display:grid;width:100%}.tc-actions input,.tc-actions button,.tc-actions a{width:100%;box-sizing:border-box}}
</style></head><body class="portal-body"><main class="tc-admin"><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/operations.php'))?>">← Operations</a><p class="eyebrow">PAYROLL TURN-IN</p><h1>Employee Time Cards</h1><p class="portal-lead">Review submitted KCMC time cards. Approved periods are locked and available for accounting export.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?><?php if ($message): ?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif; ?>
<?php if (!$periods): ?><section class="tc-card"><p>No employee pay periods have been submitted yet.</p></section><?php else: ?><section class="tc-list"><?php foreach($periods as $period): $uid=(string)($period['user_id']??'');$start=(string)($period['start']??'');$end=(string)($period['end']??'');$status=(string)($period['status']??'submitted');$entries=kcmc_timeclock_period_entries($uid,$start,$end);$minutes=array_sum(array_map(fn($e)=>(int)($e['net_minutes']??0),$entries)); ?><article class="tc-card"><div class="tc-head"><div><h2><?=kcmc_h($names[$uid]??'Former or unknown employee')?></h2><p><?=kcmc_h($start)?> through <?=kcmc_h($end)?></p></div><span class="status <?=kcmc_h($status)?>"><?=kcmc_h(ucfirst($status))?></span></div><div class="tc-meta"><div><small>Shifts</small><strong><?=count($entries)?></strong></div><div><small>Total hours</small><strong><?=kcmc_h(tca_hours($minutes))?></strong></div><div><small>Submitted</small><strong><?=kcmc_h((string)($period['submitted_at']??'—'))?></strong></div><div><small>Approved</small><strong><?=kcmc_h((string)($period['approved_at']??'—'))?></strong></div></div><?php if ($status==='returned'): ?><p class="portal-alert warning">Return reason: <?=kcmc_h((string)($period['return_reason']??''))?></p><?php endif; ?><div class="tc-actions"><?php if ($status==='submitted'): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="approve"><button class="btn gold" type="submit">Approve</button></form><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h($uid)?>"><input type="hidden" name="start" value="<?=kcmc_h($start)?>"><input type="hidden" name="end" value="<?=kcmc_h($end)?>"><input type="hidden" name="action" value="return"><label>Return reason<input name="reason" maxlength="500" required></label><button class="btn secondary" type="submit">Return</button></form><?php endif; ?><?php if ($status==='approved'): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards-export.php?user='.rawurlencode($uid).'&start='.rawurlencode($start).'&end='.rawurlencode($end)))?>">Download CSV</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards-print.php?user='.rawurlencode($uid).'&start='.rawurlencode($start).'&end='.rawurlencode($end)))?>">Print time card</a><?php endif; ?></div></article><?php endforeach; ?></section><?php endif; ?>
</main></body></html>
