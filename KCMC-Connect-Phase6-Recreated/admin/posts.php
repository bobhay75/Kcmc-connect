<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/post-controls.php';
require_once __DIR__ . '/../lib/backup-retention.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        http_response_code(403); $error = 'Reload this page and try again.';
    } elseif ((string)($_POST['confirm'] ?? '') !== '1') {
        http_response_code(422); $error = 'Review and confirm this post action.';
    } elseif (!hash_equals(hash_file('sha256', KCMC_DATA) ?: '', (string)($_POST['version'] ?? ''))) {
        http_response_code(409); $error = 'Content changed since this page opened. Review the current posts and try again.';
    } else {
        try {
            $section = (string)($_POST['section'] ?? '');
            $action = (string)($_POST['action'] ?? '');
            $data = kcmc_change_post(kcmc_content(), $section, (string)($_POST['id'] ?? ''), $action, $_POST);
            kcmc_write_content($data, (string)($user['display_name'] ?? 'Administrator'), (string)$_POST['version']);
            kcmc_prune_content_backups(KCMC_BACKUPS);
            kcmc_audit('content.post_changed', ['section' => $section, 'action' => $action]);
            header('Location: ' . kcmc_url('admin/posts.php?saved=1')); exit;
        } catch (InvalidArgumentException $e) { http_response_code(422); $error = $e->getMessage(); }
        catch (RuntimeException $e) { http_response_code(409); $error = 'The post was not saved. Reload and review current content; check that backup storage is writable before trying again.'; }
    }
}
$data = kcmc_content();
$version = hash_file('sha256', KCMC_DATA) ?: '';
?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Manage Posts • KCMC Connect</title>
<link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>"><style>
body{background:#eef2f4;color:#17324c;color-scheme:light}main{max-width:1000px;margin:24px auto;padding:16px}article{background:white;border:1px solid #dce3e7;border-radius:16px;padding:20px;margin:16px 0}form{margin-top:16px}label{display:block;margin:12px 0}input,select,button{font:inherit;max-width:100%;padding:8px}button{cursor:pointer}.danger{background:#8d2d2d;color:white;border:0;border-radius:8px}a{color:#174d75}.notice{padding:16px;background:#e6f3e7}.error{padding:16px;background:#fdeaea}input[type=checkbox]{width:auto}:focus-visible{outline:3px solid #174d75;outline-offset:3px}
</style></head><body><main><a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a><h1>Manage posts</h1><p>Delete moves a post to Trash and removes it from public view. Restore brings it back hidden for review in the Publishing Desk. Each saved action creates a content backup.</p><p><a href="#announcements">Announcements</a> · <a href="#events">Events</a> · <a href="#trash">Trash</a></p>
<?php if ($error): ?><p class="error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if (isset($_GET['saved'])): ?><p class="notice" role="status">Post updated. Previous content was backed up.</p><?php endif; ?>
<?php foreach (['announcements', 'events', 'trash'] as $group): ?><section id="<?=kcmc_h($group)?>"><h2><?=kcmc_h(ucfirst($group))?></h2>
<?php foreach (['announcements', 'events'] as $section): foreach (($data[$section] ?? []) as $post):
if (!is_array($post) || (string)($post['id'] ?? '') === '') continue;
$deleted = !empty($post['deleted_at']);
if ($group === 'trash' ? !$deleted : ($deleted || $group !== $section)) continue;
?><article><h3><?=kcmc_h((string)($post['title'] ?? 'Untitled post'))?></h3>
<p><?=kcmc_h($section === 'events' ? (string)($post['date'] ?? '') . ' • ' . (string)($post['time'] ?? '') : 'Announcement')?> · <?=kcmc_h($deleted ? 'Trash' : (string)($post['status'] ?? 'published'))?></p>
<p><?=nl2br(kcmc_h((string)($post['body'] ?? $post['description'] ?? '')))?></p>
<?php if (!$deleted && ($post['status'] ?? '') === 'hidden'): ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="version" value="<?=kcmc_h($version)?>"><input type="hidden" name="section" value="<?=kcmc_h($section)?>"><input type="hidden" name="id" value="<?=kcmc_h((string)$post['id'])?>"><input type="hidden" name="action" value="publish"><label><input type="checkbox" name="confirm" value="1" required> I reviewed this post and its dates. Publish it if its schedule is active.</label><button type="submit">Publish reviewed post</button></form><?php endif; ?>
<?php if (!$deleted && $section === 'events'): ?><form method="post">
<input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="version" value="<?=kcmc_h($version)?>"><input type="hidden" name="section" value="events"><input type="hidden" name="id" value="<?=kcmc_h((string)$post['id'])?>"><input type="hidden" name="action" value="repeat">
<label>Repeat<select name="repeat"><option value="" <?=($post['repeat'] ?? '') !== 'weekly' ? 'selected' : ''?>>Once</option><option value="weekly" <?=($post['repeat'] ?? '') === 'weekly' ? 'selected' : ''?>>Weekly</option></select></label>
<label>Last weekly date (optional)<input type="date" name="repeat_until" value="<?=kcmc_h((string)($post['repeat_until'] ?? ''))?>"></label>
<p>Weekly uses the same weekday, time and location. Leave the last date blank to continue until stopped. Saving Weekly replaces the single-event expiration. Switching to Once restores that expiration. Calendar download saves the displayed occurrence only.</p>
<label><input type="checkbox" name="confirm" value="1" required> I reviewed this event’s repeat setting.</label><button type="submit">Save repeat setting</button></form><?php endif; ?>
<form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="version" value="<?=kcmc_h($version)?>"><input type="hidden" name="section" value="<?=kcmc_h($section)?>"><input type="hidden" name="id" value="<?=kcmc_h((string)$post['id'])?>"><input type="hidden" name="action" value="<?=$deleted ? 'restore' : 'delete'?>">
<label><input type="checkbox" name="confirm" value="1" required> <?=$deleted ? 'Restore this post as hidden for review.' : 'Move this post to Trash and remove it from public view.'?></label><button class="<?=$deleted ? '' : 'danger'?>" type="submit"><?=$deleted ? 'Restore post' : 'Delete post'?></button></form></article>
<?php endforeach; endforeach; ?></section><?php endforeach; ?></main></body></html>
