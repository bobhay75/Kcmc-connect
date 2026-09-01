<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
if (kcmc_has_any_users()) {
    header('Location: ' . kcmc_url('member/login.php?next=' . rawurlencode(kcmc_url('admin/'))));
    exit;
}
$cfg = kcmc_config();
$expected = (string)($cfg['setup_key'] ?? '');
$setupEnabled = $expected !== '';
$error = '';
if ($setupEnabled && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $key = (string)($_POST['setup_key'] ?? '');
    $name = trim((string)($_POST['display_name'] ?? ''));
    $email = kcmc_normalize_email((string)($_POST['email'] ?? ''));
    $password = (string)($_POST['password'] ?? '');
    $confirm = (string)($_POST['confirm'] ?? '');
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) $error = 'Please reload and try again.';
    elseif (!hash_equals($expected, $key)) $error = 'Invalid setup key.';
    elseif (kcmc_text_length($name) < 2) $error = 'Enter your name.';
    elseif (!kcmc_valid_email($email)) $error = 'Enter a valid email address.';
    elseif (strlen($password) < 12) $error = 'Use at least 12 characters.';
    elseif ($password !== $confirm) $error = 'Passwords do not match.';
    else {
        $user = [
            'id' => kcmc_random_id('usr'),
            'email' => $email,
            'email_normalized' => $email,
            'display_name' => $name,
            'role' => 'recovery_admin',
            'password_hash' => password_hash($password, PASSWORD_DEFAULT),
            'active' => true,
            'created_at' => gmdate('c'),
            'updated_at' => gmdate('c'),
            'last_login_at' => null,
        ];
        $created = kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($user): bool {
            if (!empty($state['users'])) return false;
            $state['users'][] = $user;
            return true;
        });
        if (!$created) {
            $error = 'Setup is already complete. Sign in with the existing account.';
        } else {
            kcmc_login_user($user);
            kcmc_audit('auth.recovery_admin_created', ['role' => 'recovery_admin']);
            header('Location: ' . kcmc_url('admin/users.php?setup=1'));
            exit;
        }
    }
}
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>KCMC Secure Setup</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head><body class="portal-body"><main class="portal-shell portal-narrow"><a class="portal-back" href="<?=kcmc_h(kcmc_url())?>">← KCMC Connect</a><section class="portal-card"><p class="eyebrow">KCMC CONNECT • SECURE SETUP</p><h1>Create the recovery administrator.</h1><p class="portal-lead">This account maintains publishing and member access but does not receive private prayer-content access.</p>
<?php if (!$setupEnabled): ?><p class="portal-alert warning">Setup is locked. Configure the private <code>KCMC_SETUP_KEY</code> server environment value, complete this form, then remove the key.</p>
<?php else: ?><?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?><form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><label>Private setup key<input name="setup_key" required autocomplete="off"></label><label>Your name<input name="display_name" required autocomplete="name"></label><label>Your email<input type="email" name="email" required autocomplete="email"></label><label>New password <span class="portal-fine">(at least 12 characters)</span><input name="password" type="password" required minlength="12" autocomplete="new-password"></label><label>Confirm password<input name="confirm" type="password" required minlength="12" autocomplete="new-password"></label><button class="btn gold" type="submit">Create secure account</button></form><?php endif; ?>
</section></main></body></html>
