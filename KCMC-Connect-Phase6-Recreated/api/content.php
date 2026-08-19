<?php
require_once __DIR__ . '/../lib/bootstrap.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: public, max-age=60, stale-while-revalidate=300');
$data = kcmc_content();
$data['announcements'] = kcmc_active_items($data['announcements'] ?? []);
$data['events'] = kcmc_active_items($data['events'] ?? []);
echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
