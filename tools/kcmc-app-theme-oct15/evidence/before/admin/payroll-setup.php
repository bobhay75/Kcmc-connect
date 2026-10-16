<?php
declare(strict_types=1);
require_once __DIR__.'/../lib/bootstrap.php';
require_once __DIR__.'/../lib/operations-owner.php';
$owner=kcmc_require_operations_owner();
require_once __DIR__.'/../lib/payroll.php';
kcmc_private_headers();$error='';$message='';$cron='';
if(($_SERVER['REQUEST_METHOD']??'GET')==='POST'){
    if(!kcmc_verify_csrf($_POST['csrf']??null)){http_response_code(403);$error='Your session expired. Reload and try again.';}
    else try{
        $action=(string)($_POST['action']??'');
        if($action==='save'){
            kcmc_payroll_save_settings($owner,$_POST);
            kcmc_audit('payroll.settings_saved',['action'=>'configure','status'=>(string)($_POST['channel']??'off'),'count'=>1]);
            $message='Payroll settings saved. Use the command below to review the hosting schedule.';
        }elseif($action!=='preview_cron')throw new RuntimeException('Choose an available payroll setup action.');
        if(!empty(kcmc_payroll_recipient()))$cron=kcmc_payroll_cron_line((string)($_POST['php_cli']??''));
    }catch(Throwable $failure){$error=$failure->getMessage();}
}
$settings=kcmc_payroll_settings();$recipient=kcmc_payroll_recipient($settings);$mail=kcmc_payroll_mail_settings();$users=array_values(array_filter(kcmc_users(),static fn($user)=>!empty($user['active'])));$phpCommands=kcmc_payroll_cli_candidates();
$today=kcmc_timeclock_local_date(gmdate(DATE_ATOM));
$identity=null;try{$identity=kcmc_payroll_store_identity();}catch(Throwable $failure){$error=$error?:$failure->getMessage();}
$runPath=KCMC_PRIVATE_DATA.'/payroll-run-status.json';$lastRun=is_file($runPath)?kcmc_read_json_store($runPath,[]):[];
$deliveries=kcmc_timeclock_store()['payroll_deliveries']??[];$attention=count(array_filter($deliveries,static fn($row)=>is_array($row)&&in_array((string)($row['status']??''),['sending','failed'],true)));
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Payroll setup • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"><style>
.payroll-shell{max-width:920px}.payroll-form{display:grid;gap:16px}.payroll-form label{display:grid;gap:8px;font-weight:700}.payroll-form :is(select,input){width:100%;padding:12px;box-sizing:border-box;font:inherit}.payroll-command{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #567080;padding:16px;border-radius:12px}.payroll-shell :is(a,button,input,select):focus-visible{outline:3px solid #e3b958;outline-offset:4px}
</style></head><body class="portal-body"><main class="portal-shell payroll-shell"><header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/home.php'))?>">← Admin home</a><p class="eyebrow">OWNER SETUP</p><h1>Payroll handoff</h1></div><a class="btn secondary" href="<?=kcmc_h(kcmc_url())?>">Home</a></header>
<?php if($error):?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif;?><?php if($message):?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif;?>
<section class="portal-card"><h2>Reviewer and delivery</h2><p>Select the existing account that should review employee time totals. This grants payroll review access only. Your owner access stays available.</p>
<form class="payroll-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="save"><label>Payroll reviewer<select name="reviewer_id"><option value="">Select an active account</option><?php foreach($users as $user):?><option value="<?=kcmc_h((string)$user['id'])?>"<?=((string)$user['id']===(string)$settings['reviewer_id'])?' selected':''?>><?=kcmc_h((string)($user['display_name']??'Account'))?> — <?=kcmc_h((string)($user['email']??''))?></option><?php endforeach;?></select></label>
<label>Delivery channel<select name="channel"><option value="off"<?=$settings['channel']==='off'?' selected':''?>>Off</option><option value="queue"<?=$settings['channel']==='queue'?' selected':''?>>Private payroll review queue</option><option value="email"<?=$settings['channel']==='email'?' selected':''?><?=empty($mail['ready'])?' disabled':''?>>Email totals and private review link</option></select></label>
<p class="portal-fine"><?=!empty($mail['ready'])?'Server payroll sender: '.kcmc_h((string)$mail['from']):'Email becomes available after the server payroll sender is configured.'?> Selecting email enables future scheduled notices to this account’s email address. Mail acceptance is recorded; delivery to the inbox needs separate confirmation.</p>
<p class="portal-fine">For new email delivery or a newly selected reviewer, notices begin with pay periods ending <?=kcmc_h($today)?> or later. Earlier cards stay in the private review queue. Saving unchanged active email settings keeps the existing cutoff.</p><?php if($settings['channel']==='email'):?><p class="portal-fine">Current email cutoff: <?=kcmc_h(kcmc_payroll_valid_activation_date((string)$settings['email_activation_date'])?(string)$settings['email_activation_date']:'Save again to establish the cutoff')?>.</p><?php endif;?>
<label>Payroll review address for email<input type="url" name="review_url" maxlength="500" value="<?=kcmc_h((string)($settings['review_url']?:'https://bobsome1.com/kcmc-connect/admin/timecards.php'))?>" placeholder="https://bobsome1.com/kcmc-connect/admin/timecards.php"></label>
<label>PHP command for the hosting schedule<select name="php_cli" required><?php foreach($phpCommands as $php):?><option value="<?=kcmc_h($php)?>"><?=kcmc_h($php)?></option><?php endforeach;?></select></label><button class="btn gold" type="submit">Save payroll settings</button></form></section>
<section class="portal-card portal-section"><h2>Hosting schedule</h2><p>Period totals use the 23rd–22nd Chicago pay period. The hosting task should run every 15 minutes so closed periods reach the selected reviewer automatically. Open shifts stay flagged for attention.</p>
<?php if($recipient):?><p>Selected reviewer: <strong><?=kcmc_h((string)($recipient['display_name']??'Account'))?></strong>. Channel: <?=kcmc_h((string)$settings['channel'])?>.</p><form class="payroll-form" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="action" value="preview_cron"><label>PHP command<select name="php_cli" required><?php foreach($phpCommands as $php):?><option value="<?=kcmc_h($php)?>"><?=kcmc_h($php)?></option><?php endforeach;?></select></label><button class="btn secondary" type="submit">Prepare hosting command</button></form><?php else:?><p>Select a reviewer and enable a delivery channel to prepare the hosting command.</p><?php endif;?>
<?php if($cron):?><p>Review this exact line with the hosting setup. It uses this web session’s resolved private store and refuses a different CLI store. Preparing the line does not activate it.</p><pre class="payroll-command"><?=kcmc_h($cron)?></pre><?php endif;?>
<?php if($identity):?><p class="portal-fine">Store fingerprint: <code><?=kcmc_h((string)$identity['fingerprint'])?></code></p><?php endif;?>
<p>Last runner execution: <?=kcmc_h((string)($lastRun['finished_at']??'Not recorded'))?>. A runner receipt alone does not confirm that cPanel has an active schedule.</p><?php if($attention):?><p class="portal-alert warning"><?=kcmc_h((string)$attention)?> email attempt(s) need review. Failed or interrupted attempts are preserved and are not resent automatically.</p><?php endif;?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/timecards.php'))?>">Open employee time cards</a></section></main></body></html>
