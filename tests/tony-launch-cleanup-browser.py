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

def check(ok: bool, text: str) -> None:
    if not ok:
        raise AssertionError(text)
    print('PASS:', text)

with tempfile.TemporaryDirectory(prefix='kcmc-public-review-') as td:
    work = Path(td)
    local = work / 'app'
    shutil.copytree(APP, local, ignore=shutil.ignore_patterns('config.php', 'private', 'backups'))
    data_file = local / 'data/content.json'
    data = json.loads(data_file.read_text())
    data['announcements'].append({'id': 'front-pew-friday', 'title': 'Mary Lou’s Friday update', 'body': 'Confirmed newsletter schedule', 'status': 'published', 'priority': 50})
    data['bulletin']['notes'] = [NOTES]
    data_file.write_text(json.dumps(data, ensure_ascii=False))
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
    env = {**os.environ, 'KCMC_PRIVATE_DATA_DIR': str(private), 'KCMC_SETUP_KEY': ''}
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
                for width in [320, 390, 1440]:
                    page.set_viewport_size({'width':width, 'height':900})
                    page.goto(base + '/', wait_until='networkidle')
                    check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'no horizontal overflow at {width}px')
                    check(page.locator('.hero h1').inner_text().startswith('Come as you are.'), 'welcome headline renders')
                    check(page.locator('.header-give').get_attribute('href') == 'https://www.simplechurchgiving.net/app/giving/umckc', 'giving uses the retained church destination')
                    check(page.locator('[data-hero-toggle]').inner_text() == 'Play photos', 'reduced motion starts with rotation stopped')
                    first = page.locator('[data-hero-photo]:visible').get_attribute('src')
                    page.locator('[data-hero-next]').click()
                    check(page.locator('[data-hero-photo]:visible').get_attribute('src') != first, 'manual next photo works')
                    check('2017' in page.locator('[data-hero-photo]:visible').get_attribute('alt'), 'historical worship date remains in accessible photo description')
                    page.locator('#siteMenu summary').click()
                    check(page.locator('#siteMenu').get_attribute('open') is not None, 'dropdown opens')
                    check(page.locator('.menu-account').is_visible(), 'sign-in is available inside the menu')
                    page.keyboard.press('Escape')
                    check(page.locator('#siteMenu').get_attribute('open') is None, 'Escape closes the menu')
                    check(page.locator('#siteMenu summary').evaluate('(e)=>e===document.activeElement'), 'Escape restores focus to menu control')
                    page.locator('#siteMenu summary').focus()
                    page.keyboard.press('Enter')
                    check(page.locator('#siteMenu').get_attribute('open') is not None, 'keyboard opens the menu')
                    page.locator('#siteMenu a[data-route="news"]').click()
                    check(page.locator('#siteMenu').get_attribute('open') is None, 'route selection closes the menu')
                    check('Friday update' in page.locator('[data-view="news"]').inner_text(), 'current editorial updates render')
                    for route in ['visit', 'watch', 'events', 'serve', 'partner']:
                        page.goto(base + '/#' + route, wait_until='domcontentloaded')
                        check(page.locator(f'[data-view="{route}"]').is_visible(), f'{route} route works at {width}px')
                        check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{route} fits {width}px')
                    page.goto(base + '/', wait_until='networkidle')
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
                check(plain.locator('[data-hero-caption]').is_hidden(), 'no-JavaScript fallback keeps the source caption hidden')
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
