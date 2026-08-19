<?php
require_once __DIR__ . '/../lib/bootstrap.php';
if (kcmc_owner_configured()) { header('Location: /admin/login.php'); exit; }
$cfg = kcmc_config();
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $key = (string)($_POST['setup_key'] ?? '');
    $password = (string)($_POST['password'] ?? '');
    $confirm = (string)($_POST['confirm'] ?? '');
    $expected = (string)($cfg['setup_key'] ?? '');
    if ($expected === '' || !hash_equals($expected, $key)) $error = 'Invalid setup key.';
    elseif (strlen($password) < 12) $error = 'Use at least 12 characters.';
    elseif ($password !== $confirm) $error = 'Passwords do not match.';
    else {
        $out = "<?php\nreturn " . var_export([
            'church_email' => $cfg['church_email'],
            'setup_key' => '',
            'admin_password_hash' => password_hash($password, PASSWORD_DEFAULT),
            'session_name' => $cfg['session_name'],
        ], true) . ";\n";
        if (file_put_contents(KCMC_CONFIG, $out, LOCK_EX) === false) $error = 'Could not create config.php. Check folder permissions.';
        else { header('Location: /admin/login.php?setup=1'); exit; }
    }
}
?><!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KCMC Owner Setup</title><link rel="stylesheet" href="/styles.css"><style>body{background:#0c1724;color:#fff}.adminbox{max-width:600px;margin:8vh auto;background:#fff;color:#142238;border-radius:22px;padding:30px}.adminbox input{width:100%;padding:13px;margin:7px 0 15px;border:1px solid #ccd3da;border-radius:10px}.adminbox button{padding:13px 18px;border:0;border-radius:999px;background:#17324c;color:#fff;font-weight:800}.error{color:#a02020}</style></head><body><main class="adminbox"><p class="eyebrow">KCMC CONNECT • OWNER SETUP</p><h1>Secure the publishing desk.</h1><?php if($error): ?><p class="error"><?=kcmc_h($error)?></p><?php endif; ?><form method="post"><label>Setup key<input name="setup_key" required autocomplete="off"></label><label>New owner password<input name="password" type="password" required minlength="12"></label><label>Confirm password<input name="confirm" type="password" required minlength="12"></label><button>Create owner login</button></form></main></body></html>
