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

$allSubscriptions = kcmc_push_active_subscriptions();
$currentUserId = (string)($user['id'] ?? '');
$mySubscriptions = array_values(array_filter($allSubscriptions, static function ($subscription) use ($currentUserId): bool {
    return is_array($subscription) && $currentUserId !== '' && (string)($subscription['user_id'] ?? '') === $currentUserId;
}));

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $scope = (string)($_POST['send_scope'] ?? '');
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } elseif (!$ready) {
        $error = 'Push delivery is not fully configured on the server.';
    } elseif (!in_array($scope, ['self', 'broadcast'], true)) {
        $error = 'Choose a valid push action.';
    } elseif ((string)($_POST['confirm_send'] ?? '') !== '1') {
        $error = $scope === 'self' ? 'Confirm the device test before sending.' : 'Confirm the broadcast before sending.';
    } elseif (!empty($_SESSION['push_last_send_at']) && time() - (int)$_SESSION['push_last_send_at'] < 30) {
        $error = 'A push send was just attempted. Wait before sending another.';
    } else {
        $subscriptions = $scope === 'self' ? array_slice($mySubscriptions, 0, 5) : array_slice($allSubscriptions, 0, 200);
        if (!$subscriptions) {
            $error = $scope === 'self' ? 'This signed-in account has no active subscribed devices.' : 'There are no active subscribed devices.';
        } else {
            $_SESSION['push_last_send_at'] = time();
            $sent = 0;
            $expired = 0;
            $failed = 0;
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
            $auditAction = $scope === 'self' ? 'push.self_test_attempted' : 'push.broadcast_attempted';
            kcmc_audit($auditAction, ['sent' => $sent, 'expired' => $expired, 'failed' => $failed]);
            $label = $scope === 'self' ? 'Device test' : 'Broadcast';
            $success = "{$label} complete: {$sent} accepted, {$expired} expired subscriptions removed, {$failed} failed.";
        }
    }
}

$active = count($allSubscriptions);
$myActive = count($mySubscriptions);
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Push Updates • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>.push-actions{display:grid;gap:18px}.push-action{border:1px solid #d8e0e5;border-radius:14px;padding:16px}.push-action h2{margin-top:0}</style></head>
<body class="portal-body"><main class="portal-shell portal-narrow"><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing desk</a>
<section class="portal-card"><p class="eyebrow">PUSH UPDATES</p><h1>Notify subscribed devices</h1>
<p>This production-safe sender transmits no private content. Subscribed devices receive a generic KCMC Connect update notification and open the public app.</p>
<p class="portal-fine">Active stored subscriptions: <?=kcmc_h((string)$active)?>. Signed-in account subscriptions: <?=kcmc_h((string)$myActive)?>.</p>
<?php if (!$ready): ?><p class="portal-alert warning">Delivery is not ready. Configure the VAPID public key, subject and server-only private PEM file before sending.</p><?php endif; ?>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<div class="push-actions">
<section class="push-action"><h2>Test my subscribed device</h2><p>Use this first during release verification. It targets only active subscriptions belonging to the account currently signed in here, up to five devices.</p><form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="send_scope" value="self"><label class="portal-check"><input type="checkbox" name="confirm_send" value="1" required><span>Send one generic KCMC test notification only to my subscribed device(s).</span></label><button class="btn gold" type="submit" <?=$ready && $myActive > 0 ? '' : 'disabled'?>>Test my device</button></form></section>
<section class="push-action"><h2>Broadcast to subscribed devices</h2><p>Use this after the signed-in-device test succeeds. A maximum of 200 active subscriptions is processed per manual broadcast.</p><form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="send_scope" value="broadcast"><label class="portal-check"><input type="checkbox" name="confirm_send" value="1" required><span>Send one generic KCMC update notification to all active subscribed devices.</span></label><button class="btn gold" type="submit" <?=$ready && $active > 0 ? '' : 'disabled'?>>Send update</button></form></section>
</div>
<p class="portal-fine">A 30-second guard applies to both actions. Dead subscriptions that return HTTP 404 or 410 are automatically deactivated. Other delivery failures remain active for later review.</p>
</section></main></body></html>
