<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_role(['prayer_team', 'pastor_admin']);
$store = kcmc_read_json_store(KCMC_PRAYERS, ['version' => 1, 'prayers' => []]);
$prayers = array_values(array_filter($store['prayers'] ?? [], fn($p) => is_array($p) && in_array(($p['status'] ?? ''), ['private', 'pending', 'approved'], true)));
usort($prayers, fn($a, $b) => strcmp((string)($b['created_at'] ?? ''), (string)($a['created_at'] ?? '')));
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Prayer Team • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head><body class="portal-body"><main class="portal-shell">
<header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a><p class="eyebrow">PRAYER TEAM</p><h1>Confidential prayer inbox</h1><p class="portal-lead">Do not copy or share requests outside their approved audience.</p></div><?php if (kcmc_can_moderate_prayers($user)): ?><a class="btn gold" href="<?=kcmc_h(kcmc_url('admin/prayers.php'))?>">Pastor approvals</a><?php endif; ?></header>
<section class="portal-card"><div class="prayer-list"><?php if (!$prayers): ?><p class="portal-empty">No active requests.</p><?php endif; ?><?php foreach ($prayers as $prayer): ?><article class="prayer-card private"><div class="prayer-meta"><strong><?=kcmc_h((string)($prayer['public_name'] ?? 'Anonymous'))?></strong><span class="status-pill"><?=kcmc_h(ucwords((string)($prayer['status'] ?? 'received')))?></span><time><?=kcmc_h(date('M j, Y g:i A', strtotime((string)$prayer['created_at'])))?></time></div><p><?=nl2br(kcmc_h((string)$prayer['message']))?></p><small><?=($prayer['audience'] ?? '') === 'members' ? 'Member sharing requested' : 'Pastors and prayer team only'?></small></article><?php endforeach; ?></div></section>
</main></body></html>
