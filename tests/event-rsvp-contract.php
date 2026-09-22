<?php
declare(strict_types=1);

$tmp = sys_get_temp_dir() . '/kcmc-event-rsvp-' . bin2hex(random_bytes(5));
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) throw new RuntimeException('Could not create RSVP test storage.');
putenv('KCMC_PRIVATE_DATA_DIR=' . $tmp);

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/event-rsvp.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/audit-history.php';

function rsvp_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$valid = kcmc_event_rsvp_validate_input([
    'event' => 'Community Supper',
    'event_date' => '2026-10-14',
    'name' => '  Jane Visitor  ',
    'email' => '  JANE@EXAMPLE.COM ',
    'message' => 'Two attending.',
]);
rsvp_check(!empty($valid['ok']), 'valid RSVP input is accepted');
rsvp_check(($valid['value']['name'] ?? '') === 'Jane Visitor', 'name is trimmed');
rsvp_check(($valid['value']['email'] ?? '') === 'jane@example.com', 'email is normalized');

rsvp_check(empty(kcmc_event_rsvp_validate_input(['event'=>'x','event_date'=>'2026-10-14','name'=>'Jane','email'=>'jane@example.com'])['ok']), 'short event title is rejected');
rsvp_check(empty(kcmc_event_rsvp_validate_input(['event'=>'Event','event_date'=>'2026-02-31','name'=>'Jane','email'=>'jane@example.com'])['ok']), 'invalid event date is rejected');
rsvp_check(empty(kcmc_event_rsvp_validate_input(['event'=>'Event','event_date'=>'2026-10-14','name'=>'J','email'=>'jane@example.com'])['ok']), 'short attendee name is rejected');
rsvp_check(empty(kcmc_event_rsvp_validate_input(['event'=>'Event','event_date'=>'2026-10-14','name'=>'Jane','email'=>'not-an-email'])['ok']), 'invalid attendee email is rejected');
rsvp_check(empty(kcmc_event_rsvp_validate_input(['event'=>'Event','event_date'=>'2026-10-14','name'=>'Jane','email'=>'jane@example.com','message'=>str_repeat('x',1001)])['ok']), 'oversized note is rejected');

$events = [
    ['title'=>'Community Supper','date'=>'2026-10-14','status'=>'published','rsvp'=>true],
    ['title'=>'Phone Only','date'=>'2026-10-15','status'=>'published','rsvp'=>false],
    ['title'=>'Hidden Event','date'=>'2026-10-16','status'=>'hidden','rsvp'=>true],
    ['title'=>'Expired Event','date'=>'2026-10-17','status'=>'published','rsvp'=>true,'expires_at'=>'2020-01-01T00:00:00Z'],
];
rsvp_check(kcmc_event_rsvp_event_is_open($events, ' community supper ', '2026-10-14'), 'published RSVP-enabled event is accepted case-insensitively');
rsvp_check(!kcmc_event_rsvp_event_is_open($events, 'Phone Only', '2026-10-15'), 'event with RSVP disabled is rejected');
rsvp_check(!kcmc_event_rsvp_event_is_open($events, 'Hidden Event', '2026-10-16'), 'hidden event is rejected');
rsvp_check(!kcmc_event_rsvp_event_is_open($events, 'Expired Event', '2026-10-17'), 'expired event is rejected');
rsvp_check(!kcmc_event_rsvp_event_is_open($events, 'Community Supper', '2026-10-15'), 'wrong event date is rejected');

$hash = kcmc_event_rsvp_client_hash('203.0.113.40');
rsvp_check(strlen($hash) === 64 && !str_contains($hash, '203.0.113.40'), 'client address is represented only by a one-way hash');
$rateNow = 2000000000;
for ($i = 1; $i <= KCMC_EVENT_RSVP_RATE_LIMIT; $i++) {
    $rate = kcmc_event_rsvp_consume_rate($hash, $rateNow + $i);
    rsvp_check(!empty($rate['allowed']), "rate slot {$i} is allowed");
}
$blocked = kcmc_event_rsvp_consume_rate($hash, $rateNow + 20);
rsvp_check(empty($blocked['allowed']) && (int)$blocked['retry_after'] > 0, 'ninth RSVP inside the rate window is blocked with retry guidance');
$afterWindow = kcmc_event_rsvp_consume_rate($hash, $rateNow + KCMC_EVENT_RSVP_RATE_WINDOW + 30);
rsvp_check(!empty($afterWindow['allowed']), 'client may submit again after the rate window');

$value = $valid['value'];
$first = kcmc_event_rsvp_store($value, 2000001000);
rsvp_check(!empty($first['stored']) && empty($first['duplicate']) && str_starts_with((string)$first['id'], 'rsvp_'), 'first RSVP is stored with random RSVP ID');
$duplicate = kcmc_event_rsvp_store($value, 2000001200);
rsvp_check(empty($duplicate['stored']) && !empty($duplicate['duplicate']), 'same email/event/date within one hour is treated as already received');
$value2 = $value; $value2['email'] = 'other@example.com';
$second = kcmc_event_rsvp_store($value2, 2000001300);
rsvp_check(!empty($second['stored']), 'different attendee may RSVP for same event');
$later = kcmc_event_rsvp_store($value, 2000001000 + KCMC_EVENT_RSVP_DUPLICATE_WINDOW + 1);
rsvp_check(!empty($later['stored']), 'same attendee may submit again after duplicate window');
$recent = kcmc_event_rsvp_recent(10);
rsvp_check(count($recent) === 3, 'duplicate submission does not create an extra RSVP row');
rsvp_check(($recent[0]['submitted_at'] ?? '') >= ($recent[1]['submitted_at'] ?? ''), 'administrator RSVP rows are newest first');

$api = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/api/rsvp.php');
rsvp_check(is_string($api) && str_contains($api, "REQUEST_METHOD'] !== 'POST'"), 'RSVP API accepts POST only');
rsvp_check(str_contains((string)$api, "HTTP_X_KCMC_RSVP"), 'RSVP API requires same-app custom request header');
rsvp_check(str_contains((string)$api, "HTTP_SEC_FETCH_SITE") && str_contains((string)$api, "cross-site"), 'RSVP API rejects explicit cross-site browser submissions');
rsvp_check(str_contains((string)$api, 'CONTENT_LENGTH') && str_contains((string)$api, '> 8192'), 'RSVP API bounds request body size');
rsvp_check(str_contains((string)$api, 'kcmc_event_rsvp_consume_rate'), 'RSVP API applies bounded abuse control');
rsvp_check(str_contains((string)$api, 'kcmc_event_rsvp_event_is_open'), 'RSVP API requires a live RSVP-enabled event');
rsvp_check(str_contains((string)$api, "kcmc_audit('event.rsvp_submitted', ['count' => 1])"), 'RSVP audit records only an aggregate count');
rsvp_check(!preg_match("/kcmc_audit\('event\.rsvp_submitted'.*(email|name|message)/s", (string)$api), 'RSVP audit does not include attendee PII or note text');

$admin = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/rsvps.php');
rsvp_check(is_string($admin) && str_contains($admin, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'RSVP attendee view requires administrator role');
rsvp_check(str_contains((string)$admin, 'kcmc_private_headers()'), 'RSVP attendee view is private/no-store');
rsvp_check(str_contains((string)$admin, 'kcmc_event_rsvp_recent(200)'), 'RSVP attendee view is bounded to newest 200 rows');

$app = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/app.js');
rsvp_check(is_string($app) && str_contains($app, "fetch('./api/rsvp.php'"), 'event form posts to first-party RSVP API');
rsvp_check(str_contains((string)$app, "'X-KCMC-RSVP':'1'"), 'event form sends same-app custom request header');
rsvp_check(str_contains((string)$app, "eventDateField.name='event_date'"), 'selected event date is submitted with RSVP');
rsvp_check(str_contains((string)$app, 'sendFormByEmail(form)'), 'other public forms retain existing email handoff');

$index = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/index.php');
rsvp_check(is_string($index) && str_contains($index, "admin/rsvps.php"), 'Publishing Desk links to private RSVP inbox');
rsvp_check(kcmc_audit_event_label('event.rsvp_submitted') === 'Event RSVP received', 'audit history gives RSVP submissions a friendly label');

rsvp_check(str_starts_with(KCMC_EVENT_RSVPS, $tmp . DIRECTORY_SEPARATOR), 'RSVP records live in configured private data storage');
rsvp_check(str_starts_with(KCMC_EVENT_RSVP_RATE, $tmp . DIRECTORY_SEPARATOR), 'RSVP rate state lives in configured private data storage');

foreach (glob($tmp . '/*') ?: [] as $path) @unlink($path);
@rmdir($tmp);
putenv('KCMC_PRIVATE_DATA_DIR');
echo "Event RSVP contract checks passed.\n";
