<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/operations-owner.php';
kcmc_require_operations_owner();
require_once __DIR__ . '/../lib/push-subscriptions.php';
kcmc_private_headers();
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_session_start();
$ready = kcmc_push_delivery_ready();
$error = '';
$success = '';
$warning = '';
$failures = [];

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
                $failure = kcmc_push_failure_label($result);
                $failures[$failure] = ($failures[$failure] ?? 0) + 1;
            }
            $auditCounts = ['sent' => $sent, 'expired' => $expired, 'failed' => $failed];
            if ($scope === 'self') {
                kcmc_audit('push.self_test_attempted', $auditCounts);
            } else {
                kcmc_audit('push.broadcast_attempted', $auditCounts);
            }
            $label = $scope === 'self' ? 'Device test' : 'Broadcast';
            $summary = "{$label}: {$sent} accepted by the push service, {$expired} expired subscriptions removed, {$failed} failed.";
            if ($sent === 0) $error = $summary . ' No notification was accepted. Review the details below before retrying.';
            elseif ($failed > 0) $warning = $summary;
            else $success = $summary . ' Device display and tap behavior still need to be checked on the device.';
        }
    }
}

$active = count($allSubscriptions);
$myActive = count($mySubscriptions);
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Push Updates • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>.push-actions{display:grid;gap:18px}.push-action{border:1px solid #d8e0e5;border-radius:14px;padding:16px}.push-action h2{margin-top:0}.push-checklist{padding-left:1.25rem}.push-checklist li{margin:.45rem 0}</style></head>
<body class="portal-body"><main class="portal-shell portal-narrow"><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/home.php'))?>">← Administration</a>
<section class="portal-card"><p class="eyebrow">PUSH UPDATES</p><h1>Notify subscribed devices</h1>
<p>Send a brief KCMC Connect update to devices that have chosen to receive notifications.</p>
<p class="portal-fine">Subscribed devices: <?=kcmc_h((string)$active)?>. Devices for your account: <?=kcmc_h((string)$myActive)?>.</p>
<?php if (!$ready): ?><div class="portal-alert warning"><p>Delivery is not ready. Resolve the server setup below before sending.</p><ul><?php foreach (kcmc_push_delivery_problems() as $problem): ?><li><?=kcmc_h($problem)?></li><?php endforeach; ?></ul></div><?php endif; ?>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($warning): ?><p class="portal-alert warning" role="status"><?=kcmc_h($warning)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<?php if ($failures): ?><ul class="portal-alert warning" aria-label="Delivery failure details"><?php foreach ($failures as $failure => $count): ?><li><?=kcmc_h($failure)?>: <?=kcmc_h((string)$count)?></li><?php endforeach; ?></ul><?php endif; ?>
<div class="push-actions">
<section class="push-action"><h2>Test my subscribed device</h2><p>Send a test to notifications enabled for your account on up to five devices.</p><form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="send_scope" value="self"><label class="portal-check"><input type="checkbox" name="confirm_send" value="1" required><span>Send a test only to my devices.</span></label><button class="btn gold" type="submit" <?=$ready && $myActive > 0 ? '' : 'disabled'?>>Test my device</button></form></section>
<details class="push-action"><summary>Check delivery on your phone</summary><ol class="push-checklist"><li>Open Notifications on your phone and enable notifications. Confirm this page shows a device for your account.</li><li>Put KCMC Connect in the background. From another window or device, select <strong>Test my device</strong> above.</li><li>Check that the push service accepts the test. Review any failure message before retrying.</li><li>Check that the notification appears on your phone, then tap it to open KCMC Connect.</li><li>To test turning notifications off, disable them on that phone. Reload this page and confirm the device count decreases.</li></ol><p class="portal-fine">Use <strong>Test my device</strong> to check delivery. A broadcast is not needed. Acceptance by the push service does not confirm that your phone displayed the notification.</p></details>
<section class="push-action"><h2>Broadcast to subscribed devices</h2><p>Send an update to everyone who has enabled notifications, up to 200 devices per send.</p><form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="send_scope" value="broadcast"><label class="portal-check"><input type="checkbox" name="confirm_send" value="1" required><span>Send a KCMC update to all subscribed devices.</span></label><button class="btn gold" type="submit" <?=$ready && $active > 0 ? '' : 'disabled'?>>Send update</button></form></section>
</div>
<p class="portal-fine">Wait 30 seconds between sends. Expired device registrations are removed automatically; other failed devices stay registered.</p>
</section></main></body></html>
