<?php
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/event-calendar.php';
require_once __DIR__ . '/lib/public-presentation.php';
require_once __DIR__ . '/lib/public-features.php';
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
$worshipServices = kcmc_worship_services($kcmc);
$calendar = kcmc_public_event_calendar($kcmc['events'] ?? [], 'upcoming', $_GET['event_scope'] ?? null);
$kcmcEvents = $calendar['events'];
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
<meta property="og:image" content="assets/visuals/kcmc-building-original-20261018.jpg">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json"><?=$kcmcSchema?></script>
<title>KCMC Connect</title>
<link rel="manifest" href="manifest.webmanifest?v=20261019">
<link rel="preload" as="image" href="assets/visuals/kcmc-building-original-20261018.jpg" type="image/jpeg" fetchpriority="high">
<link rel="stylesheet" href="styles.css?v=3.0.3">
<link rel="stylesheet" href="public-presentation.css?v=fish-only-home-20261014">
<link rel="icon" href="assets/icons/icon-192.png?v=20261019">
<link rel="apple-touch-icon" href="assets/icons/icon-192.png?v=20261019">
<?php require_once __DIR__ . '/lib/screen-navigation.php'; echo kcmc_screen_assets(); ?>
<link rel="stylesheet" href="home-welcome.css?v=bulletin-disclosures-20261020">
</head>
<body class="kcmc-welcome-design" data-office-email="<?=kcmc_h($kcmcEmail)?>">
<a class="skip-link" href="#mainContent">Skip to content</a>
<div class="offline-banner" id="offlineBanner" role="status">You’re offline. Saved KCMC Connect pages are still available.</div>
<p class="sr-only" data-share-status role="status" aria-live="polite" aria-atomic="true"></p>
<header class="topbar">
  <div class="wrap inner">
    <details class="site-menu fish-menu" id="siteMenu">
      <summary aria-controls="siteMenuLinks" aria-label="KCMC Connect menu">
        <img src="./assets/icons/icon-192.png" alt="" aria-hidden="true" width="56" height="56">
      </summary>
      <nav id="siteMenuLinks" aria-label="KCMC Connect navigation">
        <?=kcmc_screen_back($member ? 'member/' : '')?>
        <a class="menu-home" href="#home" data-route="home" aria-label="Home"><strong>KCMC CONNECT</strong><small>Kimberling City Methodist Church</small></a>
        <a href="#visit" data-route="visit">Plan a visit</a>
        <a href="#watch" data-route="watch">Watch messages</a>
        <a href="#news" data-route="news">Announcements &amp; church updates</a>
        <a href="#events" data-route="events">Events</a>
        <a href="bulletin.php">Latest bulletin</a>
        <a href="care.php">Prayer &amp; care</a>
        <a href="#serve" data-route="serve">Serving</a>
        <a href="#partner" data-route="partner">Get connected</a>
        <a href="https://www.kimberlingcitymethodist.com/youth" target="_blank" rel="noopener">Kids &amp; youth</a>
        <a href="<?=kcmc_h($kcmcPhoneHref)?>">Call the church office</a>
        <a href="<?=kcmc_h($kcmcEmailHref)?>">Email the church office</a>
        <a href="https://www.facebook.com/KimberlingCityMethodistChurch" target="_blank" rel="noopener">KCMC on Facebook</a>
        <button type="button" data-share-app data-share-visit>Invite someone this Sunday</button>
        <a class="header-give" href="https://www.simplechurchgiving.net/app/giving/umckc" target="_blank" rel="noopener">Give online</a>
        <button type="button" data-install-app>Save app</button>
        <button type="button" data-share-app>Share KCMC Connect</button>
        <a class="menu-account" href="<?=kcmc_h(kcmc_url($member ? 'member/' : 'admin/login.php'))?>"><?=$member ? 'My account' : 'Staff Sign In'?></a>
        <?php if($member): ?><a href="<?=kcmc_h(kcmc_url('member/timeclock.php'))?>">Time clock</a><?php endif; ?>
        <?php if($member && kcmc_has_role(['pastor_admin', 'recovery_admin'], $member)): ?><a href="<?=kcmc_h(kcmc_url('admin/home.php'))?>">Administration</a><?php endif; ?>
      </nav>
    </details>
    <a class="welcome-brand" href="#home" data-route="home" aria-label="KCMC Connect home">KCMC CONNECT</a>
    <nav class="welcome-nav" aria-label="Main pages"><a href="#home" data-route="home">Home</a><a href="#visit" data-route="visit">Visit</a><a href="#events" data-route="events">Events</a><a href="care.php">Prayer</a><a href="<?=kcmc_h(kcmc_url($member ? 'member/' : 'admin/login.php'))?>"><?=$member ? 'My account' : 'Sign In'?></a></nav>
  </div>
</header>

<main id="mainContent">
<section class="view active" data-view="home">
  <section class="hero hero-imagery home-cover" aria-label="Welcome to KCMC">
    <img class="home-cover-photo" data-authentic-building src="./assets/visuals/kcmc-building-original-20261018.jpg" alt="Original photograph of Kimberling City Methodist Church with its natural sky and clouds" loading="eager" decoding="async" fetchpriority="high" width="1536" height="1229">
    <div class="wrap home-cover-layout"><div class="home-cover-card">
      <h1>Welcome Home</h1>
      <div class="welcome-hero-actions"><a class="btn gold" href="#visit" data-route="visit">Plan Your Visit <span aria-hidden="true">&#160;›</span></a><a class="btn secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">Watch Online <span aria-hidden="true">&#160;›</span></a></div>
    </div></div>
  </section>
  <section class="home-worship-strip" aria-label="Sunday worship at KCMC"><div class="wrap home-worship-strip-inner"><div class="home-worship-times"><span class="eyebrow">Sunday Services</span><strong>8:00 AM <span aria-hidden="true">•</span> 9:15 AM <span aria-hidden="true">•</span> 10:30 AM</strong></div></div></section>
  <nav class="welcome-quicklinks" aria-label="Your next step at KCMC">
    <a href="#events" data-route="events"><svg viewBox="0 0 48 48" aria-hidden="true"><rect x="7" y="10" width="34" height="31" rx="3"/><path d="M15 5v10m18-10v10M7 20h34M15 28h2m6 0h2m6 0h2M15 34h2m6 0h2m6 0h2"/></svg><span>Upcoming Events</span><span class="welcome-arrow" aria-hidden="true">›</span></a>
    <a href="care.php"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M23 15v17L13 42l-8-7 9-11 4-13q2-4 5 0m2 4v17l10 10 8-7-9-11-4-13q-2-4-5 0M24 2v5M11 4l4 5M37 4l-4 5"/></svg><span>Prayer Requests</span><span class="welcome-arrow" aria-hidden="true">›</span></a>
    <a href="#partner" data-route="partner"><svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="13" r="7"/><circle cx="8" cy="20" r="5"/><circle cx="40" cy="20" r="5"/><path d="M13 42V33a11 11 0 0 1 22 0v9ZM2 42v-8a7 7 0 0 1 10-6m34 14v-8a7 7 0 0 0-10-6"/></svg><span>Church Family</span><span class="welcome-arrow" aria-hidden="true">›</span></a>
  </nav>
  <div class="welcome-design-footer"><p class="welcome-mission">Called to love and serve.</p><p>KIMBERLING CITY METHODIST CHURCH</p></div>


</section>


<section class="view" data-view="visit">
  <div class="wrap partner-hero"><div class="eyebrow">I’m New</div><h1 class="display-title">Your first Sunday should feel simple.</h1><p class="lead muted">Pick the worship style that fits you, get directions, and tell the welcome team you’re coming if you’d like someone ready to meet you.</p></div>
  <section class="section"><div class="wrap visit-grid">
    <div>
      <div class="section-head"><div><div class="eyebrow">What to expect</div><h2>Come as you are.</h2></div></div>
      <div class="expect-list">
        <details class="disclosure-row"><summary><h3>Three Sunday options</h3></summary><div class="disclosure-content"><p>8:00 AM Front Porch Gospel • 9:15 AM Traditional • 10:30 AM Contemporary.</p></div></details>
        <details class="disclosure-row"><summary><h3>Warm, relaxed welcome</h3></summary><div class="disclosure-content"><p>KCMC describes its worship as a place to connect with God and community, with music and Bible-based teaching.</p></div></details>
        <details class="disclosure-row"><summary><h3>Kids at 10:30</h3></summary><div class="disclosure-content"><p>Launch Kids Children’s Church coincides with the Contemporary service.</p></div></details>
        <details class="disclosure-row"><summary><h3>One easy destination</h3></summary><div class="disclosure-content"><p>57 Kimberling City Center Lane, Kimberling City, MO 65686.</p></div></details>
        <details class="disclosure-row"><summary><h3>Accessibility or arrival question?</h3></summary><div class="disclosure-content"><p>Call the church office at (417) 739-4395 before your visit and the team can help with your specific need.</p></div></details>
      </div>
      <div class="btns"><a class="btn gold" href="https://maps.app.goo.gl/W6kRCHvbaVJ7mwte7" target="_blank" rel="noopener">Get directions</a><a class="btn secondary" href="tel:+14177394395">Call the office</a></div>
    </div>
    <form class="form-card" data-kcmc-form="visit" data-subject="I’m Coming This Sunday" novalidate>
      <div class="eyebrow">Plan a visit</div><h2>I’m coming this Sunday</h2><p class="muted">Share your plans with our welcome team and request a one-time welcome email with next steps. This does not create an account or subscribe you to ongoing messages.</p>
      <div class="field-row"><label>First name<input name="firstName" autocomplete="given-name" required></label><label>Last name<input name="lastName" autocomplete="family-name" required></label></div>
      <label>Email<input type="email" name="email" autocomplete="email" required></label>
      <label>Phone<input type="tel" name="phone" autocomplete="tel"></label>
      <label>Service<select name="service" required><option value="">Choose a service</option><option>8:00 AM — Front Porch Gospel</option><option>9:15 AM — Traditional Worship</option><option>10:30 AM — Contemporary Worship</option></select></label>
      <label>Anything we can help with?<textarea name="message" rows="4" placeholder="Kids, accessibility, where to meet, or anything else"></textarea></label>
      <button class="btn gold" type="submit">Tell the welcome team</button><p class="form-status" role="status" aria-live="polite"></p><div class="visit-next-steps" data-visit-next-steps hidden><h3>You have a place here. Take your next step.</h3><p>Come as you are. Explore what is happening, ask about a Bible study or group, or find a way to serve.</p><div class="btns"><a class="btn" href="#events" data-route="events">Upcoming events</a><a class="btn" href="#partner" data-route="partner">Find a group</a><a class="btn" href="#serve" data-route="serve">Explore serving</a><a class="btn secondary" href="https://maps.app.goo.gl/W6kRCHvbaVJ7mwte7" target="_blank" rel="noopener">Directions</a></div><p>Bringing children? Launch Kids meets during the 10:30 AM Contemporary service. Contact the church office with arrival or accessibility questions.</p><button class="btn gold" type="button" data-share-app data-share-visit>Invite someone to join you</button></div>
    </form>
  </div></section>
  <section class="section alt"><div class="wrap"><div class="section-head"><div><div class="eyebrow">Choose your service</div><h2>Same church. Different expression.</h2></div></div><div class="disclosure-list"><details class="disclosure-row"><summary><h3>8:00 AM · Front Porch Gospel</h3></summary><div class="disclosure-content"><p>Old-time country and bluegrass Gospel with an uplifting Bible-based message.</p></div></details><details class="disclosure-row"><summary><h3>9:15 AM · Traditional</h3></summary><div class="disclosure-content"><p>Hymns, piano, organ and choir with teaching based on the Bible.</p></div></details><details class="disclosure-row"><summary><h3>10:30 AM · Contemporary</h3></summary><div class="disclosure-content"><p>A laid-back coffee-shop setting with fellowship, refreshments and Launch Kids.</p></div></details></div></div></section>
</section>

<section class="view" data-view="watch">
  <div class="wrap partner-hero"><div class="eyebrow">Watch Live</div><h1 class="display-title">Worship wherever you are.</h1><p class="lead muted">Choose your Sunday service. Times are Central time.</p></div>
  <section class="section"><div class="wrap">
    <div class="library-toolbar"><label class="search-field"><span class="sr-only">Search services</span><input id="sermonSearch" type="search" placeholder="Search services"></label><select id="sermonFilter" aria-label="Filter services"><option value="all">All services</option><?php foreach($worshipServices as $service): ?><option value="<?=kcmc_h($service['id'])?>"><?=kcmc_h($service['name'])?></option><?php endforeach; ?></select></div>
    <div class="sermon-grid" id="sermonGrid">
      <?php foreach($worshipServices as $service): ?>
      <article class="sermon-card" data-search="<?=kcmc_h(strtolower($service['name'].' '.$service['time']))?>" data-type="<?=kcmc_h($service['id'])?>">
        <img class="service-photo" src="<?=kcmc_h($service['image'])?>" alt="<?=kcmc_h($service['alt'])?>" loading="lazy" decoding="async" width="720" height="540">
        <div><span class="pill"><?=kcmc_h($service['time'])?> Sunday</span><h2><?=kcmc_h($service['name'])?></h2><p><?=kcmc_h($service['description'])?></p>
        <?php if($service['recording_label'] !== ''): ?><p class="muted"><?=kcmc_h($service['recording_label'])?></p><?php endif; ?>
        <?php if($service['stream_url'] !== ''): ?><a class="btn gold" href="<?=kcmc_h($service['stream_url'])?>" target="_blank" rel="noopener" aria-label="Watch <?=kcmc_h($service['name'])?> on Facebook">Watch this service</a><?php else: ?><p class="muted">This service’s direct broadcast link has not been published yet.</p><?php endif; ?></div>
      </article>
      <?php endforeach; ?>
    </div>
    <p class="sermon-empty" hidden role="status">No services match your search.</p>
    <p>Current broadcasts and recent recordings are also available on KCMC’s Facebook page. Facebook may ask you to sign in.</p>
    <a class="btn secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">KCMC Facebook broadcasts</a>
  </div></section>
</section>

<section class="view" data-view="news">
  <div class="wrap partner-hero"><div class="eyebrow">Church updates</div><h1 class="display-title">Stay connected this week.</h1><p class="lead muted">The latest bulletin, published announcements and upcoming gatherings.</p><a class="btn secondary" href="#home" data-route="home">← Back</a></div>
  <section class="section"><div class="wrap">
    <div class="btns"><a class="btn gold" href="bulletin.php">Latest bulletin</a><a class="btn secondary" href="#events" data-route="events">Upcoming events</a></div>
    <div class="announcement-stack">
    <?php foreach($kcmcAnnouncements as $item): ?><details class="disclosure-row"><summary><h2><?=kcmc_h((string)($item['title']??''))?></h2></summary><div class="disclosure-content"><p><?=kcmc_h((string)($item['body']??''))?></p></div></details><?php endforeach; ?>
    <?php if(!$kcmcAnnouncements): ?><p class="muted">Check the bulletin and events for the latest published information.</p><?php endif; ?>
    </div>
  </div></section>
</section>
<section class="view" data-view="events">
  <div class="wrap partner-hero"><div class="eyebrow">Events</div><h1 class="display-title">What’s next at KCMC.</h1><p class="lead muted">Upcoming gatherings, studies and community events, with easy ways to connect.</p></div>
  <div class="wrap"><nav class="btns" aria-label="Event calendar view">
      <a class="btn secondary" href="events.php?event_scope=calendar">Church calendar</a>
    </nav>
    <p class="muted">Community events and special gatherings.</p></div>
  <section class="section"><div class="wrap grid3 event-grid">
    <?php if(!$kcmcEvents): ?><p>No current events are published.</p><?php endif; ?>
    <?php foreach($kcmcEvents as $event):
      $eventTitle=(string)($event['title']??'');
      $eventDate=(string)($event['date']??'');
      $eventImage=(string)($event['image']??'');
      $hasEventImage=preg_match('#\Aassets/visuals/[A-Za-z0-9][A-Za-z0-9._-]*\z#',$eventImage)===1;
      $detailsOnSlide=$hasEventImage&&($event['id']??'')==='trunk-or-treat-2026';
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
        <?php if($hasEventImage): ?><img class="event-image" src="<?=kcmc_h($eventImage.($detailsOnSlide?'?v=event-slide-20261020':''))?>" alt="<?=kcmc_h((string)($event['image_alt']??''))?>" loading="lazy" decoding="async"><?php endif; ?>
        <div class="event-card-copy">
          <?php if(!$detailsOnSlide): ?><p class="muted"><time datetime="<?=kcmc_h($eventDate)?>"><?=kcmc_h(date('D, M j',strtotime($eventDate)))?></time></p><?php endif; ?>
          <details class="disclosure-row event-disclosure"><summary><h3><?=kcmc_h($eventTitle)?></h3></summary><div class="disclosure-content">
          <p class="event-when"><?php if(!$detailsOnSlide): ?><strong><?=kcmc_h($eventTimeLabel)?></strong> • <?php endif; ?><?=kcmc_h($eventLocation)?></p>
          <?php if(!empty($event['description'])): ?><p class="event-description"><?=kcmc_h((string)$event['description'])?></p><?php endif; ?>
          <div class="btns"><?php if($rsvpEnabled): ?><button class="btn event-rsvp" type="button" aria-label="RSVP for <?=kcmc_h($eventTitle)?>">RSVP</button><?php else: ?><a class="btn" href="<?=kcmc_h($kcmcPhoneHref)?>" aria-label="Call KCMC with questions about <?=kcmc_h($eventTitle)?>">Call church office · <?=kcmc_h($kcmcPhone)?></a><?php endif; ?></div>
          </div></details>
        </div>
      </article>
    <?php endforeach; ?>
  </div><?php if($kcmcHasRsvpEvents): ?><div class="wrap form-wrap"><form class="form-card compact" id="eventForm" data-kcmc-form="event" data-subject="KCMC Event RSVP" novalidate><div class="eyebrow">Event RSVP</div><h2>Let KCMC know you’re interested.</h2><input type="hidden" name="event" id="eventName"><div class="field-row"><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div><label>Event<input id="eventDisplay" value="Choose RSVP above" readonly></label><label>Note<textarea name="message" rows="3" placeholder="Questions, number attending, or anything the team should know"></textarea></label><button class="btn gold" type="submit">Send RSVP</button><p class="form-status" role="status" aria-live="polite"></p></form></div><?php endif; ?><div class="wrap" style="margin-top:18px"><div class="notice">Questions about an event? Call the church office at <?=kcmc_h($kcmcPhone)?>.</div></div></section>
</section>

<section class="view" data-view="serve">
  <div class="wrap partner-hero"><div class="eyebrow">Serve</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Turn everyday things into ministry.</h1><p class="lead muted">Share your interests with our church team and ask about current opportunities to serve.</p></div>
  <section class="section"><div class="wrap disclosure-list">
    <details class="disclosure-row"><summary><h3>Find a place to serve</h3></summary><div class="disclosure-content"><p>Tell the team about your interests and availability using the form below. The church can help you find an active opportunity.</p></div></details>
    <details class="disclosure-row"><summary><h3>Have a question?</h3></summary><div class="disclosure-content"><p>Call the church office to ask what is needed now before making plans.</p><div class="btns"><a class="btn" href="<?=kcmc_h($kcmcPhoneHref)?>">Call the church</a></div></div></details>
  </div><div class="wrap form-wrap"><form class="form-card compact" data-kcmc-form="serve" data-subject="I Want to Serve at KCMC" novalidate><div class="eyebrow">Volunteer</div><h2>Find a place to serve.</h2><div class="field-row"><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label></div><label>I’m interested in<select name="interest"><option>Not sure — help me find a fit</option><option>Kids / Youth</option><option>Worship / Music</option><option>Hospitality / Welcome</option><option>Care / Prayer</option><option>Community Outreach</option><option>Facilities / Practical Help</option></select></label><label>Tell us a little about your availability or interests<textarea name="message" rows="4"></textarea></label><button class="btn gold" type="submit">Send my interest</button><p class="form-status" role="status" aria-live="polite"></p></form></div></section>
</section>

<section class="view" data-view="partner">
  <div class="wrap partner-hero"><div class="eyebrow">Church Family</div><h1 style="font-family:Georgia,serif;font-size:clamp(3rem,7vw,5rem);font-weight:400;margin:.1em 0">Your church week, in one place.</h1><p class="lead muted">Find your next step, ask for support, and get connected with our church team.</p></div>
  <section class="section"><div class="wrap announcement-stack">

    <details class="disclosure-row"><summary><h3>Use the app for worship, care and current links</h3></summary><div class="disclosure-content"><p>The official livestream, online giving, visit planning, office contact and current service information are all one tap away.</p></div></details>
    <details class="disclosure-row"><summary><h3>Groups and connection</h3></summary><div class="disclosure-content"><p>Looking for a small group, care connection, Bible study or ministry community? Send an interest note below and the church can help connect you.</p></div></details>
  </div><div class="wrap connection-grid form-wrap">
    <article class="form-card"><div class="eyebrow">Prayer &amp; care</div><h2>You don’t have to do life alone.</h2><p class="muted">Reach out to the church office for prayer or support. Personal prayer details are not displayed on the public app.</p><div class="btns"><a class="btn gold" href="<?=kcmc_h($kcmcPhoneHref)?>">Call the church</a><a class="btn secondary" href="care.php">Prayer &amp; care</a></div></article>
    <form class="form-card" data-kcmc-form="groups" data-subject="KCMC Connection / Group Interest" novalidate><div class="eyebrow">Find Your People</div><h2>Help me get connected.</h2><label>Name<input name="name" autocomplete="name" required></label><label>Email<input type="email" name="email" autocomplete="email" required></label><label>I’m looking for<select name="interest"><option>Small group / Bible study</option><option>Kids / family connection</option><option>Youth</option><option>Care / support</option><option>Men’s ministry</option><option>Women’s ministry</option><option>I’m new and not sure yet</option></select></label><label>Anything else?<textarea name="message" rows="4"></textarea></label><button class="btn gold" type="submit">Help me connect</button><p class="form-status" role="status" aria-live="polite"></p></form>
  </div><div class="wrap preferences"><div><div class="eyebrow">This device</div><h2>Remember my preferred service</h2><p class="muted">Optional preference is stored only on this device.</p></div><label>Preferred Sunday service<select id="preferredService"><option value="">No preference</option><option>8:00 AM — Front Porch Gospel</option><option>9:15 AM — Traditional Worship</option><option>10:30 AM — Contemporary Worship</option></select></label></div></section>
</section>
</main>

<footer class="footer"><div class="wrap footer-grid"><div><strong>KCMC CONNECT</strong><p>Kimberling City Methodist Church<br><?=kcmc_h($kcmcAddress)?></p></div><div><p><?=kcmc_h($kcmcPhone)?><br><?=kcmc_h($kcmcEmail)?></p><p class="fine">Called to love and serve.</p></div></div></footer>

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
<script src="app.js?v=tony-functions-20261020" defer></script>
<script src="public-presentation.js?v=tony-functions-20261020" defer></script>
</body></html>
