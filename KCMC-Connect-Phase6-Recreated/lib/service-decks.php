<?php
declare(strict_types=1);

/**
 * Private control plane for KCMC Sermon Assistant jobs.
 *
 * This file deliberately has no HTTP, session-start, or rendering behavior.
 * Routes must pass the authenticated user returned by KCMC Connect into these
 * functions. All durable state remains below KCMC_PRIVATE_DATA.
 */

if (!defined('KCMC_PRIVATE_DATA')) {
    throw new RuntimeException('Load bootstrap.php before service-decks.php.');
}

define('KCMC_SERVICE_DECKS_DIR', KCMC_PRIVATE_DATA . '/service-decks');
define('KCMC_SERVICE_DECKS_JOBS_DIR', KCMC_SERVICE_DECKS_DIR . '/jobs');
define('KCMC_SERVICE_DECKS_REQUESTS_DIR', KCMC_SERVICE_DECKS_DIR . '/requests');
define('KCMC_SERVICE_DECKS_ARTIFACTS_DIR', KCMC_SERVICE_DECKS_DIR . '/artifacts');
define('KCMC_SERVICE_DECKS_BACKUPS_DIR', KCMC_SERVICE_DECKS_DIR . '/backups');

const KCMC_SERVICE_DECK_SCHEMA = 1;
const KCMC_SERVICE_REQUEST_SCHEMA = 1;
const KCMC_SERMON_IMPORT_SCHEMA = 1;
const KCMC_SERMON_MANIFEST_SCHEMA = 3;
const KCMC_SERVICE_STYLE = 'Front Porch';
const KCMC_SERVICE_ITEM_TYPES = [
    'service_title',
    'song',
    'scripture',
    'sermon_title',
    'announcement',
    'blank',
];
const KCMC_SERVICE_COMPLETE_STATUSES = ['REUSED_EXISTING', 'CREATED_DRAFT'];
const KCMC_SERVICE_MAX_ITEMS = 100;
const KCMC_SERVICE_MAX_NAME_LENGTH = 160;
const KCMC_SERVICE_MAX_TITLE_LENGTH = 240;
const KCMC_SERVICE_MAX_ITEM_TEXT_LENGTH = 20000;
const KCMC_SERVICE_MAX_NOTES_LENGTH = 2000;
const KCMC_SERVICE_MAX_REQUEST_BYTES = 524288;
const KCMC_SERVICE_MAX_MANIFEST_BYTES = 1048576;
const KCMC_SERVICE_MAX_DECK_BYTES = 104857600;

function kcmc_can_manage_service_decks(?array $user = null): bool {
    if (function_exists('kcmc_has_role')) {
        return kcmc_has_role(['pastor_admin', 'recovery_admin'], $user);
    }
    return $user !== null && in_array((string)($user['role'] ?? ''), ['pastor_admin', 'recovery_admin'], true);
}

function kcmc_can_approve_service_decks(?array $user = null): bool {
    if (function_exists('kcmc_has_role')) {
        return kcmc_has_role(['pastor_admin'], $user);
    }
    return $user !== null && (string)($user['role'] ?? '') === 'pastor_admin';
}

function kcmc_service_deck_require_manager(array $user): void {
    if (!kcmc_can_manage_service_decks($user)) {
        throw new DomainException('A pastor or recovery administrator is required.');
    }
}

function kcmc_service_deck_require_approver(array $user): void {
    if (!kcmc_can_approve_service_decks($user)) {
        throw new DomainException('Only a pastor administrator may make the authoritative decision.');
    }
}

function kcmc_service_deck_actor(array $user): array {
    $id = trim((string)($user['id'] ?? ''));
    $role = (string)($user['role'] ?? '');
    if ($id === '' || strlen($id) > 128 || preg_match('/[\x00-\x1F\x7F]/', $id) === 1) {
        throw new InvalidArgumentException('The authenticated user has no valid identifier.');
    }
    if (!in_array($role, ['pastor_admin', 'recovery_admin'], true)) {
        throw new DomainException('The authenticated user cannot manage service decks.');
    }

    $displayName = kcmc_service_deck_clean_text((string)($user['display_name'] ?? ''), 160, false, 'Actor name');
    $email = strtolower(trim((string)($user['email'] ?? '')));
    if ($email !== '' && (strlen($email) > 254 || filter_var($email, FILTER_VALIDATE_EMAIL) === false)) {
        throw new InvalidArgumentException('The authenticated user has an invalid email address.');
    }

    return [
        'id' => $id,
        'display_name' => $displayName,
        'email' => $email,
        'role' => $role,
    ];
}

function kcmc_service_deck_valid_job_id(string $jobId): bool {
    return preg_match('/\Asdj_[a-f0-9]{32}\z/D', $jobId) === 1;
}

function kcmc_service_deck_assert_job_id(string $jobId): void {
    if (!kcmc_service_deck_valid_job_id($jobId)) {
        throw new InvalidArgumentException('Invalid service-deck job identifier.');
    }
}

function kcmc_service_deck_new_job_id(): string {
    return 'sdj_' . bin2hex(random_bytes(16));
}

function kcmc_service_deck_job_path(string $jobId): string {
    kcmc_service_deck_assert_job_id($jobId);
    return KCMC_SERVICE_DECKS_JOBS_DIR . '/' . $jobId . '.json';
}

function kcmc_service_deck_request_path(string $jobId): string {
    kcmc_service_deck_assert_job_id($jobId);
    return KCMC_SERVICE_DECKS_REQUESTS_DIR . '/' . $jobId . '.json';
}

function kcmc_service_deck_artifact_dir(string $jobId): string {
    kcmc_service_deck_assert_job_id($jobId);
    return KCMC_SERVICE_DECKS_ARTIFACTS_DIR . '/' . $jobId;
}

function kcmc_service_deck_artifact_path(string $jobId, string $artifact): string {
    $names = [
        'deck' => 'service-deck.pptx',
        'manifest' => 'manifest.json',
        'envelope' => 'import-envelope.json',
    ];
    if (!isset($names[$artifact])) {
        throw new InvalidArgumentException('Unknown service-deck artifact.');
    }
    return kcmc_service_deck_artifact_dir($jobId) . '/' . $names[$artifact];
}

function kcmc_service_deck_ensure_directory(string $path): void {
    if (is_link($path)) {
        throw new RuntimeException('Private service-deck storage may not use symbolic links.');
    }
    if (!is_dir($path) && !mkdir($path, 0750, true) && !is_dir($path)) {
        throw new RuntimeException('Private service-deck storage is unavailable.');
    }
    if (!chmod($path, 0750)) {
        throw new RuntimeException('Could not secure a private service-deck directory.');
    }
}

function kcmc_service_deck_ensure_storage(): void {
    kcmc_service_deck_ensure_directory(KCMC_SERVICE_DECKS_DIR);
    foreach ([
        KCMC_SERVICE_DECKS_JOBS_DIR,
        KCMC_SERVICE_DECKS_REQUESTS_DIR,
        KCMC_SERVICE_DECKS_ARTIFACTS_DIR,
        KCMC_SERVICE_DECKS_BACKUPS_DIR,
    ] as $directory) {
        kcmc_service_deck_ensure_directory($directory);
    }
}

function kcmc_service_deck_open_lock(string $path, int $operation) {
    $lockPath = $path . '.lock';
    if (is_link($lockPath)) {
        throw new RuntimeException('Unsafe service-deck lock path.');
    }
    $lock = @fopen($lockPath, 'c+');
    if ($lock === false) {
        throw new RuntimeException('Could not open private service-deck storage lock.');
    }
    if (!@chmod($lockPath, 0640) || !flock($lock, $operation)) {
        fclose($lock);
        throw new RuntimeException('Could not lock private service-deck storage.');
    }
    return $lock;
}

function kcmc_service_deck_close_lock($lock): void {
    flock($lock, LOCK_UN);
    fclose($lock);
}

function kcmc_service_deck_decode_json(string $bytes, string $label): array {
    if ($bytes === '' || trim($bytes) === '') {
        throw new UnexpectedValueException($label . ' is empty or corrupt.');
    }
    try {
        $decoded = json_decode($bytes, true, 64, JSON_THROW_ON_ERROR);
    } catch (JsonException $exception) {
        throw new UnexpectedValueException($label . ' is corrupt JSON.', 0, $exception);
    }
    if (!is_array($decoded) || array_is_list($decoded)) {
        throw new UnexpectedValueException($label . ' must be a JSON object.');
    }
    return $decoded;
}

function kcmc_service_deck_encode_json(array $value): string {
    try {
        return json_encode(
            $value,
            JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
        ) . "\n";
    } catch (JsonException $exception) {
        throw new RuntimeException('Could not encode service-deck JSON.', 0, $exception);
    }
}

function kcmc_service_deck_publish_bytes_unlocked(string $path, string $bytes, bool $replace): void {
    if (is_link($path)) {
        throw new RuntimeException('Unsafe service-deck file path.');
    }
    if (!$replace && file_exists($path)) {
        throw new RuntimeException('The private service-deck file already exists.');
    }
    $directory = dirname($path);
    kcmc_service_deck_ensure_directory($directory);
    $temporary = $directory . '/.tmp-' . bin2hex(random_bytes(12));
    $handle = @fopen($temporary, 'xb');
    if ($handle === false) {
        throw new RuntimeException('Could not create a private service-deck file.');
    }
    try {
        $length = strlen($bytes);
        $written = 0;
        while ($written < $length) {
            $count = fwrite($handle, substr($bytes, $written, 1024 * 1024));
            if ($count === false || $count === 0) {
                throw new RuntimeException('Could not write a private service-deck file.');
            }
            $written += $count;
        }
        if (!fflush($handle) || !chmod($temporary, 0640)) {
            throw new RuntimeException('Could not secure a private service-deck file.');
        }
    } catch (Throwable $exception) {
        fclose($handle);
        @unlink($temporary);
        throw $exception;
    }
    fclose($handle);
    if (!$replace && file_exists($path)) {
        @unlink($temporary);
        throw new RuntimeException('The private service-deck file already exists.');
    }
    if (!@rename($temporary, $path)) {
        @unlink($temporary);
        throw new RuntimeException('Could not publish a private service-deck file.');
    }
    if (!@chmod($path, 0640)) {
        throw new RuntimeException('Could not secure a published service-deck file.');
    }
}

function kcmc_service_deck_read_file_unlocked(string $path, string $label): string {
    if (!is_file($path) || is_link($path)) {
        throw new RuntimeException($label . ' is unavailable.');
    }
    $bytes = @file_get_contents($path);
    if ($bytes === false) {
        throw new RuntimeException('Could not read ' . $label . '.');
    }
    return $bytes;
}

function kcmc_service_deck_backup_record_unlocked(string $jobId, string $bytes): void {
    $directory = KCMC_SERVICE_DECKS_BACKUPS_DIR . '/' . $jobId;
    kcmc_service_deck_ensure_directory($directory);
    $name = gmdate('Ymd\THis\Z') . '-' . bin2hex(random_bytes(6)) . '-record.json';
    kcmc_service_deck_publish_bytes_unlocked($directory . '/' . $name, $bytes, false);
}

function kcmc_service_deck_validate_record(array $record, ?string $expectedJobId = null): void {
    if (($record['schema_version'] ?? null) !== KCMC_SERVICE_DECK_SCHEMA) {
        throw new UnexpectedValueException('Service-deck record has an unsupported schema.');
    }
    $jobId = (string)($record['job_id'] ?? '');
    if (!kcmc_service_deck_valid_job_id($jobId) || ($expectedJobId !== null && $jobId !== $expectedJobId)) {
        throw new UnexpectedValueException('Service-deck record has an invalid job identifier.');
    }
    if (($record['service_style'] ?? null) !== KCMC_SERVICE_STYLE) {
        throw new UnexpectedValueException('Service-deck record has an unsupported service style.');
    }
    $serviceDate = $record['service_date'] ?? null;
    if (!is_string($serviceDate)
        || preg_match('/\A[0-9]{4}-[0-9]{2}-[0-9]{2}\z/D', $serviceDate) !== 1) {
        throw new UnexpectedValueException('Service-deck record has an invalid service date.');
    }
    [$recordYear, $recordMonth, $recordDay] = array_map('intval', explode('-', $serviceDate));
    if ($recordYear < 2000 || $recordYear > 2100 || !checkdate($recordMonth, $recordDay, $recordYear)) {
        throw new UnexpectedValueException('Service-deck record has an invalid service date.');
    }
    if (($record['autopublish'] ?? null) !== false) {
        throw new UnexpectedValueException('Service-deck records must keep autopublish disabled.');
    }
    $request = $record['request'] ?? null;
    if (!is_array($request) || !kcmc_service_deck_is_sha256($request['sha256'] ?? null)) {
        throw new UnexpectedValueException('Service-deck record has invalid request metadata.');
    }
    if (!isset($record['history']) || !is_array($record['history']) || !array_is_list($record['history'])) {
        throw new UnexpectedValueException('Service-deck record has invalid history.');
    }
    if (!isset($record['approval']) || !is_array($record['approval'])) {
        throw new UnexpectedValueException('Service-deck record has invalid approval state.');
    }
    if (($record['approval']['autopublish'] ?? null) !== false) {
        throw new UnexpectedValueException('Service-deck approval state must keep autopublish disabled.');
    }
    $decision = $record['approval']['decision'] ?? null;
    $status = $record['status'] ?? null;
    if ($status === 'REQUEST_READY') {
        if (($record['artifacts'] ?? null) !== null || $decision !== null) {
            throw new UnexpectedValueException('Request-ready service-deck state is inconsistent.');
        }
    } elseif ($status === 'AWAITING_PASTOR_APPROVAL') {
        if (!is_array($record['artifacts'] ?? null) || $decision !== null) {
            throw new UnexpectedValueException('Awaiting-approval service-deck state is inconsistent.');
        }
    } elseif (in_array($status, ['APPROVED', 'CHANGES_REQUESTED'], true)) {
        if (!is_array($record['artifacts'] ?? null) || $decision !== $status) {
            throw new UnexpectedValueException('Decided service-deck state is inconsistent.');
        }
    } else {
        throw new UnexpectedValueException('Service-deck record has an unsupported status.');
    }
    if (is_array($record['artifacts'] ?? null)
        && (!kcmc_service_deck_is_sha256($record['artifacts']['deck']['sha256'] ?? null)
            || !kcmc_service_deck_is_sha256($record['artifacts']['manifest']['sha256'] ?? null))) {
        throw new UnexpectedValueException('Service-deck record has invalid artifact hashes.');
    }
    if ($decision === null && (($record['approval']['actor'] ?? null) !== null
        || ($record['approval']['decided_at'] ?? null) !== null
        || ($record['approval']['deck_sha256'] ?? null) !== null
        || ($record['approval']['request_sha256'] ?? null) !== null
        || ($record['approval']['manifest_sha256'] ?? null) !== null
        || ($record['approval']['notes'] ?? null) !== null
        || ($record['approval']['authoritative'] ?? null) !== false
        || ($record['approval']['identity_verified'] ?? null) !== false)) {
        throw new UnexpectedValueException('Undecided service-deck approval state is inconsistent.');
    }
    if ($decision !== null && (!in_array($decision, ['APPROVED', 'CHANGES_REQUESTED'], true)
        || ($record['approval']['authoritative'] ?? null) !== true
        || ($record['approval']['identity_verified'] ?? null) !== true)) {
        throw new UnexpectedValueException('Service-deck record has an invalid authoritative decision.');
    }
    if ($decision !== null && (($record['approval']['request_sha256'] ?? null) !== ($record['request']['sha256'] ?? null)
        || ($record['approval']['deck_sha256'] ?? null) !== ($record['artifacts']['deck']['sha256'] ?? null)
        || ($record['approval']['manifest_sha256'] ?? null) !== ($record['artifacts']['manifest']['sha256'] ?? null))) {
        throw new UnexpectedValueException('Service-deck decision is not bound to all reviewed evidence.');
    }
}

function kcmc_service_deck_read_record_unchecked(string $jobId): array {
    kcmc_service_deck_assert_job_id($jobId);
    kcmc_service_deck_ensure_storage();
    $path = kcmc_service_deck_job_path($jobId);
    if (!is_file($path) || is_link($path)) {
        throw new OutOfBoundsException('Service-deck job was not found.');
    }
    $lock = kcmc_service_deck_open_lock($path, LOCK_SH);
    try {
        $record = kcmc_service_deck_decode_json(
            kcmc_service_deck_read_file_unlocked($path, 'Service-deck record'),
            'Service-deck record'
        );
        kcmc_service_deck_validate_record($record, $jobId);
        return $record;
    } finally {
        kcmc_service_deck_close_lock($lock);
    }
}

function kcmc_service_deck_update_record(string $jobId, callable $transition): array {
    kcmc_service_deck_assert_job_id($jobId);
    kcmc_service_deck_ensure_storage();
    $path = kcmc_service_deck_job_path($jobId);
    if (!is_file($path) || is_link($path)) {
        throw new OutOfBoundsException('Service-deck job was not found.');
    }
    $lock = kcmc_service_deck_open_lock($path, LOCK_EX);
    try {
        $oldBytes = kcmc_service_deck_read_file_unlocked($path, 'Service-deck record');
        $record = kcmc_service_deck_decode_json($oldBytes, 'Service-deck record');
        kcmc_service_deck_validate_record($record, $jobId);
        $updated = $transition($record);
        if (!is_array($updated)) {
            throw new LogicException('Service-deck transition did not return a record.');
        }
        $updated['job_id'] = $jobId;
        $updated['autopublish'] = false;
        $updated['updated_at'] = gmdate('c');
        kcmc_service_deck_validate_record($updated, $jobId);
        kcmc_service_deck_backup_record_unlocked($jobId, $oldBytes);
        kcmc_service_deck_publish_bytes_unlocked($path, kcmc_service_deck_encode_json($updated), true);
        return $updated;
    } finally {
        kcmc_service_deck_close_lock($lock);
    }
}

function kcmc_service_deck_clean_text(
    string $value,
    int $maximumLength,
    bool $required,
    string $label
): string {
    if (preg_match('//u', $value) !== 1 || str_contains($value, "\0")) {
        throw new InvalidArgumentException($label . ' must be valid UTF-8 text.');
    }
    $value = trim(str_replace(["\r\n", "\r"], "\n", $value));
    if ($required && $value === '') {
        throw new InvalidArgumentException($label . ' is required.');
    }
    $length = function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);
    if ($length > $maximumLength) {
        throw new InvalidArgumentException($label . ' is too long.');
    }
    return $value;
}

function kcmc_service_deck_assert_exact_keys(array $value, array $allowed, string $label): void {
    foreach (array_keys($value) as $key) {
        if (!is_string($key) || !in_array($key, $allowed, true)) {
            throw new InvalidArgumentException($label . ' contains an unsupported field.');
        }
    }
}

function kcmc_service_deck_normalize_items(mixed $rawItems): array {
    if (!is_array($rawItems) || !array_is_list($rawItems) || count($rawItems) < 1) {
        throw new InvalidArgumentException('At least one ordered service item is required.');
    }
    if (count($rawItems) > KCMC_SERVICE_MAX_ITEMS) {
        throw new InvalidArgumentException('The service contains too many items.');
    }

    $items = [];
    foreach ($rawItems as $position => $rawItem) {
        if (!is_array($rawItem) || array_is_list($rawItem)) {
            throw new InvalidArgumentException('Each service item must be an object.');
        }
        $type = $rawItem['type'] ?? null;
        if (!is_string($type) || !in_array($type, KCMC_SERVICE_ITEM_TYPES, true)) {
            throw new InvalidArgumentException('Service item ' . ($position + 1) . ' has an unsupported type.');
        }
        $allowed = ['type', 'title'];
        if ($type === 'song') $allowed[] = 'lyrics';
        if (in_array($type, ['scripture', 'announcement', 'service_title', 'sermon_title'], true)) {
            $allowed[] = 'text';
        }
        kcmc_service_deck_assert_exact_keys($rawItem, $allowed, 'Service item ' . ($position + 1));

        $titleRequired = $type !== 'blank';
        $defaultTitle = $type === 'blank' ? 'Intentional blank' : '';
        $titleValue = array_key_exists('title', $rawItem) ? $rawItem['title'] : $defaultTitle;
        if (!is_string($titleValue)) {
            throw new InvalidArgumentException('Service item title must be text.');
        }
        $item = [
            'type' => $type,
            'title' => kcmc_service_deck_clean_text(
                $titleValue,
                KCMC_SERVICE_MAX_TITLE_LENGTH,
                $titleRequired,
                'Service item title'
            ),
        ];
        if ($item['title'] === '' && $type === 'blank') $item['title'] = $defaultTitle;

        if ($type === 'song' && array_key_exists('lyrics', $rawItem)) {
            if (!is_string($rawItem['lyrics'])) {
                throw new InvalidArgumentException('Song lyrics must be text.');
            }
            $lyrics = kcmc_service_deck_clean_text(
                $rawItem['lyrics'],
                KCMC_SERVICE_MAX_ITEM_TEXT_LENGTH,
                false,
                'Song lyrics'
            );
            if ($lyrics !== '') $item['lyrics'] = $lyrics;
        }

        if (in_array($type, ['scripture', 'announcement', 'service_title', 'sermon_title'], true)
            && array_key_exists('text', $rawItem)) {
            if (!is_string($rawItem['text'])) {
                throw new InvalidArgumentException('Service item text must be text.');
            }
            $text = kcmc_service_deck_clean_text(
                $rawItem['text'],
                KCMC_SERVICE_MAX_ITEM_TEXT_LENGTH,
                in_array($type, ['scripture', 'announcement'], true),
                'Service item text'
            );
            if ($text !== '') $item['text'] = $text;
        } elseif (in_array($type, ['scripture', 'announcement'], true)) {
            throw new InvalidArgumentException('Authorized text is required for ' . $type . '.');
        }

        $items[] = $item;
    }
    return $items;
}

function kcmc_service_deck_normalize_request_input(array $input): array {
    kcmc_service_deck_assert_exact_keys($input, ['service_name', 'service_date', 'service_style', 'items'], 'Service request');
    if (!isset($input['service_name']) || !is_string($input['service_name'])) {
        throw new InvalidArgumentException('Service name is required.');
    }
    $style = $input['service_style'] ?? KCMC_SERVICE_STYLE;
    if (!is_string($style) || $style !== KCMC_SERVICE_STYLE) {
        throw new InvalidArgumentException('Only the verified Front Porch service style is supported.');
    }
    $serviceDate = $input['service_date'] ?? null;
    if (!is_string($serviceDate)
        || preg_match('/\A[0-9]{4}-[0-9]{2}-[0-9]{2}\z/D', $serviceDate) !== 1) {
        throw new InvalidArgumentException('Service date must use YYYY-MM-DD.');
    }
    [$year, $month, $day] = array_map('intval', explode('-', $serviceDate));
    if ($year < 2000 || $year > 2100 || !checkdate($month, $day, $year)) {
        throw new InvalidArgumentException('Service date is invalid.');
    }
    return [
        'service_name' => kcmc_service_deck_clean_text(
            $input['service_name'],
            KCMC_SERVICE_MAX_NAME_LENGTH,
            true,
            'Service name'
        ),
        'service_date' => $serviceDate,
        'service_style' => KCMC_SERVICE_STYLE,
        'items' => kcmc_service_deck_normalize_items($input['items'] ?? null),
    ];
}

function kcmc_service_deck_request_document(string $jobId, array $normalized): array {
    kcmc_service_deck_assert_job_id($jobId);
    return [
        'schema_version' => KCMC_SERVICE_REQUEST_SCHEMA,
        'kcmc_job_id' => $jobId,
        'service_name' => $normalized['service_name'],
        'service_date' => $normalized['service_date'],
        'service_style' => KCMC_SERVICE_STYLE,
        'items' => $normalized['items'],
        'autopublish' => false,
    ];
}

function kcmc_service_deck_create_job(array $input, array $user): array {
    kcmc_service_deck_require_manager($user);
    $actor = kcmc_service_deck_actor($user);
    $normalized = kcmc_service_deck_normalize_request_input($input);
    kcmc_service_deck_ensure_storage();

    $createLockPath = KCMC_SERVICE_DECKS_DIR . '/create';
    $lock = kcmc_service_deck_open_lock($createLockPath, LOCK_EX);
    try {
        do {
            $jobId = kcmc_service_deck_new_job_id();
            $jobPath = kcmc_service_deck_job_path($jobId);
            $requestPath = kcmc_service_deck_request_path($jobId);
        } while (file_exists($jobPath) || file_exists($requestPath));

        $requestBytes = kcmc_service_deck_encode_json(
            kcmc_service_deck_request_document($jobId, $normalized)
        );
        if (strlen($requestBytes) > KCMC_SERVICE_MAX_REQUEST_BYTES) {
            throw new InvalidArgumentException('The service request is too large.');
        }
        $requestSha256 = hash('sha256', $requestBytes);
        $now = gmdate('c');
        $record = [
            'schema_version' => KCMC_SERVICE_DECK_SCHEMA,
            'job_id' => $jobId,
            'status' => 'REQUEST_READY',
            'service_name' => $normalized['service_name'],
            'service_date' => $normalized['service_date'],
            'service_style' => KCMC_SERVICE_STYLE,
            'item_count' => count($normalized['items']),
            'request' => [
                'path' => 'requests/' . $jobId . '.json',
                'sha256' => $requestSha256,
                'bytes' => strlen($requestBytes),
            ],
            'artifacts' => null,
            'approval' => [
                'decision' => null,
                'actor' => null,
                'decided_at' => null,
                'deck_sha256' => null,
                'request_sha256' => null,
                'manifest_sha256' => null,
                'notes' => null,
                'authoritative' => false,
                'identity_verified' => false,
                'autopublish' => false,
            ],
            'autopublish' => false,
            'created_at' => $now,
            'created_by' => $actor,
            'updated_at' => $now,
            'history' => [[
                'at' => $now,
                'event' => 'REQUEST_CREATED',
                'actor' => $actor,
                'request_sha256' => $requestSha256,
            ]],
        ];
        kcmc_service_deck_validate_record($record, $jobId);

        kcmc_service_deck_publish_bytes_unlocked($requestPath, $requestBytes, false);
        try {
            kcmc_service_deck_publish_bytes_unlocked(
                $jobPath,
                kcmc_service_deck_encode_json($record),
                false
            );
        } catch (Throwable $exception) {
            @unlink($requestPath);
            throw $exception;
        }
        return $record;
    } finally {
        kcmc_service_deck_close_lock($lock);
    }
}

function kcmc_service_deck_get_job(string $jobId, array $user): array {
    kcmc_service_deck_require_manager($user);
    return kcmc_service_deck_read_record_unchecked($jobId);
}

function kcmc_service_deck_list_jobs(array $user): array {
    kcmc_service_deck_require_manager($user);
    kcmc_service_deck_ensure_storage();
    $paths = glob(KCMC_SERVICE_DECKS_JOBS_DIR . '/sdj_*.json');
    if ($paths === false) {
        throw new RuntimeException('Could not list service-deck jobs.');
    }
    $records = [];
    foreach ($paths as $path) {
        $jobId = basename($path, '.json');
        if (!kcmc_service_deck_valid_job_id($jobId)) {
            throw new UnexpectedValueException('Private service-deck storage contains an invalid record name.');
        }
        $records[] = kcmc_service_deck_read_record_unchecked($jobId);
    }
    usort($records, static fn(array $left, array $right): int => strcmp(
        (string)($right['created_at'] ?? ''),
        (string)($left['created_at'] ?? '')
    ));
    return $records;
}

function kcmc_service_deck_request_bytes(string $jobId, array $user): string {
    kcmc_service_deck_require_manager($user);
    $record = kcmc_service_deck_read_record_unchecked($jobId);
    $path = kcmc_service_deck_request_path($jobId);
    $lock = kcmc_service_deck_open_lock($path, LOCK_SH);
    try {
        $bytes = kcmc_service_deck_read_file_unlocked($path, 'Service-deck request');
    } finally {
        kcmc_service_deck_close_lock($lock);
    }
    if (!hash_equals((string)$record['request']['sha256'], hash('sha256', $bytes))) {
        throw new UnexpectedValueException('Service-deck request hash does not match its record.');
    }
    return $bytes;
}

function kcmc_service_deck_is_sha256(mixed $value): bool {
    return is_string($value) && preg_match('/\A[a-f0-9]{64}\z/D', $value) === 1;
}

function kcmc_service_deck_import_key(?string $provided = null): string {
    $key = $provided ?? (getenv('KCMC_SERMON_IMPORT_KEY') !== false
        ? (string)getenv('KCMC_SERMON_IMPORT_KEY')
        : '');
    if (strlen($key) < 32) {
        throw new RuntimeException('KCMC_SERMON_IMPORT_KEY must contain at least 32 characters.');
    }
    return $key;
}

function kcmc_service_deck_import_key_configured(): bool {
    $key = getenv('KCMC_SERMON_IMPORT_KEY');
    return is_string($key) && strlen($key) >= 32;
}

function kcmc_service_deck_import_message(
    string $jobId,
    string $requestSha256,
    string $deckSha256,
    string $manifestSha256
): string {
    kcmc_service_deck_assert_job_id($jobId);
    foreach ([$requestSha256, $deckSha256, $manifestSha256] as $hash) {
        if (!kcmc_service_deck_is_sha256($hash)) {
            throw new InvalidArgumentException('Import message contains an invalid SHA-256 value.');
        }
    }
    return "KCMC-SERMON-IMPORT-V1\n{$jobId}\n{$requestSha256}\n{$deckSha256}\n{$manifestSha256}\n";
}

function kcmc_service_deck_decode_import_envelope(string $bytes): array {
    if (strlen($bytes) > 65536) {
        throw new InvalidArgumentException('Import envelope is too large.');
    }
    $envelope = kcmc_service_deck_decode_json($bytes, 'Sermon import envelope');
    kcmc_service_deck_assert_exact_keys(
        $envelope,
        ['schema_version', 'job_id', 'request_sha256', 'deck_sha256', 'manifest_sha256', 'signature_hmac_sha256'],
        'Sermon import envelope'
    );
    return $envelope;
}

function kcmc_service_deck_validate_manifest_items(array $manifest, array $request): void {
    $items = $manifest['items'] ?? null;
    $requestedItems = $request['items'] ?? null;
    if (!is_array($items) || !array_is_list($items) || $items === []
        || !is_array($requestedItems) || count($items) !== count($requestedItems)) {
        throw new UnexpectedValueException('Manifest items do not match the service request.');
    }
    foreach ($items as $index => $item) {
        if (!is_array($item) || array_is_list($item)) {
            throw new UnexpectedValueException('Every manifest item must be complete.');
        }
        if (!in_array((string)($item['status'] ?? ''), KCMC_SERVICE_COMPLETE_STATUSES, true)) {
            throw new UnexpectedValueException('Every manifest item must be complete.');
        }
        $qa = $item['qa'] ?? null;
        if (!is_array($qa) || ($qa['ok'] ?? null) !== true || ($qa['errors'] ?? null) !== []) {
            throw new UnexpectedValueException('Every manifest item must pass QA.');
        }
        if (!is_int($item['slides_added'] ?? null) || $item['slides_added'] < 1) {
            throw new UnexpectedValueException('Every manifest item must contribute at least one slide.');
        }
        $requested = $requestedItems[$index];
        if (!is_array($requested)
            || (string)($item['item_type'] ?? '') !== (string)($requested['type'] ?? '')
            || (string)($item['title'] ?? '') !== (string)($requested['title'] ?? '')) {
            throw new UnexpectedValueException('Manifest item order or identity does not match the request.');
        }
    }
}

function kcmc_service_deck_validate_signed_import(
    array $record,
    array $envelope,
    string $requestBytes,
    string $manifestBytes,
    string $deckBytes,
    ?string $key = null,
    bool $requireUnimported = true
): array {
    kcmc_service_deck_validate_record($record);
    kcmc_service_deck_assert_exact_keys(
        $envelope,
        ['schema_version', 'job_id', 'request_sha256', 'deck_sha256', 'manifest_sha256', 'signature_hmac_sha256'],
        'Sermon import envelope'
    );
    if (($envelope['schema_version'] ?? null) !== KCMC_SERMON_IMPORT_SCHEMA) {
        throw new UnexpectedValueException('Import envelope has an unsupported schema.');
    }
    $jobId = (string)($record['job_id'] ?? '');
    if (($envelope['job_id'] ?? null) !== $jobId) {
        throw new UnexpectedValueException('Import envelope is bound to a different job.');
    }
    foreach (['request_sha256', 'deck_sha256', 'manifest_sha256'] as $field) {
        if (!kcmc_service_deck_is_sha256($envelope[$field] ?? null)) {
            throw new UnexpectedValueException('Import envelope contains an invalid hash.');
        }
    }
    if (!is_string($envelope['signature_hmac_sha256'] ?? null)
        || preg_match('/\A[a-f0-9]{64}\z/D', (string)$envelope['signature_hmac_sha256']) !== 1) {
        throw new UnexpectedValueException('Import envelope contains an invalid signature.');
    }
    if (strlen($requestBytes) > KCMC_SERVICE_MAX_REQUEST_BYTES
        || strlen($manifestBytes) > KCMC_SERVICE_MAX_MANIFEST_BYTES
        || strlen($deckBytes) > KCMC_SERVICE_MAX_DECK_BYTES
        || $deckBytes === '') {
        throw new UnexpectedValueException('Signed import artifacts exceed the allowed size or are empty.');
    }
    if (strlen($deckBytes) < 4 || substr($deckBytes, 0, 4) !== "PK\x03\x04") {
        throw new UnexpectedValueException('Imported deck is not a PowerPoint ZIP package.');
    }

    $requestSha256 = hash('sha256', $requestBytes);
    $deckSha256 = hash('sha256', $deckBytes);
    $manifestSha256 = hash('sha256', $manifestBytes);
    if (!hash_equals((string)$record['request']['sha256'], $requestSha256)
        || !hash_equals((string)$envelope['request_sha256'], $requestSha256)
        || !hash_equals((string)$envelope['deck_sha256'], $deckSha256)
        || !hash_equals((string)$envelope['manifest_sha256'], $manifestSha256)) {
        throw new UnexpectedValueException('Signed import artifact hash mismatch.');
    }

    $message = kcmc_service_deck_import_message($jobId, $requestSha256, $deckSha256, $manifestSha256);
    $expectedSignature = hash_hmac('sha256', $message, kcmc_service_deck_import_key($key));
    if (!hash_equals($expectedSignature, (string)$envelope['signature_hmac_sha256'])) {
        throw new UnexpectedValueException('Signed import signature verification failed.');
    }

    $request = kcmc_service_deck_decode_json($requestBytes, 'Service-deck request');
    if (($request['schema_version'] ?? null) !== KCMC_SERVICE_REQUEST_SCHEMA
        || ($request['kcmc_job_id'] ?? null) !== $jobId
        || ($request['service_style'] ?? null) !== KCMC_SERVICE_STYLE
        || ($request['autopublish'] ?? null) !== false) {
        throw new UnexpectedValueException('Stored service-deck request is invalid.');
    }
    try {
        $normalizedRequest = kcmc_service_deck_normalize_request_input([
            'service_name' => $request['service_name'] ?? null,
            'service_date' => $request['service_date'] ?? null,
            'service_style' => $request['service_style'] ?? null,
            'items' => $request['items'] ?? null,
        ]);
    } catch (InvalidArgumentException $exception) {
        throw new UnexpectedValueException('Stored service-deck request is invalid.', 0, $exception);
    }
    $expectedRequestBytes = kcmc_service_deck_encode_json(
        kcmc_service_deck_request_document($jobId, $normalizedRequest)
    );
    if (!hash_equals($expectedRequestBytes, $requestBytes)) {
        throw new UnexpectedValueException('Stored service-deck request is not in canonical form.');
    }
    $manifest = kcmc_service_deck_decode_json($manifestBytes, 'Sermon manifest');
    if (($manifest['schema_version'] ?? null) !== KCMC_SERMON_MANIFEST_SCHEMA) {
        throw new UnexpectedValueException('Sermon manifest has an unsupported schema.');
    }
    if (($manifest['ready_for_approval'] ?? null) !== true) {
        throw new UnexpectedValueException('Sermon manifest is not ready for approval.');
    }
    if (($manifest['status'] ?? null) !== 'AWAITING_PASTOR_APPROVAL') {
        throw new UnexpectedValueException('Sermon manifest has an invalid approval status.');
    }
    if (($manifest['autopublish'] ?? null) !== false) {
        throw new UnexpectedValueException('Sermon manifest must keep autopublish disabled.');
    }
    if (($manifest['service'] ?? null) !== ($request['service_name'] ?? null)) {
        throw new UnexpectedValueException('Sermon manifest service does not match the request.');
    }
    if (isset($manifest['service_date']) && $manifest['service_date'] !== ($request['service_date'] ?? null)) {
        throw new UnexpectedValueException('Sermon manifest date does not match the request.');
    }
    if (isset($manifest['service_style']) && $manifest['service_style'] !== KCMC_SERVICE_STYLE) {
        throw new UnexpectedValueException('Sermon manifest has an unsupported service style.');
    }
    if (($manifest['final_deck_sha256'] ?? null) !== $deckSha256) {
        throw new UnexpectedValueException('Sermon manifest is bound to a different deck.');
    }
    $finalDeck = $manifest['final_deck'] ?? null;
    if (!is_string($finalDeck)
        || $finalDeck === ''
        || strlen($finalDeck) > 200
        || basename($finalDeck) !== $finalDeck
        || str_contains($finalDeck, '/')
        || str_contains($finalDeck, '\\')
        || preg_match('/\A[A-Za-z0-9][A-Za-z0-9._ -]*\.pptx\z/D', $finalDeck) !== 1) {
        throw new UnexpectedValueException('Sermon manifest has an unsafe final deck filename.');
    }
    $finalQa = $manifest['final_qa'] ?? null;
    if (!is_array($finalQa) || ($finalQa['ok'] ?? null) !== true
        || ($finalQa['errors'] ?? null) !== []
        || !is_int($finalQa['slides'] ?? null)
        || $finalQa['slides'] < 1) {
        throw new UnexpectedValueException('Final deck QA did not pass.');
    }
    kcmc_service_deck_validate_manifest_items($manifest, $request);

    $approval = $manifest['approval'] ?? null;
    if (!is_array($approval) || array_is_list($approval)) {
        throw new UnexpectedValueException('Sermon manifest has an invalid approval object.');
    }
    try {
        kcmc_service_deck_assert_exact_keys(
            $approval,
            ['decision', 'approved_by', 'decided_at', 'notes'],
            'Sermon manifest approval'
        );
    } catch (InvalidArgumentException $exception) {
        throw new UnexpectedValueException('Sermon manifest has an invalid approval object.', 0, $exception);
    }
    $approvedFlagPresent = array_key_exists('approved', $manifest);
    $noApprovalObject = is_array($approval)
        && array_key_exists('decision', $approval)
        && array_key_exists('approved_by', $approval)
        && array_key_exists('decided_at', $approval)
        && array_key_exists('notes', $approval)
        && $approval['decision'] === null
        && $approval['approved_by'] === null
        && $approval['decided_at'] === null
        && $approval['notes'] === null;
    if (!$noApprovalObject) {
        throw new UnexpectedValueException('Sermon manifest already contains an approval decision.');
    }
    if (is_array($approval) && (($approval['decision'] ?? null) !== null
        || ($approval['approved_by'] ?? null) !== null
        || ($approval['decided_at'] ?? null) !== null
        || ($approval['notes'] ?? null) !== null)) {
        throw new UnexpectedValueException('Sermon manifest already contains an approval decision.');
    }
    if ($approvedFlagPresent && $manifest['approved'] !== false) {
        throw new UnexpectedValueException('Sermon manifest already contains an approval decision.');
    }
    if ($requireUnimported
        && (($record['approval']['decision'] ?? null) !== null || $record['artifacts'] !== null)) {
        throw new DomainException('This service-deck job already has imported artifacts or a decision.');
    }

    return [
        'request_sha256' => $requestSha256,
        'deck_sha256' => $deckSha256,
        'manifest_sha256' => $manifestSha256,
        'final_deck' => $finalDeck,
        'manifest' => $manifest,
    ];
}

function kcmc_service_deck_import_signed_artifacts(
    string $jobId,
    string $envelopeBytes,
    string $manifestBytes,
    string $deckBytes,
    array $user,
    ?string $key = null
): array {
    kcmc_service_deck_require_manager($user);
    $actor = kcmc_service_deck_actor($user);
    $envelope = kcmc_service_deck_decode_import_envelope($envelopeBytes);
    $artifactsPublished = false;

    try {
        return kcmc_service_deck_update_record($jobId, function (array $record) use (
            $jobId,
            $envelope,
            $envelopeBytes,
            $manifestBytes,
            $deckBytes,
            $actor,
            $key,
            &$artifactsPublished
        ): array {
        if (($record['status'] ?? null) !== 'REQUEST_READY') {
            throw new DomainException('Service-deck job is not waiting for an import.');
        }
        $requestBytes = kcmc_service_deck_read_file_unlocked(
            kcmc_service_deck_request_path($jobId),
            'Service-deck request'
        );
        $validated = kcmc_service_deck_validate_signed_import(
            $record,
            $envelope,
            $requestBytes,
            $manifestBytes,
            $deckBytes,
            $key
        );

        $artifactDirectory = kcmc_service_deck_artifact_dir($jobId);
        kcmc_service_deck_ensure_directory($artifactDirectory);
        kcmc_service_deck_publish_bytes_unlocked(
            kcmc_service_deck_artifact_path($jobId, 'deck'),
            $deckBytes,
            false
        );
        try {
            kcmc_service_deck_publish_bytes_unlocked(
                kcmc_service_deck_artifact_path($jobId, 'manifest'),
                $manifestBytes,
                false
            );
            kcmc_service_deck_publish_bytes_unlocked(
                kcmc_service_deck_artifact_path($jobId, 'envelope'),
                $envelopeBytes,
                false
            );
            $artifactsPublished = true;
        } catch (Throwable $exception) {
            @unlink(kcmc_service_deck_artifact_path($jobId, 'deck'));
            @unlink(kcmc_service_deck_artifact_path($jobId, 'manifest'));
            @unlink(kcmc_service_deck_artifact_path($jobId, 'envelope'));
            throw $exception;
        }

        $now = gmdate('c');
        $record['status'] = 'AWAITING_PASTOR_APPROVAL';
        $record['artifacts'] = [
            'deck' => [
                'path' => 'artifacts/' . $jobId . '/service-deck.pptx',
                'original_name' => $validated['final_deck'],
                'sha256' => $validated['deck_sha256'],
                'bytes' => strlen($deckBytes),
            ],
            'manifest' => [
                'path' => 'artifacts/' . $jobId . '/manifest.json',
                'sha256' => $validated['manifest_sha256'],
                'bytes' => strlen($manifestBytes),
            ],
            'envelope' => [
                'path' => 'artifacts/' . $jobId . '/import-envelope.json',
                'bytes' => strlen($envelopeBytes),
            ],
            'imported_at' => $now,
            'imported_by' => $actor,
        ];
        $record['history'][] = [
            'at' => $now,
            'event' => 'SIGNED_ARTIFACTS_IMPORTED',
            'actor' => $actor,
            'deck_sha256' => $validated['deck_sha256'],
            'manifest_sha256' => $validated['manifest_sha256'],
        ];
        return $record;
        });
    } catch (Throwable $exception) {
        if ($artifactsPublished) {
            // If the record commit failed and remains in its original state,
            // remove only the artifacts created by this attempt so a verified
            // retry is possible. If the record is unreadable or did commit,
            // preserve the evidence and fail closed for manual recovery.
            try {
                $current = kcmc_service_deck_read_record_unchecked($jobId);
                if (($current['status'] ?? null) === 'REQUEST_READY'
                    && ($current['artifacts'] ?? null) === null) {
                    @unlink(kcmc_service_deck_artifact_path($jobId, 'deck'));
                    @unlink(kcmc_service_deck_artifact_path($jobId, 'manifest'));
                    @unlink(kcmc_service_deck_artifact_path($jobId, 'envelope'));
                    @rmdir(kcmc_service_deck_artifact_dir($jobId));
                }
            } catch (Throwable) {
                // Preserve uncertain private evidence rather than deleting it.
            }
        }
        throw $exception;
    }
}

function kcmc_service_deck_read_immutable_file(string $path, string $label): string {
    $lock = kcmc_service_deck_open_lock($path, LOCK_SH);
    try {
        return kcmc_service_deck_read_file_unlocked($path, $label);
    } finally {
        kcmc_service_deck_close_lock($lock);
    }
}

function kcmc_service_deck_load_artifact_bundle(array $record, ?string $key = null): array {
    kcmc_service_deck_validate_record($record);
    $jobId = (string)$record['job_id'];
    if (!is_array($record['artifacts'] ?? null)) {
        throw new DomainException('Service-deck job has no imported artifacts.');
    }
    $requestBytes = kcmc_service_deck_read_immutable_file(
        kcmc_service_deck_request_path($jobId),
        'Service-deck request'
    );
    $deckBytes = kcmc_service_deck_read_immutable_file(
        kcmc_service_deck_artifact_path($jobId, 'deck'),
        'Service-deck PowerPoint'
    );
    $manifestBytes = kcmc_service_deck_read_immutable_file(
        kcmc_service_deck_artifact_path($jobId, 'manifest'),
        'Service-deck manifest'
    );
    $envelopeBytes = kcmc_service_deck_read_immutable_file(
        kcmc_service_deck_artifact_path($jobId, 'envelope'),
        'Service-deck import envelope'
    );
    $envelope = kcmc_service_deck_decode_import_envelope($envelopeBytes);
    $validated = kcmc_service_deck_validate_signed_import(
        $record,
        $envelope,
        $requestBytes,
        $manifestBytes,
        $deckBytes,
        $key,
        false
    );
    $artifacts = $record['artifacts'];
    if (($artifacts['deck']['sha256'] ?? null) !== $validated['deck_sha256']
        || ($artifacts['manifest']['sha256'] ?? null) !== $validated['manifest_sha256']
        || ($artifacts['deck']['bytes'] ?? null) !== strlen($deckBytes)
        || ($artifacts['manifest']['bytes'] ?? null) !== strlen($manifestBytes)
        || ($artifacts['envelope']['bytes'] ?? null) !== strlen($envelopeBytes)) {
        throw new UnexpectedValueException('Stored service-deck artifact metadata does not match its exact bytes.');
    }
    return [
        'request' => $requestBytes,
        'deck' => $deckBytes,
        'manifest' => $manifestBytes,
        'envelope' => $envelopeBytes,
        'validated' => $validated,
    ];
}

function kcmc_service_deck_revalidate_imported_artifacts(
    string $jobId,
    array $user,
    ?string $key = null
): array {
    kcmc_service_deck_require_manager($user);
    $record = kcmc_service_deck_read_record_unchecked($jobId);
    $bundle = kcmc_service_deck_load_artifact_bundle($record, $key);
    return [
        'job_id' => $jobId,
        'request_sha256' => $bundle['validated']['request_sha256'],
        'deck_sha256' => $bundle['validated']['deck_sha256'],
        'manifest_sha256' => $bundle['validated']['manifest_sha256'],
        'ok' => true,
    ];
}

function kcmc_service_deck_read_artifact(
    string $jobId,
    string $artifact,
    array $user,
    ?string $key = null
): array {
    kcmc_service_deck_require_manager($user);
    if (!in_array($artifact, ['deck', 'manifest', 'envelope'], true)) {
        throw new InvalidArgumentException('Unknown service-deck artifact.');
    }
    $record = kcmc_service_deck_read_record_unchecked($jobId);
    $bundle = kcmc_service_deck_load_artifact_bundle($record, $key);
    $names = [
        'deck' => (string)($record['artifacts']['deck']['original_name'] ?? 'service-deck.pptx'),
        'manifest' => 'manifest.json',
        'envelope' => 'import-envelope.json',
    ];
    $types = [
        'deck' => 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'manifest' => 'application/json',
        'envelope' => 'application/json',
    ];
    return [
        'bytes' => $bundle[$artifact],
        'filename' => $names[$artifact],
        'content_type' => $types[$artifact],
        'sha256' => hash('sha256', $bundle[$artifact]),
    ];
}

function kcmc_service_deck_transition_decision(
    array $record,
    array $user,
    string $decision,
    string $deckSha256,
    string $notes,
    ?string $decidedAt = null
): array {
    kcmc_service_deck_require_approver($user);
    $actor = kcmc_service_deck_actor($user);
    kcmc_service_deck_validate_record($record);
    if (!in_array($decision, ['APPROVED', 'CHANGES_REQUESTED'], true)) {
        throw new InvalidArgumentException('Invalid service-deck decision.');
    }
    if (!kcmc_service_deck_is_sha256($deckSha256)) {
        throw new InvalidArgumentException('Decision requires the exact deck SHA-256.');
    }
    $notes = kcmc_service_deck_clean_text(
        $notes,
        KCMC_SERVICE_MAX_NOTES_LENGTH,
        $decision === 'CHANGES_REQUESTED',
        'Decision notes'
    );
    if (($record['status'] ?? null) !== 'AWAITING_PASTOR_APPROVAL'
        || !is_array($record['artifacts'] ?? null)) {
        throw new DomainException('Service-deck job is not awaiting pastor approval.');
    }
    if (($record['approval']['decision'] ?? null) !== null) {
        throw new DomainException('Service-deck job already has an authoritative decision.');
    }
    $expectedHash = $record['artifacts']['deck']['sha256'] ?? null;
    if (!is_string($expectedHash) || !hash_equals($expectedHash, $deckSha256)) {
        throw new DomainException('Decision deck hash does not match the imported artifact.');
    }
    $at = $decidedAt ?? gmdate('c');
    $record['approval'] = [
        'decision' => $decision,
        'actor' => $actor,
        'decided_at' => $at,
        'deck_sha256' => $deckSha256,
        'request_sha256' => (string)$record['request']['sha256'],
        'manifest_sha256' => (string)$record['artifacts']['manifest']['sha256'],
        'notes' => $notes,
        'authoritative' => true,
        'identity_verified' => true,
        'autopublish' => false,
    ];
    $record['status'] = $decision;
    $record['autopublish'] = false;
    $record['history'][] = [
        'at' => $at,
        'event' => $decision,
        'actor' => $actor,
        'deck_sha256' => $deckSha256,
        'request_sha256' => (string)$record['request']['sha256'],
        'manifest_sha256' => (string)$record['artifacts']['manifest']['sha256'],
        'notes' => $notes,
    ];
    return $record;
}

function kcmc_service_deck_record_decision(
    string $jobId,
    array $user,
    string $decision,
    string $deckSha256,
    string $notes = ''
): array {
    kcmc_service_deck_require_approver($user);
    return kcmc_service_deck_update_record(
        $jobId,
        static function (array $record) use ($user, $decision, $deckSha256, $notes): array {
            $bundle = kcmc_service_deck_load_artifact_bundle($record);
            if (!hash_equals((string)$bundle['validated']['deck_sha256'], $deckSha256)) {
                throw new DomainException('Decision deck hash does not match the freshly verified artifact.');
            }
            return kcmc_service_deck_transition_decision(
                $record,
                $user,
                $decision,
                $deckSha256,
                $notes
            );
        }
    );
}
