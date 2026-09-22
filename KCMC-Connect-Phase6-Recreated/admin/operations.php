<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';

$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();

$tools = [
    [
        'href' => 'admin/health.php',
        'eyebrow' => 'RELEASE READINESS',
        'title' => 'Release Health',
        'description' => 'Check runtime, HTTPS, private storage, backups, invitation mail, push configuration, accounts and pending invitations after deployment.',
        'action' => 'Open health checks',
    ],
    [
        'href' => 'admin/audit.php',
        'eyebrow' => 'ACTIVITY',
        'title' => 'Audit History',
        'description' => 'Review recent administrative and system actions without exposing prayer text, invitation links, push endpoints or other private payloads.',
        'action' => 'Review audit history',
    ],
    [
        'href' => 'admin/push.php',
        'eyebrow' => 'NOTIFICATIONS',
        'title' => 'Push Updates',
        'description' => 'Run the signed-in-device release test first, then send the generic KCMC update notification to active subscribed devices.',
        'action' => 'Open push controls',
    ],
    [
        'href' => 'admin/timecards.php',
        'eyebrow' => 'EMPLOYEE TIME',
        'title' => 'Time Cards',
        'description' => 'Review submitted employee pay periods, approve or return them, and export approved time cards for accounting.',
        'action' => 'Review time cards',
    ],
    [
        'href' => 'admin/backup.php',
        'eyebrow' => 'BACKUP',
        'title' => 'Download Public Content Backup',
        'description' => 'Download the current public content JSON before a major publishing change or deployment verification.',
        'action' => 'Download backup',
    ],
    [
        'href' => 'admin/restore.php',
        'eyebrow' => 'RECOVERY',
        'title' => 'Restore Public Content',
        'description' => 'Validate and restore a known-good KCMC public-content backup through the guarded recovery workflow.',
        'action' => 'Open restore tool',
    ],
];
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Operations • KCMC Connect</title>
<link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>">
<style>
body{background:#eef2f4;color:#17324c;color-scheme:light}.ops{width:min(1040px,calc(100% - 28px));margin:28px auto 80px}.ops-top{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:20px}.ops-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.ops-card{display:flex;flex-direction:column;min-height:220px;background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:22px}.ops-card h2{margin:.25rem 0 .6rem}.ops-card p{line-height:1.55}.ops-card .tool-link{margin-top:auto;align-self:flex-start;font-weight:800}.ops-card.warning{border-color:#d6b86a;background:#fffdf5}.muted{color:#607080}.ops :is(a,button):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:720px){.ops{width:min(100% - 18px,1040px);margin-top:16px}.ops-top{display:block}.ops-grid{grid-template-columns:1fr}.ops-card{min-height:0;padding:18px}}
</style>
</head>
<body><main class="ops">
<div class="ops-top"><div><a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a><p class="eyebrow">KCMC OPERATIONS</p><h1>Release, recovery and system tools</h1><p class="muted">Administrative controls for verifying the app, reviewing activity, testing notifications, employee time, and recovering public content.</p></div><a href="<?=kcmc_h(kcmc_url())?>">View public site</a></div>
<div class="ops-grid">
<?php foreach ($tools as $tool): ?>
<section class="ops-card <?=$tool['href']==='admin/restore.php'?'warning':''?>">
<p class="eyebrow"><?=kcmc_h($tool['eyebrow'])?></p>
<h2><?=kcmc_h($tool['title'])?></h2>
<p><?=kcmc_h($tool['description'])?></p>
<a class="tool-link" href="<?=kcmc_h(kcmc_url($tool['href']))?>"><?=kcmc_h($tool['action'])?> →</a>
</section>
<?php endforeach; ?>
</div>
</main></body></html>
