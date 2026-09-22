<?php
declare(strict_types=1);

$tmp = sys_get_temp_dir() . '/kcmc-connection-' . bin2hex(random_bytes(5));
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) throw new RuntimeException('Could not create connection test storage.');
putenv('KCMC_PRIVATE_DATA_DIR=' . $tmp);

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/connection-intake.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/audit-history.php';

function connection_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$visit = kcmc_connection_validate('visit', [
    'firstName' => ' Robert ', 'lastName' => ' Visitor ', 'email' => ' ROBERT@example.com ',
    'phone' => '(417) 555-0199', 'service' => '9:15 AM — Traditional Worship',
    'message' => 'First visit.', 'unexpected' => 'must not persist',
]);
connection_check(!empty($visit['ok']), 'valid Plan a Visit request is accepted');
connection_check(($visit['value']['name'] ?? '') === 'Robert Visitor', 'visit first and last name normalize to display name');
connection_check(($visit['value']['email'] ?? '') === 'robert@example.com', 'visit email is normalized');
connection_check(($visit['value']['phone'] ?? '') === '(417) 555-0199', 'optional visit phone is retained');
connection_check(($visit['value']['service'] ?? '') === '9:15 AM — Traditional Worship', 'visit service must match a published option');
connection_check(!array_key_exists('unexpected', $visit['value']), 'unknown public fields are discarded');

$serve = kcmc_connection_validate('serve', [
    'name' => 'Alex Helper', 'email' => 'alex@example.com', 'interest' => 'Community Outreach', 'message' => 'Weekends work best.',
]);
connection_check(!empty($serve['ok']) && ($serve['value']['interest'] ?? '') === 'Community Outreach', 'valid volunteer interest is accepted');
$groups = kcmc_connection_validate('groups', [
    'name' => 'Sam Seeker', 'email' => 'sam@example.com', 'interest' => 'Small group / Bible study', 'message' => '',
]);
connection_check(!empty($groups['ok']) && ($groups['value']['kind'] ?? '') === 'groups', 'valid group interest is accepted');

connection_check(empty(kcmc_connection_validate('other', ['email'=>'a@example.com'])['ok']), 'unknown form category is rejected');
connection_check(empty(kcmc_connection_validate('visit', ['firstName'=>'A','lastName'=>'B','email'=>'bad','service'=>'9:15 AM — Traditional Worship'])['ok']), 'invalid email is rejected');
connection_check(empty(kcmc_connection_validate('visit', ['firstName'=>'A','lastName'=>'B','email'=>'a@example.com','phone'=>'CALL-ME-NOW','service'=>'9:15 AM — Traditional Worship'])['ok']), 'invalid optional phone is rejected');
connection_check(empty(kcmc_connection_validate('visit', ['firstName'=>'A','lastName'=>'B','email'=>'a@example.com','service'=>'2:00 PM'])['ok']), 'unknown worship service is rejected');
connection_check(empty(kcmc_connection_validate('serve', ['name'=>'Alex','email'=>'a@example.com','interest'=>'Administrator'])['ok']), 'unknown volunteer interest is rejected');
connection_check(empty(kcmc_connection_validate('groups', ['name'=>'Sam','email'=>'a@example.com','interest'=>'Secret group'])['ok']), 'unknown group interest is rejected');
connection_check(empty(kcmc_connection_validate('serve', ['name'=>'Alex','email'=>'a@example.com','interest'=>'Kids / Youth','message'=>str_repeat('x',1501)])['ok']), 'oversized connection note is rejected');

$hash = kcmc_connection_client_hash('198.51.100.20');
connection_check(strlen($hash) === 64 && !str_contains($hash, '198.51.100.20'), 'connection abuse state stores only a one-way client hash');
$rateNow = 2100000000;
for ($i = 1; $i <= KCMC_CONNECTION_RATE_LIMIT; $i++) {
    $rate = kcmc_connection_consume_rate($hash, $rateNow + $i);
    connection_check(!empty($rate['allowed']), "connection rate slot {$i} is allowed");
}
$blocked = kcmc_connection_consume_rate($hash, $rateNow + 30);
connection_check(empty($blocked['allowed']) && (int)$blocked['retry_after'] > 0, 'connection rate limit blocks excess requests with retry guidance');
$after = kcmc_connection_consume_rate($hash, $rateNow + KCMC_CONNECTION_RATE_WINDOW + 40);
connection_check(!empty($after['allowed']), 'connection rate limit recovers after its window');

$first = kcmc_connection_store($visit['value'], 2100001000);
connection_check(!empty($first['stored']) && str_starts_with((string)$first['id'], 'connection_'), 'first connection request is stored with random ID');
$duplicate = kcmc_connection_store($visit['value'], 2100001100);
connection_check(!empty($duplicate['duplicate']) && empty($duplicate['stored']), 'same category and email within duplicate window is idempotent');
$otherType = $serve['value']; $otherType['email'] = $visit['value']['email'];
connection_check(!empty(kcmc_connection_store($otherType, 2100001200)['stored']), 'same email may submit a different connection category');
$later = kcmc_connection_store($visit['value'], 2100001000 + KCMC_CONNECTION_DUPLICATE_WINDOW + 1);
connection_check(!empty($later['stored']), 'same category and email may submit after duplicate window');
$rows = kcmc_connection_recent(20);
connection_check(count($rows) === 3, 'duplicate connection request does not create a second row');
connection_check(($rows[0]['submitted_at'] ?? '') >= ($rows[1]['submitted_at'] ?? ''), 'connection inbox is newest first');

$api = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/api/connection.php');
connection_check(is_string($api) && str_contains($api, "REQUEST_METHOD'] !== 'POST'"), 'connection API accepts POST only');
connection_check(str_contains((string)$api, 'HTTP_X_KCMC_CONNECTION'), 'connection API requires same-app custom request header');
connection_check(str_contains((string)$api, 'HTTP_SEC_FETCH_SITE') && str_contains((string)$api, 'cross-site'), 'connection API rejects explicit cross-site browser submissions');
connection_check(str_contains((string)$api, 'CONTENT_LENGTH') && str_contains((string)$api, '> 8192'), 'connection API bounds request body size');
connection_check(str_contains((string)$api, 'kcmc_connection_consume_rate'), 'connection API applies abuse controls');
connection_check(str_contains((string)$api, "kcmc_audit($auditAction, ['count' => 1])"), 'connection audit stores aggregate count only');
connection_check(!str_contains("kcmc_audit($auditAction, ['count' => 1])", 'email'), 'connection audit call contains no visitor email');

$admin = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/connections.php');
connection_check(is_string($admin) && str_contains($admin, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'connection inbox requires administrator role');
connection_check(str_contains((string)$admin, 'kcmc_private_headers()'), 'connection inbox is private/no-store');
connection_check(str_contains((string)$admin, 'kcmc_connection_recent(300)'), 'connection inbox is bounded to newest 300 rows');

$app = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/app.js');
connection_check(is_string($app) && str_contains($app, "fetch('./api/connection.php'"), 'visit/serve/group forms post to first-party connection API');
connection_check(str_contains((string)$app, "'X-KCMC-CONNECTION':'1'"), 'connection forms send same-app custom request header');
connection_check(str_contains((string)$app, "new Set(['visit','serve','groups'])"), 'only known connection forms use private intake');
connection_check(str_contains((string)$app, 'else sendFormByEmail(form)'), 'unknown future forms retain email fallback');
connection_check(str_contains((string)$app, "if(kind==='event') sendEventRsvp(form)"), 'event RSVP remains on its dedicated private path');

$rsvpPage = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/rsvps.php');
connection_check(is_string($rsvpPage) && str_contains($rsvpPage, 'admin/connections.php'), 'administrator RSVP view links to connection inbox');
connection_check(kcmc_audit_event_label('connection.visit_submitted') === 'Visit plan received', 'visit audit label is friendly');
connection_check(kcmc_audit_event_label('connection.serve_submitted') === 'Volunteer interest received', 'serve audit label is friendly');
connection_check(kcmc_audit_event_label('connection.group_submitted') === 'Group interest received', 'group audit label is friendly');

$worker = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/sw.js');
connection_check(is_string($worker) && str_contains($worker, 'Connection-intake client refresh'), 'service-worker update refreshes cached connection client');
connection_check(str_starts_with(KCMC_CONNECTION_INTAKE, $tmp . DIRECTORY_SEPARATOR), 'connection records live in configured private storage');
connection_check(str_starts_with(KCMC_CONNECTION_RATE, $tmp . DIRECTORY_SEPARATOR), 'connection rate state lives in configured private storage');

foreach (glob($tmp . '/*') ?: [] as $path) @unlink($path);
@rmdir($tmp);
putenv('KCMC_PRIVATE_DATA_DIR');
echo "Connection intake contract checks passed.\n";
