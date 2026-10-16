<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/operations-owner.php';
kcmc_require_operations_owner();
require_once __DIR__ . '/../lib/audit-history.php';
$current = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$userStore = kcmc_users_store();
$actorNames = kcmc_audit_actor_names($userStore);
$rows = kcmc_audit_recent_rows(KCMC_AUDIT_LOG, $actorNames, 75);
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Audit History • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.audit-shell{width:min(1100px,calc(100% - 28px));margin:24px auto 80px}.audit-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 0 20px}.audit-list{display:grid;gap:12px}.audit-row{background:var(--kcmc-panel, #fff);color:var(--kcmc-text, #17324c);border:1px solid var(--kcmc-line, #dce3e7);border-radius:14px;padding:16px}.audit-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap}.audit-head h2{font-size:1rem;margin:0}.audit-time{color:var(--kcmc-muted, #607080);font-size:.9rem}.audit-actor{font-weight:700}.audit-context{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.audit-chip{background:var(--kcmc-panel-muted, #eef2f4);border-radius:999px;padding:5px 9px;font-size:.82rem;color:var(--kcmc-muted, #41515f)}.audit-empty{background:var(--kcmc-panel, #fff);border:1px solid var(--kcmc-line, #dce3e7);border-radius:14px;padding:22px;color:var(--kcmc-muted, #607080)}.audit-toolbar a:focus-visible{outline:3px solid var(--kcmc-gold, #174d75);outline-offset:3px}

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
</head><body class="portal-body"><?php echo kcmc_screen_navigation('admin/operations.php', true); ?><main class="audit-shell">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/operations.php'))?>">← Operations</a><p class="eyebrow">ADMINISTRATOR HISTORY</p><h1>Recent KCMC audit events</h1><p class="portal-lead">The newest 75 operational events are shown. This view omits IP hashes, private prayer content, passwords, invitation tokens, push endpoints and raw private records.</p>
<div class="audit-toolbar"><span class="audit-time">CSV export includes the newest <?=kcmc_h((string)KCMC_AUDIT_VIEW_MAX_ROWS)?> privacy-minimized events.</span><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/audit-export.php'))?>">Download CSV</a></div>
<?php if (!$rows): ?><p class="audit-empty">No readable audit events are available yet.</p><?php else: ?><section class="audit-list" aria-label="Recent audit events"><?php foreach ($rows as $row): ?><article class="audit-row"><div class="audit-head"><div><h2><?=kcmc_h((string)$row['label'])?></h2><span class="audit-actor"><?=kcmc_h((string)$row['actor'])?></span></div><time class="audit-time" datetime="<?=kcmc_h((string)$row['at'])?>"><?=kcmc_h(gmdate('M j, Y g:i:s A', strtotime((string)$row['at'])))?> UTC</time></div><?php if (!empty($row['context'])): ?><div class="audit-context"><?php foreach ($row['context'] as $key => $value): ?><span class="audit-chip"><?=kcmc_h(ucwords(str_replace('_',' ',(string)$key)))?>: <?=kcmc_h((string)$value)?></span><?php endforeach; ?></div><?php endif; ?></article><?php endforeach; ?></section><?php endif; ?>
</main></body></html>
