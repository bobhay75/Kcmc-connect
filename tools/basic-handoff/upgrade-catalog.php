<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();

// Catalog descriptions only. Premium module code, prices, payment processing,
// entitlement secrets and installers are intentionally absent from Core.
$modules = [
    ['Publication Designer', 'Prepare and organize richer church publications, media and layouts.'],
    ['Member Portal', 'Optional member sign-in, personal workspace and member communication tools.'],
    ['Timeclock & Payroll', 'Optional staff attendance and administrative payroll workflows.'],
    ['Push Notifications', 'Optional announcements delivered to subscribed devices.'],
    ['Team Workspace', 'Optional collaboration and internal team coordination.'],
    ['AI Assistants', 'Optional writing and ministry assistance, separately configured and reviewed.'],
];
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Available Upgrades | KCMC Connect</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5f7f4;color:#193529;font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}main{width:min(1040px,calc(100% - 32px));margin:36px auto 64px}a{color:#165543}a:focus-visible{outline:3px solid #b78b36;outline-offset:4px}h1{font-size:clamp(1.8rem,4vw,2.6rem);line-height:1.2;margin:.35em 0}.intro{max-width:750px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));gap:16px;margin-top:26px}.item{background:#fff;border:1px solid #dce6de;border-radius:16px;padding:22px;box-shadow:0 3px 12px #1233210c}.item h2{font-size:1.2rem;margin:0 0 8px}.item p{margin:0 0 16px}.status{display:inline-block;border:1px solid #b8c6bc;background:#f4f7f4;border-radius:99px;padding:5px 10px;font-size:.85rem}footer{margin-top:28px;border-top:1px solid #d7e0d8;padding-top:18px;color:#456050}
</style>
</head>
<body>
<main>
<p><a href="<?=kcmc_h(kcmc_url('admin/'))?>">← Back to administration</a></p>
<p class="status">Optional capabilities</p>
<h1>Available upgrades</h1>
<p class="intro">Your Core application works independently. These additional capabilities may be available under a separate agreement and installation process. They are not included, installed, unlocked or billed from this screen.</p>
<div class="grid">
<?php foreach ($modules as [$title,$description]): ?>
<section class="item"><h2><?=kcmc_h($title)?></h2><p><?=kcmc_h($description)?></p><span class="status">Ask your software provider</span></section>
<?php endforeach; ?>
</div>
<footer>Upgrades require separate authorization, compatibility testing, secure installation and rollback verification. No payment or automatic installation occurs here.</footer>
</main>
</body>
</html>
