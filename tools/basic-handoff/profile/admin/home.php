<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_require_role(['pastor_admin', 'recovery_admin']);
header('Location: ' . kcmc_url('admin/'));
exit;
