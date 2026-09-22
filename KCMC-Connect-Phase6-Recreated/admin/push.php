<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
require_once __DIR__ . '/../lib/push.php';
$error = '';
$success = '';
$result = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } else {
        $action = (string)($_POST['action'] ?? '');
        if ($action === 'initialize') {
            if (kcmc_role($user) !== 'recovery_admin') {
                $error = 'Only a Recovery administrator can initialize the protected push key.';
            } else {
                try {
                    $vapid = kcmc_push_get_vapid(true);
                    if ($vapid === null) throw new RuntimeException('Push initialization failed.');
                    kcmc_audit('push.vapid_initialized', []);
                    $success = 'Web Push is initialized. Members can now opt in from Notification settings.';
                } catch (Throwable $e) {
                    $error = 'Web Push could not be initialized on this server.';
                }
            }
        } elseif ($action === 'send') {
            $vapid = kcmc_push_get_vapid(false);
            if ($vapid === null) {
                $error = 'Initialize Web Push before sending a notification.';
            } else {
                try {
                    $notice = kcmc_push_save_notice(
                        (string)($_POST['title'] ?? ''),
                        (string)($_POST['body'] ?? ''),
                        (string)($_POST['target'] ?? './'),
                        (string)($user['id'] ?? '')
                    );
                    $result = kcmc_push_send_all($notice, $vapid);
                    kcmc_audit('push.notification_sent', [
                        'notice_id' => (string)$notice['id'],
                        'total' => (int)$result['total'],
                        'sent' => (int)$result['sent'],
                        'failed' => (int)$result['failed'],
                        'gone' => (int)$result['gone'],
                    ]);
                    $success = 'Notification send finished.';
                } catch (InvalidArgumentException $e) {
                    $error = $e->getMessage();
                } catch (Throwable $e) {
                    $error = 'The notification could not be sent.';
                }
            }
        }
    }
}
$vapid = kcmc_push_get_vapid(false);
$count = kcmc_push_subscription_count();
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Notification Desk • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
<header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a><p class="eyebrow">KCMC WEB PUSH</p><h1>Notification Desk</h1><p class="portal-lead">Send public church notices to devices whose users explicitly opted in.</p></div><div class="portal-actions"><a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/notifications.php'))?>">My notification settings</a></div></header>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<section class="portal-card"><p class="eyebrow">STATUS</p><h2><?=is_array($vapid) ? 'Web Push ready' : 'Initialization required'?></h2><p><strong><?=kcmc_h((string)$count)?></strong> opted-in device<?=($count === 1 ? '' : 's')?> currently stored.</p><p class="portal-fine">The VAPID private key is stored only under protected server data and is never committed to Git or returned to browsers.</p>
<?php if (!is_array($vapid) && kcmc_role($user) === 'recovery_admin'): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="initialize"><button class="btn gold" type="submit">Initialize Web Push</button></form><?php elseif (!is_array($vapid)): ?><p class="portal-alert warning">Ask a Recovery administrator to initialize Web Push once.</p><?php endif; ?>
</section>
<section class="portal-card portal-section"><p class="eyebrow">PUBLIC NOTICE ONLY</p><h2>Send a notification</h2><p>Do not put prayer names, medical information, passwords, private member details, or confidential ministry information here. The push request itself carries no message payload; it only wakes the service worker, which fetches this public notice from KCMC.</p>
<form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="send"><label>Title<input name="title" maxlength="80" value="KCMC Connect" required></label><label>Message<textarea name="body" rows="4" maxlength="180" minlength="5" required></textarea></label><label>Open when tapped<input name="target" value="./" pattern="\.\/[A-Za-z0-9._~!$&amp;'()*+,;=:@%/?#-]*" required><span class="portal-fine">Keep this inside KCMC Connect, for example <code>./#events</code> or <code>./bulletin.php</code>.</span></label><button class="btn gold" type="submit" <?=is_array($vapid) ? '' : 'disabled'?>>Send to opted-in devices</button></form>
<?php if (is_array($result)): ?><div class="request-status-list"><div><span>Total</span><strong><?=kcmc_h((string)$result['total'])?></strong></div><div><span>Accepted</span><strong><?=kcmc_h((string)$result['sent'])?></strong></div><div><span>Failed</span><strong><?=kcmc_h((string)$result['failed'])?></strong></div><div><span>Expired subscriptions removed</span><strong><?=kcmc_h((string)$result['gone'])?></strong></div></div><?php endif; ?>
</section>
</main></body></html>
