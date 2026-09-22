<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/audit-history.php';
$current = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$userStore = kcmc_users_store();
$actorNames = kcmc_audit_actor_names($userStore);
$rows = kcmc_audit_recent_rows(KCMC_AUDIT_LOG, $actorNames, 75);
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Audit History • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.audit-shell{width:min(1100px,calc(100% - 28px));margin:24px auto 80px}.audit-list{display:grid;gap:12px}.audit-row{background:#fff;border:1px solid #dce3e7;border-radius:14px;padding:16px}.audit-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap}.audit-head h2{font-size:1rem;margin:0}.audit-time{color:#607080;font-size:.9rem}.audit-actor{font-weight:700}.audit-context{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.audit-chip{background:#eef2f4;border-radius:999px;padding:5px 9px;font-size:.82rem;color:#41515f}.audit-empty{background:#fff;border:1px solid #dce3e7;border-radius:14px;padding:22px;color:#607080}
</style></head><body class="portal-body"><main class="audit-shell">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing desk</a><p class="eyebrow">ADMINISTRATOR HISTORY</p><h1>Recent KCMC audit events</h1><p class="portal-lead">The newest 75 operational events are shown. This view omits IP hashes, private prayer content, passwords, invitation tokens, push endpoints and raw private records.</p>
<?php if (!$rows): ?><p class="audit-empty">No readable audit events are available yet.</p><?php else: ?><section class="audit-list" aria-label="Recent audit events"><?php foreach ($rows as $row): ?><article class="audit-row"><div class="audit-head"><div><h2><?=kcmc_h((string)$row['label'])?></h2><span class="audit-actor"><?=kcmc_h((string)$row['actor'])?></span></div><time class="audit-time" datetime="<?=kcmc_h((string)$row['at'])?>"><?=kcmc_h(gmdate('M j, Y g:i:s A', strtotime((string)$row['at'])))?> UTC</time></div><?php if (!empty($row['context'])): ?><div class="audit-context"><?php foreach ($row['context'] as $key => $value): ?><span class="audit-chip"><?=kcmc_h(ucwords(str_replace('_',' ',(string)$key)))?>: <?=kcmc_h((string)$value)?></span><?php endforeach; ?></div><?php endif; ?></article><?php endforeach; ?></section><?php endif; ?>
</main></body></html>
