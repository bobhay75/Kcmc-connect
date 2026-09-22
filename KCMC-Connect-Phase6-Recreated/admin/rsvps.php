<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/event-rsvp.php';

$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$rows = kcmc_event_rsvp_recent(200);
$counts = [];
foreach ($rows as $row) {
    $key = trim((string)($row['event'] ?? '')) . '|' . trim((string)($row['event_date'] ?? ''));
    if ($key === '|') continue;
    $counts[$key] = ($counts[$key] ?? 0) + 1;
}
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Event RSVPs • KCMC Connect</title>
<link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>">
<style>
body{background:#eef2f4;color:#17324c;color-scheme:light}.shell{width:min(1180px,calc(100% - 28px));margin:28px auto 80px}.card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:22px;margin:18px 0}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.summary article{border:1px solid #dce3e7;border-radius:14px;padding:14px;background:#f8fafb}.summary strong{display:block;font-size:1.6rem}.table{overflow-x:auto}.row{display:grid;grid-template-columns:1.2fr .9fr 1fr 1.25fr 1.8fr .9fr;gap:12px;align-items:start;padding:12px 0;border-top:1px solid #edf0f2;min-width:980px}.row.head{font-weight:800;border-top:0}.note{white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:#607080}.shell :is(a,button,input,select,textarea):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:760px){.shell{width:min(100% - 18px,1180px)}}
</style>
</head>
<body>
<main class="shell">
<a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a>
<p class="eyebrow">KCMC EVENTS</p>
<h1>Event RSVPs</h1>
<p class="muted">Newest 200 private event responses. Names, email addresses and notes are visible only to authorized administrators.</p>
<?php if ($counts): ?><section class="summary" aria-label="RSVP totals">
<?php foreach ($counts as $key => $count): [$eventName, $eventDate] = array_pad(explode('|', $key, 2), 2, ''); ?>
<article><strong><?=kcmc_h((string)$count)?></strong><span><?=kcmc_h($eventName)?><?= $eventDate !== '' ? ' • ' . kcmc_h($eventDate) : '' ?></span></article>
<?php endforeach; ?>
</section><?php endif; ?>
<section class="card">
<?php if (!$rows): ?><p>No event RSVPs have been received yet.</p><?php else: ?>
<div class="table"><div class="row head"><span>Event</span><span>Date</span><span>Name</span><span>Email</span><span>Note</span><span>Received</span></div>
<?php foreach ($rows as $row): ?>
<div class="row">
<span><strong><?=kcmc_h((string)($row['event'] ?? ''))?></strong></span>
<span><?=kcmc_h((string)($row['event_date'] ?? ''))?></span>
<span><?=kcmc_h((string)($row['name'] ?? ''))?></span>
<span><a href="mailto:<?=kcmc_h((string)($row['email'] ?? ''))?>"><?=kcmc_h((string)($row['email'] ?? ''))?></a></span>
<span class="note"><?=kcmc_h((string)($row['message'] ?? ''))?></span>
<span><?=kcmc_h(kcmc_local_date_value((string)($row['submitted_at'] ?? ''), 'M j, Y g:i A'))?></span>
</div>
<?php endforeach; ?></div>
<?php endif; ?>
</section>
</main>
</body>
</html>
