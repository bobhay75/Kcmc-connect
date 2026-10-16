<?php
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/screen-navigation.php';
kcmc_private_headers();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    kcmc_screen_error('Use the sign-out button to end your session.', 405, 'member/', false);
}
if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
    kcmc_screen_error('Invalid request.', 403, 'member/', false);
}
if (kcmc_current_user()) kcmc_audit('auth.logout');
kcmc_logout_user();
header('Location: ' . kcmc_url('member/login.php'));
