<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/password-lifecycle.php';
require_once __DIR__ . '/../lib/invitation-mailer.php';
kcmc_private_headers();
$current = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_session_start();
$mailReady = kcmc_invitation_mail_ready();
$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } else {
        $target = kcmc_find_user_by_id((string)($_POST['user_id'] ?? ''));
        if (!$target || empty($target['active'])) {
            $error = 'That active account could not be found.';
        } elseif (!kcmc_can_issue_password_reset($current, $target)) {
            $error = 'This account is outside your password-reset authority. Use Account Security for your own password; elevated administrator resets require the Recovery administrator.';
        } else {
            $created = kcmc_create_password_reset($target, (string)($current['id'] ?? ''));
            if (!$created) {
                $error = 'A password-reset link could not be created.';
            } else {
                $host = preg_match('/^[A-Za-z0-9.-]+(?::\d+)?$/', (string)($_SERVER['HTTP_HOST'] ?? '')) ? (string)$_SERVER['HTTP_HOST'] : 'localhost';
                $scheme = kcmc_is_https() ? 'https' : 'http';
                $link = $scheme . '://' . $host . kcmc_url('member/reset-password.php?token=' . rawurlencode((string)$created['token']));
                $_SESSION['password_reset_link'] = $link;
                $_SESSION['password_reset_name'] = (string)($target['display_name'] ?? 'KCMC member');
                $_SESSION['password_reset_email'] = (string)($target['email'] ?? '');
                $_SESSION['password_reset_send_status'] = '';
                $_SESSION['password_reset_send_success'] = false;
                kcmc_audit('member.password_reset_issued', ['role' => kcmc_role($target)]);

                if ((string)($_POST['send_email'] ?? '') === '1') {
                    $delivery = kcmc_password_reset_delivery($target, $link);
                    if (!$mailReady) {
                        $_SESSION['password_reset_send_status'] = 'Reset link created, but server email is not configured. Use the private link shown below.';
                    } elseif ($delivery === null) {
                        $_SESSION['password_reset_send_status'] = 'Reset link created, but recipient-bound email validation failed. Nothing was emailed.';
                    } else {
                        $send = kcmc_send_invitation_email($delivery);
                        if (!empty($send['sent'])) {
                            $_SESSION['password_reset_send_status'] = 'Password-reset email accepted by the configured server mail transport for ' . (string)$target['email'] . '.';
                            $_SESSION['password_reset_send_success'] = true;
                            kcmc_audit('member.password_reset_email_sent', ['role' => kcmc_role($target)]);
                        } else {
                            $_SESSION['password_reset_send_status'] = 'Reset link created, but the server mail transport did not accept the message. Use the private link shown below.';
                            kcmc_audit('member.password_reset_email_failed', ['role' => kcmc_role($target), 'reason' => (string)($send['reason'] ?? 'unknown')]);
                        }
                    }
                }
                header('Location: ' . kcmc_url('admin/password-resets.php?created=1'));
                exit;
            }
        }
    }
}

$resetLink = (string)($_SESSION['password_reset_link'] ?? '');
$resetName = (string)($_SESSION['password_reset_name'] ?? '');
$resetEmail = (string)($_SESSION['password_reset_email'] ?? '');
$sendStatus = (string)($_SESSION['password_reset_send_status'] ?? '');
$sendSuccess = !empty($_SESSION['password_reset_send_success']);
unset($_SESSION['password_reset_link'], $_SESSION['password_reset_name'], $_SESSION['password_reset_email'], $_SESSION['password_reset_send_status'], $_SESSION['password_reset_send_success']);

$users = kcmc_users();
usort($users, fn($a, $b) => strcmp((string)($a['display_name'] ?? ''), (string)($b['display_name'] ?? '')));
$roleNames = ['member' => 'Member', 'prayer_team' => 'Prayer team', 'pastor_admin' => 'Pastor administrator', 'recovery_admin' => 'Recovery administrator'];
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Password Resets • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.reset-link{width:100%;min-height:92px;padding:10px;border:1px solid #cbd5dc;border-radius:9px;font:inherit;overflow-wrap:anywhere}.reset-row{display:grid;grid-template-columns:1.2fr 1.5fr 1fr 1.3fr;gap:12px;align-items:center;border-top:1px solid #edf0f2;padding:14px 0}.reset-row.header{font-weight:800;border-top:0}.reset-row form{margin:0}.reset-row .portal-check{margin:0 0 8px}@media(max-width:760px){.reset-row{grid-template-columns:1fr}.reset-row.header{display:none}}
</style></head><body class="portal-body"><main class="portal-shell">
<header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a><p class="eyebrow">ACCOUNT RECOVERY</p><h1>Password reset links</h1><p class="portal-lead">Issue a one-time reset link without changing the person’s role or account status.</p></div><a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/password.php'))?>">My account security</a></header>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($resetLink !== ''): ?><section class="portal-card portal-section"><p class="eyebrow">RESET LINK CREATED</p><h2><?=kcmc_h($resetName)?> • <?=kcmc_h($resetEmail)?></h2><p>This recipient-bound link expires in one hour and works once. It is shown only on this request.</p><textarea class="reset-link" readonly aria-label="Password reset link"><?=kcmc_h($resetLink)?></textarea><?php if ($sendStatus !== ''): ?><p class="portal-alert <?=$sendSuccess ? 'success' : 'warning'?>" role="status"><?=kcmc_h($sendStatus)?></p><?php endif; ?></section><?php endif; ?>
<section class="portal-card portal-section"><p class="eyebrow">ACTIVE ACCOUNTS</p><h2>Issue a reset</h2><p class="portal-fine">Pastor administrators can reset Member and Prayer team accounts. Password resets for Pastor or Recovery administrators require the Recovery administrator.</p>
<div class="reset-row header"><span>Name</span><span>Email</span><span>Role</span><span>Action</span></div>
<?php foreach ($users as $target): if (empty($target['active'])) continue; $allowed = kcmc_can_issue_password_reset($current, $target); ?><div class="reset-row"><span><strong><?=kcmc_h((string)($target['display_name'] ?? ''))?></strong></span><span><?=kcmc_h((string)($target['email'] ?? ''))?></span><span><?=kcmc_h($roleNames[kcmc_role($target)] ?? kcmc_role($target))?></span><span><?php if (($target['id'] ?? '') === ($current['id'] ?? '')): ?><a href="<?=kcmc_h(kcmc_url('member/password.php'))?>">Change my password</a><?php elseif ($allowed): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="user_id" value="<?=kcmc_h((string)$target['id'])?>"><?php if ($mailReady): ?><label class="portal-check"><input type="checkbox" name="send_email" value="1"><span>Email reset now</span></label><?php endif; ?><button class="btn secondary" type="submit">Create reset link</button></form><?php else: ?><span class="portal-fine">Recovery administrator required</span><?php endif; ?></span></div><?php endforeach; ?>
</section></main></body></html>
