<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
kcmc_logout_user();
header('Location: ' . kcmc_url('member/login.php'));
