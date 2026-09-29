<?php
require_once __DIR__ . '/../lib/public-presentation.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
$data = kcmc_public_content();
$data['announcements'] = kcmc_active_items($data['announcements'] ?? []);
$data['events'] = kcmc_active_items($data['events'] ?? []);
echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
