<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/event-rsvp.php';

kcmc_private_headers();
header('Content-Type: application/json; charset=utf-8');

function kcmc_rsvp_json(int $status, array $payload): never {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    kcmc_rsvp_json(405, ['ok' => false, 'message' => 'RSVP submissions require POST.']);
}

if ((string)($_SERVER['HTTP_X_KCMC_RSVP'] ?? '') !== '1') {
    kcmc_rsvp_json(403, ['ok' => false, 'message' => 'Please submit the RSVP from KCMC Connect.']);
}

$fetchSite = strtolower(trim((string)($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '')));
if ($fetchSite === 'cross-site') {
    kcmc_rsvp_json(403, ['ok' => false, 'message' => 'Cross-site RSVP submissions are not accepted.']);
}

$contentLength = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($contentLength > 8192) {
    kcmc_rsvp_json(413, ['ok' => false, 'message' => 'That RSVP is too large.']);
}

$raw = file_get_contents('php://input');
$input = is_string($raw) && $raw !== '' ? json_decode($raw, true, 16) : null;
if (!is_array($input)) {
    kcmc_rsvp_json(400, ['ok' => false, 'message' => 'The RSVP could not be read.']);
}

$clientHash = kcmc_event_rsvp_client_hash((string)($_SERVER['REMOTE_ADDR'] ?? 'unknown'));
$rate = kcmc_event_rsvp_consume_rate($clientHash);
if (empty($rate['allowed'])) {
    $retry = max(1, (int)($rate['retry_after'] ?? 60));
    header('Retry-After: ' . $retry);
    kcmc_rsvp_json(429, ['ok' => false, 'message' => 'Please wait a few minutes before sending another RSVP.']);
}

$validated = kcmc_event_rsvp_validate_input($input);
if (empty($validated['ok'])) {
    kcmc_rsvp_json(422, ['ok' => false, 'message' => (string)($validated['error'] ?? 'Check the RSVP details and try again.')]);
}

$value = $validated['value'];
$content = kcmc_content();
$events = is_array($content['events'] ?? null) ? $content['events'] : [];
if (!kcmc_event_rsvp_event_is_open($events, (string)$value['event'], (string)$value['event_date'])) {
    kcmc_rsvp_json(409, ['ok' => false, 'message' => 'That event is not currently accepting RSVPs.']);
}

$result = kcmc_event_rsvp_store($value);
if (!empty($result['duplicate'])) {
    kcmc_rsvp_json(200, ['ok' => true, 'duplicate' => true, 'message' => 'Your RSVP was already received.']);
}
if (empty($result['stored'])) {
    kcmc_rsvp_json(500, ['ok' => false, 'message' => 'The RSVP could not be saved. Please call the church office.']);
}

kcmc_audit('event.rsvp_submitted', ['count' => 1]);
kcmc_rsvp_json(201, ['ok' => true, 'duplicate' => false, 'message' => 'Your RSVP has been received by KCMC.']);
