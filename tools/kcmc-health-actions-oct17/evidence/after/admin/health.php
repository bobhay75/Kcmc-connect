<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/operations-owner.php';
kcmc_require_operations_owner();
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
$requestedStatus = $_GET['status'] ?? '';
$selectedStatus = is_string($requestedStatus) && isset($statusLabels[$requestedStatus]) ? $requestedStatus : '';
$visibleChecks = array_values(array_filter($health['checks'] ?? [], static function (array $check) use ($selectedStatus): bool {
    return $selectedStatus === '' || ($check['status'] ?? 'fail') === $selectedStatus;
}));
$checkActions = [
    'php' => [
        'guidance' => 'Manage the PHP version in your hosting control panel. After a runtime change, return here to check compatibility.',
        'links' => [],
    ],
    'https' => [
        'guidance' => 'Manage the domain certificate and HTTPS redirect in your hosting control panel. This check describes the current administrator request.',
        'links' => [],
    ],
    'content' => [
        'guidance' => 'Review and edit public announcements, events and publications in Publishing. This check confirms the content file can be read; it does not review the information inside it.',
        'links' => [['admin/', 'Open Publishing']],
    ],
    'private_storage' => [
        'guidance' => 'Manage private storage and its permissions in your hosting control panel. Keep private records outside the public website; do not move or publish them to resolve an access problem.',
        'links' => [],
    ],
    'backups' => [
        'guidance' => 'Download a copy of the current public content or open the recovery form. A download does not create a stored automatic backup or reset the backup age shown above. Opening recovery does not restore anything.',
        'links' => [['admin/backup.php', 'Download content backup'], ['admin/restore.php', 'Open content recovery']],
    ],
    'setup_key' => [
        'guidance' => 'After initial account setup, remove the recovery setup key (KCMC_SETUP_KEY) from the hosting configuration. Its value is never displayed here. This screen cannot change server configuration.',
        'links' => [],
    ],
    'invitation_mail' => [
        'guidance' => 'Create and review invitations in Member access. Server readiness does not confirm an invitation reached its recipient. Email is sent only when you explicitly choose to send an invitation there.',
        'links' => [['admin/users.php', 'Manage invitations']],
    ],
    'push_delivery' => [
        'guidance' => 'Open Broadcast updates to review delivery readiness and its device-test controls. Configuration readiness does not confirm delivery. Opening the screen sends no notification.',
        'links' => [['admin/push.php', 'Open push testing']],
    ],
    'pwa' => [
        'guidance' => 'Open KCMC Connect to check the app in your browser. The files being present does not confirm installation on a device. Notification settings apply to this browser.',
        'links' => [['', 'Open KCMC Connect'], ['member/notifications.php', 'This browser’s notifications']],
    ],
    'accounts' => [
        'guidance' => 'Review account access and roles in Member access. Changes to an account require a separate action on that screen.',
        'links' => [['admin/users.php', 'Manage accounts']],
    ],
    'pending_invites' => [
        'guidance' => 'Review current invitations and their activation state in Member access.',
        'links' => [['admin/users.php', 'Manage invitations']],
    ],
    'push_subscriptions' => [
        'guidance' => 'Review subscription counts and testing in Broadcast updates. To change notifications for this device, open this browser’s settings. A stored subscription does not guarantee delivery.',
        'links' => [['admin/push.php', 'Review push subscriptions'], ['member/notifications.php', 'This browser’s notifications']],
    ],
    'audit' => [
        'guidance' => 'Open the protected audit history to review recorded administrative actions.',
        'links' => [['admin/audit.php', 'Open audit history']],
    ],
];
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Release Health • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.health-shell{width:min(1100px,calc(100% - 28px));margin:24px auto 80px}.health-top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}.health-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}.health-stat,.health-check{background:var(--kcmc-panel, #fff);color:var(--kcmc-text, #17324c);border:1px solid var(--kcmc-line, #dce3e7);border-radius:16px;padding:18px}.health-stat strong{display:block;font-size:1.8rem}.health-stat a{font-weight:800}.health-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.health-check{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:start}.health-dot{width:13px;height:13px;border-radius:50%;margin-top:7px;background:var(--kcmc-muted, #607080)}.health-check.pass .health-dot{background:var(--kcmc-success, #2b7a46)}.health-check.warn .health-dot{background:var(--kcmc-warning, #a06b12)}.health-check.fail .health-dot{background:var(--kcmc-error-line, #a33434)}.health-check h2{font-size:1rem;margin:0 0 4px}.health-check p{margin:0;color:var(--kcmc-muted, #536273)}.health-pill{display:inline-block;border-radius:999px;padding:6px 10px;font-weight:800;font-size:.85rem}.health-pill.pass{background:var(--kcmc-success-bg, #e6f3e7);color:var(--kcmc-success, #215b2d)}.health-pill.warn{background:var(--kcmc-warning-bg, #fff3d6);color:var(--kcmc-warning, #77510c)}.health-pill.fail{background:var(--kcmc-error-bg, #fbe4e4);color:var(--kcmc-error, #7d2525)}.health-meta{color:var(--kcmc-muted, #607080);font-size:.9rem}.health-actions{display:flex;gap:10px;flex-wrap:wrap}.health-actions a{text-decoration:none}@media(max-width:760px){.health-summary,.health-grid{grid-template-columns:1fr 1fr}}@media(max-width:520px){.health-summary,.health-grid{grid-template-columns:1fr}}

/* Interactive health controls use native links and disclosures. */
.health-stat-link{display:block;text-decoration:none;color:var(--kcmc-text);transition:border-color .15s,background .15s}.health-stat-link:hover,.health-stat-link[aria-current="true"]{border-color:var(--kcmc-gold)}.health-stat-link .health-stat-action{display:block;color:var(--kcmc-gold);font-size:.85rem;font-weight:700;margin-top:6px}.health-stat-link:focus-visible,.health-check summary:focus-visible,.health-filter a:focus-visible{outline:3px solid var(--kcmc-gold);outline-offset:4px}.health-filter{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:24px 0 14px;scroll-margin-top:24px}.health-filter h2{margin:0;font-size:1.2rem}.health-filter p{margin:0}.health-filter a{color:var(--kcmc-gold)}details.health-check{display:block;padding:0;overflow:visible}details.health-check summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:12px;align-items:start;padding:18px;cursor:pointer;list-style:none;border-radius:16px}details.health-check summary::-webkit-details-marker{display:none}details.health-check summary::marker{content:""}details.health-check summary:hover{background:rgba(214,173,98,.06)}.health-check-title,.health-check-detail,.health-check-state{display:block}.health-check-title{font-weight:800;margin-bottom:4px}.health-check-detail{color:var(--kcmc-muted);overflow-wrap:anywhere}.health-check-state{margin-top:8px;font-size:.85rem;color:var(--kcmc-gold)}.health-chevron{color:var(--kcmc-gold);font-size:1.3rem;line-height:1;transition:transform .15s}details.health-check[open] .health-chevron{transform:rotate(90deg)}.health-check-body{margin:0 18px 18px;padding-top:14px;border-top:1px solid var(--kcmc-line)}.health-check-body p{line-height:1.6}.health-check-body .health-actions{margin-top:14px}.health-empty{grid-column:1/-1;padding:24px;border:1px solid var(--kcmc-line);border-radius:16px}.health-generated{display:block;font-size:1rem;margin-top:6px;color:var(--kcmc-muted)}@media(prefers-reduced-motion:reduce){.health-stat-link,.health-chevron{transition:none}}

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
</head><body class="portal-body"><?php echo kcmc_screen_navigation('admin/operations.php', true); ?><main class="health-shell">
<div class="health-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/operations.php'))?>">← Operations</a><p class="eyebrow">RELEASE HEALTH</p><h1>KCMC production readiness</h1><p class="portal-lead">A read-only operational check of the deployed app. No passwords, tokens, invitation links, prayer content or private-key material are displayed here.</p></div><div><span class="health-pill <?=kcmc_h($overall)?>"><?=kcmc_h($statusLabels[$overall] ?? 'Action needed')?></span></div></div>
<nav class="health-summary" aria-label="Health overview">
<?php foreach (['pass' => 'Checks ready', 'warn' => 'Review', 'fail' => 'Action needed'] as $filterStatus => $filterLabel): ?>
<a class="health-stat health-stat-link" href="<?=kcmc_h(kcmc_url('admin/health.php?status=' . $filterStatus . '#health-checks'))?>"<?=$selectedStatus === $filterStatus ? ' aria-current="true"' : ''?>><span><?=kcmc_h($filterLabel)?></span><strong><?=kcmc_h((string)($summary[$filterStatus] ?? 0))?></strong><span class="health-stat-action">View checks →</span></a>
<?php endforeach; ?>
<a class="health-stat health-stat-link" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>"><span>Active accounts</span><strong><?=kcmc_h((string)($metrics['active_accounts'] ?? 0))?></strong><span class="health-stat-action">Manage accounts →</span></a>
</nav>
<div class="health-filter" id="health-checks"><h2><?=$selectedStatus === '' ? 'All health checks' : kcmc_h($statusLabels[$selectedStatus]) . ' checks'?></h2><p class="health-meta">Select a check for details and next steps.</p><?php if ($selectedStatus !== ''): ?><a href="<?=kcmc_h(kcmc_url('admin/health.php#health-checks'))?>">Show all checks</a><?php endif; ?></div>
<section class="health-grid" aria-label="Release health checks">
<?php foreach ($visibleChecks as $check):
    $status = (string)($check['status'] ?? 'fail');
    $checkId = (string)($check['id'] ?? '');
    $action = $checkActions[$checkId] ?? ['guidance' => 'Review this finding with your hosting administrator.', 'links' => []];
?>
<details class="health-check <?=kcmc_h($status)?>" data-check="<?=kcmc_h($checkId)?>"><summary><span class="health-dot" aria-hidden="true"></span><span><span class="health-check-title"><?=kcmc_h((string)($check['label'] ?? 'Check'))?></span><span class="health-check-detail"><?=kcmc_h((string)($check['detail'] ?? ''))?></span><span class="health-check-state"><?=kcmc_h($statusLabels[$status] ?? 'Action needed')?> · Details &amp; actions</span></span><span class="health-chevron" aria-hidden="true">›</span></summary><div class="health-check-body"><p><?=kcmc_h($action['guidance'])?></p><?php if ($action['links']): ?><div class="health-actions"><?php foreach ($action['links'] as [$path, $label]): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url($path))?>"><?=kcmc_h($label)?></a><?php endforeach; ?></div><?php endif; ?></div></details>
<?php endforeach; ?>
<?php if (!$visibleChecks): ?><div class="health-empty"><p>No checks are currently marked as <?=kcmc_h($statusLabels[$selectedStatus] ?? 'Ready')?>.</p><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/health.php#health-checks'))?>">Show all checks</a></div><?php endif; ?>
</section>
<section class="portal-card portal-section"><p class="eyebrow">FOLLOW-UP</p><h2>New private responses</h2><p class="portal-fine">Counts only are shown here. Names, email addresses, phone numbers and notes stay inside their authenticated inboxes.</p><div class="health-summary"><div class="health-stat"><span>New event RSVPs</span><strong><?=kcmc_h((string)($rsvpFollowUp['new']??0))?></strong><a href="<?=kcmc_h(kcmc_url('admin/rsvps.php?status=new'))?>">Open New RSVPs</a></div><div class="health-stat"><span>New connection requests</span><strong><?=kcmc_h((string)($connectionFollowUp['new']??0))?></strong><a href="<?=kcmc_h(kcmc_url('admin/connections.php?status=new'))?>">Open New Connections</a></div></div></section>
<section class="portal-card portal-section"><p class="eyebrow">CURRENT COUNTS</p><h2>Access and notification state</h2><div class="health-summary"><a class="health-stat health-stat-link" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>"><span>Pending invitations</span><strong><?=kcmc_h((string)($metrics['pending_invites']??0))?></strong><span class="health-stat-action">Manage invitations →</span></a><a class="health-stat health-stat-link" href="<?=kcmc_h(kcmc_url('admin/push.php'))?>"><span>Push subscriptions</span><strong><?=kcmc_h((string)($metrics['active_push_subscriptions']??0))?></strong><span class="health-stat-action">Review subscriptions →</span></a><a class="health-stat health-stat-link" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>"><span>Disabled accounts</span><strong><?=kcmc_h((string)($metrics['disabled_accounts']??0))?></strong><span class="health-stat-action">Manage accounts →</span></a><div class="health-stat"><span>Generated</span><time class="health-generated" datetime="<?=kcmc_h((string)($health['generated_at']??''))?>"><?=kcmc_h(gmdate('M j, g:i A', strtotime((string)($health['generated_at']??'now'))))?> UTC</time></div></div><div class="health-actions"><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>">Member access</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/push.php'))?>">Push updates</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/backup.php'))?>">Download content backup</a></div></section>
</main></body></html>
