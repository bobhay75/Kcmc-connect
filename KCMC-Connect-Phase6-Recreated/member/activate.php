<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$token = trim((string)($_GET['token'] ?? $_POST['token'] ?? ''));
$tokenHash = $token !== '' ? hash('sha256', $token) : '';
$invites = kcmc_read_json_store(KCMC_INVITES, ['version' => 1, 'invites' => []]);
$invite = null;
foreach (($invites['invites'] ?? []) as $candidate) {
    $candidateHash = (string)($candidate['token_hash'] ?? '');
    if ($tokenHash !== '' && strlen($candidateHash) === strlen($tokenHash) && hash_equals($candidateHash, $tokenHash) && empty($candidate['used_at']) && strtotime((string)($candidate['expires_at'] ?? '')) > time()) {
        $invite = $candidate;
        break;
    }
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $invite) {
    $password = (string)($_POST['password'] ?? '');
    $confirm = (string)($_POST['confirm'] ?? '');
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) $error = 'Please reload and try again.';
    elseif (strlen($password) < 12) $error = 'Use at least 12 characters.';
    elseif ($password !== $confirm) $error = 'Passwords do not match.';
    else {
        $claimedInvite = kcmc_update_json_store(KCMC_INVITES, ['version' => 1, 'invites' => []], function (array &$state) use ($tokenHash): ?array {
            foreach ($state['invites'] as &$stored) {
                $storedHash = (string)($stored['token_hash'] ?? '');
                if (strlen($storedHash) !== strlen($tokenHash) || !hash_equals($storedHash, $tokenHash)) continue;
                if (!empty($stored['used_at']) || strtotime((string)($stored['expires_at'] ?? '')) <= time()) return null;
                $stored['used_at'] = gmdate('c');
                $claimed = $stored;
                unset($stored);
                return $claimed;
            }
            unset($stored);
            return null;
        });
        if (!$claimedInvite) {
            $invite = null;
            $error = 'This invitation was already used or has expired.';
        } else {
        $createdUser = kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($claimedInvite, $password): array {
            $normalized = kcmc_normalize_email((string)$claimedInvite['email']);
            foreach ($state['users'] as &$existing) {
                if (($existing['email_normalized'] ?? '') === $normalized) {
                    $existing['display_name'] = (string)$claimedInvite['display_name'];
                    $existing['role'] = (string)$claimedInvite['role'];
                    $existing['password_hash'] = password_hash($password, PASSWORD_DEFAULT);
                    $existing['active'] = true;
                    $existing['updated_at'] = gmdate('c');
                    return $existing;
                }
            }
            unset($existing);
            $user = [
                'id' => kcmc_random_id('usr'),
                'email' => (string)$claimedInvite['email'],
                'email_normalized' => $normalized,
                'display_name' => (string)$claimedInvite['display_name'],
                'role' => (string)$claimedInvite['role'],
                'password_hash' => password_hash($password, PASSWORD_DEFAULT),
                'active' => true,
                'created_at' => gmdate('c'),
                'updated_at' => gmdate('c'),
                'last_login_at' => null,
            ];
            $state['users'][] = $user;
            return $user;
        });
        kcmc_login_user($createdUser);
        kcmc_audit('auth.invite_activated', ['role' => kcmc_role($createdUser)]);
        header('Location: ' . kcmc_url('member/'));
        exit;
        }
    }
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Create Password • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow"><a class="portal-back" href="<?=kcmc_h(kcmc_url())?>">← KCMC Connect</a><section class="portal-card">
<?php if (!$invite): ?>
  <p class="eyebrow">INVITATION EXPIRED</p><h1>This link is no longer valid.</h1><p>Ask Tony, Barry or the KCMC system administrator for a new invitation.</p>
<?php else: ?>
  <p class="eyebrow">WELCOME TO KCMC CONNECT</p><h1>Create your password.</h1><p class="portal-lead">This one-time link is for <?=kcmc_h((string)$invite['display_name'])?>.</p>
  <?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
  <form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="token" value="<?=kcmc_h($token)?>">
  <label>New password <span class="portal-fine">(at least 12 characters)</span><input type="password" name="password" autocomplete="new-password" minlength="12" required autofocus></label>
  <label>Confirm password<input type="password" name="confirm" autocomplete="new-password" minlength="12" required></label>
  <button class="btn gold" type="submit">Create password</button></form>
<?php endif; ?>
</section></main></body></html>
