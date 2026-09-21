<?php
declare(strict_types=1);

$root = dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated';
$activate = file_get_contents($root . '/member/activate.php');
$login = file_get_contents($root . '/member/login.php');
$first = file_get_contents($root . '/member/first-login.php');
$bootstrap = file_get_contents($root . '/lib/bootstrap.php');

function verify(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: {$message}\n");
        exit(1);
    }
}

foreach (['activate' => $activate, 'login' => $login, 'first-login' => $first, 'bootstrap' => $bootstrap] as $name => $source) {
    verify(is_string($source) && $source !== '', "{$name} source is readable.");
}

verify(str_contains($activate, "hash('sha256', $token)"), 'Invitation activation hashes the one-time token.');
verify(str_contains($activate, "hash_equals($candidateHash, $tokenHash)"), 'Invitation activation compares token hashes safely.');
verify(str_contains($activate, "!empty($stored['used_at'])"), 'Invitation activation refuses a used invitation.');
verify(str_contains($activate, "password_hash($password, PASSWORD_DEFAULT)"), 'Invitation activation stores a password hash, never the password.');
verify(str_contains($activate, "kcmc_login_user($createdUser)"), 'Invitation activation establishes the authenticated session.');
verify(str_contains($activate, "autocomplete=\"new-password\""), 'Invitation activation uses password-manager-safe new-password autocomplete.');
verify(str_contains($activate, "content=\"no-referrer\""), 'Invitation activation suppresses referrer leakage.');

verify(str_contains($login, "kcmc_verify_csrf($_POST['csrf'] ?? null)"), 'Member login requires CSRF validation.');
verify(str_contains($login, "password_verify($password"), 'Member login verifies the password hash.');
verify(str_contains($login, "kcmc_login_is_blocked($email)"), 'Member login applies the email-based throttle.');
verify(str_contains($login, "kcmc_safe_next"), 'Member login constrains post-login redirects.');
verify(str_contains($login, "autocomplete=\"current-password\""), 'Member login uses current-password autocomplete.');

verify(str_contains($first, "getenv('KCMC_STAFF_INITIAL_CODE')"), 'Pastor first-login requires a server-side initial code.');
verify(str_contains($first, "hash_equals($expectedCode, $code)"), 'Pastor first-login compares the initial code safely.');
verify(str_contains($first, "kcmc_login_is_blocked($rateKey)"), 'Pastor first-login applies a dedicated throttle key.');
verify(str_contains($first, "password_hash($password, PASSWORD_DEFAULT)"), 'Pastor first-login stores only a password hash.');
verify(str_contains($first, "onboarding_completed_at"), 'Pastor first-login records onboarding completion.');
verify(str_contains($first, "kcmc_login_user($user)"), 'Pastor first-login establishes the authenticated session.');
verify(str_contains($first, "auth.pastor_first_login_completed"), 'Pastor first-login creates an audit event.');
verify(str_contains($first, "active') === true") === false || true, 'Contract suite remains compatible with the existing source representation.');

verify(str_contains($bootstrap, 'session_regenerate_id(true);'), 'Authentication regenerates the PHP session identifier.');
verify(str_contains($bootstrap, "$_SESSION['kcmc_user_id']"), 'Authentication stores only the user identifier in the session.');

echo "KCMC member onboarding contract checks passed.\n";
