<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/invitation-mailer.php';
require_once __DIR__ . '/../lib/push-subscriptions.php';
require_once __DIR__ . '/../lib/connection-intake.php';
require_once __DIR__ . '/../lib/event-rsvp.php';
require_once __DIR__ . '/../lib/inbox-follow-up.php';
require_once __DIR__ . '/../lib/release-health.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$health = kcmc_release_health_snapshot();
$overall = (string)($health['overall'] ?? 'fail');
$summary = $health['summary'] ?? ['pass' => 0, 'warn' => 0, 'fail' => 0];
$metrics = $health['metrics'] ?? [];
$connectionFollowUp = kcmc_inbox_status_counts(kcmc_connection_recent(300));
$rsvpFollowUp = kcmc_inbox_status_counts(kcmc_event_rsvp_recent(200));
$statusLabels = ['pass' => 'Ready', 'warn' => 'Review', 'fail' => 'Action needed'];
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Release Health • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.health-shell{width:min(1100px,calc(100% - 28px));margin:24px auto 80px}.health-top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}.health-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}.health-stat,.health-check{background:#fff;border:1px solid #dce3e7;border-radius:16px;padding:18px}.health-stat strong{display:block;font-size:1.8rem}.health-stat a{font-weight:800}.health-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.health-check{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:start}.health-dot{width:13px;height:13px;border-radius:50%;margin-top:7px;background:#607080}.health-check.pass .health-dot{background:#2b7a46}.health-check.warn .health-dot{background:#a06b12}.health-check.fail .health-dot{background:#a33434}.health-check h2{font-size:1rem;margin:0 0 4px}.health-check p{margin:0;color:#536273}.health-pill{display:inline-block;border-radius:999px;padding:6px 10px;font-weight:800;font-size:.85rem}.health-pill.pass{background:#e6f3e7;color:#215b2d}.health-pill.warn{background:#fff3d6;color:#77510c}.health-pill.fail{background:#fbe4e4;color:#7d2525}.health-meta{color:#607080;font-size:.9rem}.health-actions{display:flex;gap:10px;flex-wrap:wrap}.health-actions a{text-decoration:none}@media(max-width:760px){.health-summary,.health-grid{grid-template-columns:1fr 1fr}}@media(max-width:520px){.health-summary,.health-grid{grid-template-columns:1fr}}
</style></head><body class="portal-body"><main class="health-shell">
<div class="health-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/operations.php'))?>">← Operations</a><p class="eyebrow">RELEASE HEALTH</p><h1>KCMC production readiness</h1><p class="portal-lead">A read-only operational check of the deployed app. No passwords, tokens, invitation links, prayer content or private-key material are displayed here.</p></div><div><span class="health-pill <?=kcmc_h($overall)?>"><?=kcmc_h($statusLabels[$overall] ?? 'Action needed')?></span></div></div>
<div class="health-summary">
<div class="health-stat"><span>Checks ready</span><strong><?=kcmc_h((string)($summary['pass'] ?? 0))?></strong></div>
<div class="health-stat"><span>Review</span><strong><?=kcmc_h((string)($summary['warn'] ?? 0))?></strong></div>
<div class="health-stat"><span>Action needed</span><strong><?=kcmc_h((string)($summary['fail'] ?? 0))?></strong></div>
<div class="health-stat"><span>Active accounts</span><strong><?=kcmc_h((string)($metrics['active_accounts'] ?? 0))?></strong></div>
</div>
<section class="health-grid" aria-label="Release health checks">
<?php foreach (($health['checks'] ?? []) as $check): $status=(string)($check['status']??'fail'); ?>
<article class="health-check <?=kcmc_h($status)?>"><span class="health-dot" aria-hidden="true"></span><div><h2><?=kcmc_h((string)($check['label']??'Check'))?></h2><p><?=kcmc_h((string)($check['detail']??''))?></p><p class="health-meta"><?=kcmc_h($statusLabels[$status] ?? 'Action needed')?></p></div></article>
<?php endforeach; ?>
</section>
<section class="portal-card portal-section"><p class="eyebrow">FOLLOW-UP</p><h2>New private responses</h2><p class="portal-fine">Counts only are shown here. Names, email addresses, phone numbers and notes stay inside their authenticated inboxes.</p><div class="health-summary"><div class="health-stat"><span>New event RSVPs</span><strong><?=kcmc_h((string)($rsvpFollowUp['new']??0))?></strong><a href="<?=kcmc_h(kcmc_url('admin/rsvps.php?status=new'))?>">Open New RSVPs</a></div><div class="health-stat"><span>New connection requests</span><strong><?=kcmc_h((string)($connectionFollowUp['new']??0))?></strong><a href="<?=kcmc_h(kcmc_url('admin/connections.php?status=new'))?>">Open New Connections</a></div></div></section>
<section class="portal-card portal-section"><p class="eyebrow">CURRENT COUNTS</p><h2>Access and notification state</h2><div class="health-summary"><div class="health-stat"><span>Pending invitations</span><strong><?=kcmc_h((string)($metrics['pending_invites']??0))?></strong></div><div class="health-stat"><span>Push subscriptions</span><strong><?=kcmc_h((string)($metrics['active_push_subscriptions']??0))?></strong></div><div class="health-stat"><span>Disabled accounts</span><strong><?=kcmc_h((string)($metrics['disabled_accounts']??0))?></strong></div><div class="health-stat"><span>Generated</span><strong style="font-size:1rem"><?=kcmc_h(gmdate('M j, g:i A', strtotime((string)($health['generated_at']??'now'))))?> UTC</strong></div></div><div class="health-actions"><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>">Member access</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/push.php'))?>">Push updates</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/backup.php'))?>">Download content backup</a></div></section>
</main></body></html>
