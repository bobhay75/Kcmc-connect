<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    exit('Use the sign-out button to end your session.');
}
if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
    http_response_code(403);
    exit('Invalid request.');
}
if (kcmc_current_user()) kcmc_audit('auth.logout');
kcmc_logout_user();
header('Location: ' . kcmc_url('member/login.php'));
