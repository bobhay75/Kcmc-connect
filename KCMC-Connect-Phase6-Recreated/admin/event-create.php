<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/backup-retention.php';
require_once __DIR__ . '/../lib/event-create.php';

$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();

$error = '';
$values = [
    'title' => '',
    'date' => '',
    'time' => '',
    'end_time' => '',
    'location' => 'KCMC',
    'description' => '',
    'priority' => '50',
    'status' => 'published',
    'expires' => '',
];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    foreach (array_keys($values) as $key) $values[$key] = trim((string)($_POST[$key] ?? $values[$key]));
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        http_response_code(403);
        $error = 'Please reload and try again.';
    } else {
        $validated = kcmc_validate_new_event($values);
        if (empty($validated['ok'])) {
            http_response_code(422);
            $error = (string)($validated['error'] ?? 'Event details are invalid.');
        } else {
            $data = kcmc_content();
            if (!isset($data['events']) || !is_array($data['events'])) $data['events'] = [];
            $event = $validated['event'];
            if (kcmc_event_duplicate_exists($data['events'], (string)$event['title'], (string)$event['date'])) {
                http_response_code(409);
                $error = 'An event with this title and date already exists.';
            } else {
                $event['id'] = kcmc_random_id('event');
                $data['events'][] = $event;
                kcmc_write_content($data, (string)($user['display_name'] ?? 'Administrator'));
                $rotation = kcmc_prune_content_backups(KCMC_BACKUPS);
                kcmc_audit('event.created', [
                    'status' => (string)$event['status'],
                    'count' => 1,
                ]);
                if (($rotation['removed'] ?? 0) > 0 || ($rotation['failed'] ?? 0) > 0) {
                    kcmc_audit('content.backups_rotated', [
                        'removed' => (int)($rotation['removed'] ?? 0),
                        'failed' => (int)($rotation['failed'] ?? 0),
                        'kept' => (int)($rotation['kept'] ?? 0),
                    ]);
                }
                header('Location: ' . kcmc_url('admin/?msg=' . rawurlencode('Event created successfully. Backup created automatically.')));
                exit;
            }
        }
    }
}
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Add Event • KCMC Connect</title>
<link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>">
<style>
body{background:#eef2f4;color:#17324c;color-scheme:light}.shell{width:min(860px,calc(100% - 28px));margin:28px auto 80px}.card{background:#fff;border:1px solid #dce3e7;border-radius:18px;padding:22px;margin:18px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}label{display:block;font-weight:700}.card input,.card textarea,.card select{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5dc;border-radius:9px;margin:6px 0 14px;font:inherit;background:#fff;color:#17324c}.card textarea{min-height:140px}.btn{display:inline-block;border:0;border-radius:999px;padding:12px 17px;background:#17324c;color:#fff;text-decoration:none;font-weight:800;cursor:pointer}.secondary{background:#e8eef2;color:#17324c}.error{background:#fdeaea;color:#7b1f1f;border:1px solid #e5b9b9;padding:12px 14px;border-radius:10px}.muted{color:#607080}.actions{display:flex;gap:10px;flex-wrap:wrap}.shell :is(a,button,input,select,textarea):focus-visible{outline:3px solid #174d75;outline-offset:3px}@media(max-width:700px){.grid,.three{grid-template-columns:1fr}}
</style>
</head>
<body>
<main class="shell">
<a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing Desk</a>
<p class="eyebrow">KCMC EVENTS</p>
<h1>Add an event</h1>
<p class="muted">Create a new public or hidden event. Publishing creates an automatic content backup.</p>
<?php if ($error !== ''): ?><p class="error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<form class="card" method="post">
<input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>">
<label>Event title<input name="title" maxlength="120" value="<?=kcmc_h($values['title'])?>" required></label>
<div class="three">
<label>Date<input type="date" name="date" value="<?=kcmc_h($values['date'])?>" required></label>
<label>Start time<input name="time" placeholder="4:30 PM" value="<?=kcmc_h($values['time'])?>"></label>
<label>End time<input name="end_time" placeholder="6:30 PM" value="<?=kcmc_h($values['end_time'])?>"></label>
</div>
<label>Location<input name="location" maxlength="180" value="<?=kcmc_h($values['location'])?>"></label>
<label>Description<textarea name="description" maxlength="2000"><?=kcmc_h($values['description'])?></textarea></label>
<div class="three">
<label>Priority<input type="number" name="priority" min="0" max="100" step="1" value="<?=kcmc_h($values['priority'])?>"></label>
<label>Status<select name="status"><option value="published" <?=$values['status']==='published'?'selected':''?>>Published</option><option value="hidden" <?=$values['status']==='hidden'?'selected':''?>>Hidden</option></select></label>
<label>Expires<input type="date" name="expires" value="<?=kcmc_h($values['expires'])?>"></label>
</div>
<p class="muted">A duplicate title on the same date is blocked. Times use formats such as 4:30 PM. Expiration is optional and cannot precede the event date.</p>
<div class="actions"><button class="btn" type="submit">Create event</button><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/'))?>">Cancel</a></div>
</form>
</main>
</body>
</html>
