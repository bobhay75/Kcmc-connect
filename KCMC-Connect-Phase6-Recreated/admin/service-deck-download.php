<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/service-decks.php';

kcmc_private_headers();
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    header('Allow: GET');
    http_response_code(405);
    exit('Method not allowed.');
}

$queryKeys = array_keys($_GET);
sort($queryKeys, SORT_STRING);
if ($queryKeys !== ['artifact', 'job_id']
    || !is_string($_GET['job_id'] ?? null)
    || !is_string($_GET['artifact'] ?? null)) {
    http_response_code(400);
    exit('Invalid download request.');
}

$jobId = $_GET['job_id'];
$artifact = $_GET['artifact'];
if (!kcmc_service_deck_valid_job_id($jobId)
    || !in_array($artifact, ['request', 'deck'], true)) {
    http_response_code(404);
    exit('Private service-deck file not found.');
}

try {
    $record = kcmc_service_deck_get_job($jobId, $user);
    $serviceDate = (string)($record['service_date'] ?? '');
    if (preg_match('/\A[0-9]{4}-[0-9]{2}-[0-9]{2}\z/D', $serviceDate) !== 1) {
        throw new UnexpectedValueException('Service-deck record date is invalid.');
    }

    if ($artifact === 'request') {
        $bytes = kcmc_service_deck_request_bytes($jobId, $user);
        $contentType = 'application/json; charset=utf-8';
        $filename = 'kcmc-front-porch-request-' . $serviceDate . '-' . $jobId . '.json';
        $sha256 = hash('sha256', $bytes);
    } else {
        // read_artifact revalidates the HMAC, request, manifest, readiness,
        // metadata, and a fresh SHA-256 of the exact PHP-owned deck bytes.
        $verified = kcmc_service_deck_read_artifact($jobId, 'deck', $user);
        $bytes = $verified['bytes'];
        if (!is_string($bytes)
            || !is_string($verified['sha256'] ?? null)
            || !hash_equals((string)$verified['sha256'], hash('sha256', $bytes))) {
            throw new UnexpectedValueException('Verified deck bytes are inconsistent.');
        }
        $contentType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
        $filename = 'kcmc-front-porch-service-' . $serviceDate . '-' . $jobId . '.pptx';
        $sha256 = (string)$verified['sha256'];
    }

    kcmc_audit('service_deck.artifact_downloaded', [
        'job_id' => $jobId,
        'artifact' => $artifact,
        'sha256' => $sha256,
        'bytes' => strlen($bytes),
    ]);
    if (session_status() === PHP_SESSION_ACTIVE) session_write_close();
    header('X-Content-Type-Options: nosniff');
    header('Content-Type: ' . $contentType);
    header('Content-Disposition: attachment; filename="' . $filename . '"');
    header('Content-Length: ' . strlen($bytes));
    echo $bytes;
} catch (InvalidArgumentException | OutOfBoundsException $exception) {
    http_response_code(404);
    exit('Private service-deck file not found.');
} catch (Throwable $exception) {
    kcmc_audit('service_deck.download_rejected', [
        'job_id' => $jobId,
        'artifact' => $artifact,
        'reason_type' => get_class($exception),
    ]);
    http_response_code(409);
    exit('The exact verified private artifact is unavailable.');
}
