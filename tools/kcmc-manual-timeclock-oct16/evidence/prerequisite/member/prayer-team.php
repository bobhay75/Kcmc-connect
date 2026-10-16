<?php
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/screen-navigation.php';
kcmc_private_headers();
kcmc_require_role(['prayer_team', 'pastor_admin']);
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET' && ($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') {
    header('Allow: GET, HEAD');
    kcmc_screen_error('Use the prayer inbox link to open this page.', 405, 'admin/prayer-inbox.php');
}
header('Location: ' . kcmc_url('admin/prayer-inbox.php'), true, 303);
exit;
