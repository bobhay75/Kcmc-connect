<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/connection-intake.php';

$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$rows = kcmc_connection_recent(300);
$labels = ['visit' => 'Plan a Visit', 'serve' => 'Serve', 'groups' => 'Find Your People'];
$counts = ['visit' => 0, 'serve' => 0, 'groups' => 0];
foreach ($rows as $row) {
    $kind = (string)($row['kind'] ?? '');
    if (isset($counts[$kind])) $counts[$kind]++;
}
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Connection Inbox • KCMC Connect</title>
<link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>">
<style>
body{background:#eef2f4;color:#17324c;color-scheme:light}.shell{width:min(1180px,calc(100% - 28px));margin:28px auto 80px}.card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:22px;margin:18px 0}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.summary article{border:1px solid #dce3e7;border-radius:14px;padding:14px;background:#f8fafb}.summary strong{display:block;font-size:1.7rem}.table{overflow-x:auto}.row{display:grid;grid-template-columns:.8fr 1.1fr 1.25fr 1.1fr 1.25fr 1.8fr .9fr;gap:12px;align-items:start;padding:12px 0;border-top:1px solid #edf0f2;min-width:1120px}.row.head{font-weight:800;border-top:0}.note{white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:#607080}.nav{display:flex;gap:14px;flex-wrap:wrap}.shell :is(a,button,input,select,textarea):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:760px){.shell{width:min(100% - 18px,1180px)}}
</style>
</head>
<body><main class="shell">
<nav class="nav" aria-label="Administrator navigation"><a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a><a href="<?=kcmc_h(kcmc_url('admin/rsvps.php'))?>">Event RSVPs</a></nav>
<p class="eyebrow">KCMC CONNECTIONS</p><h1>Connection inbox</h1>
<p class="muted">Newest 300 visit, volunteer and group-interest requests. Contact details and notes remain inside the authenticated administrator area.</p>
<section class="summary" aria-label="Connection request totals">
<?php foreach ($counts as $kind => $count): ?><article><strong><?=kcmc_h((string)$count)?></strong><span><?=kcmc_h($labels[$kind])?></span></article><?php endforeach; ?>
</section>
<section class="card">
<?php if (!$rows): ?><p>No connection requests have been received yet.</p><?php else: ?>
<div class="table"><div class="row head"><span>Type</span><span>Name</span><span>Email</span><span>Phone</span><span>Service / Interest</span><span>Note</span><span>Received</span></div>
<?php foreach ($rows as $row): $kind=(string)($row['kind']??''); $detail=trim((string)($row['service']??'')) ?: trim((string)($row['interest']??'')); ?>
<div class="row">
<span><?=kcmc_h($labels[$kind] ?? ucfirst($kind))?></span>
<span><strong><?=kcmc_h((string)($row['name'] ?? ''))?></strong></span>
<span><a href="mailto:<?=kcmc_h((string)($row['email'] ?? ''))?>"><?=kcmc_h((string)($row['email'] ?? ''))?></a></span>
<span><?php $phone=trim((string)($row['phone']??'')); if($phone!==''): ?><a href="tel:<?=kcmc_h(preg_replace('/[^0-9+]/','',$phone)??'')?>"><?=kcmc_h($phone)?></a><?php else: ?>—<?php endif; ?></span>
<span><?=kcmc_h($detail)?></span>
<span class="note"><?=kcmc_h((string)($row['message'] ?? ''))?></span>
<span><?=kcmc_h(kcmc_local_date_value((string)($row['submitted_at'] ?? ''), 'M j, Y g:i A'))?></span>
</div>
<?php endforeach; ?></div>
<?php endif; ?>
</section>
</main></body></html>
