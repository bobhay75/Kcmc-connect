<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_login();
require_once __DIR__ . '/../lib/push.php';
$vapidReady = kcmc_push_get_vapid(false) !== null;
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Notifications • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><script src="<?=kcmc_h(kcmc_url('member/push.js?v=1'))?>" defer></script></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
<header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a><p class="eyebrow">KCMC NOTIFICATIONS</p><h1>Church updates on this device.</h1><p class="portal-lead">Notifications are optional. KCMC Connect sends public church updates only—never prayer names, medical details, passwords, or private member content.</p></div></header>
<section class="portal-card" data-push-settings data-api="<?=kcmc_h(kcmc_url('member/push.php'))?>" data-sw="<?=kcmc_h(kcmc_url('sw.js'))?>" data-scope="<?=kcmc_h(kcmc_url())?>" data-csrf="<?=kcmc_h(kcmc_csrf())?>">
<p class="eyebrow">THIS DEVICE</p><h2>Push notifications</h2>
<?php if (!$vapidReady): ?><p class="portal-alert warning">Push notifications are not initialized yet. A Recovery administrator must initialize the protected VAPID key first.</p><?php endif; ?>
<p data-push-status role="status" aria-live="polite">Checking notification support…</p>
<div class="portal-actions"><button class="btn gold" type="button" data-push-enable disabled>Enable notifications</button><button class="btn secondary" type="button" data-push-disable hidden>Turn off notifications</button></div>
<p class="portal-fine">Your browser creates a private push subscription for this device. KCMC stores the subscription endpoint in protected server storage so it can wake this browser for public church notices.</p>
</section>
<?php if (kcmc_can_publish($user)): ?><section class="portal-card portal-section"><p class="eyebrow">ADMINISTRATION</p><h2>Send a church notification</h2><p>Pastor and Recovery administrators can send a public KCMC notice to opted-in devices.</p><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/push.php'))?>">Open notification desk</a></section><?php endif; ?>
</main></body></html>
