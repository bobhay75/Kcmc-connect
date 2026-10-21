<?php
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/public-features.php';
header('Cache-Control: no-store');
$content = kcmc_content();
$bulletin = is_array($content['bulletin'] ?? null) ? $content['bulletin'] : [];
$services = array_values(array_filter($bulletin['services'] ?? [], 'is_array'));
$notes = array_values(array_filter($bulletin['notes'] ?? [], fn($note): bool => is_string($note) && trim($note) !== ''));
$currentBulletin = kcmc_bulletin_is_current($bulletin);
if (!$currentBulletin) {
    $bulletin['title'] = 'Weekly bulletin being updated';
    $bulletin['welcome'] = 'This week’s bulletin has not been confirmed yet. Contact the church office for the latest details.';
    $notes = [];
}
$date = trim((string)($bulletin['date'] ?? ''));
$dateLabel = $currentBulletin && $date !== '' && strtotime($date) !== false ? date('l, F j, Y', strtotime($date)) : 'Awaiting this week’s update';
$contact = is_array($content['contact'] ?? null) ? $content['contact'] : [];
$phone = trim((string)($contact['phone'] ?? '417-739-4395'));
$phoneHref = 'tel:' . preg_replace('/[^0-9+]/', '', $phone);
$email = kcmc_valid_email((string)($contact['email'] ?? '')) ? kcmc_normalize_email((string)$contact['email']) : 'secretary@umckc.org';
$address = trim((string)($contact['address'] ?? '57 Kimberling City Center Lane, Kimberling City, MO 65686'));
$officeHours = trim((string)($contact['office_hours'] ?? ''));
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d2235">
<meta name="description" content="The current digital weekly bulletin for Kimberling City Methodist Church.">
<title><?=kcmc_h((string)($bulletin['title'] ?? 'Sunday at KCMC'))?> • KCMC Connect</title>
<link rel="stylesheet" href="styles.css?v=3.0.0">
<style>
body{margin:0;background:#0d2235;color:#f8f5ec}.bulletin-page{width:min(900px,calc(100% - 28px));margin:24px auto 64px}.bulletin-toolbar{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 18px}.bulletin-toolbar a{color:#f8f5ec;text-underline-offset:4px}.bulletin-print{font:inherit;font-weight:700;background:#e7b34f;color:#10263a;border:0;border-radius:5px;padding:12px 18px;cursor:pointer}.bulletin-print[hidden]{display:none}.bulletin-paper{--bulletin-ink:#162f40;--bulletin-muted:#4c6069;--kcmc-text:#162f40;--kcmc-muted:#4c6069;color-scheme:light;background:#fffdf6;color:var(--bulletin-ink);padding:42px 48px;box-shadow:0 14px 42px #0004}.bulletin-paper h1,.bulletin-paper h2,.bulletin-paper h3{color:var(--bulletin-ink);line-height:1.3}.bulletin-masthead{text-align:center;border-bottom:3px double #ac8846;padding-bottom:26px;margin-bottom:24px}.bulletin-church{font-family:Georgia,serif;font-size:clamp(1.6rem,5vw,2.5rem);line-height:1.25;letter-spacing:.01em;margin:0 0 10px}.bulletin-mission{font-family:Georgia,serif;font-style:italic;color:#765314;margin:8px 0 20px}.bulletin-issue{font-size:.78rem;font-weight:750;letter-spacing:.1em;text-transform:uppercase;color:var(--bulletin-muted)}.bulletin-masthead h1{font-family:Georgia,serif;font-size:clamp(1.6rem,4vw,2.15rem);font-weight:400;margin:18px 0 10px}.bulletin-welcome{font-size:1rem;line-height:1.7;margin:0;color:var(--bulletin-muted)}.bulletin-section-label{font-size:.76rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:#765314;margin:28px 0 8px}.bulletin-hint{font-size:.9rem;color:var(--bulletin-muted);margin:0 0 8px}.bulletin-entry{border-bottom:1px solid #d9d1bd}.bulletin-entry>summary{display:block;list-style:none;cursor:pointer;position:relative;padding:20px 34px 20px 0;min-height:48px}.bulletin-entry>summary::-webkit-details-marker{display:none}.bulletin-entry>summary::after{content:'+';position:absolute;right:4px;top:20px;color:#765314;font:1.4rem/1 Georgia,serif}.bulletin-entry[open]>summary::after{content:'−'}.bulletin-entry>summary:focus-visible{outline:3px solid #a36d17;outline-offset:3px}.bulletin-entry h2,.bulletin-entry h3{font-family:Georgia,serif;font-weight:400;font-size:1.3rem;margin:0}.bulletin-service-time{display:inline-block;min-width:108px;font-family:Arial,sans-serif;font-size:1rem;font-weight:750;color:#765314}.bulletin-detail{padding:0 0 22px;line-height:1.7;overflow-wrap:anywhere}.bulletin-detail p{margin:0 0 10px;white-space:pre-line;color:var(--bulletin-muted)}.bulletin-detail ul{padding-left:1.2rem;margin:0}.bulletin-detail li{margin:0 0 14px;white-space:pre-line}.bulletin-detail a,.bulletin-links a{color:#173f59;text-decoration:underline;text-underline-offset:4px}.bulletin-links{display:flex;flex-wrap:wrap;gap:16px;margin-top:26px;padding-top:18px;border-top:3px double #ac8846}.bulletin-footnote{margin:22px 0 0;color:var(--bulletin-muted);font-size:.85rem;line-height:1.6}@media(max-width:600px){.bulletin-page{width:calc(100% - 20px);margin-top:16px}.bulletin-paper{padding:28px 22px}.bulletin-toolbar{font-size:.9rem}.bulletin-service-time{display:block;margin-bottom:5px}.bulletin-entry h2,.bulletin-entry h3{font-size:1.2rem}}@media print{body{background:#fff!important;color:#000!important}.screen-navigation,.bulletin-toolbar,.bulletin-hint{display:none!important}.bulletin-page{width:auto;max-width:none;margin:0;padding:0}.bulletin-paper{padding:0;box-shadow:none;background:#fff;color:#000}.bulletin-masthead{break-after:avoid}.bulletin-entry>summary{padding:14px 0 10px;min-height:0;break-after:avoid}.bulletin-entry>summary::after{display:none}.bulletin-detail{padding-bottom:12px}.bulletin-entry{border-bottom:1px solid #bbb}.bulletin-links{display:none}.bulletin-detail a{color:#000}.bulletin-paper p,.bulletin-detail li{orphans:3;widows:3}@page{margin:16mm}}
</style>
<?php require_once __DIR__ . '/lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
</head>
<body><?php echo kcmc_screen_navigation('', false); ?>
<main class="bulletin-page">
<nav class="bulletin-toolbar" aria-label="Bulletin controls"><a href="./#news">← Back to church updates</a><button type="button" class="bulletin-print" id="bulletinPrint" hidden>Print bulletin</button></nav>
<article class="bulletin-paper">
<header class="bulletin-masthead">
<p class="bulletin-church">Kimberling City<br>Methodist Church</p>
<p class="bulletin-mission">Called to love and serve.</p>
<p class="bulletin-issue">Weekly bulletin · <?=kcmc_h($dateLabel)?></p>
<h1><?=kcmc_h((string)($bulletin['title'] ?? 'Sunday at KCMC'))?></h1>
<p class="bulletin-welcome"><?=kcmc_h((string)($bulletin['welcome'] ?? 'There is a place for you here.'))?></p>
</header>
<p class="bulletin-hint">Select a heading to read the details.</p>
<p class="bulletin-section-label">Sunday worship</p>
<?php foreach ($services as $service): ?>
<details class="bulletin-entry"><summary><h2><span class="bulletin-service-time"><?=kcmc_h((string)($service['time'] ?? ''))?></span> <?=kcmc_h((string)($service['name'] ?? 'Worship'))?></h2></summary><div class="bulletin-detail"><p><?=kcmc_h((string)($service['detail'] ?? ''))?></p><a href="./#watch">Watch worship services</a></div></details>
<?php endforeach; ?>
<p class="bulletin-section-label">Church life</p>
<details class="bulletin-entry"><summary><h2>This week at KCMC</h2></summary><div class="bulletin-detail">
<?php if ($notes): ?><ul><?php foreach ($notes as $note): ?><li><?=kcmc_h($note)?></li><?php endforeach; ?></ul><?php else: ?><p>This week’s bulletin notes have not been confirmed. Please contact the church office.</p><?php endif; ?>
</div></details>
<details class="bulletin-entry"><summary><h2>Church office &amp; contact</h2></summary><div class="bulletin-detail"><p><?=kcmc_h($address)?></p><?php if ($officeHours !== ''): ?><p>Office hours: <?=kcmc_h($officeHours)?></p><?php endif; ?><p><a href="<?=kcmc_h($phoneHref)?>">Call <?=kcmc_h($phone)?></a></p><p><a href="<?=kcmc_h('mailto:' . $email)?>"><?=kcmc_h($email)?></a></p></div></details>
<nav class="bulletin-links" aria-label="Church links"><a href="./#events">Upcoming events</a><a href="care.php">Prayer &amp; care</a><a href="./#home">KCMC Connect home</a></nav>
<p class="bulletin-footnote">Prayer requests and prayer details are available only after verified member sign-in.</p>
</article>
</main>
<script>
(() => {
  const entries = Array.from(document.querySelectorAll('.bulletin-entry'));
  let savedState = null;
  const expandForPrint = () => {
    if (savedState !== null) return;
    savedState = entries.map(entry => entry.open);
    entries.forEach(entry => { entry.open = true; });
  };
  const restoreAfterPrint = () => {
    if (savedState === null) return;
    entries.forEach((entry, index) => { entry.open = savedState[index]; });
    savedState = null;
  };
  window.addEventListener('beforeprint', expandForPrint);
  window.addEventListener('afterprint', restoreAfterPrint);
  const button = document.getElementById('bulletinPrint');
  button.hidden = false;
  button.addEventListener('click', () => { expandForPrint(); window.print(); });
})();
</script>
</body>
</html>
