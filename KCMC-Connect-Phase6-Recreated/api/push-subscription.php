<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/push-subscriptions.php';
kcmc_private_headers();
header('Content-Type: application/json; charset=utf-8');
$user = kcmc_require_login();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    header('Allow: POST');
    echo json_encode(['ok' => false, 'error' => 'Method not allowed']);
    exit;
}

$raw = file_get_contents('php://input');
$payload = is_string($raw) ? json_decode($raw, true) : null;
if (!is_array($payload) || !kcmc_verify_csrf($payload['csrf'] ?? null)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Invalid request']);
    exit;
}
if (!kcmc_push_enabled()) {
    http_response_code(503);
    echo json_encode(['ok' => false, 'error' => 'Push notifications are not configured']);
    exit;
}

$action = (string)($payload['action'] ?? '');
$userId = (string)($user['id'] ?? '');
if ($action === 'subscribe') {
    $subscription = $payload['subscription'] ?? null;
    if (!is_array($subscription) || !kcmc_push_save_subscription($userId, $subscription)) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'Invalid subscription']);
        exit;
    }
    $endpoint = (string)($subscription['endpoint'] ?? '');
    kcmc_audit('push.subscription_saved', ['endpoint_hash' => hash('sha256', $endpoint)]);
    echo json_encode(['ok' => true, 'active' => kcmc_push_active_for_user($userId)]);
    exit;
}

if ($action === 'unsubscribe') {
    $endpoint = trim((string)($payload['endpoint'] ?? ''));
    $removed = kcmc_push_remove_subscription($userId, $endpoint);
    if ($removed) kcmc_audit('push.subscription_revoked', ['endpoint_hash' => hash('sha256', $endpoint)]);
    echo json_encode(['ok' => true, 'removed' => $removed, 'active' => kcmc_push_active_for_user($userId)]);
    exit;
}

http_response_code(400);
echo json_encode(['ok' => false, 'error' => 'Unknown action']);
