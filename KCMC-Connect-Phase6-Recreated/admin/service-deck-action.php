<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/service-decks.php';

kcmc_private_headers();
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    exit('Method not allowed.');
}
if (!kcmc_verify_csrf(isset($_POST['csrf']) && is_string($_POST['csrf']) ? $_POST['csrf'] : null)) {
    http_response_code(403);
    exit('Invalid request.');
}

/** @return never */
function kcmc_service_deck_action_redirect(string $kind, string $message): void {
    $query = http_build_query([$kind => $message], '', '&', PHP_QUERY_RFC3986);
    header('Location: ' . kcmc_url('admin/service-decks.php?' . $query), true, 303);
    exit;
}

function kcmc_service_deck_action_string(mixed $value, string $label): string {
    if (!is_string($value)) {
        throw new InvalidArgumentException($label . ' must be text.');
    }
    return $value;
}

function kcmc_service_deck_action_exact_post_fields(array $allowed): void {
    foreach (array_keys($_POST) as $field) {
        if (!is_string($field) || !in_array($field, $allowed, true)) {
            throw new InvalidArgumentException('The request contains an unsupported field.');
        }
    }
}

/** Normalize the form into the worker's type-specific request keys. */
function kcmc_service_deck_action_items(mixed $posted): array {
    if (!is_array($posted)) {
        throw new InvalidArgumentException('Service items are required.');
    }
    $items = [];
    foreach (array_values($posted) as $postedItem) {
        if (!is_array($postedItem) || array_is_list($postedItem)) {
            throw new InvalidArgumentException('Each service item must be an object.');
        }
        $type = kcmc_service_deck_action_string($postedItem['type'] ?? null, 'Service item type');
        $allowed = ['type', 'title'];
        if ($type === 'song') $allowed[] = 'lyrics';
        if (in_array($type, ['service_title', 'scripture', 'sermon_title', 'announcement'], true)) {
            $allowed[] = 'text';
        }
        foreach (array_keys($postedItem) as $key) {
            if (!is_string($key) || !in_array($key, $allowed, true)) {
                throw new InvalidArgumentException('A service item contains an unsupported field.');
            }
        }
        $title = kcmc_service_deck_action_string($postedItem['title'] ?? '', 'Service item title');
        $item = ['type' => $type, 'title' => $title];
        if ($type === 'song') {
            $lyrics = kcmc_service_deck_action_string(
                $postedItem['lyrics'] ?? '',
                'Song lyrics'
            );
            if (trim($lyrics) !== '') $item['lyrics'] = $lyrics;
        } elseif (in_array($type, ['service_title', 'scripture', 'sermon_title', 'announcement'], true)) {
            $text = kcmc_service_deck_action_string($postedItem['text'] ?? '', 'Service item text');
            if (trim($text) !== '' || in_array($type, ['scripture', 'announcement'], true)) {
                $item['text'] = $text;
            }
        }
        $items[] = $item;
    }
    return $items;
}

/**
 * Read an actual HTTP upload without trusting a client-supplied path, MIME
 * type, or byte count.
 */
function kcmc_service_deck_action_upload(
    string $field,
    int $maximumBytes,
    callable $validName,
    string $label
): string {
    $upload = $_FILES[$field] ?? null;
    if (!is_array($upload)
        || is_array($upload['name'] ?? null)
        || is_array($upload['tmp_name'] ?? null)
        || is_array($upload['error'] ?? null)
        || is_array($upload['size'] ?? null)) {
        throw new InvalidArgumentException($label . ' upload is required.');
    }
    if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        throw new InvalidArgumentException($label . ' upload did not complete.');
    }
    $name = $upload['name'] ?? null;
    $temporary = $upload['tmp_name'] ?? null;
    if (!is_string($name) || !$validName($name)
        || !is_string($temporary) || $temporary === '' || !is_uploaded_file($temporary)) {
        throw new InvalidArgumentException($label . ' upload is invalid.');
    }
    $size = @filesize($temporary);
    if (!is_int($size) || $size < 1 || $size > $maximumBytes
        || !is_int($upload['size'] ?? null) || $upload['size'] !== $size) {
        throw new InvalidArgumentException($label . ' upload has an invalid size.');
    }
    $bytes = @file_get_contents($temporary);
    if (!is_string($bytes) || strlen($bytes) !== $size) {
        throw new RuntimeException('Could not read an uploaded service-deck artifact.');
    }
    return $bytes;
}

function kcmc_service_deck_action_exact_uploads(): void {
    $fields = array_keys($_FILES);
    sort($fields, SORT_STRING);
    if ($fields !== ['deck', 'envelope', 'manifest']) {
        throw new InvalidArgumentException('Import requires exactly three approved artifacts.');
    }
}

/** @return never */
function kcmc_service_deck_action_forbidden(string $message): void {
    http_response_code(403);
    exit($message);
}

$action = isset($_POST['action']) && is_string($_POST['action']) ? $_POST['action'] : '';
$actionForAudit = in_array($action, ['create', 'import', 'approve', 'request_changes'], true)
    ? $action
    : 'unknown';
$jobIdForAudit = isset($_POST['job_id']) && is_string($_POST['job_id']) ? $_POST['job_id'] : '';

try {
    if ($action === 'create') {
        kcmc_service_deck_action_exact_post_fields([
            'csrf', 'action', 'service_name', 'service_date', 'service_style', 'items',
        ]);
        if ($_FILES !== []) {
            throw new InvalidArgumentException('A service request does not accept uploads.');
        }
        $record = kcmc_service_deck_create_job([
            'service_name' => kcmc_service_deck_action_string(
                $_POST['service_name'] ?? null,
                'Service name'
            ),
            'service_date' => kcmc_service_deck_action_string(
                $_POST['service_date'] ?? null,
                'Service date'
            ),
            'service_style' => kcmc_service_deck_action_string(
                $_POST['service_style'] ?? KCMC_SERVICE_STYLE,
                'Service style'
            ),
            'items' => kcmc_service_deck_action_items($_POST['items'] ?? null),
        ], $user);
        kcmc_audit('service_deck.request_created', [
            'job_id' => (string)$record['job_id'],
            'item_count' => (int)$record['item_count'],
            'request_sha256' => (string)$record['request']['sha256'],
        ]);
        kcmc_service_deck_action_redirect(
            'msg',
            'Private build request created. Download it for the trusted Sermon Assistant worker.'
        );
    }

    if ($action === 'import') {
        kcmc_service_deck_action_exact_post_fields(['csrf', 'action', 'job_id']);
        kcmc_service_deck_action_exact_uploads();
        $jobId = kcmc_service_deck_action_string($_POST['job_id'] ?? null, 'Job identifier');
        kcmc_service_deck_assert_job_id($jobId);
        // Fail before accepting artifact data when the private trust key is not configured.
        kcmc_service_deck_import_key();

        $deckBytes = kcmc_service_deck_action_upload(
            'deck',
            KCMC_SERVICE_MAX_DECK_BYTES,
            static fn(string $name): bool => preg_match('/\A[^\\\/]+\.pptx\z/iD', $name) === 1,
            'PowerPoint deck'
        );
        if (!str_starts_with($deckBytes, "PK\x03\x04")) {
            throw new InvalidArgumentException('PowerPoint deck does not have the required ZIP signature.');
        }
        $manifestBytes = kcmc_service_deck_action_upload(
            'manifest',
            KCMC_SERVICE_MAX_MANIFEST_BYTES,
            static fn(string $name): bool => $name === 'approval.json',
            'Approval manifest'
        );
        $envelopeBytes = kcmc_service_deck_action_upload(
            'envelope',
            65536,
            static fn(string $name): bool => $name === 'kcmc-import.json',
            'Signed import envelope'
        );
        $record = kcmc_service_deck_import_signed_artifacts(
            $jobId,
            $envelopeBytes,
            $manifestBytes,
            $deckBytes,
            $user
        );
        kcmc_audit('service_deck.signed_artifacts_imported', [
            'job_id' => $jobId,
            'deck_sha256' => (string)$record['artifacts']['deck']['sha256'],
            'manifest_sha256' => (string)$record['artifacts']['manifest']['sha256'],
            'deck_bytes' => (int)$record['artifacts']['deck']['bytes'],
        ]);
        kcmc_service_deck_action_redirect(
            'msg',
            'Signed build imported privately. A pastor administrator must review and decide it.'
        );
    }

    if ($action === 'approve' || $action === 'request_changes') {
        $decisionFields = [
            'csrf', 'action', 'job_id', 'reviewed_deck_sha256', 'current_password', 'notes',
        ];
        if ($action === 'approve') $decisionFields[] = 'visual_reviewed';
        kcmc_service_deck_action_exact_post_fields($decisionFields);
        if ($_FILES !== []) {
            throw new InvalidArgumentException('A pastor decision does not accept uploads.');
        }
        if (!kcmc_can_approve_service_decks($user)) {
            kcmc_audit('service_deck.decision_forbidden', [
                'job_id' => kcmc_service_deck_valid_job_id($jobIdForAudit) ? $jobIdForAudit : null,
            ]);
            kcmc_service_deck_action_forbidden('Only a pastor administrator may make this decision.');
        }
        $jobId = kcmc_service_deck_action_string($_POST['job_id'] ?? null, 'Job identifier');
        kcmc_service_deck_assert_job_id($jobId);
        $currentPassword = kcmc_service_deck_action_string(
            $_POST['current_password'] ?? null,
            'Current password'
        );
        $passwordHash = (string)($user['password_hash'] ?? '');
        $stepUpEmail = kcmc_normalize_email((string)(
            $user['email_normalized'] ?? $user['email'] ?? ''
        ));
        $stepUpBlocked = $stepUpEmail === '' || kcmc_login_is_blocked($stepUpEmail);
        if ($stepUpBlocked || $currentPassword === '' || $passwordHash === ''
            || !password_verify($currentPassword, $passwordHash)) {
            if ($stepUpEmail !== '' && !$stepUpBlocked) {
                kcmc_record_login_failure($stepUpEmail);
            }
            kcmc_audit('service_deck.decision_reauthentication_failed', ['job_id' => $jobId]);
            kcmc_service_deck_action_redirect(
                'error',
                'Identity verification was not accepted. Wait before retrying if necessary. No decision was recorded.'
            );
        }
        kcmc_clear_login_failures($stepUpEmail);
        $deckSha256 = kcmc_service_deck_action_string(
            $_POST['reviewed_deck_sha256'] ?? null,
            'Reviewed deck SHA-256'
        );
        if (!kcmc_service_deck_is_sha256($deckSha256)) {
            throw new InvalidArgumentException('Reviewed deck SHA-256 is invalid.');
        }
        $notes = kcmc_service_deck_action_string($_POST['notes'] ?? '', 'Decision notes');
        $decision = $action === 'approve' ? 'APPROVED' : 'CHANGES_REQUESTED';
        if ($decision === 'APPROVED'
            && (!isset($_POST['visual_reviewed']) || $_POST['visual_reviewed'] !== '1')) {
            throw new InvalidArgumentException('Visual review confirmation is required.');
        }
        if ($decision === 'CHANGES_REQUESTED' && trim($notes) === '') {
            throw new InvalidArgumentException('Change notes are required.');
        }

        // record_decision freshly reopens and verifies the immutable request,
        // HMAC envelope, manifest readiness, and exact deck hash inside the
        // locked authoritative transition.
        $record = kcmc_service_deck_record_decision(
            $jobId,
            $user,
            $decision,
            $deckSha256,
            $notes
        );
        kcmc_audit('service_deck.decision_recorded', [
            'job_id' => $jobId,
            'decision' => $decision,
            'deck_sha256' => $deckSha256,
            'authoritative' => true,
            'identity_verified' => true,
            'autopublish' => false,
        ]);
        kcmc_service_deck_action_redirect(
            'msg',
            $decision === 'APPROVED'
                ? 'Pastor approval recorded for the exact reviewed deck. Nothing was published.'
                : 'Changes requested. Nothing was published.'
        );
    }

    throw new InvalidArgumentException('Unknown service-deck action.');
} catch (InvalidArgumentException | UnexpectedValueException | DomainException $exception) {
    kcmc_audit('service_deck.action_rejected', [
        'action' => $actionForAudit,
        'job_id' => kcmc_service_deck_valid_job_id($jobIdForAudit) ? $jobIdForAudit : null,
        'reason_type' => get_class($exception),
    ]);
    $message = match ($action) {
        'create' => 'The request was not created. Check the service details and ordered items.',
        'import' => 'The import was rejected. Confirm the job and use the exact signed, approval-ready files.',
        'approve', 'request_changes' => 'No decision was recorded. Reopen the job and verify the exact reviewed deck.',
        default => 'That service-deck action is not available.',
    };
    kcmc_service_deck_action_redirect('error', $message);
} catch (Throwable $exception) {
    kcmc_audit('service_deck.action_failed', [
        'action' => $actionForAudit,
        'job_id' => kcmc_service_deck_valid_job_id($jobIdForAudit) ? $jobIdForAudit : null,
        'reason_type' => get_class($exception),
    ]);
    kcmc_service_deck_action_redirect(
        'error',
        'The private service-deck operation could not be completed. No publishing occurred.'
    );
}
