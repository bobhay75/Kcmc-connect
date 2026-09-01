<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
if (!kcmc_has_any_users()) {
    header('Location: ' . kcmc_url('admin/setup.php'));
    exit;
}
$next = kcmc_safe_next((string)($_GET['next'] ?? $_POST['next'] ?? ''), 'member/');
if (kcmc_current_user()) {
    header('Location: ' . $next);
    exit;
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = kcmc_normalize_email((string)($_POST['email'] ?? ''));
    $password = (string)($_POST['password'] ?? '');
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload the page and try again.';
    } elseif (kcmc_login_is_blocked($email)) {
        $error = 'Sign-in is temporarily locked. Please wait 15 minutes or contact a KCMC administrator.';
    } else {
        $user = kcmc_find_user_by_email($email);
        if ($user && !empty($user['active']) && password_verify($password, (string)($user['password_hash'] ?? ''))) {
            if (password_needs_rehash((string)$user['password_hash'], PASSWORD_DEFAULT)) {
                kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($user, $password): void {
                    foreach ($state['users'] as &$stored) if (($stored['id'] ?? '') === ($user['id'] ?? '')) $stored['password_hash'] = password_hash($password, PASSWORD_DEFAULT);
                    unset($stored);
                });
            }
            kcmc_clear_login_failures($email);
            kcmc_update_user_login((string)$user['id']);
            kcmc_login_user($user);
            kcmc_audit('auth.login', ['role' => kcmc_role($user)]);
            header('Location: ' . $next);
            exit;
        }
        kcmc_record_login_failure($email);
        $error = 'The email or password was not recognized.';
    }
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Member Sign In • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
  <a class="portal-back" href="<?=kcmc_h(kcmc_url())?>">← KCMC Connect</a>
  <section class="portal-card">
    <p class="eyebrow">KCMC MEMBERS</p><h1>Welcome back.</h1>
    <p class="portal-lead">Prayer and member information stay behind verified sign-in.</p>
    <?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
    <?php if (isset($_GET['activated'])): ?><p class="portal-alert success">Your password is ready. You can sign in now.</p><?php endif; ?>
    <form class="portal-form" method="post">
      <input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="next" value="<?=kcmc_h($next)?>">
      <label>Email address<input type="email" name="email" autocomplete="email" required autofocus></label>
      <label>Password<input type="password" name="password" autocomplete="current-password" required></label>
      <button class="btn gold" type="submit">Sign in securely</button>
    </form>
    <p class="portal-fine">New members receive a one-time invitation from a KCMC administrator to create their password.</p>
  </section>
</main></body></html>
