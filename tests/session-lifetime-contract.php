<?php
declare(strict_types=1);
$private = sys_get_temp_dir() . '/kcmc-session-' . bin2hex(random_bytes(5));
putenv('KCMC_PRIVATE_DATA_DIR=' . $private);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/session-lifetime.php';

function session_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

session_check(KCMC_SESSION_IDLE_SECONDS === 1800, 'idle timeout is 30 minutes');
session_check(KCMC_SESSION_ABSOLUTE_SECONDS === 43200, 'absolute session lifetime is 12 hours');
session_check(KCMC_SESSION_REGENERATE_SECONDS === 900, 'session ID rotation interval is 15 minutes');

$now = 2000000000;
$legacy = ['kcmc_user_id' => 'usr_legacy'];
$legacyState = kcmc_session_lifetime_state($legacy, $now);
session_check(($legacyState['status'] ?? '') === 'initialize', 'legacy authenticated session is identified for safe timestamp initialization');
$legacyApplied = kcmc_session_apply_lifetime($legacy, $now);
session_check(($legacyApplied['status'] ?? '') === 'active' && !empty($legacyApplied['initialized']), 'legacy authenticated session is initialized without forced logout');
session_check($legacy['kcmc_auth_started_at'] === $now && $legacy['kcmc_auth_last_activity_at'] === $now && $legacy['kcmc_auth_last_regenerated_at'] === $now, 'legacy session receives all lifetime timestamps');

$active = [
    'kcmc_auth_started_at' => $now - 1000,
    'kcmc_auth_last_activity_at' => $now - 1799,
    'kcmc_auth_last_regenerated_at' => $now - 899,
];
$state = kcmc_session_lifetime_state($active, $now);
session_check(($state['status'] ?? '') === 'active' && empty($state['regenerate']), '29:59 idle and 14:59 rotation age remain active without rotation');

$rotate = $active;
$rotate['kcmc_auth_last_regenerated_at'] = $now - 900;
$rotateState = kcmc_session_lifetime_state($rotate, $now);
session_check(($rotateState['status'] ?? '') === 'active' && !empty($rotateState['regenerate']), '15:00 rotation boundary requests session ID regeneration');
$beforeActivity = $rotate['kcmc_auth_last_activity_at'];
$publicState = kcmc_session_apply_lifetime($rotate, $now, false);
session_check(($publicState['status'] ?? '') === 'active' && empty($publicState['regenerate']), 'public-page session lookup does not request rotation');
session_check($rotate['kcmc_auth_last_activity_at'] === $beforeActivity, 'public-page session lookup does not extend idle lifetime');

$touch = $active;
$touchApplied = kcmc_session_apply_lifetime($touch, $now, true);
session_check(($touchApplied['status'] ?? '') === 'active' && $touch['kcmc_auth_last_activity_at'] === $now, 'authenticated private activity refreshes idle timestamp');

$idle = [
    'kcmc_auth_started_at' => $now - 2000,
    'kcmc_auth_last_activity_at' => $now - 1800,
    'kcmc_auth_last_regenerated_at' => $now - 200,
];
session_check((kcmc_session_lifetime_state($idle, $now)['status'] ?? '') === 'idle_expired', '30:00 idle boundary expires the session');

$absoluteAlmost = [
    'kcmc_auth_started_at' => $now - 43199,
    'kcmc_auth_last_activity_at' => $now - 5,
    'kcmc_auth_last_regenerated_at' => $now - 100,
];
session_check((kcmc_session_lifetime_state($absoluteAlmost, $now)['status'] ?? '') === 'active', '11:59:59 absolute age remains active');
$absolute = $absoluteAlmost;
$absolute['kcmc_auth_started_at'] = $now - 43200;
session_check((kcmc_session_lifetime_state($absolute, $now)['status'] ?? '') === 'absolute_expired', '12:00:00 absolute boundary expires even with recent activity');

$future = $active;
$future['kcmc_auth_last_activity_at'] = $now + 301;
session_check((kcmc_session_lifetime_state($future, $now)['status'] ?? '') === 'invalid_clock', 'implausible future session timestamp fails closed');

$marked = $active;
kcmc_session_mark_regenerated($marked, $now);
session_check($marked['kcmc_auth_last_regenerated_at'] === $now, 'session regeneration timestamp can be synchronized explicitly');

kcmc_session_audit_expiration('usr_test', 'idle_expired', $now);
$auditRaw = @file_get_contents(KCMC_AUDIT_LOG);
session_check(is_string($auditRaw) && str_contains($auditRaw, '"action":"auth.session_expired"'), 'session expiration writes an audit event');
session_check(str_contains((string)$auditRaw, '"actor_id":"usr_test"') && str_contains((string)$auditRaw, '"reason":"idle_expired"'), 'expiration audit records actor and bounded reason');

$bootstrap = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php');
session_check(is_string($bootstrap) && str_contains($bootstrap, 'function kcmc_current_user(bool $recordActivity = true)'), 'central current-user path accepts activity-recording mode');
session_check(str_contains((string)$bootstrap, 'kcmc_session_apply_lifetime($_SESSION, $now, $recordActivity)'), 'central current-user path enforces session lifetime');
session_check(str_contains((string)$bootstrap, 'kcmc_current_user(false)'), 'public optional-session lookup does not refresh authenticated activity');
session_check(str_contains((string)$bootstrap, 'kcmc_session_initialize_auth($_SESSION, time())'), 'successful login initializes authenticated session lifetime');
session_check(str_contains((string)$bootstrap, "\$_SESSION['kcmc_session_expired']"), 'expired-session marker is preserved for sign-in feedback');
session_check(str_contains((string)$bootstrap, "&expired=1"), 'login redirect identifies an expired secure session');

$login = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/login.php');
session_check(is_string($login) && str_contains($login, 'Your secure KCMC session expired. Sign in again to continue.'), 'sign-in page explains session expiration');

$password = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/member/password.php');
session_check(is_string($password) && str_contains($password, 'kcmc_session_mark_regenerated($_SESSION, time())'), 'password-change session rotation synchronizes lifetime state');

$auditHistory = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/audit-history.php');
session_check(is_string($auditHistory) && str_contains($auditHistory, "'auth.session_expired' => 'Secure session expired'"), 'administrator audit history labels session expiration');

@unlink(KCMC_AUDIT_LOG);
@rmdir($private);
echo "Authenticated session lifetime contract checks passed.\n";
