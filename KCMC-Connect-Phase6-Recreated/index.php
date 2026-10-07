<?php
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/public-presentation.php';
$kcmc = kcmc_public_content();
$member = kcmc_current_user_if_session();
$memberCanPray = $member !== null && kcmc_has_role(['member', 'prayer_team', 'pastor_admin'], $member);
$kcmcContact = is_array($kcmc['contact'] ?? null) ? $kcmc['contact'] : [];
$kcmcPhone = (string)($kcmc['contact']['phone'] ?? '417-739-4395');
$kcmcPhoneHref = 'tel:' . preg_replace('/[^0-9+]/', '', $kcmcPhone);
$kcmcEmail = kcmc_valid_email((string)($kcmcContact['email'] ?? '')) ? kcmc_normalize_email((string)$kcmcContact['email']) : 'secretary@umckc.org';
$kcmcEmailHref = 'mailto:' . $kcmcEmail;
$kcmcAddress = trim((string)($kcmcContact['address'] ?? '57 Kimberling City Center Lane, Kimberling City, MO 65686'));
$kcmcOfficeHours = trim((string)($kcmcContact['office_hours'] ?? 'Tuesday–Thursday, 9:00 AM–4:00 PM'));
$kcmcSchema = json_encode([
  '@context' => 'https://schema.org',
  '@type' => 'Church',
  'name' => 'Kimberling City Methodist Church',
  'address' => $kcmcAddress,
  'telephone' => $kcmcPhone,
  'email' => $kcmcEmail,
], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?: '{}';
$kcmcEvents = kcmc_active_items($kcmc['events'] ?? []);
usort($kcmcEvents, 'kcmc_compare_event_start');
$kcmcHasRsvpEvents = count(array_filter($kcmcEvents, fn($event)=>!array_key_exists('rsvp',$event)||$event['rsvp']!==false)) > 0;
$kcmcAnnouncements = kcmc_active_items($kcmc['announcements'] ?? []);
usort($kcmcAnnouncements, fn($a,$b)=>(int)($b['priority']??0)<=>(int)($a['priority']??0));
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d2235">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="KCMC Connect">
<meta name="description" content="KCMC Connect — plan a visit, worship, church news, events, prayer, serving and giving for Kimberling City Methodist Church in Kimberling City, Missouri.">
<meta name="robots" content="index,follow">
<meta name="color-scheme" content="dark">
<meta property="og:title" content="KCMC Connect | Kimberling City Methodist Church">
<meta property="og:description" content="Plan a visit, watch worship, find events, request prayer and connect with KCMC.">
<meta property="og:type" content="website">
<meta property="og:image" content="assets/visuals/kcmc-building-2024.webp">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json"><?=$kcmcSchema?></script>
<title>KCMC Connect</title>
<link rel="manifest" href="manifest.webmanifest?v=3.0.1">
<link rel="preload" as="image" href="assets/visuals/kcmc-building-2024.webp" type="image/webp" fetchpriority="high">
<link rel="stylesheet" href="styles.css?v=3.0.3">
<link rel="stylesheet" href="public-presentation.css?v=contemporary-bright-20261007">
<link rel="icon" href="assets/icons/icon-192.png?v=3.0.1">
<link rel="apple-touch-icon" href="assets/icons/icon-192.png?v=3.0.1">
</head>
<body data-office-email="<?=kcmc_h($kcmcEmail)?>">
<?php if (!empty($kcmcAnnouncements)): $top=$kcmcAnnouncements[0]; ?>
<div class="phase6-announcement" role="status"><div class="shell"><strong><?=kcmc_h((string)($top['title']??''))?></strong><span><?=kcmc_h((string)($top['body']??''))?></span></div></div>
<?php endif; ?>
<a class="skip-link" href="#mainContent">Skip to content</a>
<div class="offline-banner" id="offlineBanner" role="status">You’re offline. Saved KCMC Connect pages are still available.</div>
<p class="sr-only" data-share-status role="status" aria-live="polite" aria-atomic="true"></p>
<header class="topbar">
  <div class="wrap inner">
    <a class="brand" href="#home" data-route="home" aria-label="KCMC Connect home"><span class="mark">K</span><span><strong>KCMC CONNECT</strong><small>Kimberling City Methodist Church</small></span></a>
    <nav class="desktop-nav" aria-label="Primary">
      <a href="#visit" data-route="visit">I’m New</a><a href="#watch" data-route="watch">Watch</a><a href="#news" data-route="news">Updates</a><a href="#events" data-route="events">Events</a><a href="#serve" data-route="serve">Serve</a><a href="#partner" data-route="partner">Connect</a>
    </nav>
    <a class="header-give" href="https://www.simplechurchgiving.net/app/giving/umckc" target="_blank" rel="noopener">Give</a>
    <details class="site-menu" id="siteMenu">
      <summary aria-controls="siteMenuLinks">Menu</summary>
      <nav id="siteMenuLinks" aria-label="More navigation">
        <a href="#visit" data-route="visit">Plan a visit</a>
        <a href="#watch" data-route="watch">Watch messages</a>
        <a href="#news" data-route="news">Church updates</a>
        <a href="#events" data-route="events">Events</a>
        <a href="bulletin.php">Latest bulletin</a>
        <a href="care.php">Prayer &amp; care</a>
        <a href="#serve" data-route="serve">Serving</a>
        <a href="https://www.simplechurchgiving.net/app/giving/umckc" target="_blank" rel="noopener">Give online</a>
        <button type="button" data-share-app>Share KCMC Connect</button>
        <a class="menu-account" href="<?=kcmc_h(kcmc_url($member ? 'member/' : 'admin/login.php'))?>"><?=$member ? 'My account' : 'Staff Sign In'?></a>
        <?php if($member && kcmc_has_role(['pastor_admin', 'recovery_admin'], $member)): ?><a href="<?=kcmc_h(kcmc_url('admin/'))?>">Administration</a><?php endif; ?>
      </nav>
    </details>
    <button class="install" type="button" data-install-app>Save app</button>
    <button class="install" type="button" data-share-app aria-label="Share KCMC Connect">Share</button>
  </div>
</header>

<main id="mainContent">
<section class="view active" data-view="home">
  <section class="hero hero-imagery" data-hero-gallery aria-label="Welcome to KCMC">
    <img class="hero-photo is-current" data-hero-photo src="./assets/visuals/kcmc-building-2024.webp" alt="Kimberling City Methodist Church exterior, photographed in 2024" loading="eager" decoding="async" fetchpriority="high" width="640" height="513">
    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-worship-2017.webp" alt="People gathered for worship at KCMC, photographed in 2017" loading="lazy" decoding="async" width="640" height="344" hidden>
    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-stage-2014.webp" alt="KCMC worship stage, photographed in 2014" loading="lazy" decoding="async" width="640" height="480" hidden>
    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-ministry-group.jpg" alt="KCMC church family and ministry group" loading="lazy" decoding="async" width="640" height="480" hidden>
    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-congregation-gathering.jpg" alt="People seated around tables facing the KCMC worship stage" loading="lazy" decoding="async" width="2048" height="1105" hidden>
    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-family-outdoor-event.jpg" alt="Children and adults enjoying balloons and an inflatable slide at a Kimberling City outdoor event" loading="lazy" decoding="async" width="2048" height="1536" hidden>
    <img class="hero-photo" data-hero-photo style="object-fit:contain" src="./assets/visuals/kcmc-bridge-logo.jpg" alt="Kimberling City Methodist Church logo with a blue bridge and black cross" loading="lazy" decoding="async" width="1156" height="1156" hidden>
    <img class="hero-photo" data-hero-photo style="object-fit:contain" src="./assets/visuals/kcmc-bridge-wordmark.png" alt="Kimberling City Methodist Church bridge and cross logo over a sunset bridge photograph" loading="lazy" decoding="async" width="2048" height="706" hidden>
    <img class="hero-photo" data-hero-photo style="object-fit:contain" src="./assets/visuals/kcmc-bridge-logo-composite.png" alt="Sunset bridge photograph with the Kimberling City Methodist Church logo inset at lower right" loading="lazy" decoding="async" width="2048" height="1144" hidden>
    <div class="wrap hero-grid">
      <div>
        <div class="eyebrow">Welcome to Kimberling City Methodist Church</div>
        <h1>Come as you are.<br>Find your people.</h1>
        <p class="lead">Join us for worship, get to know our church, and find your next step. There’s a place for you at KCMC.</p>
        <div class="install-callout" data-install-callout>
          <span class="install-callout-icon" aria-hidden="true">↓</span>
          <span class="install-callout-copy"><strong>Keep KCMC one touch away</strong><span data-install-message>Save KCMC Connect to this device for quick access.</span></span>
          <button class="btn gold install-callout-button" type="button" data-install-app>Save to Home Screen</button>
        </div>
        <div class="actions">
          <a class="action" href="#watch" data-route="watch"><b>Watch</b><span>Live & recent worship</span></a>
          <a class="action" href="https://www.simplechurchgiving.net/app/giving/umckc" target="_blank" rel="noopener"><b>Give</b><span>Secure online giving</span></a>
          <a class="action" href="care.php"><b>Care</b><span>Talk with our church team</span></a>
          <a class="action" href="#visit" data-route="visit"><b>Visit</b><span>Plan your first Sunday</span></a>
        </div>
        <div class="hero-photo-controls" data-hero-controls hidden>
          <button type="button" data-hero-previous aria-label="Previous church photo">←</button>
          <button type="button" data-hero-toggle>Pause photos</button>
          <button type="button" data-hero-next aria-label="Next church photo">→</button>
        </div>
        <p class="sr-only" data-hero-status role="status" aria-live="polite"></p>
      </div>
      <aside class="hero-card" aria-label="Next worship services">
        <span class="pill">Sunday worship</span>
        <div class="service-time">8:00 • 9:15 • 10:30</div>
        <h2>Three expressions. One church.</h2>
        <p>Front Porch Gospel, Traditional Worship, and Contemporary Worship each offer a distinct style with a common mission.</p>
        <div class="btns"><a class="btn gold" href="#watch" data-route="watch">Watch worship</a><a class="btn secondary" href="https://maps.app.goo.gl/W6kRCHvbaVJ7mwte7" target="_blank" rel="noopener">Directions</a></div>
      </aside>
    </div>
  </section>

  <section class="section" aria-label="KCMC kids and family photos">
    <div class="wrap grid3" data-kcmc-photo-gallery>
      <div><img style="display:block;width:100%;height:auto;border-radius:18px" src="./assets/visuals/kcmc-family-outdoor-event.jpg" alt="Children and adults enjoying balloons and an inflatable slide at a Kimberling City outdoor event" loading="lazy" decoding="async" width="2048" height="1536"></div>
      <div><img style="display:block;width:100%;height:auto;border-radius:18px" src="./assets/visuals/kcmc-kids-safari.jpg" alt="Children seated in a decorated safari cart inside KCMC" loading="lazy" decoding="async" width="2048" height="1536"></div>
      <div><img style="display:block;width:100%;height:auto;border-radius:18px" src="./assets/visuals/kcmc-kids-game-room.jpg" alt="Children playing foosball and other table games in the KCMC game room" loading="lazy" decoding="async" width="2048" height="1289"></div>
    </div>
  </section>

  <section class="section welcome-next">
    <div class="wrap">
      <div class="section-head"><div><div class="eyebrow">Life together</div><h2>Your next step starts here.</h2></div><p>Leading people to become deeply committed followers of Jesus Christ.</p></div>
      <div class="grid3">
        <article class="card"><h3>New to KCMC?</h3><p>Find service times, directions and a friendly way to introduce yourself.</p><div class="btns"><a class="btn" href="#visit" data-route="visit">Plan your visit</a></div></article>
        <article class="card"><h3>This week</h3><p>Find the church bulletin and the gatherings published by our team.</p><div class="btns"><a class="btn" href="bulletin.php">Read the bulletin</a><a class="btn secondary" href="#events" data-route="events">See events</a></div></article>
        <article class="card"><h3>Get connected</h3><p>Ask about groups, serving, or finding your place in church life.</p><div class="btns"><a class="btn" href="#partner" data-route="partner">Get connected</a></div></article>
      </div>
    </div>
  </section>

  <section class="section alt">
    <div class="wrap">
      <div class="section-head"><div><div class="eyebrow">Sunday worship</div><h2>Choose your experience</h2></div><p>All three Sunday services are at Kimberling City Methodist Church, <?=kcmc_h($kcmcAddress)?>.</p></div>
      <div class="grid3">
        <article class="card"><div class="time">8:00 AM</div><h3>Front Porch Gospel</h3><p>Old-time country and bluegrass Gospel music with an uplifting Bible-based message.</p></article>
        <article class="card"><div class="time">9:15 AM</div><h3>Traditional Worship</h3><p>Hymns, piano, organ and choir in a traditional worship setting.</p></article>
        <article class="card"><div class="time">10:30 AM</div><h3>Contemporary Worship</h3><p>A relaxed coffee-shop setting with fellowship, refreshments and Launch Kids.</p></article>
      </div>
    </div>
  </section>

  <!-- KCMC_CONTEMPORARY_FEATURE_20261002 BEGIN -->
  <section class="section cw-section" data-contemporary-feature aria-labelledby="cw-title">
    <div class="wrap">
      <div class="cw-feature">
        <div class="cw-copy">
          <p class="cw-kicker">Sunday mornings <span>10:30 AM</span></p>
          <h2 id="cw-title">Contemporary<br><span>Worship.</span></h2>
          <p class="cw-intro">Come as you are. Find your place.</p>
          <p class="cw-description">A relaxed, coffee-shop setting with fellowship, refreshments, and an uplifting message from the Bible.</p>
          <p class="cw-family">Bringing the family? Launch Kids meets during the 10:30 service.</p>
          <div class="cw-actions">
            <a class="cw-button cw-primary" href="#visit" data-route="visit">Plan your Sunday <span aria-hidden="true">&#8594;</span></a>
            <a class="cw-button cw-secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener noreferrer">Watch messages</a>
          </div>
          <p class="cw-online-note">Messages and worship are on our official Facebook page. Facebook may ask you to sign in.</p>
        </div>
        <div class="cw-media">
          <img src="assets/visuals/kcmc-worship-2017.webp" alt="People gathered around tables for worship at KCMC, photographed in 2017" width="640" height="344" loading="lazy" decoding="async">
        </div>
      </div>
    </div>
  </section>
  <!-- KCMC_CONTEMPORARY_FEATURE_20261002 END -->

  <section class="section alt">
    <div class="wrap contact-strip"><div><div class="eyebrow">Need a person?</div><h2>Call the church office.</h2><p class="muted"><?=kcmc_h($kcmcOfficeHours)?> • <?=kcmc_h($kcmcPhone)?> • <?=kcmc_h($kcmcEmail)?></p></div><div class="btns" style="align-content:center"><a class="btn gold" href="<?=kcmc_h($kcmcPhoneHref)?>">Call now</a><a class="btn secondary" href="<?=kcmc_h($kcmcEmailHref)?>">Email</a></div></div>
  </section>
</section>


<section class="view" data-view="visit">
  <div class="wrap partner-hero"><div class="eyebrow">I’m New</div><h1 class="display-title">Your first Sunday should feel simple.</h1><p class="lead muted">Pick the worship style that fits you, get directions, and tell the welcome team you’re coming if you’d like someone ready to meet you.</p></div>
  <section class="section"><div class="wrap visit-grid">
    <div>
      <div class="section-head"><div><div class="eyebrow">What to expect</div><h2>Come as you are.</h2></div></div>
      <div class="expect-list">
        <article class="expect"><b>Three Sunday options</b><span>8:00 AM Front Porch Gospel • 9:15 AM Traditional • 10:30 AM Contemporary.</span></article>
        <article class="expect"><b>Warm, relaxed welcome</b><span>KCMC describes its worship as a place to connect with God and community, with music and Bible-based teaching.</span></article>
        <article class="expect"><b>Kids at 10:30</b><span>Launch Kids Children’s Church coincides with the Contemporary service.</span></article>
        <article class="expect"><b>One easy destination</b><span>57 Kimberling City Center Lane, Kimberling City, MO 65686.</span></article>
        <article class="expect"><b>Accessibility or arrival question?</b><span>Call the church office at (417) 739-4395 before your visit and the team can help with your specific need.</span></article>
      </div>
      <div class="btns"><a class="btn gold" href="https://maps.app.goo.gl/W6kRCHvbaVJ7mwte7" target="_blank" rel="noopener">Get directions</a><a class="btn secondary" href="tel:+14177394395">Call the office</a></div>
    </div>
    <form class="form-card" data-kcmc-form="visit" data-subject="I’m Coming This Sunday" novalidate>
      <div class="eyebrow">Plan a visit</div><h2>I’m coming this Sunday</h2><p class="muted">Send the welcome team your details. Nothing here creates a member account.</p>
      <div class="field-row"><label>First name<input name="firstName" autocomplete="given-name" required></label><label>Last name<input name="lastName" autocomplete="family-name" required></label></div>
      <label>Email<input type="email" name="email" autocomplete="email" required></label>
      <label>Phone<input type="tel" name="phone" autocomplete="tel"></label>
      <label>Service<select name="service" required><option value="">Choose a service</option><option>8:00 AM — Front Porch Gospel</option><option>9:15 AM — Traditional Worship</option><option>10:30 AM — Contemporary Worship</option></select></label>
      <label>Anything we can help with?<textarea name="message" rows="4" placeholder="Kids, accessibility, where to meet, or anything else"></textarea></label>
      <button class="btn gold" type="submit">Tell the welcome team</button><p class="form-status" role="status" aria-live="polite"></p>
    </form>
  </div></section>
  <section class="section alt"><div class="wrap"><div class="section-head"><div><div class="eyebrow">Choose your service</div><h2>Same church. Different expression.</h2></div></div><div class="grid3"><article class="card"><div class="time">8:00</div><h3>Front Porch Gospel</h3><p>Old-time country and bluegrass Gospel with an uplifting Bible-based message.</p></article><article class="card"><div class="time">9:15</div><h3>Traditional</h3><p>Hymns, piano, organ and choir with teaching based on the Bible.</p></article><article class="card"><div class="time">10:30</div><h3>Contemporary</h3><p>A laid-back coffee-shop setting with fellowship, refreshments and Launch Kids.</p></article></div></div></section>
</section>

<section class="view" data-view="watch">
  <div class="wrap partner-hero"><div class="eyebrow">Watch</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Worship wherever you are.</h1><p class="lead muted">Use the official Facebook live room for current broadcasts and recent services.</p></div>
  <section class="section"><div class="wrap video-card"><div class="video-art watch-art"><div><span class="pill">Official livestream</span><br><br><b>Sunday<br>Online</b></div></div><div class="video-copy"><h2 class="section-title">Live when KCMC is live.</h2><p class="muted">When the church is not broadcasting, the same destination provides recent live videos and replays.</p><div class="btns"><a class="btn gold" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">Open live room</a><a class="btn secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">KCMC messages and worship</a></div></div></div></section>
  <section class="section alt"><div class="wrap"><div class="section-head"><div><div class="eyebrow">Message library</div><h2>Watch. Reflect. Share.</h2></div><p>Find current messages and worship services from KCMC.</p></div><div class="library-toolbar"><label class="search-field"><span class="sr-only">Search messages</span><input id="sermonSearch" type="search" placeholder="Search messages, series or speaker"></label><select id="sermonFilter" aria-label="Filter messages"><option value="all">All services</option><option value="contemporary">Contemporary</option></select></div><div class="sermon-grid" id="sermonGrid"><article class="sermon-card" data-search="kcmc messages worship contemporary service" data-type="contemporary"><div class="sermon-thumb contemporary-art"></div><div><span class="pill">Contemporary</span><h3>KCMC messages and worship</h3><p class="muted">Browse messages and worship in the official KCMC video archive. Facebook may require sign-in.</p><div class="btns"><a class="btn" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">Watch service</a></div></div></article></div></div></section>
</section>

<section class="view" data-view="news">
  <div class="wrap partner-hero"><div class="eyebrow">Church updates</div><h1 class="display-title">Stay connected this week.</h1><p class="lead muted">The latest bulletin, published announcements and upcoming gatherings.</p></div>
  <section class="section"><div class="wrap">
    <div class="btns"><a class="btn gold" href="bulletin.php">Latest bulletin</a><a class="btn secondary" href="#events" data-route="events">Upcoming events</a><a class="btn secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch" target="_blank" rel="noopener">KCMC on Facebook</a></div>
    <div class="announcement-stack">
    <?php foreach($kcmcAnnouncements as $item): ?><article class="announcement"><h2><?=kcmc_h((string)($item['title']??''))?></h2><p><?=kcmc_h((string)($item['body']??''))?></p></article><?php endforeach; ?>
    <?php if(!$kcmcAnnouncements): ?><p class="muted">Check the bulletin and events for the latest published information.</p><?php endif; ?>
    </div>
  </div></section>
</section>
<section class="view" data-view="events">
  <div class="wrap partner-hero"><div class="eyebrow">Events</div><h1 class="display-title">What’s next at KCMC.</h1><p class="lead muted">Upcoming gatherings, studies and community events, with one-tap calendar saves and easy ways to connect.</p></div>
  <section class="section"><div class="wrap grid3 event-grid">
    <?php if(!$kcmcEvents): ?><p>No current events are published.</p><?php endif; ?>
    <?php foreach($kcmcEvents as $event):
      $eventTitle=(string)($event['title']??'');
      $eventDate=(string)($event['date']??'');
      $eventImage=(string)($event['image']??'');
      $hasEventImage=preg_match('#\Aassets/visuals/[A-Za-z0-9][A-Za-z0-9._-]*\z#',$eventImage)===1;
      $eventTime=(string)($event['time']??'');
      $eventEndTime=(string)($event['end_time']??'');
      $eventTimeLabel=$eventEndTime!==''?$eventTime.'–'.$eventEndTime:$eventTime;
      $eventLocation=(string)($event['location']??'KCMC');
      $eventAddress=(string)($event['address']??$kcmcAddress);
      $calendarLocation=$eventLocation.($eventAddress!==''?', '.$eventAddress:'');
      $rsvpEnabled=!array_key_exists('rsvp',$event)||$event['rsvp']!==false;
    ?>
      <article class="card event-card<?=$hasEventImage?' has-image':''?>"
        data-event="<?=kcmc_h($eventTitle)?>"
        data-date="<?=kcmc_h($eventDate)?>"
        data-time="<?=kcmc_h($eventTime)?>"
        data-end-time="<?=kcmc_h($eventEndTime)?>"
        data-location="<?=kcmc_h($calendarLocation)?>"
        data-description="<?=kcmc_h((string)($event['description']??''))?>">
        <?php if($hasEventImage): ?><img class="event-image" src="<?=kcmc_h($eventImage)?>" alt="<?=kcmc_h((string)($event['image_alt']??''))?>" loading="lazy" decoding="async"><?php endif; ?>
        <div class="event-card-copy">
          <div class="event-pills"><time class="pill" datetime="<?=kcmc_h($eventDate)?>"><?=kcmc_h(date('D, M j',strtotime($eventDate)))?></time><?php if(!empty($event['label'])): ?><span class="pill important"><?=kcmc_h((string)$event['label'])?></span><?php endif; ?></div>
          <h3><?=kcmc_h($eventTitle)?></h3>
          <p class="event-when"><strong><?=kcmc_h($eventTimeLabel)?></strong> • <?=kcmc_h($eventLocation)?></p>
          <?php if(!empty($event['description'])): ?><p class="event-description"><?=kcmc_h((string)$event['description'])?></p><?php endif; ?>
          <div class="btns"><?php if($rsvpEnabled): ?><button class="btn event-rsvp" type="button" aria-label="RSVP for <?=kcmc_h($eventTitle)?>">RSVP</button><?php else: ?><a class="btn" href="<?=kcmc_h($kcmcPhoneHref)?>" aria-label="Call KCMC with questions about <?=kcmc_h($eventTitle)?>">Event questions</a><?php endif; ?><button class="btn secondary add-calendar" type="button" aria-label="Add <?=kcmc_h($eventTitle)?> to calendar">Add to calendar</button></div>
        </div>
      </article>
    <?php endforeach; ?>
  </div><?php if($kcmcHasRsvpEvents): ?><div class="wrap form-wrap"><form class="form-card compact" id="eventForm" data-kcmc-form="event" data-subject="KCMC Event RSVP" novalidate><div class="eyebrow">Event RSVP</div><h2>Let KCMC know you’re interested.</h2><input type="hidden" name="event" id="eventName"><div class="field-row"><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div><label>Event<input id="eventDisplay" value="Choose RSVP above" readonly></label><label>Note<textarea name="message" rows="3" placeholder="Questions, number attending, or anything the team should know"></textarea></label><button class="btn gold" type="submit">Send RSVP</button><p class="form-status" role="status" aria-live="polite"></p></form></div><?php endif; ?><div class="wrap" style="margin-top:18px"><div class="notice">Questions about an event? Call the church office at <?=kcmc_h($kcmcPhone)?>.</div></div></section>
</section>

<section class="view" data-view="serve">
  <div class="wrap partner-hero"><div class="eyebrow">Serve</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Turn everyday things into ministry.</h1><p class="lead muted">Share your interests with our church team and ask about current opportunities to serve.</p></div>
  <section class="section"><div class="wrap serve-grid">
    <article class="serve-card"><span class="pill">Start here</span><h3>Find a place to serve</h3><p>Tell the team about your interests and availability using the form below. The church can help you find an active opportunity.</p></article>
    <article class="serve-card"><span class="pill">Talk with us</span><h3>Have a question?</h3><p>Call the church office to ask what is needed now before making plans.</p><div class="btns"><a class="btn" href="<?=kcmc_h($kcmcPhoneHref)?>">Call the church</a></div></article>
  </div><div class="wrap form-wrap"><form class="form-card compact" data-kcmc-form="serve" data-subject="I Want to Serve at KCMC" novalidate><div class="eyebrow">Volunteer</div><h2>Find a place to serve.</h2><div class="field-row"><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div><label>I’m interested in<select name="interest"><option>Not sure — help me find a fit</option><option>Kids / Youth</option><option>Worship / Music</option><option>Hospitality / Welcome</option><option>Care / Prayer</option><option>Community Outreach</option><option>Facilities / Practical Help</option></select></label><label>Tell us a little about your availability or interests<textarea name="message" rows="4"></textarea></label><button class="btn gold" type="submit">Send my interest</button><p class="form-status" role="status" aria-live="polite"></p></form></div></section>
</section>

<section class="view" data-view="partner">
  <div class="wrap partner-hero"><div class="eyebrow">Partner Hub</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Your church week, in one place.</h1><p class="lead muted">Find your next step, ask for support, and get connected with our church team.</p></div>
  <section class="section"><div class="wrap announcement-stack">

    <article class="announcement"><span class="pill">This week</span><h3>Use the app for worship, care and current links</h3><p>The official livestream, online giving, visit planning, office contact and current service information are all one tap away.</p></article>
    <article class="announcement"><span class="pill">Find Your People</span><h3>Groups and connection</h3><p>Looking for a small group, care connection, Bible study or ministry community? Send an interest note below and the church can help connect you.</p></article>
  </div><div class="wrap connection-grid form-wrap">
    <article class="form-card"><div class="eyebrow">Prayer &amp; care</div><h2>You don’t have to do life alone.</h2><p class="muted">Reach out to the church office for prayer or support. Personal prayer details are not displayed on the public app.</p><div class="btns"><a class="btn gold" href="<?=kcmc_h($kcmcPhoneHref)?>">Call the church</a><a class="btn secondary" href="care.php">Prayer &amp; care</a></div></article>
    <form class="form-card" data-kcmc-form="groups" data-subject="KCMC Connection / Group Interest" novalidate><div class="eyebrow">Find Your People</div><h2>Help me get connected.</h2><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label><label>I’m looking for<select name="interest"><option>Small group / Bible study</option><option>Kids / family connection</option><option>Youth</option><option>Care / support</option><option>Men’s ministry</option><option>Women’s ministry</option><option>I’m new and not sure yet</option></select></label><label>Anything else?<textarea name="message" rows="4"></textarea></label><button class="btn gold" type="submit">Help me connect</button><p class="form-status" role="status" aria-live="polite"></p></form>
  </div><div class="wrap preferences"><div><div class="eyebrow">This device</div><h2>Remember my preferred service</h2><p class="muted">Optional preference is stored only on this device.</p></div><label>Preferred Sunday service<select id="preferredService"><option value="">No preference</option><option>8:00 AM — Front Porch Gospel</option><option>9:15 AM — Traditional Worship</option><option>10:30 AM — Contemporary Worship</option></select></label></div></section>
</section>
</main>

<footer class="footer"><div class="wrap footer-grid"><div><strong>KCMC CONNECT</strong><p>Kimberling City Methodist Church<br><?=kcmc_h($kcmcAddress)?></p></div><div><p><?=kcmc_h($kcmcPhone)?><br><a href="<?=kcmc_h($kcmcEmailHref)?>"><?=kcmc_h($kcmcEmail)?></a><br><a href="https://www.facebook.com/KimberlingCityMethodistChurch" target="_blank" rel="noopener">KCMC on Facebook</a></p><p class="fine">Leading people to become deeply committed followers of Jesus Christ.</p></div></div></footer>

<nav class="mobile-nav" aria-label="Mobile navigation"><a href="#home" data-route="home"><span>⌂</span>Home</a><a href="#visit" data-route="visit"><span>◎</span>Visit</a><a href="#watch" data-route="watch"><span>▶</span>Watch</a><a href="#events" data-route="events"><span>◇</span>Events</a><a href="#partner" data-route="partner"><span>✦</span>Connect</a></nav>
<div class="install-sheet" id="installSheet" role="dialog" aria-modal="true" aria-labelledby="installSheetTitle" hidden>
  <div class="install-sheet-card" tabindex="-1">
    <button class="install-sheet-close" type="button" aria-label="Close install instructions" data-install-close>×</button>
    <div class="eyebrow" data-install-eyebrow>Keep KCMC close</div>
    <h2 id="installSheetTitle">Add KCMC to your Home Screen</h2>
    <div class="install-sheet-copy" data-install-sheet-copy></div>
    <button class="btn gold install-sheet-native" type="button" data-install-native hidden>Install KCMC Connect</button>
    <p class="install-sheet-note">After it is saved, KCMC Connect opens from your screen like an app.</p>
  </div>
</div>
<script src="app.js?v=3.0.2" defer></script>
<script src="public-presentation.js?v=tony-bright-photos-20261007" defer></script>
<a class="phase6-bulletin-fab" href="bulletin.php">Latest Bulletin</a>
</body></html>