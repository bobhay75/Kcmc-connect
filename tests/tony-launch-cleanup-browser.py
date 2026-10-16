#!/usr/bin/env python3
"""Isolated public-page acceptance. No production requests, private records or writes."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
OUT = Path(os.environ.get('KCMC_REVIEW_OUTPUT', '/tmp/kcmc-tony-review'))
OUT.mkdir(parents=True, exist_ok=True)
NOTES = 'The answer is ______.  Keep these spaces. <not-markup>'
ANNOUNCEMENT_BODY = ('Bring individually wrapped treats and keep the walkways clear. ' * 40).strip()

def check(ok: bool, text: str) -> None:
    if not ok:
        raise AssertionError(text)
    print('PASS:', text)

with tempfile.TemporaryDirectory(prefix='kcmc-public-review-') as td:
    work = Path(td)
    local = work / 'app'
    shutil.copytree(APP, local, ignore=shutil.ignore_patterns('config.php', 'private', 'backups'))
    data_file = local / 'data/content.json'
    data = json.loads(data_file.read_text(encoding='utf-8'))
    data['announcements'].append({'id': 'front-pew-friday', 'title': 'Mary Lou’s Friday update', 'body': 'Confirmed newsletter schedule', 'status': 'published', 'priority': 50})
    data['announcements'].append({'id': 'long-volunteer-detail', 'title': 'Volunteer instructions', 'body': ANNOUNCEMENT_BODY, 'status': 'published', 'priority': 100})
    data['bulletin']['notes'] = [NOTES]
    data_file.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    before = hashlib.sha256(data_file.read_bytes()).hexdigest()
    # Mirror a configured installation using a synthetic, inaccessible account.
    # An empty account store routes to setup rather than normal member sign-in.
    private = work / 'private'
    private.mkdir(mode=0o750)
    password_hash = subprocess.run(
        ['php', '-r', 'echo password_hash($argv[1], PASSWORD_DEFAULT);',
         'Synthetic-Public-Test-Password-2031!'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    (private / 'users.json').write_text(json.dumps({'version': 1, 'users': [{
        'id': 'synthetic_admin', 'email': 'admin@example.invalid',
        'email_normalized': 'admin@example.invalid', 'display_name': 'Synthetic Admin',
        'role': 'pastor_admin', 'active': True, 'password_hash': password_hash,
        'created_at': '2031-01-01T00:00:00Z',
    }]}))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}/app'
    env = {**os.environ, 'KCMC_PRIVATE_DATA_DIR': str(private), 'KCMC_SETUP_KEY': '', 'KCMC_OPERATIONS_OWNER_USER_ID': 'synthetic_admin'}
    with open(work / 'php.log', 'w+') as log:
        server = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(work)], stdout=log, stderr=log, env=env)
        try:
            for _ in range(50):
                try:
                    with urllib.request.urlopen(base + '/') as res:
                        home_html = res.read().decode()
                        check(not res.headers.get('Set-Cookie'), 'anonymous homepage does not create a session')
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('PHP server failed to start')
            with urllib.request.urlopen(base + '/api/content.php') as res:
                payload = json.load(res)
                check('no-store' in res.headers.get('Cache-Control', ''), 'public data refresh cannot retain the retired cached source')
            check('news' not in payload, 'monthly data is absent from the public API')
            check(all(a['id'] != 'sep-news-16' for a in payload['announcements']), 'retired monthly announcement is not publicly returned')
            check(any(a['id'] == 'front-pew-friday' for a in payload['announcements']), 'Mary Lou Friday update remains available')
            check('Verified members only' not in home_html and 'The Bridge to Salvation' not in home_html, 'retired presentation is absent from server HTML')
            with sync_playwright() as p:
                opts = {}
                if os.environ.get('KCMC_CHROMIUM_PATH'):
                    opts['executable_path'] = os.environ['KCMC_CHROMIUM_PATH']
                browser = p.chromium.launch(**opts)
                errors: list[str] = []
                failures: list[str] = []
                context = browser.new_context(reduced_motion='reduce', viewport={'width':390,'height':844})
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('response', lambda r: failures.append(f'{r.status} {r.url}') if r.url.startswith(base) and r.status >= 400 else None)
                for width in [320, 390, 768, 1100, 1101, 1440, 1920]:
                    page.set_viewport_size({'width':width, 'height':900})
                    page.goto(base + '/', wait_until='networkidle')
                    check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'no horizontal overflow at {width}px')
                    check(page.locator('.home-cover-card').count() == 1, 'one compact photo-controls shell is retained')
                    for selector in ['.home-cover-card > .eyebrow', '.hero h1', '.home-cover-card > .lead', '.home-worship-strip', '.family-welcome-copy']:
                        check(page.locator(selector).is_hidden(), selector + ' stays off the photo-only homepage')
                    check(page.locator('.hero h1').text_content().startswith('Come as you are.'), 'welcome copy remains in the source without cluttering the homepage')
                    check(page.locator('.home-cover-card').evaluate("el => { const s=getComputedStyle(el); return s.backgroundColor === 'rgba(0, 0, 0, 0)' && s.boxShadow === 'none' && parseFloat(s.padding) === 0; }"), 'photo controls use a transparent shell without a cream welcome card')
                    check(page.locator('.header-give').get_attribute('href') == 'https://www.simplechurchgiving.net/app/giving/umckc', 'giving uses the retained church destination')
                    check(page.locator('.home-cover-card').count() == 1 and page.locator('.hero-card').count() == 0, 'one compact controls shell replaces competing hero boxes')
                    check(page.locator('.home-cover-actions .action').count() == 0, 'homepage destination actions are moved into the fish menu')
                    check(page.locator('.phase6-announcement, .mobile-nav, .phase6-bulletin-fab').count() == 0, 'announcement bar and duplicate navigation are absent')
                    check(page.locator('#siteMenu').get_attribute('open') is None, 'fish navigation starts closed')
                    check(page.locator('#siteMenuLinks').is_hidden(), 'menu destinations stay hidden until the fish is opened')
                    outside_actions = page.locator('body a:visible, body button:visible').evaluate_all("els => els.filter(el => !el.closest('#siteMenu') && !el.matches('.skip-link,[data-hero-previous],[data-hero-toggle],[data-hero-next]')).map(el => el.textContent.trim())")
                    check(outside_actions == [], 'closed-menu homepage has no destination links or ordinary action buttons outside the fish: ' + repr(outside_actions))
                    check(ANNOUNCEMENT_BODY not in page.locator('[data-view="home"]').inner_text(), 'long volunteer details cannot clutter the homepage')
                    home_panels = page.locator('[data-view="home"] > .section:visible')
                    check(home_panels.count() == 2 and home_panels.evaluate_all("els => els.every(el => el.matches('[aria-label=\"KCMC kids and family photos\"],[data-family-welcome]'))"), 'only church and family photo panels follow the welcome screen')
                    photo_box = page.locator('[data-hero-photo]:visible').bounding_box()
                    card_box = page.locator('.home-cover-card').bounding_box()
                    controls_box = page.locator('[data-hero-controls]').bounding_box()
                    cover_box = page.locator('[data-hero-gallery]').bounding_box()
                    check(card_box['y'] >= photo_box['y'] + photo_box['height'] - 1, 'compact controls follow rather than obscure the authentic church photograph')
                    check(cover_box['height'] <= photo_box['height'] + controls_box['height'] + 64 and card_box['height'] <= controls_box['height'] + 4, 'photo cover reserves no blank welcome-card or service-strip space')
                    check(page.locator('[data-hero-photo]:visible').evaluate("el => el.naturalWidth === 1402 && getComputedStyle(el).objectFit === 'contain'"), 'whole authentic exterior remains visible without cropping')
                    check(page.locator('[data-hero-controls] button:visible').count() == 3 and page.locator('.home-bulletin-link').count() == 0, 'only the three photo controls remain outside the fish menu')
                    page.locator('[data-hero-toggle]').focus()
                    check(page.locator('[data-hero-toggle]').evaluate("el => parseFloat(getComputedStyle(el).outlineWidth) >= 3"), 'photo control has visible keyboard focus')
                    check(page.locator('[data-hero-toggle]').inner_text() == 'Play photos', 'reduced motion starts with rotation stopped')
                    first = page.locator('[data-hero-photo]:visible').get_attribute('src')
                    page.locator('[data-hero-next]').click()
                    check(page.locator('[data-hero-photo]:visible').get_attribute('src') != first, 'manual next photo works')
                    check('2017' in page.locator('[data-hero-photo]:visible').get_attribute('alt'), 'historical worship date remains in accessible photo description')
                    check(page.locator('.topbar .inner > *').count() == 1, 'fish dropdown is the only top-level header control')
                    check(page.locator('#siteMenu summary img').get_attribute('src') == './assets/icons/icon-192.png', 'existing KCMC fish logo opens navigation')
                    page.locator('#siteMenu summary').hover()
                    expect(page.locator('#siteMenu')).to_have_attribute('open', '')
                    page.locator('#siteMenu a[data-route="visit"]').hover()
                    check(page.locator('#siteMenu').get_attribute('open') is not None, 'pointer moves from fish to links without closing menu')
                    page.mouse.move(width - 1, 80)
                    expect(page.locator('#siteMenu')).not_to_have_attribute('open', '')
                    page.locator('#siteMenu summary').click()
                    check(page.locator('#siteMenu').get_attribute('open') is not None, 'click pins the hover-opened dropdown')
                    check(page.locator('#siteMenu [data-install-app]').is_visible(), 'Save app is available inside the fish dropdown')
                    check(page.locator('#siteMenu .header-give').is_visible(), 'giving is available inside the fish dropdown')
                    check(page.locator('.menu-account').is_visible(), 'sign-in is available inside the menu')
                    for name, href in [('Latest bulletin', 'bulletin.php'), ('Kids & youth', 'https://www.kimberlingcitymethodist.com/youth'), ('Call the church office', 'tel:4177394395'), ('Email the church office', 'mailto:secretary@umckc.org'), ('KCMC on Facebook', 'https://www.facebook.com/KimberlingCityMethodistChurch')]:
                        check(page.locator('#siteMenuLinks').get_by_role('link', name=name, exact=True).get_attribute('href') == href, name + ' remains reachable inside the fish')
                    check(page.locator('#siteMenuLinks [data-share-visit]').is_visible(), 'Sunday invitation action is available in the fish menu')
                    page.keyboard.press('Escape')
                    check(page.locator('#siteMenu').get_attribute('open') is None, 'Escape closes the menu')
                    check(page.locator('#siteMenu summary').evaluate('(e)=>e===document.activeElement'), 'Escape restores focus to menu control')
                    page.locator('#siteMenu summary').focus()
                    page.keyboard.press('Enter')
                    check(page.locator('#siteMenu').get_attribute('open') is not None, 'keyboard opens the menu')
                    page.keyboard.press('Tab')
                    check(page.evaluate('Boolean(document.activeElement.closest("#siteMenuLinks"))'), 'Tab enters the open navigation')
                    page.locator('#siteMenu a[data-route="news"]').click()
                    expect(page.locator('[data-view="news"]')).to_be_visible()
                    check(page.locator('#siteMenu').get_attribute('open') is None, 'route selection closes the menu')
                    check('Friday update' in page.locator('[data-view="news"]').inner_text(), 'current editorial updates render')
                    check(ANNOUNCEMENT_BODY in page.locator('[data-view="news"]').inner_text(), 'full long volunteer instructions are preserved in Church updates')
                    for route in ['visit', 'watch', 'events', 'serve', 'partner']:
                        page.locator('#siteMenu summary').click()
                        page.locator(f'#siteMenu a[data-route="{route}"]').click()
                        expect(page.locator(f'[data-view="{route}"]')).to_be_visible()
                        check(page.locator('#siteMenu').get_attribute('open') is None, f'{route} selection closes the fish menu')
                        check(page.locator(f'[data-view="{route}"]').is_visible(), f'{route} remains reachable through the fish at {width}px')
                        if route == 'visit':
                            service_options = page.locator('[data-view="visit"] .expect-list').inner_text()
                            check(all(t in service_options for t in ['8:00 AM Front Porch Gospel', '9:15 AM Traditional', '10:30 AM Contemporary']), 'all three service times and worship styles remain available through fish → Plan a visit')
                        check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{route} fits {width}px')
                    page.goto(base + '/', wait_until='networkidle')
                    archived_photos = page.locator('[data-kcmc-photo-gallery] img, .family-photo')
                    archived_photos.evaluate_all("imgs => imgs.forEach(img => img.loading = 'eager')")
                    for photo in archived_photos.all():
                        expect(photo).to_have_js_property('complete', True)
                        check(photo.evaluate('(img) => img.naturalWidth > 0'), 'supplied gallery and family photos load')
                    page.evaluate('window.scrollTo(0, 0)')
                    page.screenshot(path=str(OUT / f'home-viewport-{width}.png'))
                    page.screenshot(path=str(OUT / f'home-{width}.png'), full_page=True)
                page.goto(base + '/bulletin.php')
                check(page.locator('.bulletin-notes li').text_content() == NOTES, 'rendered notes preserve blanks, double spaces and literal markup')
                page.goto(base + '/news.php')
                check(page.url.endswith('/#news'), 'legacy newsletter URL redirects to current updates')
                page.goto(base + '/care.php')
                check('We’re here for you.' in page.locator('body').inner_text(), 'care page welcomes visitors without an account')
                for path in ['member/', 'admin/health.php', 'admin/audit.php', 'admin/timecards.php', 'member/timeclock.php']:
                    page.goto(base + '/' + path)
                    check('/member/login.php' in page.url, f'{path} redirects to sign-in (actual: {page.url})')
                check(not errors, 'no browser JavaScript errors: ' + '; '.join(errors))
                check(not failures, 'no failed local assets: ' + '; '.join(failures))
                context.close()
                touch_context = browser.new_context(viewport={'width':390,'height':844}, has_touch=True, is_mobile=True, reduced_motion='reduce', service_workers='block')
                touch = touch_context.new_page()
                touch.goto(base + '/', wait_until='networkidle')
                touch.locator('#siteMenu summary').tap()
                check(touch.locator('#siteMenu').get_attribute('open') is not None, 'touch opens the fish menu without hover')
                touch.locator('#siteMenu a[data-route="news"]').tap()
                expect(touch.locator('[data-view="news"]')).to_be_visible()
                check(touch.locator('[data-view="news"]').is_visible() and ANNOUNCEMENT_BODY in touch.locator('[data-view="news"]').inner_text(), 'touch selection reaches the complete announcement behind the fish')
                check(touch.locator('#siteMenu').get_attribute('open') is None, 'touch route selection closes the fish')
                touch.goto(base + '/', wait_until='networkidle')
                touch.locator('#siteMenu summary').tap()
                touch.touchscreen.tap(380, 90)
                check(touch.locator('#siteMenu').get_attribute('open') is None, 'outside tap closes navigation')
                touch.locator('#siteMenu summary').tap()
                touch.locator('#siteMenu [data-install-app]').tap()
                check(touch.locator('.install-sheet').is_visible(), 'Save app opens installation help from the touch dropdown')
                check(touch.locator('#siteMenu').get_attribute('open') is None, 'menu closes after choosing Save app')
                touch_context.close()
                # Freeze browser time before navigation so interval boundaries are
                # exact and acceptance never needs a seven-minute wall-clock wait.
                c2 = browser.new_context(viewport={'width':390,'height':844}, reduced_motion='no-preference')
                auto = c2.new_page()
                auto.clock.install(time=datetime(2031, 1, 1, tzinfo=timezone.utc))
                auto.clock.pause_at(datetime(2031, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
                auto.goto(base + '/', wait_until='networkidle')
                auto.wait_for_function("[...document.querySelectorAll('[data-hero-photo]')].every(img => img.complete && img.naturalWidth > 0)")
                photo = auto.locator('[data-hero-photo]:visible')
                first = photo.get_attribute('src')
                check(auto.locator('[data-hero-toggle]').inner_text() == 'Pause photos', 'normal motion offers a pause control')
                auto.clock.run_for(8000)
                check(photo.get_attribute('src') == first, 'photo does not advance at the retired 8-second interval')
                auto.clock.run_for(411999)
                check(photo.get_attribute('src') == first, 'photo remains unchanged through 419999 ms')
                auto.clock.run_for(1)
                check(photo.get_attribute('src') == auto.locator('[data-hero-photo]').nth(1).get_attribute('src'), 'automatic rotation advances exactly at 420000 ms')
                auto.locator('[data-hero-toggle]').click()
                check(auto.locator('[data-hero-toggle]').inner_text() == 'Play photos', 'first pause click actually stops rotation')
                frozen = photo.get_attribute('src')
                auto.clock.run_for(420000)
                check(photo.get_attribute('src') == frozen, 'paused photo remains unchanged for a full seven-minute interval')
                auto.locator('[data-hero-toggle]').click()
                auto.mouse.move(0, 0)  # Pointer hover intentionally suspends autoplay.
                check(auto.locator('[data-hero-toggle]').inner_text() == 'Pause photos', 'play control resumes automatic rotation')
                auto.clock.run_for(419999)
                check(photo.get_attribute('src') == frozen, 'resumed rotation waits a full interval')
                auto.clock.run_for(1)
                check(photo.get_attribute('src') == auto.locator('[data-hero-photo]').nth(2).get_attribute('src'), 'resumed rotation advances at seven minutes')
                auto.locator('[data-hero-previous]').click()
                check(photo.get_attribute('src') == frozen and auto.locator('[data-hero-toggle]').inner_text() == 'Play photos', 'manual previous works and pauses rotation')
                auto.mouse.move(0, 0)
                auto.clock.run_for(420000)
                check(photo.get_attribute('src') == frozen, 'manual selection stays paused for a full interval')
                auto.locator('[data-hero-toggle]').click()
                auto.mouse.move(0, 0)
                auto.emulate_media(reduced_motion='reduce')
                # Chromium dispatches the media-query change asynchronously.
                expect(auto.locator('[data-hero-toggle]')).to_have_text('Play photos')
                auto.clock.run_for(420000)
                check(photo.get_attribute('src') == frozen and auto.locator('[data-hero-toggle]').inner_text() == 'Play photos', 'reduced-motion change stops automatic rotation')
                auto.locator('[data-hero-next]').click()
                check(photo.get_attribute('src') == auto.locator('[data-hero-photo]').nth(2).get_attribute('src'), 'manual next remains available with reduced motion')
                c2.close()
                # JavaScript-disabled welcome remains usable; no dead visible gallery buttons.
                c3 = browser.new_context(java_script_enabled=False, viewport={'width':390,'height':844})
                plain = c3.new_page()
                plain.goto(base + '/')
                check(plain.locator('[data-hero-photo]:visible').count() == 1, 'no-JavaScript static photo fallback works')
                check(plain.locator('[data-hero-caption]').count() == 0, 'no-JavaScript fallback contains no source caption element')
                plain.locator('#siteMenu summary').click()
                check(plain.locator('.menu-account').is_visible(), 'native menu works without JavaScript')
                c3.close()
                browser.close()
            check(hashlib.sha256(data_file.read_bytes()).hexdigest() == before, 'all public reads left content unchanged')
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
print('Tony public launch browser acceptance passed.')
