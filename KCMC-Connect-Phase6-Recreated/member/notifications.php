<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/push-subscriptions.php';
kcmc_private_headers();
$user = kcmc_require_login();
$enabled = kcmc_push_enabled();
$activeCount = kcmc_push_active_for_user((string)($user['id'] ?? ''));
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Notifications • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><script src="<?=kcmc_h(kcmc_url('member/push-settings.js?v=display-test-20261018'))?>" defer></script><?php require_once __DIR__ . '/../lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
</head>
<body class="portal-body"><?php echo kcmc_screen_navigation('member/', true); ?><main class="portal-shell portal-narrow">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a>
<section class="portal-card" id="push-settings" data-enabled="<?=$enabled ? '1' : '0'?>" data-public-key="<?=kcmc_h(kcmc_push_public_key())?>" data-worker="<?=kcmc_h(kcmc_url('sw.js'))?>" data-api="<?=kcmc_h(kcmc_url('api/push-subscription.php'))?>" data-csrf="<?=kcmc_h(kcmc_csrf())?>">
<p class="eyebrow">NOTIFICATIONS</p><h1>Church updates on this device</h1>
<?php if (!$enabled): ?>
<p class="portal-alert warning">Push notifications are not enabled on the KCMC server yet. No browser permission will be requested.</p>
<p>This page is ready for the final server-side delivery setup, but KCMC Connect does not claim push support until that path is configured and verified.</p>
<?php else: ?>
<p>Choose whether this browser may receive brief KCMC announcements. Permission is requested only after you press Enable.</p>
<p class="portal-fine">The first sender is intentionally generic: no prayer text, custom message content or member data is transmitted in the push request.</p>
<p id="push-status" class="portal-alert" role="status">Checking this device…</p>
<div class="portal-actions"><button class="btn gold" id="push-enable" type="button">Enable notifications</button><button class="btn secondary" id="push-disable" type="button">Disable on this device</button></div>
<p class="portal-fine">Stored active subscriptions for your account: <?=kcmc_h((string)$activeCount)?></p>
<details><summary>Check notification display</summary><p>Try a display test on this device before checking delivery from KCMC. Enable notifications first.</p><button class="btn secondary" id="push-display-test" type="button">Test notification display</button><p id="push-display-status" class="portal-fine" role="status">This display test stays on this device.</p><p class="portal-fine">On Windows, check Settings → System → Notifications: allow notifications for Microsoft Edge or the installed KCMC app, turn on banners, and turn off Do not disturb while testing. Also allow notifications for KCMC in Edge’s site permissions.</p></details>
<?php endif; ?>
</section></main></body></html>
