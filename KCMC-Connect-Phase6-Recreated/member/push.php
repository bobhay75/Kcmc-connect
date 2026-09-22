<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_login();
require_once __DIR__ . '/../lib/push.php';
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

function kcmc_push_json(array $payload, int $status = 200): never {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

$method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
if ($method === 'GET') {
    $vapid = kcmc_push_get_vapid(false);
    kcmc_push_json([
        'enabled' => is_array($vapid),
        'public_key' => is_array($vapid) ? (string)$vapid['public_key'] : null,
    ]);
}
if ($method !== 'POST') {
    header('Allow: GET, POST');
    kcmc_push_json(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$raw = file_get_contents('php://input');
if (!is_string($raw) || strlen($raw) > 16384) kcmc_push_json(['ok' => false, 'error' => 'invalid_request'], 400);
$input = json_decode($raw, true);
if (!is_array($input)) kcmc_push_json(['ok' => false, 'error' => 'invalid_json'], 400);
if (!kcmc_verify_csrf(isset($input['csrf']) ? (string)$input['csrf'] : null)) kcmc_push_json(['ok' => false, 'error' => 'csrf'], 403);

$action = (string)($input['action'] ?? '');
if ($action === 'subscribe') {
    if (kcmc_push_get_vapid(false) === null) kcmc_push_json(['ok' => false, 'error' => 'push_not_configured'], 503);
    $subscription = is_array($input['subscription'] ?? null) ? $input['subscription'] : [];
    if (!kcmc_push_save_subscription($subscription, $user)) kcmc_push_json(['ok' => false, 'error' => 'invalid_subscription'], 400);
    kcmc_audit('push.subscription_saved', []);
    kcmc_push_json(['ok' => true]);
}
if ($action === 'unsubscribe') {
    $endpoint = trim((string)($input['endpoint'] ?? ''));
    if ($endpoint === '' || strlen($endpoint) > 4096) kcmc_push_json(['ok' => false, 'error' => 'invalid_endpoint'], 400);
    $removed = kcmc_push_remove_subscription($endpoint, $user);
    kcmc_audit('push.subscription_removed', ['removed' => $removed]);
    kcmc_push_json(['ok' => true, 'removed' => $removed]);
}

kcmc_push_json(['ok' => false, 'error' => 'invalid_action'], 400);
