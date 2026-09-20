<?php
declare(strict_types=1);

/**
 * Static regression checks for the invitation -> activation -> session boundary.
 *
 * This test intentionally does not create real users or consume real invitation
 * tokens. It protects the security contracts of the production activation flow:
 * CSRF, one-time atomic claim, password minimum, role propagation, session
 * regeneration, and no-referrer handling for token-bearing activation URLs.
 */

$root = dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated';
$activation = file_get_contents($root . '/member/activate.php');
$bootstrap = file_get_contents($root . '/lib/bootstrap.php');

function verify(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: {$message}\n");
        exit(1);
    }
    echo "PASS: {$message}\n";
}

verify(is_string($activation), 'activation endpoint is readable');
verify(is_string($bootstrap), 'bootstrap is readable');

verify(str_contains($activation, 'kcmc_verify_csrf($_POST[\'csrf\'] ?? null)'), 'activation POST requires CSRF validation');
verify(str_contains($activation, 'strlen($password) < 12'), 'activation enforces the 12-character password minimum');
verify(str_contains($activation, 'hash(\'sha256\', $token)'), 'activation hashes the submitted token before lookup');
verify(str_contains($activation, 'hash_equals($storedHash, $tokenHash)'), 'activation compares token hashes with constant-time comparison');
verify(str_contains($activation, 'empty($stored[\'used_at\'])') && str_contains($activation, '$stored[\'used_at\'] = gmdate(\'c\')'), 'activation atomically rejects and marks one-time tokens');
verify(str_contains($activation, '\'role\' => (string)$claimedInvite[\'role\']'), 'activation carries the invitation role onto the account');
verify(str_contains($activation, 'password_hash($password, PASSWORD_DEFAULT)'), 'activation stores only a password hash');
verify(str_contains($activation, 'kcmc_login_user($createdUser)'), 'successful activation establishes the authenticated session');
verify(str_contains($bootstrap, 'session_regenerate_id(true);'), 'login flow regenerates the session identifier');
verify(str_contains($activation, '<meta name="referrer" content="no-referrer">'), 'activation page suppresses referrer leakage of token URLs');
verify(str_contains($activation, 'autocomplete="new-password"'), 'activation password fields use new-password autocomplete semantics');

// Token-bearing URLs must not be placed in ordinary audit context.
verify(str_contains($bootstrap, "preg_match('/(?:password|token|message|body|text|setup_key)/i"), 'audit sanitization suppresses token and password fields');

echo "All invitation activation contract checks passed.\n";
