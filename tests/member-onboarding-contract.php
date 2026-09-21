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

verify(str_contains($activate, 'hash(\'sha256\', $token)'), 'Invitation activation hashes the one-time token.');
verify(str_contains($activate, 'hash_equals($candidateHash, $tokenHash)'), 'Invitation activation compares token hashes safely.');
verify(str_contains($activate, "!empty(\$stored['used_at'])"), 'Invitation activation refuses a used invitation.');
verify(str_contains($activate, 'password_hash($password, PASSWORD_DEFAULT)'), 'Invitation activation stores a password hash, never the password.');
verify(str_contains($activate, 'kcmc_login_user($createdUser)'), 'Invitation activation establishes the authenticated session.');
verify(str_contains($activate, 'autocomplete="new-password"'), 'Invitation activation uses password-manager-safe new-password autocomplete.');
verify(str_contains($activate, 'content="no-referrer"'), 'Invitation activation suppresses referrer leakage.');

verify(str_contains($login, "kcmc_verify_csrf(\$_POST['csrf'] ?? null)"), 'Member login requires CSRF validation.');
verify(str_contains($login, 'password_verify($password'), 'Member login verifies the password hash.');
verify(str_contains($login, 'kcmc_login_is_blocked($email)'), 'Member login applies the email-based throttle.');
verify(str_contains($login, 'kcmc_safe_next'), 'Member login constrains post-login redirects.');
verify(str_contains($login, 'autocomplete="current-password"'), 'Member login uses current-password autocomplete.');

verify(str_contains($first, 'http_response_code(410);'), 'Legacy pastor first-login route is permanently retired.');
verify(!str_contains($first, "KCMC_STAFF_INITIAL_CODE"), 'Legacy shared pastor code is not accepted.');
verify(!str_contains($first, '<form'), 'Retired first-login route exposes no account-creation form.');
verify(str_contains($first, 'recipient-bound, one-time invitation'), 'Retired first-login route directs pastors to recipient-bound invitations.');
verify(!str_contains($login, 'member/first-login.php'), 'Member login no longer links to the legacy shared-code route.');
verify(str_contains($login, 'recipient-bound, one-time invitation'), 'Member login directs all new accounts to the invitation workflow.');

verify(str_contains($bootstrap, 'session_regenerate_id(true);'), 'Authentication regenerates the PHP session identifier.');
verify(str_contains($bootstrap, "\$_SESSION['kcmc_user_id']"), 'Authentication stores only the user identifier in the session.');

echo "KCMC member onboarding contract checks passed.\n";
