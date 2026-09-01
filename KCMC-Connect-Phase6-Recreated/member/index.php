<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_login();
$prayerAccess = kcmc_has_role(['member', 'prayer_team', 'pastor_admin'], $user);
$allPrayers = [];
if ($prayerAccess) {
    $store = kcmc_read_json_store(KCMC_PRAYERS, ['version' => 1, 'prayers' => []]);
    $allPrayers = array_values(array_filter($store['prayers'] ?? [], 'is_array'));
}
$memberWall = array_values(array_filter($allPrayers, fn(array $prayer): bool => ($prayer['status'] ?? '') === 'approved' && ($prayer['audience'] ?? '') === 'members'));
usort($memberWall, fn($a, $b) => strcmp((string)($b['created_at'] ?? ''), (string)($a['created_at'] ?? '')));
$myRequests = array_values(array_filter($allPrayers, fn(array $prayer): bool => ($prayer['submitted_by'] ?? '') === ($user['id'] ?? '')));
usort($myRequests, fn($a, $b) => strcmp((string)($b['created_at'] ?? ''), (string)($a['created_at'] ?? '')));
$firstName = trim(explode(' ', (string)$user['display_name'])[0]);
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Member Prayer • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell">
  <header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url())?>">← KCMC Connect</a><p class="eyebrow">VERIFIED MEMBER AREA</p><h1>Welcome, <?=kcmc_h($firstName)?>.</h1><p class="portal-lead">Prayer stays inside the KCMC family and under pastoral care.</p></div><nav class="portal-actions">
    <?php if (kcmc_can_publish($user)): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/'))?>">Publishing</a><?php endif; ?>
    <?php if (kcmc_can_manage_users($user)): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>">Members</a><?php endif; ?>
    <?php if (kcmc_can_view_private_prayers($user)): ?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/prayer-team.php'))?>">Prayer team</a><?php endif; ?>
    <a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/logout.php'))?>">Sign out</a>
  </nav></header>
  <?php if (!$prayerAccess): ?>
  <section class="portal-card portal-section"><p class="eyebrow">RECOVERY ACCESS</p><h2>Prayer content is intentionally unavailable.</h2><p>This account can maintain member access and publish public church information, but it cannot read, submit or moderate prayer requests.</p><div class="portal-actions"><a class="btn gold" href="<?=kcmc_h(kcmc_url('admin/users.php'))?>">Manage member access</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/'))?>">Open publishing</a></div></section>
  <?php else: ?>
  <?php if (isset($_GET['submitted'])): ?><p class="portal-alert success">Your request was received securely.</p><?php endif; ?>
  <div class="portal-grid">
    <section class="portal-card"><p class="eyebrow">REQUEST PRAYER</p><h2>How can we pray?</h2><p>Pastors and the prayer team can receive your request privately. Sharing with members is optional and always requires pastoral approval.</p>
      <form class="portal-form" method="post" action="<?=kcmc_h(kcmc_url('member/submit-prayer.php'))?>">
        <input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>">
        <label>Prayer or care request<textarea name="message" rows="7" minlength="10" maxlength="2000" required></textarea></label>
        <label>How should your name appear?<select name="name_display"><option value="anonymous">Anonymous</option><option value="first_name">Use my first name</option></select></label>
        <label class="portal-check"><input type="checkbox" name="share_with_members" value="1"><span>After Tony or Barry approves it, share this request on the members-only prayer wall.</span></label>
        <button class="btn gold" type="submit">Send private request</button>
      </form>
    </section>
    <section class="portal-card"><p class="eyebrow">MEMBERS-ONLY PRAYER WALL</p><h2>Pray with KCMC.</h2>
      <?php if (!$memberWall): ?><p class="portal-empty">No member-shared requests are currently published.</p><?php endif; ?>
      <div class="prayer-list"><?php foreach ($memberWall as $prayer): ?><article class="prayer-card">
        <div class="prayer-meta"><strong><?=kcmc_h((string)($prayer['public_name'] ?? 'Anonymous'))?></strong><time datetime="<?=kcmc_h((string)($prayer['created_at'] ?? ''))?>"><?=kcmc_h(date('M j', strtotime((string)$prayer['created_at'])))?></time></div>
        <p><?=nl2br(kcmc_h((string)($prayer['message'] ?? '')))?></p>
      </article><?php endforeach; ?></div>
    </section>
  </div>
  <section class="portal-card portal-section"><p class="eyebrow">MY REQUESTS</p><h2>Your recent submissions</h2>
    <?php if (!$myRequests): ?><p class="portal-empty">You have not submitted a prayer request.</p><?php endif; ?>
    <div class="request-status-list"><?php foreach (array_slice($myRequests, 0, 10) as $request): ?><div><span><?=kcmc_h(date('M j, Y', strtotime((string)$request['created_at'])))?></span><strong><?=kcmc_h(ucwords(str_replace('_', ' ', (string)($request['status'] ?? 'received'))))?></strong><small><?=($request['audience'] ?? '') === 'members' ? 'Requested for member sharing' : 'Pastors and prayer team only'?></small></div><?php endforeach; ?></div>
  </section>
  <?php endif; ?>
</main></body></html>
