<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$current = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_session_start();
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } else {
        $action = (string)($_POST['action'] ?? 'invite');
        if ($action === 'invite') {
            $name = trim((string)($_POST['display_name'] ?? ''));
            $email = kcmc_normalize_email((string)($_POST['email'] ?? ''));
            $role = (string)($_POST['role'] ?? 'member');
            $allowed = ['member', 'prayer_team', 'pastor_admin'];
            if (kcmc_role($current) === 'recovery_admin') $allowed[] = 'recovery_admin';
            if (kcmc_text_length($name) < 2) $error = 'Enter the person’s name.';
            elseif (!kcmc_valid_email($email)) $error = 'Enter a valid email address.';
            elseif (!in_array($role, $allowed, true)) $error = 'That role cannot be assigned by this account.';
            elseif (($existing = kcmc_find_user_by_email($email)) && !empty($existing['active'])) $error = 'That email already has an active account.';
            else {
                $token = bin2hex(random_bytes(32));
                $invite = [
                    'id' => kcmc_random_id('invite'),
                    'email' => $email,
                    'display_name' => $name,
                    'role' => $role,
                    'token_hash' => hash('sha256', $token),
                    'created_at' => gmdate('c'),
                    'expires_at' => gmdate('c', time() + 7 * 86400),
                    'created_by' => (string)$current['id'],
                    'used_at' => null,
                ];
                kcmc_update_json_store(KCMC_INVITES, ['version' => 1, 'invites' => []], function (array &$state) use ($invite, $email): void {
                    foreach ($state['invites'] as &$old) if (($old['email'] ?? '') === $email && empty($old['used_at'])) $old['used_at'] = 'superseded';
                    unset($old);
                    $state['invites'][] = $invite;
                });
                $host = preg_match('/^[A-Za-z0-9.-]+(?::\d+)?$/', (string)($_SERVER['HTTP_HOST'] ?? '')) ? (string)$_SERVER['HTTP_HOST'] : 'localhost';
                $scheme = kcmc_is_https() ? 'https' : 'http';
                $_SESSION['invite_link'] = $scheme . '://' . $host . kcmc_url('member/activate.php?token=' . rawurlencode($token));
                $_SESSION['invite_email'] = $email;
                kcmc_audit('member.invited', ['invite_id' => $invite['id'], 'role' => $role]);
                header('Location: ' . kcmc_url('admin/users.php?invited=1'));
                exit;
            }
        } elseif ($action === 'set_active') {
            $targetId = (string)($_POST['user_id'] ?? '');
            $active = (string)($_POST['active'] ?? '') === '1';
            $target = kcmc_find_user_by_id($targetId);
            if (!$target) $error = 'Member account not found.';
            elseif ($targetId === ($current['id'] ?? '')) $error = 'You cannot disable your own account.';
            elseif (kcmc_role($target) === 'recovery_admin' && kcmc_role($current) !== 'recovery_admin') $error = 'Only a recovery administrator can change another recovery account.';
            elseif (kcmc_role($target) === 'pastor_admin' && kcmc_role($current) !== 'recovery_admin') $error = 'Only the recovery administrator can disable a pastor administrator.';
            else {
                kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($targetId, $active): void {
                    foreach ($state['users'] as &$stored) if (($stored['id'] ?? '') === $targetId) { $stored['active'] = $active; $stored['updated_at'] = gmdate('c'); }
                    unset($stored);
                });
                kcmc_audit('member.status_changed', ['user_id' => $targetId, 'active' => $active]);
                $success = $active ? 'Account enabled.' : 'Account disabled.';
            }
        }
    }
}

$inviteLink = (string)($_SESSION['invite_link'] ?? '');
$inviteEmail = (string)($_SESSION['invite_email'] ?? '');
unset($_SESSION['invite_link'], $_SESSION['invite_email']);
$users = kcmc_users();
usort($users, fn($a, $b) => strcmp((string)($a['display_name'] ?? ''), (string)($b['display_name'] ?? '')));
$roleNames = ['member' => 'Member', 'prayer_team' => 'Prayer team', 'pastor_admin' => 'Pastor administrator', 'recovery_admin' => 'Recovery administrator'];
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Member Access • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head><body class="portal-body"><main class="portal-shell">
<header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing desk</a><p class="eyebrow">KCMC ACCESS</p><h1>Members and administrators</h1><p class="portal-lead">Every person receives a separate email login and creates their own password.</p></div><a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/'))?>">Member home</a></header>
<?php if (isset($_GET['setup'])): ?><p class="portal-alert success">Recovery account created. Remove the server setup key now, then invite Tony and Barry.</p><?php endif; ?>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?><?php if ($success): ?><p class="portal-alert success"><?=kcmc_h($success)?></p><?php endif; ?>
<?php if ($inviteLink): ?><section class="portal-card portal-section invite-result"><p class="eyebrow">ONE-TIME INVITATION</p><h2>Send this secure link to <?=kcmc_h($inviteEmail)?>.</h2><p>The link expires in seven days and disappears from this screen after you leave.</p><input value="<?=kcmc_h($inviteLink)?>" readonly onclick="this.select()"><div class="portal-actions"><a class="btn gold" href="mailto:<?=rawurlencode($inviteEmail)?>?subject=<?=rawurlencode('Your KCMC Connect invitation')?>&body=<?=rawurlencode("Use this one-time link to create your KCMC Connect password:\n\n" . $inviteLink)?>">Email invitation</a></div></section><?php endif; ?>
<div class="portal-grid">
<section class="portal-card"><p class="eyebrow">INVITE A PERSON</p><h2>Create their sign-in.</h2><p>Start with Pastor Tony Blevins and Associate Pastor Barry Smith as Pastor administrators.</p><form class="portal-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="invite"><label>Name<input name="display_name" placeholder="Pastor Tony Blevins" required></label><label>Email<input type="email" name="email" required></label><label>Role<select name="role"><option value="member">Member</option><option value="prayer_team">Prayer team</option><option value="pastor_admin">Pastor administrator</option><?php if (kcmc_role($current) === 'recovery_admin'): ?><option value="recovery_admin">Recovery administrator</option><?php endif; ?></select></label><button class="btn gold" type="submit">Create invitation</button></form></section>
<section class="portal-card"><p class="eyebrow">ROLE BOUNDARIES</p><h2>Privacy by design.</h2><ul class="portal-list"><li><strong>Members</strong> submit prayer and see pastor-approved member requests.</li><li><strong>Prayer team</strong> sees confidential requests but cannot publish them.</li><li><strong>Pastor administrators</strong> approve prayer sharing and publish church content.</li><li><strong>Recovery administrators</strong> maintain access and publishing but cannot read private prayer content.</li></ul></section>
</div>
<section class="portal-card portal-section"><p class="eyebrow">ACTIVE DIRECTORY</p><h2>Current accounts</h2><div class="member-table"><div class="member-row header"><span>Name</span><span>Email</span><span>Role</span><span>Status</span><span>Action</span></div><?php foreach ($users as $member): ?><div class="member-row"><span><strong><?=kcmc_h((string)$member['display_name'])?></strong></span><span><?=kcmc_h((string)$member['email'])?></span><span><?=kcmc_h($roleNames[kcmc_role($member)] ?? kcmc_role($member))?></span><span><?=!empty($member['active']) ? 'Active' : 'Disabled'?></span><span><?php if (($member['id'] ?? '') !== ($current['id'] ?? '')): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="set_active"><input type="hidden" name="user_id" value="<?=kcmc_h((string)$member['id'])?>"><input type="hidden" name="active" value="<?=!empty($member['active']) ? '0' : '1'?>"><button class="portal-link-button" type="submit"><?=!empty($member['active']) ? 'Disable' : 'Enable'?></button></form><?php else: ?>Current user<?php endif; ?></span></div><?php endforeach; ?></div></section>
</main></body></html>
