<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_role(['prayer_team', 'pastor_admin', 'recovery_admin']);
$publisher = kcmc_can_publish($user);
$owner = kcmc_is_designated_owner($user);
$tools = [];
if ($publisher) {
    $tools[] = ['admin/', 'Publishing', 'Manage approved church announcements, events and publications.'];
    $tools[] = ['admin/users.php', 'Member access', 'Manage invitations and account access.'];
    $tools[] = ['admin/password-resets.php', 'Password resets', 'Issue one-time reset links when permitted.'];
    $tools[] = ['admin/rsvps.php', 'Event RSVPs', 'Review event responses.'];
    $tools[] = ['admin/connections.php', 'Connections', 'Review requests to connect with KCMC.'];
}
if (kcmc_can_view_private_prayers($user)) $tools[] = ['admin/prayer-inbox.php', 'Confidential prayer inbox', 'Read requests within your existing prayer ministry access.'];
if (kcmc_can_moderate_prayers($user)) {
    $tools[] = ['admin/prayers.php', 'Member prayer approvals', 'Review requests for the existing member prayer wall.'];
    $tools[] = ['admin/prayer-care.php', 'Prayer & Care review', 'Review prayer-warrior signups and requested sharing.'];
}
if ($owner) {
    $tools[] = ['admin/timecards.php', 'Employee time cards', 'Review periods, corrections and time totals.'];
    $tools[] = ['admin/push.php', 'Broadcast updates', 'Test this device and send church updates.'];
    $tools[] = ['admin/operations.php', 'Operations', 'Release checks, audit history, backups and recovery.'];
}
$title = $publisher ? 'Administration' : 'Ministry work';
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title><?=kcmc_h($title)?> • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.admin-home{max-width:1040px}.admin-home h1{font-size:clamp(2.2rem,6vw,4.5rem)}.admin-tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.admin-tool h2{font-size:1.7rem}.admin-tool p{line-height:1.55}.admin-home :is(a,button):focus-visible{outline:3px solid #e3b958;outline-offset:4px}@media(max-width:640px){.admin-tools{grid-template-columns:1fr}.admin-home .portal-top{display:block}}
</style></head><body class="portal-body"><main class="portal-shell admin-home"><header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Account home</a><p class="eyebrow">KCMC CONNECT</p><h1><?=kcmc_h($title)?></h1><p class="portal-lead">Your authorized work tools.</p></div><a class="btn secondary" href="<?=kcmc_h(kcmc_url())?>">Home</a></header><div class="admin-tools"><?php foreach ($tools as [$href, $label, $description]): ?><section class="portal-card admin-tool"><h2><?=kcmc_h($label)?></h2><p><?=kcmc_h($description)?></p><a class="btn secondary" href="<?=kcmc_h(kcmc_url($href))?>">Open <?=kcmc_h($label)?></a></section><?php endforeach; ?></div></main></body></html>
