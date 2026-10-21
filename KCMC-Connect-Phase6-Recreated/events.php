<?php
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/event-calendar.php';
require_once __DIR__ . '/lib/public-features.php';
$d = kcmc_content();
$calendar = kcmc_public_event_calendar($d['events'] ?? [], 'upcoming', $_GET['event_scope'] ?? null);
$events = $calendar['events'];
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Upcoming events at Kimberling City Methodist Church.">
  <title>Events • KCMC Connect</title>
  <link rel="stylesheet" href="styles.css?v=3.0.0">
  <style>
    .page{width:min(900px,calc(100% - 30px));margin:45px auto 80px}.eventx{background:var(--kcmc-panel, #fff);color:var(--kcmc-text, #18232c);border:1px solid var(--kcmc-line, #dfe5e8);border-radius:18px;margin:18px 0;overflow:hidden;box-shadow:0 10px 32px rgba(0,0,0,.12)}.eventx img{display:block;width:100%;height:auto}.eventx-copy{padding:22px}.eventx small{font-weight:800;color:var(--kcmc-muted, #476477)}.eventx h2{margin:.3em 0}.eventx p{color:var(--kcmc-muted, #41515b);margin:.45em 0}.eventx .detail{font-weight:750}.eventx .label{display:inline-block;margin-bottom:8px;padding:5px 9px;border-radius:999px;background:var(--kcmc-warning-bg, #fff0d1);color:var(--kcmc-warning, #744d10);font-size:.76rem;font-weight:850;text-transform:uppercase;letter-spacing:.06em}
    .eventx-disclosure>summary{cursor:pointer;min-height:48px;padding:8px 0}.eventx-disclosure>summary h2{display:inline;font-size:1.45rem}.eventx-disclosure[open]>summary{margin-bottom:14px}
  </style>
<?php require_once __DIR__ . '/lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
</head>
<body><?php echo kcmc_screen_navigation('', false); ?>
<main class="page" id="events">
  <a href="./#events">← KCMC Connect</a>
  <p class="eyebrow">WHAT’S HAPPENING</p>
  <h1>Upcoming events</h1>
  <nav class="btns" aria-label="Event calendar view">
      <a class="btn secondary" href="?event_scope=<?= $calendar['scope']==='calendar'?'events':'calendar' ?>"><?= $calendar['scope']==='calendar'?'Community events':'Church calendar' ?></a>
    </nav>
    <p class="muted">Showing published gatherings.</p>
  <?php if(!$events): ?><p>No current events are published.</p><?php endif; ?>
  <?php foreach($events as $event):
    $image = (string)($event['image'] ?? '');
    $hasImage = preg_match('#\Aassets/visuals/[A-Za-z0-9][A-Za-z0-9._-]*\z#', $image) === 1;
    $detailsOnSlide = $hasImage && ($event['id'] ?? '') === 'trunk-or-treat-2026';
    $time = (string)($event['time'] ?? '');
    $endTime = (string)($event['end_time'] ?? '');
    $timeLabel = $endTime !== '' ? $time . '–' . $endTime : $time;
  ?>
    <article class="eventx">
      <?php if($hasImage): ?><img src="<?=kcmc_h($image.($detailsOnSlide?'?v=event-slide-20261020':''))?>" alt="<?=kcmc_h((string)($event['image_alt'] ?? ''))?>" loading="lazy" decoding="async"><?php endif; ?>
      <div class="eventx-copy"><details class="eventx-disclosure"><summary><h2><?=kcmc_h((string)($event['title'] ?? ''))?></h2></summary><div>
        <?php if(!$detailsOnSlide): ?><small><time datetime="<?=kcmc_h((string)($event['date'] ?? ''))?>"><?=kcmc_h(date('l, F j, Y', strtotime((string)($event['date'] ?? ''))))?></time> • <?=kcmc_h($timeLabel)?></small><?php endif; ?>
        <p class="detail"><?=kcmc_h((string)($event['location'] ?? 'KCMC'))?></p>
        <?php if(!empty($event['address'])): ?><p><?=kcmc_h((string)$event['address'])?></p><?php endif; ?>
        <?php if(!empty($event['description'])): ?><p><?=kcmc_h((string)$event['description'])?></p><?php endif; ?>
      </div></details></div>
    </article>
  <?php endforeach; ?>
</main>
</body>
</html>
