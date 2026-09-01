<?php
require_once __DIR__ . '/../lib/bootstrap.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
if (!is_file(KCMC_DATA)) { http_response_code(404); exit('No content'); }
header('Content-Type: application/json');
header('Content-Disposition: attachment; filename="kcmc-content-backup-'.gmdate('Y-m-d-His').'.json"');
readfile(KCMC_DATA);
