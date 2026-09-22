<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/push.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('Pragma: no-cache');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

if (strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET')) !== 'GET') {
    header('Allow: GET');
    http_response_code(405);
    echo json_encode(['error' => 'method_not_allowed']);
    exit;
}
$notice = kcmc_push_public_notice();
if ($notice === null) {
    http_response_code(404);
    echo json_encode(['error' => 'no_notice']);
    exit;
}
echo json_encode($notice, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
