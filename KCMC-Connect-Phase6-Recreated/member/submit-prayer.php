<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_role(['member', 'prayer_team', 'pastor_admin']);
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !kcmc_verify_csrf($_POST['csrf'] ?? null)) {
    http_response_code(403);
    exit('Invalid request.');
}
$message = trim((string)($_POST['message'] ?? ''));
if (kcmc_text_length($message) < 10 || kcmc_text_length($message) > 2000) {
    http_response_code(422);
    exit('Prayer requests must be between 10 and 2,000 characters.');
}
$shareWithMembers = (string)($_POST['share_with_members'] ?? '') === '1';
$display = (string)($_POST['name_display'] ?? '') === 'first_name' ? 'first_name' : 'anonymous';
$publicName = 'Anonymous';
if ($display === 'first_name') $publicName = trim(explode(' ', (string)$user['display_name'])[0]);
$prayer = [
    'id' => kcmc_random_id('prayer'),
    'submitted_by' => (string)$user['id'],
    'message' => $message,
    'public_name' => $publicName,
    'audience' => $shareWithMembers ? 'members' : 'pastors_only',
    'status' => $shareWithMembers ? 'pending' : 'private',
    'created_at' => gmdate('c'),
    'updated_at' => gmdate('c'),
    'approved_at' => null,
    'approved_by' => null,
];
kcmc_update_json_store(KCMC_PRAYERS, ['version' => 1, 'prayers' => []], function (array &$state) use ($prayer): void {
    $state['prayers'][] = $prayer;
});
kcmc_audit('prayer.submitted', ['prayer_id' => $prayer['id'], 'audience' => $prayer['audience']]);
header('Location: ' . kcmc_url('member/?submitted=1'));
