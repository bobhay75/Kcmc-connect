<?php
require_once __DIR__ . '/lib/bootstrap.php';
$content = kcmc_content();
$bulletin = is_array($content['bulletin'] ?? null) ? $content['bulletin'] : [];
$services = array_values(array_filter($bulletin['services'] ?? [], 'is_array'));
$notes = array_values(array_filter($bulletin['notes'] ?? [], fn($note): bool => is_string($note) && trim($note) !== ''));
$date = trim((string)($bulletin['date'] ?? ''));
$dateLabel = $date !== '' && strtotime($date) !== false ? date('Sunday, F j, Y', strtotime($date)) : 'Current Sunday information';
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d2235">
<meta name="description" content="Current Sunday worship information for Kimberling City Methodist Church.">
<title><?=kcmc_h((string)($bulletin['title'] ?? 'Sunday at KCMC'))?> • KCMC Connect</title>
<link rel="stylesheet" href="styles.css?v=3.0.0">
<style>
body{background:linear-gradient(180deg,#0d2235 0,#17384f 25rem,#eef2f3 25rem);color:#10263a}.bulletin-page{width:min(1040px,calc(100% - 28px));margin:0 auto;padding:26px 0 70px}.bulletin-back{display:inline-flex;color:#fff;text-decoration:none;font-weight:850;margin:6px 0 25px}.bulletin-hero{color:#fff;padding:8px 4px 30px}.bulletin-hero h1{font-family:Georgia,serif;font-size:clamp(2.7rem,7vw,5.2rem);line-height:.98;font-weight:400;margin:.16em 0}.bulletin-hero p{max-width:760px;color:#dfe9ee;font-size:1.08rem;line-height:1.65}.bulletin-sheet{background:#fffdf8;border-radius:26px;box-shadow:0 20px 55px rgba(0,0,0,.22);overflow:hidden}.bulletin-section{padding:30px 34px;border-top:1px solid #e8e2d8}.bulletin-section:first-child{border-top:0}.bulletin-section h2{font-family:Georgia,serif;font-size:clamp(1.8rem,4vw,2.55rem);font-weight:400;margin:0 0 18px}.service-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.service-card{background:#f4ecdf;border:1px solid #e1d4bf;border-radius:17px;padding:20px}.service-card strong{display:block;font-size:1.45rem;color:#a45c11}.service-card h3{margin:.35rem 0 .45rem}.service-card p{line-height:1.55;margin:0;color:#4f5d66}.bulletin-notes{margin:0;padding-left:1.2rem}.bulletin-notes li{margin:.75rem 0;line-height:1.6}.bulletin-actions{display:flex;gap:10px;flex-wrap:wrap}.bulletin-actions a{display:inline-flex;padding:12px 17px;border-radius:999px;text-decoration:none;font-weight:850;background:#0d2235;color:#fff}.bulletin-actions a.alt{background:#fff;color:#0d2235;border:1px solid #ccd4d8}.bulletin-fine{color:#607080;font-size:.9rem;margin-top:18px}@media(max-width:760px){.service-grid{grid-template-columns:1fr}.bulletin-section{padding:24px 20px}.bulletin-hero h1{font-size:3.15rem}}
</style>
</head>
<body>
<main class="bulletin-page">
<a class="bulletin-back" href="./#home">← KCMC Connect</a>
<header class="bulletin-hero">
<p class="eyebrow">SUNDAY BULLETIN • <?=kcmc_h($dateLabel)?></p>
<h1><?=kcmc_h((string)($bulletin['title'] ?? 'Sunday at KCMC'))?></h1>
<p><?=kcmc_h((string)($bulletin['welcome'] ?? 'Come as you are. Grow in faith. Serve the Ozarks.'))?></p>
</header>
<article class="bulletin-sheet">
<section class="bulletin-section">
<h2>Join us for worship</h2>
<div class="service-grid">
<?php foreach ($services as $service): ?>
<article class="service-card"><strong><?=kcmc_h((string)($service['time'] ?? ''))?></strong><h3><?=kcmc_h((string)($service['name'] ?? 'Worship'))?></h3><p><?=kcmc_h((string)($service['detail'] ?? ''))?></p></article>
<?php endforeach; ?>
</div>
</section>
<section class="bulletin-section">
<h2>This week at KCMC</h2>
<?php if ($notes): ?><ul class="bulletin-notes"><?php foreach ($notes as $note): ?><li><?=kcmc_h($note)?></li><?php endforeach; ?></ul><?php else: ?><p>Leadership has not published additional bulletin notes yet.</p><?php endif; ?>
</section>
<section class="bulletin-section">
<h2>Stay connected</h2>
<div class="bulletin-actions"><a href="./#watch">Watch KCMC</a><a class="alt" href="care.php">Prayer &amp; care</a><a class="alt" href="./#events">Events</a></div>
<p class="bulletin-fine">Prayer requests and prayer details are available only after verified member sign-in.</p>
</section>
</article>
</main>
</body>
</html>
