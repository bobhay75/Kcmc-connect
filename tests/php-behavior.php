<?php
declare(strict_types=1);

$serviceDeckTestRoot = sys_get_temp_dir() . '/kcmc-service-decks-' . bin2hex(random_bytes(8));
if (!mkdir($serviceDeckTestRoot, 0750, true) && !is_dir($serviceDeckTestRoot)) {
    fwrite(STDERR, "FAIL: Could not create isolated private-data test directory.\n");
    exit(1);
}
putenv('KCMC_PRIVATE_DATA_DIR=' . $serviceDeckTestRoot);
putenv('KCMC_SERMON_IMPORT_KEY=php-behavior-test-key-0123456789abcdef');

function remove_test_tree(string $path): void {
    if (!file_exists($path) && !is_link($path)) return;
    if (is_file($path) || is_link($path)) {
        @unlink($path);
        return;
    }
    $entries = scandir($path);
    if (is_array($entries)) {
        foreach ($entries as $entry) {
            if ($entry === '.' || $entry === '..') continue;
            remove_test_tree($path . DIRECTORY_SEPARATOR . $entry);
        }
    }
    @rmdir($path);
}

register_shutdown_function(static function () use ($serviceDeckTestRoot): void {
    remove_test_tree($serviceDeckTestRoot);
});

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/service-decks.php';

function expect_same(mixed $expected, mixed $actual, string $message): void {
    if ($expected !== $actual) {
        fwrite(STDERR, "FAIL: {$message}\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true) . "\n");
        exit(1);
    }
}

function expect_true(bool $actual, string $message): void {
    expect_same(true, $actual, $message);
}

function expect_throws(callable $callback, string $message, string $expectedClass = Throwable::class): void {
    try {
        $callback();
    } catch (Throwable $exception) {
        if ($exception instanceof $expectedClass) return;
        fwrite(STDERR, "FAIL: {$message}\nExpected exception: {$expectedClass}\nActual exception: " . get_class($exception) . ': ' . $exception->getMessage() . "\n");
        exit(1);
    }
    fwrite(STDERR, "FAIL: {$message}\nExpected exception: {$expectedClass}\nActual: no exception\n");
    exit(1);
}

$_SERVER['SCRIPT_NAME'] = '/kcmc-connect/member/login.php';
$_COOKIE = [];

expect_same(false, kcmc_session_cookie_present(), 'Anonymous public visits must not look authenticated.');
expect_same(null, kcmc_current_user_if_session(), 'Anonymous public visits must not start a member lookup.');
expect_same(PHP_SESSION_NONE, session_status(), 'Anonymous public visits must not create a PHP session.');

$announcements = [
    ['id' => 'backpack-blessing-2026', 'priority' => 200, 'status' => 'hidden'],
    ['id' => 'sep-news-16', 'priority' => 100, 'status' => 'published'],
    ['id' => 'lower-priority', 'priority' => 20, 'status' => 'published'],
];
expect_same(1, kcmc_featured_announcement_index($announcements), 'Publishing must skip retired announcements.');
$announcements[] = ['id' => 'owner-announcement', 'priority' => 10, 'status' => 'hidden'];
expect_same(3, kcmc_featured_announcement_index($announcements), 'The stable owner announcement must remain editable.');

$content = ['events' => []];
expect_same(true, kcmc_apply_required_public_content($content), 'Required public content must be added once.');
expect_same(false, kcmc_apply_required_public_content($content), 'Required public content migration must be idempotent.');

expect_same('/kcmc-connect/admin/', kcmc_safe_next('/kcmc-connect/admin/'), 'Local redirects must remain available.');
expect_same('/kcmc-connect/member/', kcmc_safe_next('https://example.com/steal'), 'External redirects must be rejected.');

$safeAudit = kcmc_sanitize_audit_context([
    'role' => 'member',
    'message' => 'private prayer',
    'nested' => ['token_hash' => 'secret', 'action' => 'approved'],
]);
expect_same(['role' => 'member', 'nested' => ['action' => 'approved']], $safeAudit, 'Audit context must remove sensitive fields recursively.');

expect_same(false, kcmc_can_view_private_prayers(['role' => 'recovery_admin']), 'Recovery administrators must not read prayer content.');
expect_same(true, kcmc_can_view_private_prayers(['role' => 'pastor_admin']), 'Pastor administrators must retain prayer access.');

$member = [
    'id' => 'usr_member',
    'display_name' => 'Member One',
    'email' => 'member@example.test',
    'role' => 'member',
];
$recovery = [
    'id' => 'usr_recovery',
    'display_name' => 'Recovery Admin',
    'email' => 'recovery@example.test',
    'role' => 'recovery_admin',
];
$pastor = [
    'id' => 'usr_pastor',
    'display_name' => 'Pastor Admin',
    'email' => 'pastor@example.test',
    'role' => 'pastor_admin',
];

expect_same(false, kcmc_can_manage_service_decks($member), 'Members must not manage service decks.');
expect_same(true, kcmc_can_manage_service_decks($recovery), 'Recovery administrators may manage service-deck jobs.');
expect_same(true, kcmc_can_manage_service_decks($pastor), 'Pastor administrators may manage service-deck jobs.');
expect_same(false, kcmc_can_approve_service_decks($recovery), 'Recovery administrators must not issue authoritative approvals.');
expect_same(true, kcmc_can_approve_service_decks($pastor), 'Pastor administrators are authoritative approvers.');
expect_same(true, kcmc_service_deck_import_key_configured(), 'A 32-character import key must be recognized as configured.');

$serviceInput = [
    'service_name' => "Sunday Front Porch\r\nService",
    'service_date' => '2026-09-20',
    'service_style' => 'Front Porch',
    'items' => [
        ['type' => 'service_title', 'title' => 'Sunday Front Porch'],
        ['type' => 'song', 'title' => 'Sample Song', 'lyrics' => "Line one\r\nLine two"],
        ['type' => 'scripture', 'title' => 'John 1:1', 'text' => 'Authorized Scripture text.'],
        ['type' => 'sermon_title', 'title' => 'The Message'],
        ['type' => 'announcement', 'title' => 'Church Supper', 'text' => 'Wednesday at six.'],
        ['type' => 'blank'],
    ],
];

expect_throws(
    static fn() => kcmc_service_deck_create_job($serviceInput, $member),
    'Members must not create service-deck jobs.',
    DomainException::class
);
$job = kcmc_service_deck_create_job($serviceInput, $recovery);
$jobId = (string)$job['job_id'];
expect_true(kcmc_service_deck_valid_job_id($jobId), 'Job identifiers must be opaque sdj_ values with 128 random bits.');
expect_same('REQUEST_READY', $job['status'], 'New service-deck jobs must wait for a signed import.');
expect_same('2026-09-20', $job['service_date'], 'The validated service date must be recorded.');
expect_same(false, $job['autopublish'], 'New jobs must never enable autopublish.');
expect_same('usr_recovery', $job['created_by']['id'], 'Job ownership must come from the authenticated session user.');
$inconsistentRecord = $job;
$inconsistentRecord['status'] = 'APPROVED';
expect_throws(
    static fn() => kcmc_service_deck_validate_record($inconsistentRecord),
    'Record statuses must agree with artifacts and authoritative decision state.',
    UnexpectedValueException::class
);

$requestBytes = kcmc_service_deck_request_bytes($jobId, $recovery);
$request = json_decode($requestBytes, true, 64, JSON_THROW_ON_ERROR);
expect_same($jobId, $request['kcmc_job_id'], 'Request job binding must be generated by the server.');
expect_same(false, $request['autopublish'], 'Deterministic worker requests must disable autopublish.');
expect_same("Sunday Front Porch\nService", $request['service_name'], 'Request line endings must be normalized deterministically.');
expect_same('Intentional blank', $request['items'][5]['title'], 'Blank items must receive a deterministic safe title.');
expect_same($requestBytes, kcmc_service_deck_encode_json($request), 'Request JSON must use exact deterministic bytes.');
expect_same(hash('sha256', $requestBytes), $job['request']['sha256'], 'The job must bind the exact request bytes by SHA-256.');
expect_same(0640, fileperms(kcmc_service_deck_request_path($jobId)) & 0777, 'Private request files must use mode 0640.');
expect_same(0750, fileperms(KCMC_SERVICE_DECKS_DIR) & 0777, 'Private service-deck directories must use mode 0750.');

expect_throws(
    static fn() => kcmc_service_deck_artifact_path('../content.json', 'deck'),
    'Path-shaped job IDs must be rejected.',
    InvalidArgumentException::class
);
expect_throws(
    static fn() => kcmc_service_deck_artifact_path('sdj_' . str_repeat('a', 32), '../../deck'),
    'Artifact names must come from a fixed allowlist.',
    InvalidArgumentException::class
);

$hostileTop = $serviceInput;
$hostileTop['job_id'] = 'sdj_' . str_repeat('a', 32);
expect_throws(
    static fn() => kcmc_service_deck_create_job($hostileTop, $pastor),
    'Clients must not override server-generated job fields.',
    InvalidArgumentException::class
);
$hostileItem = $serviceInput;
$hostileItem['items'][1]['status'] = 'APPROVED';
expect_throws(
    static fn() => kcmc_service_deck_create_job($hostileItem, $pastor),
    'Clients must not inject worker status fields into ordered items.',
    InvalidArgumentException::class
);
$badStyle = $serviceInput;
$badStyle['service_style'] = 'Traditional';
expect_throws(
    static fn() => kcmc_service_deck_create_job($badStyle, $pastor),
    'Unverified service styles must fail closed.',
    InvalidArgumentException::class
);
$badDate = $serviceInput;
$badDate['service_date'] = '2026-02-30';
expect_throws(
    static fn() => kcmc_service_deck_create_job($badDate, $pastor),
    'Impossible service dates must be rejected.',
    InvalidArgumentException::class
);
$tooManyItems = $serviceInput;
$tooManyItems['items'] = array_fill(0, KCMC_SERVICE_MAX_ITEMS + 1, ['type' => 'blank']);
expect_throws(
    static fn() => kcmc_service_deck_create_job($tooManyItems, $pastor),
    'Service item count limits must be enforced.',
    InvalidArgumentException::class
);
$longName = $serviceInput;
$longName['service_name'] = str_repeat('x', KCMC_SERVICE_MAX_NAME_LENGTH + 1);
expect_throws(
    static fn() => kcmc_service_deck_create_job($longName, $pastor),
    'Service name length limits must be enforced.',
    InvalidArgumentException::class
);

$deckBytes = "PK\x03\x04KCMC deterministic test PowerPoint bytes";
$deckSha256 = hash('sha256', $deckBytes);
$manifestItems = [];
foreach ($request['items'] as $requestedItem) {
    $manifestItems[] = [
        'title' => $requestedItem['title'],
        'status' => 'CREATED_DRAFT',
        'item_type' => $requestedItem['type'],
        'slides_added' => 1,
        'qa' => ['ok' => true, 'errors' => [], 'warnings' => []],
    ];
}
$manifest = [
    'schema_version' => 3,
    'service' => $request['service_name'],
    'service_style' => 'Front Porch',
    'status' => 'AWAITING_PASTOR_APPROVAL',
    'ready_for_approval' => true,
    'items' => $manifestItems,
    'final_deck' => 'sunday-front-porch-service.pptx',
    'final_deck_sha256' => $deckSha256,
    'final_qa' => ['ok' => true, 'errors' => [], 'warnings' => [], 'slides' => count($manifestItems)],
    'approval' => ['decision' => null, 'approved_by' => null, 'decided_at' => null, 'notes' => null],
    'autopublish' => false,
];
$importKey = (string)getenv('KCMC_SERMON_IMPORT_KEY');
$makeEnvelope = static function (
    string $boundJobId,
    string $boundRequestBytes,
    string $boundManifestBytes,
    string $boundDeckBytes,
    string $key
): array {
    $requestHash = hash('sha256', $boundRequestBytes);
    $deckHash = hash('sha256', $boundDeckBytes);
    $manifestHash = hash('sha256', $boundManifestBytes);
    $message = kcmc_service_deck_import_message($boundJobId, $requestHash, $deckHash, $manifestHash);
    return [
        'schema_version' => 1,
        'job_id' => $boundJobId,
        'request_sha256' => $requestHash,
        'deck_sha256' => $deckHash,
        'manifest_sha256' => $manifestHash,
        'signature_hmac_sha256' => hash_hmac('sha256', $message, $key),
    ];
};
$manifestBytes = kcmc_service_deck_encode_json($manifest);
$envelope = $makeEnvelope($jobId, $requestBytes, $manifestBytes, $deckBytes, $importKey);
$envelopeBytes = kcmc_service_deck_encode_json($envelope);

$validated = kcmc_service_deck_validate_signed_import(
    $job,
    $envelope,
    $requestBytes,
    $manifestBytes,
    $deckBytes
);
expect_same($deckSha256, $validated['deck_sha256'], 'A valid signed import must bind the exact deck bytes.');

$badEnvelopeSchema = $envelope;
$badEnvelopeSchema['schema_version'] = 2;
expect_throws(
    static fn() => kcmc_service_deck_validate_signed_import($job, $badEnvelopeSchema, $requestBytes, $manifestBytes, $deckBytes),
    'Unsupported envelope schemas must fail closed.',
    UnexpectedValueException::class
);
$badSignature = $envelope;
$badSignature['signature_hmac_sha256'] = str_repeat('0', 64);
expect_throws(
    static fn() => kcmc_service_deck_validate_signed_import($job, $badSignature, $requestBytes, $manifestBytes, $deckBytes),
    'Invalid HMAC signatures must be rejected.',
    UnexpectedValueException::class
);
$badRequestHash = $envelope;
$badRequestHash['request_sha256'] = str_repeat('0', 64);
expect_throws(
    static fn() => kcmc_service_deck_validate_signed_import($job, $badRequestHash, $requestBytes, $manifestBytes, $deckBytes),
    'Request hash mismatches must be rejected.',
    UnexpectedValueException::class
);
expect_throws(
    static fn() => kcmc_service_deck_validate_signed_import($job, $envelope, $requestBytes, $manifestBytes, $deckBytes . 'tampered'),
    'Deck hash mismatches must be rejected.',
    UnexpectedValueException::class
);
expect_throws(
    static fn() => kcmc_service_deck_validate_signed_import($job, $envelope, $requestBytes, $manifestBytes . " ", $deckBytes),
    'Manifest hash mismatches must be rejected.',
    UnexpectedValueException::class
);

$expectBadManifest = static function (array $candidate, string $message) use (
    $job,
    $jobId,
    $requestBytes,
    $deckBytes,
    $importKey,
    $makeEnvelope
): void {
    $candidateBytes = kcmc_service_deck_encode_json($candidate);
    $candidateEnvelope = $makeEnvelope($jobId, $requestBytes, $candidateBytes, $deckBytes, $importKey);
    expect_throws(
        static fn() => kcmc_service_deck_validate_signed_import(
            $job,
            $candidateEnvelope,
            $requestBytes,
            $candidateBytes,
            $deckBytes
        ),
        $message,
        UnexpectedValueException::class
    );
};
$badManifest = $manifest;
$badManifest['schema_version'] = 2;
$expectBadManifest($badManifest, 'Unsupported manifest schemas must be rejected.');
$badManifest = $manifest;
$badManifest['ready_for_approval'] = false;
$expectBadManifest($badManifest, 'A manifest that is not ready for approval must be rejected.');
$badManifest = $manifest;
$badManifest['final_qa']['ok'] = false;
$expectBadManifest($badManifest, 'A manifest with failed final QA must be rejected.');
$badManifest = $manifest;
$badManifest['items'][2]['status'] = 'NEEDS_HUMAN_INPUT';
$expectBadManifest($badManifest, 'Every imported service item must be complete.');
$badManifest = $manifest;
$badManifest['autopublish'] = true;
$expectBadManifest($badManifest, 'Autopublish must remain disabled in the producer manifest.');
$badManifest = $manifest;
$badManifest['approval']['decision'] = 'APPROVED';
$badManifest['approval']['approved_by'] = 'offline-name';
$expectBadManifest($badManifest, 'Producer manifests containing an approval must be rejected.');
$badManifest = $manifest;
$badManifest['approval']['authoritative'] = true;
$expectBadManifest($badManifest, 'Producer manifests must not inject authoritative approval fields.');
$badManifest = $manifest;
$badManifest['final_deck'] = '../outside.pptx';
$expectBadManifest($badManifest, 'Unsafe manifest deck paths must be rejected.');
expect_throws(
    static fn() => kcmc_service_deck_validate_signed_import($job, $envelope, $requestBytes, $manifestBytes, $deckBytes, 'short'),
    'Short import keys must be rejected.',
    RuntimeException::class
);

$imported = kcmc_service_deck_import_signed_artifacts(
    $jobId,
    $envelopeBytes,
    $manifestBytes,
    $deckBytes,
    $recovery
);
expect_same('AWAITING_PASTOR_APPROVAL', $imported['status'], 'A verified import must stop at pastor approval.');
expect_same(false, $imported['autopublish'], 'Verified imports must not publish content.');
expect_same($deckSha256, $imported['artifacts']['deck']['sha256'], 'Imported records must retain the exact deck hash.');
expect_same(2, count($imported['history']), 'Import must append record-level history.');
expect_same(0640, fileperms(kcmc_service_deck_artifact_path($jobId, 'deck')) & 0777, 'Private deck artifacts must use mode 0640.');

$download = kcmc_service_deck_read_artifact($jobId, 'deck', $recovery);
expect_same($deckBytes, $download['bytes'], 'Artifact reads must return the exact bytes that were freshly revalidated.');
expect_same($deckSha256, $download['sha256'], 'Artifact reads must rehash the exact opened bytes.');
$revalidated = kcmc_service_deck_revalidate_imported_artifacts($jobId, $pastor);
expect_same(true, $revalidated['ok'], 'Stored producer evidence must revalidate before approval.');

expect_throws(
    static fn() => kcmc_service_deck_record_decision($jobId, $recovery, 'APPROVED', $deckSha256),
    'Recovery administrators must not make authoritative decisions.',
    DomainException::class
);
expect_throws(
    static fn() => kcmc_service_deck_record_decision($jobId, $pastor, 'APPROVED', str_repeat('0', 64)),
    'Decisions must bind the freshly verified exact deck hash.',
    DomainException::class
);
expect_throws(
    static fn() => kcmc_service_deck_transition_decision($imported, $pastor, 'CHANGES_REQUESTED', $deckSha256, ''),
    'Change requests must explain the requested change.',
    InvalidArgumentException::class
);
$changePreview = kcmc_service_deck_transition_decision(
    $imported,
    $pastor,
    'CHANGES_REQUESTED',
    $deckSha256,
    'Correct slide five.'
);
expect_same('usr_pastor', $changePreview['approval']['actor']['id'], 'Pure decision transitions must bind the session actor, not submitted identity fields.');
expect_same(false, $changePreview['autopublish'], 'Change requests must keep autopublish disabled.');
$approved = kcmc_service_deck_record_decision($jobId, $pastor, 'APPROVED', $deckSha256, 'Reviewed in KCMC Connect.');
expect_same('APPROVED', $approved['status'], 'Pastor approval must create an authoritative terminal decision.');
expect_same('usr_pastor', $approved['approval']['actor']['id'], 'Decision identity must come only from the authenticated session.');
expect_same(true, $approved['approval']['authoritative'], 'Pastor decisions must be explicitly authoritative.');
expect_same(true, $approved['approval']['identity_verified'], 'Pastor decisions must bind a verified session identity.');
expect_same(false, $approved['approval']['autopublish'], 'An approval decision must not publish automatically.');
expect_same($job['request']['sha256'], $approved['approval']['request_sha256'], 'Approval must bind the exact request hash.');
expect_same(hash('sha256', $manifestBytes), $approved['approval']['manifest_sha256'], 'Approval must bind the exact manifest hash.');
expect_same(3, count($approved['history']), 'Decision must append immutable record-level history.');
expect_throws(
    static fn() => kcmc_service_deck_record_decision($jobId, $pastor, 'CHANGES_REQUESTED', $deckSha256, 'Again'),
    'A job must not accept a second authoritative decision.',
    DomainException::class
);

$backupFiles = glob(KCMC_SERVICE_DECKS_BACKUPS_DIR . '/' . $jobId . '/*-record.json');
expect_true(is_array($backupFiles) && count($backupFiles) >= 2, 'Import and decision transitions must create private record backups.');
foreach ($backupFiles as $backupFile) {
    expect_same(0640, fileperms($backupFile) & 0777, 'Private record backups must use mode 0640.');
}

$listedJobs = kcmc_service_deck_list_jobs($pastor);
expect_same($jobId, $listedJobs[0]['job_id'], 'Authorized managers must be able to list private jobs newest first.');

$corruptInput = $serviceInput;
$corruptInput['service_name'] = 'Corruption sentinel';
$corruptJob = kcmc_service_deck_create_job($corruptInput, $pastor);
file_put_contents(kcmc_service_deck_job_path((string)$corruptJob['job_id']), "{not-json\n", LOCK_EX);
expect_throws(
    static fn() => kcmc_service_deck_get_job((string)$corruptJob['job_id'], $pastor),
    'Corrupt private JSON must raise an error instead of silently resetting state.',
    UnexpectedValueException::class
);

echo "KCMC PHP behavior checks passed.\n";
