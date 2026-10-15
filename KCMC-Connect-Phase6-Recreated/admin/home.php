<?php
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/payroll.php';
kcmc_private_headers();
$user = kcmc_require_role(['prayer_team', 'pastor_admin', 'recovery_admin']);
$publisher = kcmc_can_publish($user);
$owner = kcmc_is_designated_owner($user);
$groups = ['Work & publishing' => [], 'People & care' => [], 'Operations' => []];
if ($publisher) {
    $groups['Work & publishing'][] = ['member/work.php', 'Team workspace', 'Assignments, dates and task conversations.'];
    $groups['Work & publishing'][] = ['admin/', 'Publishing', 'Announcements, events and publications.'];
    $groups['People & care'][] = ['admin/users.php', 'Member access', 'Invitations and account access.'];
    $groups['People & care'][] = ['admin/password-resets.php', 'Password resets', 'One-time reset links when permitted.'];
    $groups['People & care'][] = ['admin/rsvps.php', 'Event RSVPs', 'Review event responses.'];
    $groups['People & care'][] = ['admin/connections.php', 'Connections', 'Requests to connect with KCMC.'];
}
if (kcmc_can_view_private_prayers($user)) $groups['People & care'][] = ['admin/prayer-inbox.php', 'Confidential prayer inbox', 'Requests within your prayer ministry access.'];
if (kcmc_can_moderate_prayers($user)) {
    $groups['People & care'][] = ['admin/prayers.php', 'Member prayer approvals', 'Review the existing member prayer wall.'];
    $groups['People & care'][] = ['admin/prayer-care.php', 'Prayer & Care review', 'Prayer-warrior signups and requested sharing.'];
}
if (kcmc_can_review_payroll($user)) $groups['Operations'][] = ['admin/timecards.php', 'Employee time cards', 'Periods, corrections and time totals.'];
if ($owner) {
    $groups['Operations'][] = ['admin/payroll-setup.php', 'Payroll setup', 'Choose the reviewer and period-end delivery.'];
    $groups['Work & publishing'][] = ['admin/push.php', 'Broadcast updates', 'Device testing and church updates.'];
    $groups['Operations'][] = ['admin/operations.php', 'Operations', 'Release checks, audit history and recovery.'];
}
$title = $publisher ? 'Administration' : 'Ministry work';
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title><?=kcmc_h($title)?> • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.admin-home{max-width:1120px}.admin-home h1{font-size:clamp(2.2rem,5vw,3.5rem);margin:8px 0}.admin-home .portal-top{margin-bottom:28px}.admin-home .portal-lead{font-size:1.05rem}.admin-tools{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:28px}.admin-group{min-width:0;border-top:2px solid #d8b267;padding-top:14px}.admin-group h2{font-family:inherit;font-size:1.05rem;margin:0 0 8px;color:#e8c57a}.admin-links{display:grid}.admin-link{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;padding:13px 0;border-bottom:1px solid #395465;text-decoration:none;color:#f1f5f7;min-height:44px;box-sizing:border-box;overflow-wrap:anywhere}.admin-link strong{font-size:1rem;line-height:1.45}.admin-link small{grid-column:1;line-height:1.5;color:#bdcbd4;font-size:.88rem}.admin-link>span{grid-column:2;grid-row:1/3;align-self:center;color:#e8c57a}.admin-link:hover strong{text-decoration:underline;text-underline-offset:4px}.admin-home :is(a,button):focus-visible{outline:3px solid #e3b958;outline-offset:4px}@media(max-width:640px){.admin-tools{grid-template-columns:1fr;gap:26px}.admin-home .portal-top{display:block}.admin-home .portal-top>.btn{margin-top:12px}.admin-home h1{font-size:2.5rem}}
</style></head><body class="portal-body"><main class="portal-shell admin-home"><header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Account home</a><p class="eyebrow">KCMC CONNECT</p><h1><?=kcmc_h($title)?></h1><p class="portal-lead">Your authorized work tools.</p></div><a class="btn secondary" href="<?=kcmc_h(kcmc_url())?>">Home</a></header><div class="admin-tools"><?php foreach ($groups as $group => $links): if (!$links) continue; ?><section class="admin-group"><h2><?=kcmc_h($group)?></h2><nav class="admin-links" aria-label="<?=kcmc_h($group)?>"><?php foreach ($links as [$href, $label, $description]): ?><a class="admin-link" href="<?=kcmc_h(kcmc_url($href))?>" aria-label="Open <?=kcmc_h($label)?>"><strong><?=kcmc_h($label)?></strong><small><?=kcmc_h($description)?></small><span aria-hidden="true">→</span></a><?php endforeach; ?></nav></section><?php endforeach; ?></div></main></body></html>
