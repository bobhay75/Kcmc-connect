<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
kcmc_require_role(['prayer_team', 'pastor_admin']);
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET' && ($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') {
    http_response_code(405);
    header('Allow: GET, HEAD');
    exit('Use the prayer inbox link to open this page.');
}
header('Location: ' . kcmc_url('admin/prayer-inbox.php'), true, 303);
exit;
