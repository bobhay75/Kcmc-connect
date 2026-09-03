<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();

if (!kcmc_has_any_users()) {
    header('Location: ' . kcmc_url('admin/setup.php'));
    exit;
}

$staff = [
    'tony' => 'Pastor Tony Blevins',
    'barry' => 'Associate Pastor Barry Smith',
];
$expectedCode = trim((string)(getenv('KCMC_STAFF_INITIAL_CODE') ?: ''));
$enabled = $expectedCode !== '';
$error = '';
$selected = (string)($_POST['staff'] ?? 'tony');

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $enabled) {
    $code = trim((string)($_POST['temporary_code'] ?? ''));
    $email = kcmc_normalize_email((string)($_POST['email'] ?? ''));
    $password = (string)($_POST['password'] ?? '');
    $confirm = (string)($_POST['confirm'] ?? '');
    $name = $staff[$selected] ?? '';
    $rateKey = 'first-login-' . ($selected !== '' ? $selected : 'unknown');

    $alreadyClaimed = false;
    if ($name !== '') {
        foreach (kcmc_users() as $existing) {
            if (strcasecmp(trim((string)($existing['display_name'] ?? '')), $name) === 0 && !empty($existing['active'])) {
                $alreadyClaimed = true;
                break;
            }
        }
    }

    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload the page and try again.';
    } elseif ($name === '') {
        $error = 'Choose your name.';
    } elseif (kcmc_login_is_blocked($rateKey)) {
        $error = 'First sign-in is temporarily locked. Please wait 15 minutes or contact the KCMC administrator.';
    } elseif (!hash_equals($expectedCode, $code)) {
        kcmc_record_login_failure($rateKey);
        $error = 'The temporary first-sign-in code was not recognized.';
    } elseif ($alreadyClaimed) {
        $error = 'This pastor account has already been personalized. Use the regular sign-in page.';
    } elseif (!kcmc_valid_email($email)) {
        $error = 'Enter your email address.';
    } elseif (($existingEmail = kcmc_find_user_by_email($email)) && !empty($existingEmail['active'])) {
        $error = 'That email address is already attached to an active KCMC Connect account.';
    } elseif (strlen($password) < 12) {
        $error = 'Create a personal password with at least 12 characters.';
    } elseif ($password !== $confirm) {
        $error = 'The personal passwords do not match.';
    } else {
        $user = [
            'id' => kcmc_random_id('usr'),
            'email' => $email,
            'email_normalized' => $email,
            'display_name' => $name,
            'role' => 'pastor_admin',
            'password_hash' => password_hash($password, PASSWORD_DEFAULT),
            'active' => true,
            'created_at' => gmdate('c'),
            'updated_at' => gmdate('c'),
            'last_login_at' => gmdate('c'),
            'onboarding_completed_at' => gmdate('c'),
        ];

        kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($user, $name, $email): void {
            foreach ($state['users'] as $stored) {
                if (!empty($stored['active']) && strcasecmp(trim((string)($stored['display_name'] ?? '')), $name) === 0) {
                    throw new RuntimeException('This pastor account has already been personalized.');
                }
                if (!empty($stored['active']) && kcmc_normalize_email((string)($stored['email'] ?? '')) === $email) {
                    throw new RuntimeException('That email is already in use.');
                }
            }
            $state['users'][] = $user;
        });

        kcmc_clear_login_failures($rateKey);
        kcmc_login_user($user);
        kcmc_audit('auth.pastor_first_login_completed', ['role' => 'pastor_admin', 'staff' => $selected]);
        header('Location: ' . kcmc_url('admin/'));
        exit;
    }
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Pastor First Sign In • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
  <a class="portal-back" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">← Regular sign in</a>
  <section class="portal-card">
    <p class="eyebrow">KCMC CONNECT • FIRST SIGN IN</p>
    <h1>Personalize your pastor account.</h1>
    <p class="portal-lead">Use the temporary code provided by KCMC. Before entering the admin area, choose your own email address and a private password known only to you.</p>
    <?php if (!$enabled): ?><p class="portal-alert warning">Pastor first sign-in is currently locked. The server administrator must configure the private KCMC_STAFF_INITIAL_CODE value.</p><?php endif; ?>
    <?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
    <?php if ($enabled): ?>
    <form class="portal-form" method="post">
      <input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>">
      <label>Your name<select name="staff" required><option value="tony" <?=$selected === 'tony' ? 'selected' : ''?>>Pastor Tony Blevins</option><option value="barry" <?=$selected === 'barry' ? 'selected' : ''?>>Associate Pastor Barry Smith</option></select></label>
      <label>Temporary first-sign-in code<input name="temporary_code" type="password" inputmode="numeric" autocomplete="one-time-code" required></label>
      <label>Your email address<input type="email" name="email" autocomplete="email" required></label>
      <label>Create your personal password <span class="portal-fine">(at least 12 characters)</span><input name="password" type="password" minlength="12" autocomplete="new-password" required></label>
      <label>Confirm your personal password<input name="confirm" type="password" minlength="12" autocomplete="new-password" required></label>
      <button class="btn gold" type="submit">Finish setup and enter KCMC Connect</button>
    </form>
    <?php endif; ?>
    <p class="portal-fine">The temporary code is only for initial setup. After personalization, use your email address and personal password on the regular sign-in page.</p>
  </section>
</main></body></html>
