<?php
declare(strict_types=1);
ob_start();
$private = sys_get_temp_dir() . '/kcmc-session-credential-' . bin2hex(random_bytes(5));
mkdir($private, 0700);
mkdir($private . '/sessions', 0700);
ini_set('session.save_path', $private . '/sessions');
putenv('KCMC_PRIVATE_DATA_DIR=' . $private);
$_SERVER['SCRIPT_NAME'] = '/kcmc-connect/member/index.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/session-lifetime.php';
register_shutdown_function(function () use ($private): void {
    if (session_status() === PHP_SESSION_ACTIVE) session_write_close();
    foreach (glob($private . '/sessions/*') ?: [] as $file) unlink($file);
    foreach (glob($private . '/*') ?: [] as $file) if (is_file($file)) unlink($file);
    rmdir($private . '/sessions');
    rmdir($private);
});
function credential_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}
$user = ['id' => 'synthetic_owner', 'role' => 'pastor_admin', 'active' => true, 'password_hash' => password_hash('Synthetic credential original 2031!', PASSWORD_DEFAULT)];
putenv('KCMC_OPERATIONS_OWNER_USER_ID=synthetic_owner');
$before = $user;
kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($user): void { $state['users'] = [$user]; });

$binding = [];
kcmc_session_bind_credentials($binding, $user);
credential_check(kcmc_session_credentials_match($binding, $user), 'fresh credential binding validates');
credential_check(!str_contains(json_encode($binding), $user['password_hash']), 'session binding contains no stored password hash');
$otherBinding = [];
kcmc_session_bind_credentials($otherBinding, $user);
credential_check($binding !== $otherBinding, 'independent sessions use distinct random bindings');
$replacement = $user;
$replacement['password_hash'] = password_hash('Synthetic credential replacement 2031!', PASSWORD_DEFAULT);
credential_check(!kcmc_session_credentials_match($binding, $replacement), 'a changed password hash revokes the previous binding');
$another = $user;
$another['id'] = 'synthetic_other';
credential_check(!kcmc_session_credentials_match($binding, $another), 'credential binding cannot transfer to another account');
credential_check(!kcmc_session_credentials_match([], $user), 'legacy missing binding requires fresh authentication');
foreach ([null, [], 12, '', 'not-a-hash'] as $bad) {
    $malformed = $user;
    $malformed['password_hash'] = $bad;
    credential_check(!kcmc_session_credentials_match($binding, $malformed), 'malformed stored credential fails closed');
}
foreach (['kcmc_auth_credential_nonce', 'kcmc_auth_credential_tag'] as $key) {
    foreach ([null, [], 12, '', str_repeat('f', 64), str_repeat('a', 65)] as $bad) {
        $malformed = $binding;
        $malformed[$key] = $bad;
        credential_check(!kcmc_session_credentials_match($malformed, $user), 'malformed or tampered session binding fails closed');
    }
}

kcmc_login_user($user);
$session = $_SESSION;
credential_check(kcmc_current_user() === $user, 'central successful login creates a usable credential-bound session');
credential_check(kcmc_is_designated_owner(kcmc_current_user()) && kcmc_can_publish() && kcmc_can_manage_users(), 'designated owner authority is preserved');
$session['kcmc_auth_started_at'] = time() - 1000;
$session['kcmc_auth_last_activity_at'] = time() - 100;
$session['kcmc_auth_last_regenerated_at'] = time() - 100;
$_SESSION = $session;
credential_check(kcmc_current_user(false) !== null && $_SESSION['kcmc_auth_last_activity_at'] === $session['kcmc_auth_last_activity_at'], 'public optional lookup checks credentials without extending idle lifetime');
credential_check($_SESSION['kcmc_auth_started_at'] === $session['kcmc_auth_started_at'], 'credential validation retains original absolute expiry');
$legacy = $session;
unset($legacy['kcmc_auth_credential_nonce'], $legacy['kcmc_auth_credential_tag']);
foreach ([true, false] as $activity) {
    $_SESSION = $legacy;
    credential_check(kcmc_current_user($activity) === null && !isset($_SESSION['kcmc_user_id']), 'central legacy session cannot silently acquire a credential binding');
}
kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($replacement): void { $state['users'] = [$replacement]; });
foreach ([true, false] as $activity) {
    $_SESSION = $session;
    $oldCsrf = $_SESSION['csrf'];
    $oldId = session_id();
    credential_check(kcmc_current_user($activity) === null, 'central lookup rejects a session authenticated before the credential changed');
    credential_check(!isset($_SESSION['kcmc_user_id']) && !isset($_SESSION['kcmc_auth_credential_tag']), 'revocation clears authenticated state and old credential binding');
    credential_check($_SESSION['csrf'] !== $oldCsrf && session_id() !== $oldId, 'revocation rotates session ID and CSRF');
    credential_check(($_SESSION['kcmc_session_expired'] ?? '') === 'credentials_changed', 'revocation retains a bounded sign-in feedback reason');
}
kcmc_login_user($replacement);
credential_check(kcmc_current_user() === $replacement, 'fresh authentication after password replacement restores access');
$aged = $_SESSION;
$aged['kcmc_auth_started_at'] = time() - KCMC_SESSION_ABSOLUTE_SECONDS;
$_SESSION = $aged;
credential_check(kcmc_current_user() === null && ($_SESSION['kcmc_session_expired'] ?? '') === 'absolute_expired', 'credential binding cannot bypass absolute expiry');
kcmc_login_user($replacement);
$_SESSION['kcmc_auth_last_activity_at'] = time() - KCMC_SESSION_IDLE_SECONDS;
credential_check(kcmc_current_user() === null && ($_SESSION['kcmc_session_expired'] ?? '') === 'idle_expired', 'credential binding cannot bypass idle expiry');
$stored = kcmc_find_user_by_id('synthetic_owner');
credential_check($stored === $replacement, 'session verification does not rewrite account schema or authority');
$audit = file_get_contents(KCMC_AUDIT_LOG);
credential_check(str_contains($audit, '"reason":"credentials_changed"') && !str_contains($audit, $before['password_hash']) && !str_contains($audit, $replacement['password_hash']) && !str_contains($audit, $binding['kcmc_auth_credential_nonce']) && !str_contains($audit, $binding['kcmc_auth_credential_tag']), 'audit records only a bounded reason and no credential or binding secret');
echo "Session credential contract checks passed.\n";
