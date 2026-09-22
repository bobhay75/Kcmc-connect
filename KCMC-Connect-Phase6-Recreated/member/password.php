<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/password-lifecycle.php';
kcmc_private_headers();
$user = kcmc_require_login();
kcmc_session_start();
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $currentPassword = (string)($_POST['current_password'] ?? '');
    $newPassword = (string)($_POST['new_password'] ?? '');
    $confirm = (string)($_POST['confirm_password'] ?? '');
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } elseif (!password_verify($currentPassword, (string)($user['password_hash'] ?? ''))) {
        $error = 'The current password was not recognized.';
    } elseif (($policy = kcmc_password_policy_error($newPassword, $confirm, (string)($user['password_hash'] ?? ''))) !== '') {
        $error = $policy;
    } else {
        $userId = (string)($user['id'] ?? '');
        $changed = kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($userId, $newPassword): bool {
            foreach ($state['users'] as &$stored) {
                if (!is_array($stored) || ($stored['id'] ?? '') !== $userId || empty($stored['active'])) continue;
                $stored['password_hash'] = password_hash($newPassword, PASSWORD_DEFAULT);
                $stored['updated_at'] = gmdate('c');
                unset($stored);
                return true;
            }
            unset($stored);
            return false;
        });
        if (!$changed) {
            $error = 'Your active account could not be updated.';
        } else {
            kcmc_revoke_password_resets_for_user($userId, 'password_changed');
            kcmc_clear_login_failures((string)($user['email_normalized'] ?? $user['email'] ?? ''));
            session_regenerate_id(true);
            $_SESSION['csrf'] = bin2hex(random_bytes(24));
            kcmc_audit('auth.password_changed', ['role' => kcmc_role($user)]);
            $success = 'Password changed successfully. Your current session remains signed in.';
            $user = kcmc_find_user_by_id($userId) ?? $user;
        }
    }
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Account Security • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a>
<section class="portal-card"><p class="eyebrow">ACCOUNT SECURITY</p><h1>Change your password</h1><p>Confirm your current password, then choose a new password with at least 12 characters.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>">
<label>Current password<input type="password" name="current_password" autocomplete="current-password" required autofocus></label>
<label>New password <span class="portal-fine">(at least 12 characters)</span><input type="password" name="new_password" autocomplete="new-password" minlength="12" required></label>
<label>Confirm new password<input type="password" name="confirm_password" autocomplete="new-password" minlength="12" required></label>
<button class="btn gold" type="submit">Change password</button></form>
<p class="portal-fine">Changing your password also invalidates any unused password-reset links previously issued for this account.</p>
</section></main></body></html>
