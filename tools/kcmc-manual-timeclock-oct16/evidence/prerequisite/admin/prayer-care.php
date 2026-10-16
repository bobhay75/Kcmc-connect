<?php
// Keep one controller and the existing prayer-role, privacy and CSRF checks.
// Only this server-owned route enables the administrative review controls.
define('KCMC_CARE_ADMIN_PAGE', true);
require __DIR__ . '/../member/prayer-care.php';
