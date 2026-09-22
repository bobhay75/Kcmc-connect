<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/connection-intake.php';
require_once __DIR__ . '/../lib/inbox-follow-up.php';

$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
kcmc_session_start();
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } else {
        $id = trim((string)($_POST['id'] ?? ''));
        $status = strtolower(trim((string)($_POST['status'] ?? '')));
        if ($id === '' || !in_array($status, KCMC_INBOX_STATUSES, true)) {
            $error = 'Choose a valid follow-up status.';
        } else {
            $result = kcmc_connection_update_follow_up($id, $status);
            if (!empty($result['updated'])) {
                kcmc_audit('connection.follow_up_changed', [
                    'previous_status' => (string)$result['previous'],
                    'status' => (string)$result['current'],
                    'count' => 1,
                ]);
                $success = 'Connection request updated to ' . kcmc_inbox_status_label((string)$result['current']) . '.';
            } elseif ((string)($result['current'] ?? '') === $status) {
                $success = 'That connection request is already marked ' . kcmc_inbox_status_label($status) . '.';
            } else {
                $error = 'That connection request could not be updated.';
            }
        }
    }
}

$allRows = kcmc_connection_recent(300);
$labels = ['visit' => 'Plan a Visit', 'serve' => 'Serve', 'groups' => 'Find Your People'];
$typeCounts = ['visit' => 0, 'serve' => 0, 'groups' => 0];
foreach ($allRows as $row) {
    $kind = (string)($row['kind'] ?? '');
    if (isset($typeCounts[$kind])) $typeCounts[$kind]++;
}
$statusCounts = kcmc_inbox_status_counts($allRows);
$filter = strtolower(trim((string)($_GET['status'] ?? 'all')));
if ($filter !== 'all' && !in_array($filter, KCMC_INBOX_STATUSES, true)) $filter = 'all';
$rows = $filter === 'all' ? $allRows : array_values(array_filter($allRows, static fn($row): bool => is_array($row) && kcmc_inbox_status($row['status'] ?? null) === $filter));
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Connection Inbox • KCMC Connect</title>
<link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>">
<style>
body{background:#eef2f4;color:#17324c;color-scheme:light}.shell{width:min(1240px,calc(100% - 28px));margin:28px auto 80px}.card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:22px;margin:18px 0}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.summary article{border:1px solid #dce3e7;border-radius:14px;padding:14px;background:#f8fafb}.summary strong{display:block;font-size:1.7rem}.table{overflow-x:auto}.row{display:grid;grid-template-columns:.75fr 1fr 1.2fr 1fr 1.2fr 1.5fr .75fr 1.25fr;gap:12px;align-items:start;padding:12px 0;border-top:1px solid #edf0f2;min-width:1220px}.row.head{font-weight:800;border-top:0}.note{white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:#607080}.nav,.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.filters a{padding:8px 12px;border:1px solid #cbd5dc;border-radius:999px;text-decoration:none}.filters a[aria-current="page"]{background:#17324c;color:#fff;border-color:#17324c}.status-form{display:flex;gap:7px;align-items:center}.status-form select{max-width:115px;padding:7px}.status-form button{border:0;border-radius:999px;padding:8px 11px;background:#17324c;color:#fff;font-weight:700;cursor:pointer}.portal-alert{padding:12px 14px;border-radius:10px}.portal-alert.success{background:#e6f3e7;color:#215b2d}.portal-alert.error{background:#f8e6e6;color:#7f2424}.shell :is(a,button,input,select,textarea):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:760px){.shell{width:min(100% - 18px,1240px)}}
</style>
</head>
<body><main class="shell">
<nav class="nav" aria-label="Administrator navigation"><a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a><a href="<?=kcmc_h(kcmc_url('admin/rsvps.php'))?>">Event RSVPs</a></nav>
<p class="eyebrow">KCMC CONNECTIONS</p><h1>Connection inbox</h1>
<p class="muted">Newest 300 visit, volunteer and group-interest requests. Contact details and notes remain inside the authenticated administrator area.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<section class="summary" aria-label="Connection request totals">
<?php foreach ($typeCounts as $kind => $count): ?><article><strong><?=kcmc_h((string)$count)?></strong><span><?=kcmc_h($labels[$kind])?></span></article><?php endforeach; ?>
<article><strong><?=kcmc_h((string)$statusCounts['new'])?></strong><span>New</span></article><article><strong><?=kcmc_h((string)$statusCounts['contacted'])?></strong><span>Contacted</span></article><article><strong><?=kcmc_h((string)$statusCounts['closed'])?></strong><span>Closed</span></article>
</section>
<nav class="filters" aria-label="Follow-up status filters"><span class="muted">Show:</span><?php foreach (['all'=>'All','new'=>'New','contacted'=>'Contacted','closed'=>'Closed'] as $value=>$label): ?><a href="<?=kcmc_h(kcmc_url('admin/connections.php?status=' . rawurlencode($value)))?>" <?=$filter===$value?'aria-current="page"':''?>><?=kcmc_h($label)?></a><?php endforeach; ?></nav>
<section class="card">
<?php if (!$rows): ?><p>No connection requests match this view.</p><?php else: ?>
<div class="table"><div class="row head"><span>Type</span><span>Name</span><span>Email</span><span>Phone</span><span>Service / Interest</span><span>Note</span><span>Received</span><span>Follow-up</span></div>
<?php foreach ($rows as $row): $kind=(string)($row['kind']??''); $detail=trim((string)($row['service']??'')) ?: trim((string)($row['interest']??'')); $rowStatus=kcmc_inbox_status($row['status']??null); ?>
<div class="row">
<span><?=kcmc_h($labels[$kind] ?? ucfirst($kind))?></span>
<span><strong><?=kcmc_h((string)($row['name'] ?? ''))?></strong></span>
<span><a href="mailto:<?=kcmc_h((string)($row['email'] ?? ''))?>"><?=kcmc_h((string)($row['email'] ?? ''))?></a></span>
<span><?php $phone=trim((string)($row['phone']??'')); if($phone!==''): ?><a href="tel:<?=kcmc_h(preg_replace('/[^0-9+]/','',$phone)??'')?>"><?=kcmc_h($phone)?></a><?php else: ?>—<?php endif; ?></span>
<span><?=kcmc_h($detail)?></span>
<span class="note"><?=kcmc_h((string)($row['message'] ?? ''))?></span>
<span><?=kcmc_h(kcmc_local_date_value((string)($row['submitted_at'] ?? ''), 'M j, Y g:i A'))?></span>
<span><form class="status-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="id" value="<?=kcmc_h((string)($row['id']??''))?>"><select name="status" aria-label="Follow-up status for <?=kcmc_h((string)($row['name']??'request'))?>"><?php foreach (KCMC_INBOX_STATUSES as $status): ?><option value="<?=kcmc_h($status)?>" <?=$rowStatus===$status?'selected':''?>><?=kcmc_h(kcmc_inbox_status_label($status))?></option><?php endforeach; ?></select><button type="submit">Save</button></form></span>
</div>
<?php endforeach; ?></div>
<?php endif; ?>
</section>
</main></body></html>
