<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/connection-intake.php';

kcmc_private_headers();
header('Content-Type: application/json; charset=utf-8');

function kcmc_connection_json(int $status, array $payload): never {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    kcmc_connection_json(405, ['ok' => false, 'message' => 'Connection requests require POST.']);
}
if ((string)($_SERVER['HTTP_X_KCMC_CONNECTION'] ?? '') !== '1') {
    kcmc_connection_json(403, ['ok' => false, 'message' => 'Please submit this form from KCMC Connect.']);
}
$fetchSite = strtolower(trim((string)($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '')));
if ($fetchSite === 'cross-site') {
    kcmc_connection_json(403, ['ok' => false, 'message' => 'Cross-site submissions are not accepted.']);
}
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 8192) {
    kcmc_connection_json(413, ['ok' => false, 'message' => 'That request is too large.']);
}

$raw = file_get_contents('php://input');
$payload = is_string($raw) && $raw !== '' ? json_decode($raw, true, 16) : null;
if (!is_array($payload)) {
    kcmc_connection_json(400, ['ok' => false, 'message' => 'The request could not be read.']);
}
$kind = strtolower(trim((string)($payload['kind'] ?? '')));
$rate = kcmc_connection_consume_rate(kcmc_connection_client_hash((string)($_SERVER['REMOTE_ADDR'] ?? 'unknown')));
if (empty($rate['allowed'])) {
    $retry = max(1, (int)($rate['retry_after'] ?? 60));
    header('Retry-After: ' . $retry);
    kcmc_connection_json(429, ['ok' => false, 'message' => 'Please wait a few minutes before sending another request.']);
}

$validated = kcmc_connection_validate($kind, $payload);
if (empty($validated['ok'])) {
    kcmc_connection_json(422, ['ok' => false, 'message' => (string)($validated['error'] ?? 'Check the form and try again.')]);
}
$result = kcmc_connection_store($validated['value']);
if (!empty($result['duplicate'])) {
    kcmc_connection_json(200, ['ok' => true, 'duplicate' => true, 'message' => 'KCMC already received this request.']);
}
if (empty($result['stored'])) {
    kcmc_connection_json(500, ['ok' => false, 'message' => 'The request could not be saved. Please call the church office.']);
}

$auditAction = match ($kind) {
    'visit' => 'connection.visit_submitted',
    'serve' => 'connection.serve_submitted',
    'groups' => 'connection.group_submitted',
    default => 'connection.submitted',
};
kcmc_audit($auditAction, ['count' => 1]);
kcmc_connection_json(201, ['ok' => true, 'duplicate' => false, 'message' => 'Thank you. KCMC has received your request.']);
