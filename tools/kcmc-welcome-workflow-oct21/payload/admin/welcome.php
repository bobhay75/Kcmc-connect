<?php
declare(strict_types=1);
require_once __DIR__.'/../lib/bootstrap.php';
require_once __DIR__.'/../lib/connection-intake.php';
require_once __DIR__.'/../lib/welcome-drafts.php';
$user=kcmc_require_role(['pastor_admin','recovery_admin']);
kcmc_private_headers();
kcmc_session_start();
$id=trim((string)($_GET['id']??''));
$row=null;
foreach(kcmc_connection_recent(300) as $candidate) {
    if(is_array($candidate)&&$id!==''&&hash_equals((string)($candidate['id']??''),$id)){$row=$candidate;break;}
}
if($row===null){http_response_code(404);exit('Connection request not found. Return to the Connections inbox.');}
$email=(string)($row['email']??'');
$draft=kcmc_welcome_draft_read($id,$row);
$error='';$success='';
if($_SERVER['REQUEST_METHOD']==='POST'){
    if(!kcmc_verify_csrf($_POST['csrf']??null)){$error='Reload this page and try again.';}
    elseif(!kcmc_valid_email($email)||preg_match('/[\r\n]/',$email)){$error='This connection does not have a valid email address.';}
    else{
        $subject=(string)($_POST['subject']??'');$body=(string)($_POST['body']??'');
        $result=kcmc_welcome_draft_save($id,$subject,$body,(int)($_POST['revision']??-1),(string)($user['id']??''));
        if(!empty($result['ok'])){kcmc_audit('connection.welcome_draft_saved',['connection_id'=>$id]);$success='Welcome draft saved. No email has been sent.';$draft=kcmc_welcome_draft_read($id,$row);}
        else{$error=(string)($result['error']??'Draft could not be saved.');$draft['subject']=$subject;$draft['body']=$body;}
    }
}
$validEmail=kcmc_valid_email($email)&&!preg_match('/[\r\n]/',$email);
$mailto=$validEmail?'mailto:'.rawurlencode($email).'?subject='.rawurlencode((string)$draft['subject']).'&body='.rawurlencode((string)$draft['body']):'';
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Prepare Welcome • KCMC</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css'))?>"><style>.welcome-compose{max-width:900px}.welcome-compose textarea{width:100%;min-height:420px}.welcome-compose label{display:block;margin:18px 0}.welcome-compose input{display:block;width:100%}.welcome-compose .actions{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.welcome-compose .recipient{overflow-wrap:anywhere}</style><?php require_once __DIR__.'/../lib/screen-navigation.php';echo kcmc_screen_assets();?></head><body class="portal-body"><?php echo kcmc_screen_navigation('admin/connections.php',true);?><main class="portal-shell welcome-compose"><section class="portal-card"><p class="eyebrow">CONNECTIONS</p><h1>Prepare a KCMC welcome</h1><p class="recipient"><strong>To:</strong> <?=kcmc_h((string)($row['name']??''))?> &lt;<?=kcmc_h($email)?>&gt;</p><p>Personalize the message, save your draft, then open it in your email app to review and send.</p><?php if($error):?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif;?><?php if($success):?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif;?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="revision" value="<?=kcmc_h((string)($draft['revision']??0))?>"><label>Subject<input name="subject" maxlength="200" required value="<?=kcmc_h((string)$draft['subject'])?>"></label><label>Welcome message<textarea name="body" maxlength="6000" required><?=kcmc_h((string)$draft['body'])?></textarea></label><button class="btn gold" type="submit">Save welcome draft</button></form><div class="actions"><?php if($mailto!==''&&$error===''):?><a class="btn secondary" id="openWelcomeDraft" href="<?=kcmc_h($mailto)?>">Open draft in email app</a><?php endif;?><a class="btn secondary" href="<?=kcmc_h(kcmc_url('welcome-kit.php'))?>" target="_blank" rel="noopener">Preview welcome package</a></div><p class="portal-fine">Save edits before opening the email draft. Opening your email app does not mark this request Contacted. Update its follow-up status after you send.</p></section></main><script>const compose=document.querySelector('form');const openDraft=document.getElementById('openWelcomeDraft');if(compose&&openDraft){compose.addEventListener('input',()=>{openDraft.remove();});}</script></body></html>
