<?php
declare(strict_types=1);
$private = sys_get_temp_dir() . '/kcmc-password-' . bin2hex(random_bytes(5));
putenv('KCMC_PRIVATE_DATA_DIR=' . $private);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/password-lifecycle.php';

function password_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$member = ['id' => 'usr_member', 'email' => 'member@example.com', 'email_normalized' => 'member@example.com', 'display_name' => 'Member One', 'role' => 'member', 'active' => true, 'password_hash' => password_hash('CurrentPassword123!', PASSWORD_DEFAULT)];
$prayer = ['id' => 'usr_prayer', 'email' => 'prayer@example.com', 'display_name' => 'Prayer One', 'role' => 'prayer_team', 'active' => true];
$pastor = ['id' => 'usr_pastor', 'email' => 'pastor@example.com', 'display_name' => 'Pastor One', 'role' => 'pastor_admin', 'active' => true];
$pastor2 = ['id' => 'usr_pastor2', 'email' => 'pastor2@example.com', 'display_name' => 'Pastor Two', 'role' => 'pastor_admin', 'active' => true];
$recovery = ['id' => 'usr_recovery', 'email' => 'recovery@example.com', 'display_name' => 'Recovery One', 'role' => 'recovery_admin', 'active' => true];
$recovery2 = ['id' => 'usr_recovery2', 'email' => 'recovery2@example.com', 'display_name' => 'Recovery Two', 'role' => 'recovery_admin', 'active' => true];
$disabled = ['id' => 'usr_disabled', 'email' => 'disabled@example.com', 'display_name' => 'Disabled', 'role' => 'member', 'active' => false];

password_check(kcmc_can_issue_password_reset($pastor, $member), 'Pastor administrator may reset a Member account');
password_check(kcmc_can_issue_password_reset($pastor, $prayer), 'Pastor administrator may reset a Prayer team account');
password_check(!kcmc_can_issue_password_reset($pastor, $pastor2), 'Pastor administrator cannot reset another Pastor administrator');
password_check(!kcmc_can_issue_password_reset($pastor, $recovery), 'Pastor administrator cannot reset a Recovery administrator');
password_check(!kcmc_can_issue_password_reset($pastor, $pastor), 'administrator cannot issue a reset for their own account');
password_check(kcmc_can_issue_password_reset($recovery, $pastor), 'Recovery administrator may reset a Pastor administrator');
password_check(kcmc_can_issue_password_reset($recovery, $recovery2), 'Recovery administrator may reset another Recovery administrator');
password_check(!kcmc_can_issue_password_reset($recovery, $recovery), 'Recovery administrator uses Account Security for their own password');
password_check(!kcmc_can_issue_password_reset($recovery, $disabled), 'disabled accounts cannot receive password resets');

password_check(kcmc_password_policy_error('short', 'short') !== '', 'password policy rejects fewer than 12 characters');
password_check(kcmc_password_policy_error('LongEnoughPassword1!', 'DifferentPassword1!') !== '', 'password policy rejects confirmation mismatch');
password_check(kcmc_password_policy_error('CurrentPassword123!', 'CurrentPassword123!', (string)$member['password_hash']) !== '', 'password policy rejects current-password reuse');
password_check(kcmc_password_policy_error('DifferentPassword456!', 'DifferentPassword456!', (string)$member['password_hash']) === '', 'password policy accepts a distinct matching 12+ character password');

$now = 1790111000;
$first = kcmc_create_password_reset($member, (string)$pastor['id'], $now);
password_check(is_array($first) && preg_match('/\A[a-f0-9]{64}\z/', (string)$first['token']) === 1, 'reset creation returns a cryptographically random one-time token');
$storeRaw = file_get_contents(KCMC_PASSWORD_RESETS);
password_check(is_string($storeRaw) && !str_contains($storeRaw, (string)$first['token']), 'raw reset token is never stored');
password_check(str_contains((string)$storeRaw, hash('sha256', (string)$first['token'])), 'only reset token hash is stored');
password_check(kcmc_find_password_reset((string)$first['token'], $now + 1) !== null, 'fresh reset token resolves');
password_check(kcmc_find_password_reset((string)$first['token'], $now + KCMC_PASSWORD_RESET_TTL) === null, 'reset expires after one hour');
password_check(kcmc_find_password_reset(str_repeat('0', 64), $now + 1) === null, 'wrong reset token fails closed');

$second = kcmc_create_password_reset($member, (string)$pastor['id'], $now + 10);
password_check(is_array($second), 'replacement reset token is created');
password_check(kcmc_find_password_reset((string)$first['token'], $now + 11) === null, 'new reset supersedes older unused reset for the same user');
password_check(kcmc_find_password_reset((string)$second['token'], $now + 11) !== null, 'newest reset remains active');
$claimed = kcmc_claim_password_reset((string)$second['token'], $now + 20);
password_check(is_array($claimed) && ($claimed['user_id'] ?? '') === $member['id'], 'valid reset can be claimed once');
password_check(kcmc_claim_password_reset((string)$second['token'], $now + 21) === null, 'claimed reset cannot be reused');
password_check(kcmc_find_password_reset((string)$second['token'], $now + 21) === null, 'claimed reset is no longer discoverable');

$third = kcmc_create_password_reset($member, (string)$pastor['id'], $now + 30);
password_check(is_array($third), 'another reset can be created after a completed reset');
password_check(kcmc_revoke_password_resets_for_user((string)$member['id'], 'password_changed') === 1, 'password change revokes the remaining unused reset');
password_check(kcmc_find_password_reset((string)$third['token'], $now + 31) === null, 'revoked reset is unusable');

$link = 'https://example.com/kcmc-connect/member/reset-password.php?token=' . str_repeat('a', 64);
$delivery = kcmc_password_reset_delivery($member, $link);
password_check(is_array($delivery) && ($delivery['email'] ?? '') === 'member@example.com', 'reset delivery is bound to the account email');
password_check(str_contains((string)($delivery['message'] ?? ''), $link), 'reset delivery contains the exact one-time link');
password_check(!str_contains(strtolower((string)($delivery['message'] ?? '')), 'your password is'), 'reset delivery never transmits a password');
password_check(kcmc_password_reset_delivery($member, 'http://example.com/reset') === null, 'reset email refuses a non-HTTPS link');

$changePage = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/password.php');
password_check(is_string($changePage) && str_contains($changePage, 'kcmc_require_login()'), 'password change requires a signed-in account');
password_check(str_contains((string)$changePage, 'password_verify($currentPassword'), 'password change re-verifies the current password');
password_check(str_contains((string)$changePage, 'kcmc_verify_csrf'), 'password change requires CSRF validation');
password_check(str_contains((string)$changePage, 'session_regenerate_id(true)'), 'password change rotates the session identifier');
password_check(str_contains((string)$changePage, 'kcmc_revoke_password_resets_for_user'), 'password change invalidates outstanding reset links');

$resetPage = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/reset-password.php');
password_check(is_string($resetPage) && str_contains($resetPage, 'kcmc_claim_password_reset'), 'reset endpoint atomically claims the one-time token');
password_check(str_contains((string)$resetPage, 'password_hash($password, PASSWORD_DEFAULT)'), 'reset endpoint hashes the replacement password');
password_check(str_contains((string)$resetPage, 'kcmc_clear_login_failures'), 'successful reset clears sign-in lock failures');
password_check(str_contains((string)$resetPage, "member/login.php?reset=1"), 'successful reset returns the user to normal sign-in');

$adminPage = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/password-resets.php');
password_check(is_string($adminPage) && str_contains($adminPage, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'reset console requires administrator role');
password_check(str_contains((string)$adminPage, 'kcmc_can_issue_password_reset'), 'reset console enforces role hierarchy');
password_check(str_contains((string)$adminPage, 'kcmc_send_invitation_email'), 'reset console can use configured server mail transport');
password_check(!preg_match('/password_hash|current_password|new_password/', (string)$adminPage), 'administrator reset console never handles account passwords');

$memberHome = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/index.php');
password_check(is_string($memberHome) && str_contains($memberHome, 'member/password.php') && str_contains($memberHome, 'admin/password-resets.php'), 'member home links account security and administrator reset console');

$login = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/login.php');
password_check(is_string($login) && str_contains($login, 'Forgot your password?') && str_contains($login, "isset(\$_GET['reset'])"), 'sign-in explains password recovery and reset completion');

@unlink(KCMC_PASSWORD_RESETS);
@unlink(KCMC_PASSWORD_RESETS . '.lock');
@rmdir($private);
echo "Password lifecycle contract checks passed.\n";
