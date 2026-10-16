<?php
require_once __DIR__ . '/../lib/prayer-care.php';
require_once __DIR__ . '/../lib/screen-navigation.php';
kcmc_private_headers();
$user = kcmc_require_role(KCMC_CARE_ROLES);
$leader = kcmc_care_leader($user);
$careAdmin = defined('KCMC_CARE_ADMIN_PAGE') && KCMC_CARE_ADMIN_PAGE === true;
if ($careAdmin && !$leader) { kcmc_screen_error('Access denied.', 403); }
$carePath = $careAdmin ? 'admin/prayer-care.php' : 'member/prayer-care.php';
$view = is_string($_GET['view'] ?? null) ? $_GET['view'] : ($careAdmin ? 'review' : 'needs');
if (!in_array($view, ['needs','praise','mine','review'], true)) $view = 'needs';
if ($view === 'review' && !$leader) { kcmc_screen_error('Access denied.', 403); }
if (!$careAdmin && $view === 'review' && ($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
    header('Location: ' . kcmc_url('admin/prayer-care.php?view=review'), true, 303);
    exit;
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf(is_string($_POST['csrf'] ?? null) ? $_POST['csrf'] : null)) { kcmc_screen_error('Invalid request.', 403, $carePath); }
    try {
        $revision = filter_var($_POST['revision'] ?? null, FILTER_VALIDATE_INT);
        if ($revision === false || $revision === null || $revision < 0) throw new DomainException('Reload this page before saving.');
        $action = is_string($_POST['action'] ?? null) ? $_POST['action'] : '';
        if (!$careAdmin && $leader) {
            $adminAction = $view === 'review' || in_array($action, ['approve', 'approve_warrior', 'decline_warrior'], true);
            if (!$adminAction && in_array($action, ['private', 'answered', 'close'], true)) {
                $current = kcmc_care_read();
                $targetId = is_string($_POST['entry_id'] ?? null) ? $_POST['entry_id'] : '';
                $target = $current['entries'][$targetId] ?? null;
                $adminAction = is_array($target) && $target['author'] !== $user['id'];
            }
            if ($adminAction) {
                // Preserve the old form's POST payload and its verified CSRF.
                // The administrative route rechecks both before any mutation.
                header('Location: ' . kcmc_url('admin/prayer-care.php?view=review'), true, 307);
                exit;
            }
        }
        kcmc_care_save($user, $action, $_POST, $revision);
        header('Location: ' . kcmc_url($carePath . '?view=' . $view . '&saved=1'), true, 303);
        exit;
    } catch (DomainException $e) { http_response_code(422); $error = $e->getMessage(); }
      catch (Throwable $e) { http_response_code(503); $error = 'Prayer & Care could not save. Please contact the church office or try again later.'; }
}
try { $state = kcmc_care_read(); }
catch (Throwable $e) { kcmc_screen_error('Prayer & Care is temporarily unavailable. Please contact the church office.', 503); }
$now = time();
$warrior = kcmc_care_warrior($state, $user);
$signup = $state['warriors'][$user['id']]['status'] ?? '';
$entries = array_filter($state['entries'], fn($e)=>kcmc_care_visible($e,$state,$user,$now));
uasort($entries, fn($a,$b)=>$b['updated_at'] <=> $a['updated_at']);
function care_fields(array $state, string $id = ''): void {
    echo '<input type="hidden" name="csrf" value="'.kcmc_h(kcmc_csrf()).'"><input type="hidden" name="revision" value="'.$state['revision'].'">';
    if ($id !== '') echo '<input type="hidden" name="entry_id" value="'.kcmc_h($id).'">';
}
function care_date(int $stamp): string { return (new DateTimeImmutable('@'.$stamp))->setTimezone(new DateTimeZone('America/Chicago'))->format('M j, Y'); }
$display = array_filter($entries, function($e) use($view,$state,$user,$now) {
    if ($view === 'mine') return $e['author'] === $user['id'] || ($e['kind'] === 'need' && kcmc_care_shared($e,$state,$user,$now) && in_array($user['id'],$state['commitments'][$e['id']] ?? [],true));
    if ($view === 'review') return in_array($e['status'],['private','pending','approved'],true);
    return $e['kind'] === ($view === 'praise' ? 'praise' : 'need') && kcmc_care_shared($e,$state,$user,$now);
});
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title><?= $careAdmin ? 'Prayer &amp; Care Review' : 'Prayer &amp; Care' ?> • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.3'))?>">
<style>.care-nav{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.care-nav a[aria-current]{background:#d8b267;color:#102638}.care-section{margin:20px 0}.care-section summary{cursor:pointer;font-weight:800;padding:10px 0}.care-note{font-size:.95rem;line-height:1.6}.care-card{overflow-wrap:anywhere}.care-card textarea{width:100%;box-sizing:border-box}.care-card .portal-actions{flex-wrap:wrap}.care-status{font-size:.9rem}.care-review{margin:18px 0;border-bottom:1px solid #567080;padding-bottom:16px}@media(max-width:480px){.care-nav a{flex:1 1 auto;text-align:center}.care-card .portal-actions .btn{max-width:100%;white-space:normal}.portal-shell{width:calc(100% - 24px)}.portal-card{padding:20px}}</style><?php require_once __DIR__ . '/../lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
</head>
<body class="portal-body"><?php echo kcmc_screen_navigation($careAdmin ? 'admin/home.php' : 'member/', true); ?><main class="portal-shell portal-narrow">
<a class="portal-back" href="<?=kcmc_h(kcmc_url($careAdmin ? 'admin/home.php' : 'member/'))?>"><?= $careAdmin ? '← Administration' : '← Account home' ?></a>
<header><p class="eyebrow">MEMBERS ONLY</p><h1><?= $careAdmin ? 'Prayer &amp; Care review' : 'Prayer &amp; Care' ?></h1><p class="portal-lead">Pray together. Share hope. Celebrate answered prayers.</p><p class="care-note">Keep requests confidential. Share only your own details or details you have permission to share. Nothing here is public.</p></header>
<?php if ($error): ?><p class="portal-alert" role="alert"><?=kcmc_h($error)?></p><?php elseif(isset($_GET['saved'])): ?><p class="portal-alert success" role="status">Saved securely.</p><?php endif; ?>
<nav class="care-nav" aria-label="Prayer &amp; Care views"><?php if ($careAdmin): ?><a class="btn secondary" href="?view=review"<?=$view==='review'?' aria-current="page"':''?>>Pastoral review</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/prayer-care.php'))?>">My Prayer &amp; Care</a><?php else: ?><?php foreach(['needs'=>'Current needs','praise'=>'Praise reports','mine'=>'My prayers'] as $key=>$label): ?><a class="btn secondary" href="?view=<?=$key?>"<?=$view===$key?' aria-current="page"':''?>><?=$label?></a><?php endforeach; ?><?php endif; ?></nav>
<?php if($view !== 'review'): ?>
<details class="portal-card care-section"<?=!$signup?' open':''?>><summary>Prayer warriors<?= $signup==='approved'?' · You’re on the team':($signup==='pending'?' · Awaiting approval':'') ?></summary>
<?php if(in_array($signup,['pending','approved'],true)): ?><p><?=$signup==='pending'?'Your signup is waiting for pastoral approval.':'Choose “I’ll pray for this” on a current need to add it to My prayers. Others can pray for the same need.'?></p><form method="post"><?php care_fields($state); ?><button class="btn secondary" name="action" value="leave"><?=$signup==='pending'?'Withdraw signup':'Leave prayer team'?></button></form>
<?php else: ?><p>Volunteer to carry prayer needs with KCMC. A pastoral leader will approve your signup. Joining does not give access to the confidential prayer inbox.</p><?php if($signup==='declined'): ?><p>Please speak with a pastoral leader before applying again.</p><?php endif; ?><form class="portal-form" method="post"><?php care_fields($state); ?><label class="portal-check"><input type="checkbox" name="confidential" value="1" required><span>I will keep prayer requests confidential and respect their chosen audience.</span></label><button class="btn gold" name="action" value="join">Sign up to pray</button></form><?php endif; ?></details>
<details class="portal-card care-section"><summary>Share a prayer need or praise report</summary><p class="care-note">Pastoral care only is the default. Group sharing requires your permission and pastoral review. Shared posts are shown for 30 days; you can update or close your own submission in My prayers.</p>
<form class="portal-form" method="post"><?php care_fields($state); ?><label>What would you like to share?<select name="kind"><option value="need">Prayer need</option><option value="praise">Praise report — answered prayer</option></select></label>
<label>Your words<textarea name="message" rows="5" minlength="10" maxlength="2000" required><?= $error && ($_POST['action'] ?? '')==='submit' && is_string($_POST['message'] ?? null) ? kcmc_h($_POST['message']) : '' ?></textarea></label>
<label>Who may see this?<select name="audience"><option value="pastoral">Pastoral care only</option><option value="team">Approved prayer warriors</option><option value="members">Verified church members</option></select></label>
<label>Name shown<select name="name_display"><option value="anonymous">Anonymous</option><option value="first_name">My first name</option></select></label>
<label class="portal-check"><input type="checkbox" name="consent" value="1"><span>If I choose group sharing, I give permission to share these words with that group and have permission for any details about others.</span></label>
<button class="btn gold" name="action" value="submit">Submit for care</button></form></details>
<?php endif; ?>
<?php if($view==='review'): ?><section class="portal-card care-section"><h2>Prayer-warrior signups</h2><p>Approval applies only to this new prayer ministry. Account roles and the confidential inbox stay unchanged.</p>
<?php if(!$state['warriors']): ?><p>No signups yet.</p><?php endif; ?>
<?php foreach($state['warriors'] as $id=>$record): ?><div class="care-review"><strong><?=kcmc_h($record['name'])?></strong> · <?=kcmc_h($record['status'])?><?php if($record['status']!=='withdrawn'): ?><form class="portal-actions" method="post"><?php care_fields($state); ?><input type="hidden" name="target" value="<?=kcmc_h((string)$id)?>"><?php if($record['status']!=='approved'): ?><button class="btn gold" name="action" value="approve_warrior">Approve signup</button><?php endif; ?><button class="btn secondary" name="action" value="decline_warrior"><?=$record['status']==='approved'?'Remove approval':'Decline signup'?></button></form><?php endif; ?></div><?php endforeach; ?></section><?php endif; ?>
<section aria-label="<?=kcmc_h($view==='praise'?'Praise reports':'Prayer entries')?>"><h2><?=['needs'=>'Current prayer needs','praise'=>'Praise reports','mine'=>'My prayers','review'=>'New ministry submissions'][$view]?></h2>
<?php if(!$display): ?><p class="portal-empty"><?= $view==='mine'?'Your submissions and chosen prayer needs will appear here.':($view==='praise'?'No praise reports have been shared with your group yet.':'No current items are available for this view.') ?></p><?php endif; ?>
<?php foreach($display as $entry): $own=$entry['author']===$user['id']; $canManage=$own||($careAdmin&&$leader); $chosen=in_array($user['id'],$state['commitments'][$entry['id']] ?? [],true); ?>
<article class="portal-card care-card care-section"><div class="prayer-meta"><strong><?=kcmc_h($entry['name'])?></strong><span><?=$entry['kind']==='praise'?'Praise report':'Prayer need'?></span></div><p><?=nl2br(kcmc_h($entry['message']))?></p>
<p class="care-status"><?=kcmc_h(['pastoral'=>'Pastoral care only','team'=>'Approved prayer warriors','members'=>'Verified church members'][$entry['audience']])?> · <?=kcmc_h($entry['expires_at']<=$now?'Expired':ucfirst($entry['status']))?> · Review by <?=care_date($entry['expires_at'])?></p>
<?php if($warrior && $entry['kind']==='need' && kcmc_care_shared($entry,$state,$user,$now)): ?><form method="post"><?php care_fields($state,$entry['id']); ?><button class="btn gold" name="action" value="<?=$chosen?'unpray':'pray'?>"><?=$chosen?'On my prayer list — remove':'I’ll pray for this'?></button></form><?php endif; ?>
<?php if($canManage): ?><form class="portal-actions care-section" method="post"><?php care_fields($state,$entry['id']); ?>
<?php if($careAdmin && $leader && $entry['status']==='pending' && $entry['expires_at']>$now): ?><button class="btn gold" name="action" value="approve">Approve chosen audience</button><?php endif; ?>
<?php if(!in_array($entry['status'],['closed','answered'],true)): ?><button class="btn secondary" name="action" value="private">Keep pastoral only</button><?php if($entry['kind']==='need'): ?><button class="btn secondary" name="action" value="answered">Mark answered</button><?php endif; ?><button class="btn secondary" name="action" value="close">Close</button><?php endif; ?></form>
<?php if($entry['status']==='answered'): ?><p class="care-note">Thank God for answered prayer. To share a praise report, use “Share a prayer need or praise report” above and choose which details to share. Your original request is not copied or published.</p><?php endif; ?>
<?php if($own): ?><details><summary>Update my words</summary><p>Updates to shared submissions need fresh pastoral approval.</p><form class="portal-form" method="post"><?php care_fields($state,$entry['id']); ?><label>Updated words<textarea name="message" rows="4" minlength="10" maxlength="2000" required><?=kcmc_h($entry['message'])?></textarea></label><button class="btn secondary" name="action" value="update">Save update for review</button></form></details><?php endif; ?>
<?php endif; ?></article><?php endforeach; ?></section>
<?php if (!$careAdmin): ?><details class="care-section"><summary>Earlier prayer requests</summary><p class="care-note"><a href="<?=kcmc_h(kcmc_url('member/prayers.php'))?>">Open earlier prayer requests</a> and the existing approved member prayer wall. Their privacy rules stay the same; they are not copied into this ministry.</p></details><?php endif; ?>
</main></body></html>
