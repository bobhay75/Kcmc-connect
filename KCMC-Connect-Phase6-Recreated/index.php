<?php
require_once __DIR__ . '/lib/bootstrap.php';
$kcmc = kcmc_content();
$member = kcmc_current_user();
$memberCanPray = $member !== null && kcmc_has_role(['member', 'prayer_team', 'pastor_admin'], $member);
$kcmcNews = is_array($kcmc['news'] ?? null) ? $kcmc['news'] : [];
$kcmcEvents = kcmc_active_items($kcmc['events'] ?? []);
usort($kcmcEvents, fn($a,$b)=>strcmp((string)($a['date']??''),(string)($b['date']??'')));
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
<meta property="og:image" content="assets/visuals/kimberling-city-missouri-bridge-2024.jpg?v=3.0.0">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Church","name":"Kimberling City Methodist Church","address":{"@type":"PostalAddress","streetAddress":"57 Kimberling City Center Lane","addressLocality":"Kimberling City","addressRegion":"MO","postalCode":"65686","addressCountry":"US"},"telephone":"+1-417-739-4395","email":"secretary@umckc.org"}</script>
<title>KCMC Connect</title>
<link rel="manifest" href="manifest.webmanifest?v=3.0.0">
<link rel="preload" as="image" href="assets/visuals/kimberling-city-missouri-bridge-2024.jpg?v=3.0.0" type="image/jpeg" fetchpriority="high">
<link rel="stylesheet" href="styles.css?v=3.0.0">
<link rel="icon" href="assets/icons/icon-192.png?v=3.0.0">
<link rel="apple-touch-icon" href="assets/icons/icon-192.png?v=3.0.0">
</head>
<body>
<?php if (!empty($kcmcAnnouncements)): $top=$kcmcAnnouncements[0]; ?>
<div class="phase6-announcement" role="status"><div class="shell"><strong><?=kcmc_h((string)($top['title']??''))?></strong><span><?=kcmc_h((string)($top['body']??''))?></span></div></div>
<?php endif; ?>
<a class="skip-link" href="#mainContent">Skip to content</a>
<div class="offline-banner" id="offlineBanner" role="status">You’re offline. Saved KCMC Connect pages are still available.</div>
<header class="topbar">
  <div class="wrap inner">
    <a class="brand" href="#home" data-route="home" aria-label="KCMC Connect home"><span class="mark">K</span><span><strong>KCMC CONNECT</strong><small>Kimberling City Methodist Church</small></span></a>
    <nav class="desktop-nav" aria-label="Primary">
      <a href="#visit" data-route="visit">I’m New</a><a href="#watch" data-route="watch">Watch</a><a href="#news" data-route="news">News</a><a href="#events" data-route="events">Events</a><a href="#serve" data-route="serve">Serve</a><a href="#partner" data-route="partner">Connect</a>
    </nav>
    <a class="topbar-account" href="<?=kcmc_h(kcmc_url($member ? 'member/' : 'member/login.php'))?>"><?=$member ? 'Member home' : 'Member sign in'?></a>
    <button class="install" type="button" data-install-app>Save app</button>
  </div>
</header>

<main id="mainContent">
<section class="view active" data-view="home">
  <section class="hero hero-imagery">
    <img class="hero-photo" src="./assets/visuals/kimberling-city-missouri-bridge-2024.jpg?v=3.0.0" alt="Highway 13 crossing Table Rock Lake on the Kimberling City Bridge in Kimberling City, Missouri" loading="eager" decoding="async" fetchpriority="high">
    <div class="wrap hero-grid">
      <div>
        <div class="eyebrow">Kimberling City • Table Rock Lake</div>
        <h1>One church.<br>Connected all week.</h1>
        <p class="lead">Worship, church news, events, care, serving and giving—all in one simple place.</p>
        <div class="install-callout" data-install-callout>
          <span class="install-callout-icon" aria-hidden="true">↓</span>
          <span class="install-callout-copy"><strong>Keep KCMC one touch away</strong><span data-install-message>Save KCMC Connect to this device for quick access.</span></span>
          <button class="btn gold install-callout-button" type="button" data-install-app>Save to Home Screen</button>
        </div>
        <div class="actions">
          <a class="action" href="#watch" data-route="watch"><b>Watch</b><span>Live & recent worship</span></a>
          <a class="action" href="https://www.simplechurchgiving.net/app/giving/umckc" target="_blank" rel="noopener"><b>Give</b><span>Secure online giving</span></a>
          <a class="action" href="care.php"><b>Prayer</b><span>Verified members only</span></a>
          <a class="action" href="#visit" data-route="visit"><b>Visit</b><span>Plan your first Sunday</span></a>
        </div>
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

  <section class="section visual-story-section" aria-label="KCMC in the Ozarks">
    <div class="wrap visual-story">
      <figure class="mission-visual">
        <img src="./assets/visuals/kimberling-city-missouri-bridge-2024.jpg?v=3.0.0" loading="eager" decoding="async" alt="Kimberling City Bridge carrying Highway 13 across Table Rock Lake, photographed in 2024">
        <figcaption><span class="eyebrow">Mission statement</span><strong>Leading people to become deeply committed followers of Jesus Christ.</strong></figcaption>
      </figure>
      <figure class="ministry-visual">
        <img src="./assets/visuals/kcmc-ministry-group.jpg" loading="eager" decoding="async" alt="Children and leaders taking part in KCMC ministry">
        <figcaption><span class="eyebrow">KCMC ministry</span><strong>Faith lived together.</strong><span>Children, families and volunteers growing together through worship and service.</span></figcaption>
      </figure>
    </div>
  </section>

  <section class="section current-update" aria-label="Current KCMC ministry highlights">
    <div class="wrap">
      <div class="section-head"><div><div class="eyebrow"><?=kcmc_h((string)($kcmcNews['month']??'Church News'))?> • Issue #<?=kcmc_h((string)($kcmcNews['issue']??''))?></div><h2>New beginnings at KCMC.</h2></div><p>Stories, ministry updates, fall events and ways to connect at KCMC.</p></div>
      <div class="stat-grid">
        <?php foreach(array_slice($kcmcNews['highlights']??[],0,4) as $highlight): ?><article class="stat-card"><strong><?=kcmc_h((string)($highlight['stat']??''))?></strong><span><?=kcmc_h((string)($highlight['label']??''))?></span></article><?php endforeach; ?>
      </div>
      <div class="btns"><a class="btn gold" href="#news" data-route="news">Read September news</a><a class="btn secondary" href="#events" data-route="events">See current events</a></div>
    </div>
  </section>

  <section class="section alt">
    <div class="wrap">
      <div class="section-head"><div><div class="eyebrow">Sunday worship</div><h2>Choose your experience</h2></div><p>All three Sunday services are at Kimberling City Methodist Church, 57 Kimberling City Center Lane.</p></div>
      <div class="grid3">
        <article class="card"><div class="time">8:00 AM</div><h3>Front Porch Gospel</h3><p>Old-time country and bluegrass Gospel music with an uplifting Bible-based message.</p></article>
        <article class="card"><div class="time">9:15 AM</div><h3>Traditional Worship</h3><p>Hymns, piano, organ and choir in a traditional worship setting.</p></article>
        <article class="card"><div class="time">10:30 AM</div><h3>Contemporary Worship</h3><p>A relaxed coffee-shop setting with fellowship, refreshments and Launch Kids.</p></article>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap video-card">
      <div class="video-art contemporary-art"><div><span class="pill">Featured this week</span><br><br><b>Contemporary<br>Worship</b></div></div>
      <div class="video-copy"><div class="eyebrow">Last week at KCMC</div><h2 style="font-family:Georgia,serif;font-size:3rem;font-weight:400;margin:.15em 0">Catch up before Sunday.</h2><p class="muted">Watch last week’s contemporary service on Facebook, then jump into the live room for the next broadcast.</p><div class="btns"><a class="btn gold" href="https://www.facebook.com/share/v/14s1bqo8acA/" target="_blank" rel="noopener">Watch featured video</a><a class="btn secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">All live videos</a></div></div>
    </div>
  </section>

  <section class="section alt">
    <div class="wrap contact-strip"><div><div class="eyebrow">Need a person?</div><h2>Call the church office.</h2><p class="muted">Tuesday–Thursday, 8:00 AM–4:00 PM • (417) 739-4395 • secretary@umckc.org</p></div><div class="btns" style="align-content:center"><a class="btn gold" href="tel:+14177394395">Call now</a><a class="btn secondary" href="mailto:secretary@umckc.org">Email</a></div></div>
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
  <section class="section"><div class="wrap video-card"><div class="video-art watch-art"><div><span class="pill">Official livestream</span><br><br><b>Sunday<br>Online</b></div></div><div class="video-copy"><h2 class="section-title">Live when KCMC is live.</h2><p class="muted">When the church is not broadcasting, the same destination provides recent live videos and replays.</p><div class="btns"><a class="btn gold" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">Open live room</a><a class="btn secondary" href="https://www.facebook.com/share/v/14s1bqo8acA/" target="_blank" rel="noopener">Featured contemporary service</a></div></div></div></section>
  <section class="section alt"><div class="wrap"><div class="section-head"><div><div class="eyebrow">Sermon library</div><h2>Watch. Reflect. Share.</h2></div><p>Find current messages and worship services from KCMC.</p></div><div class="library-toolbar"><label class="search-field"><span class="sr-only">Search sermons</span><input id="sermonSearch" type="search" placeholder="Search sermons, series or speaker"></label><select id="sermonFilter" aria-label="Filter sermons"><option value="all">All services</option><option value="contemporary">Contemporary</option></select></div><div class="sermon-grid" id="sermonGrid"><article class="sermon-card" data-search="contemporary worship featured service" data-type="contemporary"><div class="sermon-thumb contemporary-art"></div><div><span class="pill">Contemporary</span><h3>Featured contemporary service</h3><p class="muted">Watch the current featured service, then browse the official live-video archive for additional messages.</p><div class="btns"><a class="btn" href="https://www.facebook.com/share/v/14s1bqo8acA/" target="_blank" rel="noopener">Watch service</a></div></div></article></div></div></section>
</section>

<section class="view" data-view="news">
  <div class="wrap partner-hero"><div class="eyebrow">Church News • <?=kcmc_h((string)($kcmcNews['month']??''))?> • Issue #<?=kcmc_h((string)($kcmcNews['issue']??''))?></div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0"><?=kcmc_h((string)($kcmcNews['title']??'The Bridge to Salvation'))?></h1><p class="lead muted">News, ministry updates and opportunities to connect at KCMC.</p></div>
  <section class="section">
    <div class="wrap stat-grid news-stats" aria-label="September KCMC highlights"><?php foreach(array_slice($kcmcNews['highlights']??[],0,4) as $highlight): ?><article class="stat-card"><strong><?=kcmc_h((string)($highlight['stat']??''))?></strong><span><?=kcmc_h((string)($highlight['label']??''))?></span></article><?php endforeach; ?></div>
    <div class="wrap news-layout">
      <?php $reflection=is_array($kcmcNews['reflection']??null)?$kcmcNews['reflection']:[]; ?><article class="news-feature"><div class="eyebrow">Pastoral reflection</div><h3><?=kcmc_h((string)($reflection['title']??'New Beginnings'))?></h3><p><?=kcmc_h((string)($reflection['body']??''))?></p><p><b>Scripture:</b> <?=kcmc_h((string)($reflection['scripture']??''))?>.</p></article>
      <div class="news-list">
        <?php foreach($kcmcNews['sections']??[] as $section): ?><article class="news-item"><span class="pill"><?=kcmc_h((string)($section['label']??'Church News'))?></span><h3><?=kcmc_h((string)($section['title']??''))?></h3><p><?=kcmc_h((string)($section['body']??''))?></p></article><?php endforeach; ?>
      </div>
    </div>
    <div class="wrap newsletter-text-grid">
      <article class="news-item"><span class="pill important">Groups</span><h3>Find your weekly rhythm</h3><ul><?php foreach($kcmcNews['groups']??[] as $item): ?><li><?=kcmc_h((string)$item)?></li><?php endforeach; ?></ul></article>
      <article class="news-item"><span class="pill important">Ways to help</span><h3>Practical ministry this month</h3><ul><?php foreach($kcmcNews['outreach']??[] as $item): ?><li><?=kcmc_h((string)$item)?></li><?php endforeach; ?></ul></article>
    </div>
  </section>
</section>
<section class="view" data-view="events">
  <div class="wrap partner-hero"><div class="eyebrow">Events</div><h1 class="display-title">What’s next at KCMC.</h1><p class="lead muted">Upcoming September gatherings, studies and ministry events, with one-tap calendar saves and RSVP contact.</p></div>
  <section class="section"><div class="wrap grid3 event-grid">
    <?php if(!$kcmcEvents): ?><p>No current events are published.</p><?php endif; ?>
    <?php foreach($kcmcEvents as $event): ?><article class="card event-card" data-event="<?=kcmc_h((string)($event['title']??''))?>" data-date="<?=kcmc_h((string)($event['date']??''))?>" data-time="<?=kcmc_h((string)($event['time']??''))?>"><span class="pill"><?=kcmc_h(date('M j',strtotime((string)($event['date']??''))))?></span><h3><?=kcmc_h((string)($event['title']??''))?></h3><p><?=kcmc_h((string)($event['time']??''))?> • <?=kcmc_h((string)($event['location']??'KCMC'))?></p><div class="btns"><button class="btn event-rsvp" type="button">RSVP</button><button class="btn secondary add-calendar" type="button">Add to calendar</button></div></article><?php endforeach; ?>
  </div><div class="wrap form-wrap"><form class="form-card compact" id="eventForm" data-kcmc-form="event" data-subject="KCMC Event RSVP" novalidate><div class="eyebrow">Event RSVP</div><h2>Let KCMC know you’re interested.</h2><input type="hidden" name="event" id="eventName"><div class="field-row"><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div><label>Event<input id="eventDisplay" value="Choose RSVP above" readonly></label><label>Note<textarea name="message" rows="3" placeholder="Questions, number attending, or anything the team should know"></textarea></label><button class="btn gold" type="submit">Send RSVP</button><p class="form-status" role="status" aria-live="polite"></p></form></div><div class="wrap" style="margin-top:18px"><div class="notice">Questions about an event? Call the church office at (417) 739-4395.</div></div></section>
</section>

<section class="view" data-view="serve">
  <div class="wrap partner-hero"><div class="eyebrow">Serve</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Turn everyday things into ministry.</h1><p class="lead muted">Practical ways to serve our congregation and community this September.</p></div>
  <section class="section"><div class="wrap serve-grid">
    <article class="serve-card"><span class="pill important">WEB Kids</span><h3>Pack weekend food bags</h3><p>Volunteers meet Thursdays at 9:00 AM at Reeds Spring Primary to pack 100 bags for K–4 students.</p></article>
    <article class="serve-card"><span class="pill">WEB Kids</span><h3>Best Choice barcodes</h3><p>Save Best Choice barcodes from boxes and cans; proceeds support the WEB Kids program.</p></article>
    <article class="serve-card"><span class="pill">Methodist Women</span><h3>Harter House receipts</h3><p>Save full receipts from the Kimberling City Harter House for mission work.</p></article>
    <article class="serve-card"><span class="pill">Ronald McDonald House</span><h3>Aluminum pull tabs</h3><p>Save aluminum pull tabs from soda cans for Ronald McDonald House support.</p></article>
    <article class="serve-card"><span class="pill">Music</span><h3>Join choir or handbells</h3><p>Bring your voice or learn to ring handbells as KCMC prepares music that leads the church in worship.</p></article>
    <article class="serve-card"><span class="pill">Church life</span><h3>Find your place</h3><p>Call the church office to ask about current volunteer openings across KCMC ministries.</p></article>
  </div><div class="wrap form-wrap"><form class="form-card compact" data-kcmc-form="serve" data-subject="I Want to Serve at KCMC" novalidate><div class="eyebrow">Volunteer</div><h2>Find a place to serve.</h2><div class="field-row"><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div><label>I’m interested in<select name="interest"><option>Not sure — help me find a fit</option><option>Kids / Youth</option><option>Worship / Music</option><option>Hospitality / Welcome</option><option>Care / Prayer</option><option>Community Outreach</option><option>Facilities / Practical Help</option></select></label><label>Tell us a little about your availability or interests<textarea name="message" rows="4"></textarea></label><button class="btn gold" type="submit">Send my interest</button><p class="form-status" role="status" aria-live="polite"></p></form></div></section>
</section>

<section class="view" data-view="partner">
  <div class="wrap partner-hero"><div class="eyebrow">Partner Hub</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Your church week, in one place.</h1><p class="lead muted">Announcements, serving, prayer, giving and the latest Church News.</p></div>
  <section class="section"><div class="wrap announcement-stack">
    <article class="announcement"><span class="pill important">September News</span><h3>New beginnings • outreach • fall connection</h3><p>Issue #16 brings ministry updates, September events, Bible studies, music and practical ways to serve.</p><div class="btns"><a class="btn" href="#news" data-route="news">Read current news</a></div></article>
    <article class="announcement"><span class="pill">This week</span><h3>Use the app for worship, care and current links</h3><p>The official livestream, online giving, visit planning, office contact and current service information are all one tap away.</p></article>
    <article class="announcement"><span class="pill">Find Your People</span><h3>Groups and connection</h3><p>Looking for a small group, care connection, Bible study or ministry community? Send an interest note below and the church can help connect you.</p></article>
  </div><div class="wrap connection-grid form-wrap">
    <article class="form-card"><div class="eyebrow">Prayer & care</div><h2>A trusted room for prayer.</h2><div class="privacy-lock"><span class="privacy-lock-icon" aria-hidden="true">🔒</span><div><h3>Members only</h3><p>Prayer names, medical details and request content stay behind verified sign-in. Tony or Barry approves anything shared with members.</p></div></div><div class="btns"><?php if($memberCanPray): ?><a class="btn gold" href="<?=kcmc_h(kcmc_url('member/'))?>">Open member prayer</a><?php elseif($member): ?><a class="btn gold" href="<?=kcmc_h(kcmc_url('member/'))?>">Open secure account</a><?php else: ?><a class="btn gold" href="<?=kcmc_h(kcmc_url('member/login.php'))?>">Member sign in</a><?php endif; ?><a class="btn secondary" href="care.php">Prayer privacy</a></div></article>
    <form class="form-card" data-kcmc-form="groups" data-subject="KCMC Connection / Group Interest" novalidate><div class="eyebrow">Find Your People</div><h2>Help me get connected.</h2><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label><label>I’m looking for<select name="interest"><option>Small group / Bible study</option><option>Kids / family connection</option><option>Youth</option><option>Care / support</option><option>Men’s ministry</option><option>Women’s ministry</option><option>I’m new and not sure yet</option></select></label><label>Anything else?<textarea name="message" rows="4"></textarea></label><button class="btn gold" type="submit">Help me connect</button><p class="form-status" role="status" aria-live="polite"></p></form>
  </div><div class="wrap preferences"><div><div class="eyebrow">This device</div><h2>Remember my preferred service</h2><p class="muted">Optional preference is stored only on this device.</p></div><label>Preferred Sunday service<select id="preferredService"><option value="">No preference</option><option>8:00 AM — Front Porch Gospel</option><option>9:15 AM — Traditional Worship</option><option>10:30 AM — Contemporary Worship</option></select></label></div></section>
</section>
</main>

<footer class="footer"><div class="wrap footer-grid"><div><strong>KCMC CONNECT</strong><p>Kimberling City Methodist Church<br>57 Kimberling City Center Lane<br>Kimberling City, MO 65686</p></div><div><p>(417) 739-4395<br><a href="mailto:secretary@umckc.org">secretary@umckc.org</a><br><a href="https://www.facebook.com/KimberlingCityMethodistChurch" target="_blank" rel="noopener">KCMC on Facebook</a></p><p class="fine">Leading people to become deeply committed followers of Jesus Christ.</p></div></div></footer>

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
<script src="app.js?v=3.0.0" defer></script>
<a class="phase6-bulletin-fab" href="bulletin.php">Latest Bulletin</a>
</body></html>
