<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_require_owner();
if (!is_file(KCMC_DATA)) { http_response_code(404); exit('No content'); }
header('Content-Type: application/json');
header('Content-Disposition: attachment; filename="kcmc-content-backup-'.gmdate('Y-m-d-His').'.json"');
readfile(KCMC_DATA);
