<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/password-lifecycle.php';
kcmc_private_headers();
$token = trim((string)($_GET['token'] ?? $_POST['token'] ?? ''));
$reset = kcmc_find_password_reset($token);
$target = $reset ? kcmc_find_user_by_id((string)($reset['user_id'] ?? '')) : null;
if (!$target || empty($target['active'])) {
    $reset = null;
    $target = null;
}
$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $reset && $target) {
    $password = (string)($_POST['password'] ?? '');
    $confirm = (string)($_POST['confirm'] ?? '');
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } elseif (($policy = kcmc_password_policy_error($password, $confirm, (string)($target['password_hash'] ?? ''))) !== '') {
        $error = $policy;
    } else {
        $claimed = kcmc_claim_password_reset($token);
        if (!$claimed) {
            $reset = null;
            $target = null;
            $error = 'This password-reset link was already used or has expired.';
        } else {
            $userId = (string)($claimed['user_id'] ?? '');
            $currentTarget = kcmc_find_user_by_id($userId);
            if (!$currentTarget || empty($currentTarget['active'])) {
                $reset = null;
                $target = null;
                $error = 'This account is not available for password reset.';
            } else {
                $changed = kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($userId, $password): bool {
                    foreach ($state['users'] as &$stored) {
                        if (!is_array($stored) || ($stored['id'] ?? '') !== $userId || empty($stored['active'])) continue;
                        $stored['password_hash'] = password_hash($password, PASSWORD_DEFAULT);
                        $stored['updated_at'] = gmdate('c');
                        unset($stored);
                        return true;
                    }
                    unset($stored);
                    return false;
                });
                if (!$changed) {
                    $reset = null;
                    $target = null;
                    $error = 'The account could not be updated.';
                } else {
                    kcmc_revoke_password_resets_for_user($userId, 'password_reset');
                    kcmc_clear_login_failures((string)($currentTarget['email_normalized'] ?? $currentTarget['email'] ?? ''));
                    kcmc_audit('auth.password_reset_completed', ['role' => kcmc_role($currentTarget)]);
                    header('Location: ' . kcmc_url('member/login.php?reset=1'));
                    exit;
                }
            }
        }
    }
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Reset Password • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow"><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">← Member sign in</a><section class="portal-card">
<?php if (!$reset || !$target): ?>
<p class="eyebrow">RESET LINK UNAVAILABLE</p><h1>This link is no longer valid.</h1><p>Ask a KCMC Connect administrator for a new password-reset link.</p>
<?php else: ?>
<p class="eyebrow">KCMC ACCOUNT RECOVERY</p><h1>Create a new password.</h1><p class="portal-lead">This one-time link is for <?=kcmc_h((string)($target['display_name'] ?? 'your KCMC account'))?> and expires one hour after it is issued.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="token" value="<?=kcmc_h($token)?>">
<label>New password <span class="portal-fine">(at least 12 characters)</span><input type="password" name="password" autocomplete="new-password" minlength="12" required autofocus></label>
<label>Confirm new password<input type="password" name="confirm" autocomplete="new-password" minlength="12" required></label>
<button class="btn gold" type="submit">Reset password</button></form>
<p class="portal-fine">After the reset, this link and any other unused reset links for the account stop working.</p>
<?php endif; ?>
</section></main></body></html>
