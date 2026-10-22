<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_role(['recovery_admin']);
$path = KCMC_PRIVATE_DATA . '/development-ledger.json';
$error = ''; $message = '';
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) { http_response_code(403); $error = 'Session expired.'; }
    else {
        try {
            $action = (string)($_POST['action'] ?? '');
            if (!in_array($action, ['start','stop','note'], true)) throw new RuntimeException('Invalid action.');
            $note = trim((string)($_POST['note'] ?? ''));
            if (strlen($note) > 1000) throw new RuntimeException('Note too long.');
            kcmc_update_json_store($path, ['sessions'=>[], 'events'=>[]], function (&$data) use ($action,$note,$user) {
                $now = gmdate('Y-m-d\TH:i:s\Z');
                $data['sessions'] = is_array($data['sessions'] ?? null) ? $data['sessions'] : [];
                $data['events'] = is_array($data['events'] ?? null) ? $data['events'] : [];
                $open = null;
                foreach ($data['sessions'] as $i=>$session) if (empty($session['ended_at'])) $open=$i;
                if ($action === 'start') {
                    if ($open !== null) throw new RuntimeException('A session is already running.');
                    $data['sessions'][]=['id'=>bin2hex(random_bytes(12)),'started_at'=>$now,'ended_at'=>null,'note'=>$note,'actor_id'=>(string)$user['id']];
                } elseif ($action === 'stop') {
                    if ($open === null) throw new RuntimeException('No running session.');
                    $data['sessions'][$open]['ended_at']=$now;
                    $data['sessions'][$open]['close_note']=$note;
                } else {
                    if ($open === null) throw new RuntimeException('Start a session first.');
                    if ($note === '') throw new RuntimeException('Enter an activity note.');
                }
                $data['events'][]=['at'=>$now,'action'=>$action,'note'=>$note,'actor_id'=>(string)$user['id']];
            });
            kcmc_audit('development_ledger.'.$action,['count'=>1]);
            $message='Development ledger updated.';
        } catch (Throwable $e) { $error=$e->getMessage(); }
    }
}
$data=kcmc_read_json_store($path,['sessions'=>[],'events'=>[]]);
$sessions=is_array($data['sessions']??null)?$data['sessions']:[];
$open=false;$seconds=0;
foreach ($sessions as $s) {
    if (empty($s['ended_at'])) {$open=true;continue;}
    $start=strtotime((string)$s['started_at']);$end=strtotime((string)$s['ended_at']);
    if ($start!==false&&$end!==false&&$end>$start) $seconds+=$end-$start;
}
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Private KCMC Development Ledger</title></head>
<body style="font:16px system-ui;max-width:720px;margin:30px auto;padding:16px">
<h1>Private KCMC Development Ledger</h1><p>Separate from church payroll. Session elapsed time is not automatically approved billable time.</p>
<?php if ($error): ?><p role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($message): ?><p role="status"><?=kcmc_h($message)?></p><?php endif; ?>
<h2><?=$open?'Session running':'No active session'?></h2>
<p>Completed session elapsed time: <?=number_format($seconds/3600,2)?> hours (before breaks and billable review)</p>
<form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>">
<label>Activity / evidence reference <textarea name="note" maxlength="1000" rows="3" style="display:block;width:100%"></textarea></label>
<button type="submit" name="action" value="<?=$open?'stop':'start'?>"><?=$open?'Stop session':'Start session'?></button>
<?php if($open): ?><button type="submit" name="action" value="note">Log activity</button><?php endif; ?>
</form><h2>Recent sessions</h2><ol>
<?php foreach(array_reverse(array_slice($sessions,-30)) as $s): ?><li><?=kcmc_h((string)$s['started_at'])?> → <?=kcmc_h((string)($s['ended_at']??'Open'))?> — <?=kcmc_h((string)($s['note']??''))?></li><?php endforeach; ?>
</ol></body></html>
