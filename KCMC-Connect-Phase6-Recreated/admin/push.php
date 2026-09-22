<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/push-subscriptions.php';
kcmc_private_headers();
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_session_start();
$ready = kcmc_push_delivery_ready();
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } elseif (!$ready) {
        $error = 'Push delivery is not fully configured on the server.';
    } elseif ((string)($_POST['confirm_send'] ?? '') !== '1') {
        $error = 'Confirm the broadcast before sending.';
    } elseif (!empty($_SESSION['push_last_send_at']) && time() - (int)$_SESSION['push_last_send_at'] < 30) {
        $error = 'A push broadcast was just attempted. Wait before sending another.';
    } else {
        $_SESSION['push_last_send_at'] = time();
        $sent = 0;
        $expired = 0;
        $failed = 0;
        $subscriptions = array_slice(kcmc_push_active_subscriptions(), 0, 200);
        foreach ($subscriptions as $subscription) {
            $result = kcmc_push_send_empty($subscription);
            if (!empty($result['sent'])) {
                $sent++;
                continue;
            }
            if (!empty($result['expired'])) {
                kcmc_push_deactivate_endpoint((string)$subscription['endpoint'], 'gone');
                $expired++;
                continue;
            }
            $failed++;
        }
        kcmc_audit('push.broadcast_attempted', ['sent' => $sent, 'expired' => $expired, 'failed' => $failed]);
        $success = "Push attempt complete: {$sent} accepted, {$expired} expired subscriptions removed, {$failed} failed.";
    }
}

$active = count(kcmc_push_active_subscriptions());
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Push Updates • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow"><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing desk</a>
<section class="portal-card"><p class="eyebrow">PUSH UPDATES</p><h1>Notify subscribed devices</h1>
<p>This first production-safe sender transmits no private content. Subscribed devices receive a generic KCMC Connect update notification and open the public app.</p>
<p class="portal-fine">Active stored subscriptions: <?=kcmc_h((string)$active)?>. A maximum of 200 subscriptions is processed per manual send.</p>
<?php if (!$ready): ?><p class="portal-alert warning">Delivery is not ready. Configure the VAPID public key, subject and server-only private PEM file before sending.</p><?php endif; ?>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><label class="portal-check"><input type="checkbox" name="confirm_send" value="1" required><span>Send one generic KCMC update notification to all active subscribed devices.</span></label><button class="btn gold" type="submit" <?=$ready && $active > 0 ? '' : 'disabled'?>>Send update</button></form>
<p class="portal-fine">Dead subscriptions that return HTTP 404 or 410 are automatically deactivated. Other delivery failures remain active for later review.</p>
</section></main></body></html>
