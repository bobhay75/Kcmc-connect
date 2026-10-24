<?php
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/event-calendar.php';
$d = kcmc_content();
$calendar = kcmc_event_calendar($d['events'] ?? [], $_GET['event_view'] ?? null);
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
  </style>
<?php require_once __DIR__ . '/lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
</head>
<body><?php echo kcmc_screen_navigation('', false); ?>
<main class="page" id="events">
  <a href="./#events">← KCMC Connect</a>
  <p class="eyebrow">WHAT’S HAPPENING</p>
  <h1>Upcoming events</h1>
  <nav class="btns" aria-label="Event calendar view">
      <a class="btn <?= $calendar['view']==='upcoming'?'gold':'secondary' ?>" href="?event_view=upcoming#events"<?= $calendar['view']==='upcoming'?' aria-current="page"':'' ?>>Upcoming</a>
      <a class="btn <?= $calendar['view']==='next-week'?'gold':'secondary' ?>" href="?event_view=next-week#events"<?= $calendar['view']==='next-week'?' aria-current="page"':'' ?>>Next week</a>
    </nav>
    <p class="muted"><?= $calendar['view']==='next-week'?'Next week: '.kcmc_h($calendar['range']).' · Sunday–Saturday · Central time':'Showing the next occurrence of each published event.' ?></p>
  <?php if(!$events): ?><p><?= $calendar['view']==='next-week'?'No events are published for next week. Choose Upcoming to see other dates.':'No current events are published.' ?></p><?php endif; ?>
  <?php foreach($events as $event):
    $image = (string)($event['image'] ?? '');
    // Restore the established artwork when Trunk or Treat has no assigned image.
    if ($image === '' && preg_match('/trunk\s*(?:or|&)\s*treat/i', (string)($event['title'] ?? ''))) {
      $image = 'assets/visuals/trunk-or-treat-2026.svg';
    }
    $hasImage = preg_match('#\Aassets/visuals/[A-Za-z0-9][A-Za-z0-9._-]*\z#', $image) === 1;
    $time = (string)($event['time'] ?? '');
    $endTime = (string)($event['end_time'] ?? '');
    $timeLabel = $endTime !== '' ? $time . '–' . $endTime : $time;
  ?>
    <article class="eventx">
      <?php if($hasImage): ?><img src="<?=kcmc_h($image)?>" alt="<?=kcmc_h((string)($event['image_alt'] ?? ''))?>" loading="lazy" decoding="async"><?php endif; ?>
      <div class="eventx-copy">
        <?php if(!empty($event['label'])): ?><span class="label"><?=kcmc_h((string)$event['label'])?></span><?php endif; ?>
        <small><time datetime="<?=kcmc_h((string)($event['date'] ?? ''))?>"><?=kcmc_h(date('l, F j, Y', strtotime((string)($event['date'] ?? ''))))?></time> • <?=kcmc_h($timeLabel)?></small>
        <h2><?=kcmc_h((string)($event['title'] ?? ''))?></h2>
        <p class="detail"><?=kcmc_h((string)($event['location'] ?? 'KCMC'))?></p>
        <?php if(!empty($event['address'])): ?><p><?=kcmc_h((string)$event['address'])?></p><?php endif; ?>
        <?php if(!empty($event['description'])): ?><p><?=kcmc_h((string)$event['description'])?></p><?php endif; ?>
      </div>
    </article>
  <?php endforeach; ?>
</main>
</body>
</html>
