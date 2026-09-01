<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$next = kcmc_url('admin/');
header('Location: ' . kcmc_url('member/login.php?next=' . rawurlencode($next)));
