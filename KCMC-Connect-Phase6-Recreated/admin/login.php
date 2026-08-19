<?php
require_once __DIR__ . '/../lib/bootstrap.php';
if (!kcmc_owner_configured()) { header('Location: /admin/setup.php'); exit; }
kcmc_session_start();
$error='';
if ($_SERVER['REQUEST_METHOD']==='POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) $error='Please reload and try again.';
    else {
        $cfg=kcmc_config();
        if (password_verify((string)($_POST['password']??''),(string)$cfg['admin_password_hash'])) {
            session_regenerate_id(true); $_SESSION['kcmc_owner']=true; header('Location: /admin/'); exit;
        }
        $error='Incorrect password.';
    }
}
?><!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KCMC Owner Login</title><link rel="stylesheet" href="/styles.css"><style>body{background:#0c1724;color:#fff}.adminbox{max-width:520px;margin:10vh auto;background:#fff;color:#142238;border-radius:22px;padding:30px}.adminbox input{width:100%;padding:13px;margin:7px 0 15px;border:1px solid #ccd3da;border-radius:10px}.adminbox button{padding:13px 18px;border:0;border-radius:999px;background:#17324c;color:#fff;font-weight:800}.error{color:#a02020}</style></head><body><main class="adminbox"><p class="eyebrow">KCMC CONNECT • OWNER</p><h1>Publishing Desk</h1><?php if($error): ?><p class="error"><?=kcmc_h($error)?></p><?php endif; ?><form method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><label>Password<input type="password" name="password" required autofocus></label><button>Sign in</button></form><p><a href="/">← Back to KCMC Connect</a></p></main></body></html>
