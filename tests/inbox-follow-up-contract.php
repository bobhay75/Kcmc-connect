<?php
declare(strict_types=1);

$tmp = sys_get_temp_dir() . '/kcmc-inbox-follow-up-' . bin2hex(random_bytes(5));
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) throw new RuntimeException('Could not create inbox follow-up test storage.');
putenv('KCMC_PRIVATE_DATA_DIR=' . $tmp);

require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/connection-intake.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/event-rsvp.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/inbox-follow-up.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/audit-history.php';

function follow_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

follow_check(kcmc_inbox_status(null) === 'new', 'legacy row without status is treated as New');
follow_check(kcmc_inbox_status('CONTACTED') === 'contacted', 'status normalization is case-insensitive');
follow_check(kcmc_inbox_status('unexpected') === 'new', 'unknown stored status fails safely to New');
follow_check(kcmc_inbox_status_label('closed') === 'Closed', 'status labels are staff friendly');

kcmc_update_json_store(KCMC_CONNECTION_INTAKE, ['version'=>1,'submissions'=>[]], function(array &$state): void {
    $state['submissions'] = [
        ['id'=>'connection_a','kind'=>'visit','name'=>'A','email'=>'a@example.com','submitted_at'=>'2026-09-22T20:00:00Z'],
        ['id'=>'connection_b','kind'=>'serve','name'=>'B','email'=>'b@example.com','status'=>'contacted','submitted_at'=>'2026-09-22T20:01:00Z'],
    ];
});
kcmc_update_json_store(KCMC_EVENT_RSVPS, ['version'=>1,'rsvps'=>[]], function(array &$state): void {
    $state['rsvps'] = [
        ['id'=>'rsvp_a','event'=>'Dinner','event_date'=>'2026-10-10','name'=>'C','email'=>'c@example.com','submitted_at'=>'2026-09-22T20:02:00Z'],
    ];
});

$counts = kcmc_inbox_status_counts(kcmc_connection_recent(20));
follow_check($counts === ['new'=>1,'contacted'=>1,'closed'=>0,'total'=>2], 'status counts include legacy New and stored Contacted rows');

$changed = kcmc_connection_update_follow_up('connection_a', 'closed', 2000000000);
follow_check(!empty($changed['updated']) && $changed['previous'] === 'new' && $changed['current'] === 'closed', 'connection request moves from legacy New to Closed');
$connectionState = kcmc_read_json_store(KCMC_CONNECTION_INTAKE, ['submissions'=>[]]);
$connectionA = $connectionState['submissions'][0] ?? [];
follow_check(($connectionA['status'] ?? '') === 'closed', 'connection follow-up status persists atomically');
follow_check(($connectionA['status_updated_at'] ?? '') === gmdate('c', 2000000000), 'connection status change records server timestamp');
follow_check(($connectionA['email'] ?? '') === 'a@example.com', 'connection contact data is preserved during status change');

$same = kcmc_connection_update_follow_up('connection_a', 'closed', 2000000100);
follow_check(empty($same['updated']) && $same['current'] === 'closed', 'saving the current connection status is idempotent');
$invalid = kcmc_connection_update_follow_up('connection_a', 'deleted', 2000000200);
follow_check(empty($invalid['updated']), 'invalid follow-up status is rejected');
$missing = kcmc_connection_update_follow_up('missing', 'contacted', 2000000200);
follow_check(empty($missing['updated']), 'missing connection row is not created by status update');

$rsvpChanged = kcmc_event_rsvp_update_follow_up('rsvp_a', 'contacted', 2000000300);
follow_check(!empty($rsvpChanged['updated']) && $rsvpChanged['previous'] === 'new' && $rsvpChanged['current'] === 'contacted', 'RSVP moves from legacy New to Contacted');
$rsvpState = kcmc_read_json_store(KCMC_EVENT_RSVPS, ['rsvps'=>[]]);
follow_check(($rsvpState['rsvps'][0]['status'] ?? '') === 'contacted', 'RSVP follow-up status persists atomically');
follow_check(($rsvpState['rsvps'][0]['email'] ?? '') === 'c@example.com', 'RSVP attendee data is preserved during status change');

$connectionsPage = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/connections.php');
follow_check(is_string($connectionsPage) && str_contains($connectionsPage, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'connection inbox remains administrator-only');
follow_check(str_contains((string)$connectionsPage, 'kcmc_private_headers()'), 'connection inbox remains private/no-store');
follow_check(str_contains((string)$connectionsPage, 'kcmc_verify_csrf'), 'connection follow-up updates require CSRF validation');
follow_check(str_contains((string)$connectionsPage, 'KCMC_INBOX_STATUSES'), 'connection inbox constrains follow-up choices to allowed states');
follow_check(str_contains((string)$connectionsPage, "connection.follow_up_changed"), 'connection follow-up changes emit audit event');
follow_check(str_contains((string)$connectionsPage, "?status="), 'connection inbox exposes status filters');

$rsvpPage = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/rsvps.php');
follow_check(is_string($rsvpPage) && str_contains($rsvpPage, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'RSVP inbox remains administrator-only');
follow_check(str_contains((string)$rsvpPage, 'kcmc_private_headers()'), 'RSVP inbox remains private/no-store');
follow_check(str_contains((string)$rsvpPage, 'kcmc_verify_csrf'), 'RSVP follow-up updates require CSRF validation');
follow_check(str_contains((string)$rsvpPage, "event_rsvp.follow_up_changed"), 'RSVP follow-up changes emit audit event');
follow_check(str_contains((string)$rsvpPage, "?status="), 'RSVP inbox exposes status filters');

$publishingDesk = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/index.php');
follow_check(is_string($publishingDesk) && str_contains($publishingDesk, "admin/connections.php"), 'Publishing Desk links directly to the connection inbox');
follow_check(str_contains((string)$publishingDesk, "admin/rsvps.php"), 'Publishing Desk retains direct RSVP inbox navigation');

follow_check(kcmc_audit_event_label('connection.follow_up_changed') === 'Connection follow-up changed', 'audit history labels connection follow-up changes');
follow_check(kcmc_audit_event_label('event_rsvp.follow_up_changed') === 'Event RSVP follow-up changed', 'audit history labels RSVP follow-up changes');
$visible = kcmc_audit_visible_context(['previous_status'=>'new','status'=>'contacted','count'=>1,'email'=>'private@example.com','message'=>'private note','id'=>'secret']);
follow_check(($visible['previous_status'] ?? '') === 'new' && ($visible['status'] ?? '') === 'contacted' && ($visible['count'] ?? '') === '1', 'audit view exposes only operational follow-up fields');
follow_check(!isset($visible['email']) && !isset($visible['message']) && !isset($visible['id']), 'audit view excludes inbox contact details and row identifiers');

foreach (glob($tmp . '/*') ?: [] as $path) @unlink($path);
@rmdir($tmp);
putenv('KCMC_PRIVATE_DATA_DIR');
echo "Inbox follow-up contract checks passed.\n";
