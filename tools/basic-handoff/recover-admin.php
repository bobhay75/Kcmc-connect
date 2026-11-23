<?php
declare(strict_types=1);
// Private hosting-operator tool. Keep outside the application and public_html.
if (PHP_SAPI !== 'cli' || $argc !== 3 || !stream_isatty(STDIN) || !stream_isatty(STDOUT)) {
    exit(1);
}
$root = realpath($argv[1]);
if (!$root || !is_file($root . '/lib/bootstrap.php')) exit(1);
require $root . '/lib/bootstrap.php';
$email = kcmc_normalize_email($argv[2]);
if (!kcmc_valid_email($email) || !is_file(KCMC_USERS)) exit(1);
$password = bin2hex(random_bytes(24));
$changed = kcmc_update_json_store(KCMC_USERS, [], function (array &$state) use ($email, $password): bool {
    $matches = [];
    foreach (($state['users'] ?? []) as $i => $user) {
        if (kcmc_normalize_email($user['email'] ?? '') === $email) $matches[] = $i;
    }
    if (count($matches) !== 1) throw new RuntimeException('Expected one existing administrator.');
    $user = &$state['users'][$matches[0]];
    if (empty($user['active']) || !in_array(kcmc_role($user), ['pastor_admin', 'recovery_admin'], true)) throw new RuntimeException('An active administrator is required.');
    $user['password_hash'] = password_hash($password, PASSWORD_DEFAULT);
    $user['updated_at'] = gmdate('c');
    return true;
});
if (!$changed) exit(1);
kcmc_audit('auth.operator_password_recovery', []);
echo "Replacement password (shown once): ", $password, PHP_EOL;
