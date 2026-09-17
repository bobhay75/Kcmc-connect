"""Full-app acceptance on a disposable localhost copy, never a live host.

Run: python tests/browser-acceptance.py
Requires PHP and playwright (Chromium installed). No real accounts, secrets,
prayers, invitations, mail delivery, or production URLs are used. Native share
is mocked: this does NOT certify Android/iPhone OS sharing or production Apache.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results' / 'browser-acceptance'
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list[dict] = []
PUBLIC_URL = 'https://bobsome1.com/kcmc-connect/'


def check(name, fn):
    try:
        fn()
        RESULTS.append({'name': name, 'passed': True})
        print('PASS:', name, flush=True)
    except Exception as exc:
        RESULTS.append({'name': name, 'passed': False, 'error': str(exc)})
        print('FAIL:', name, str(exc), flush=True)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def contrast(page, selector, background_selector):
    return page.evaluate('''([selector, backgroundSelector]) => {
      const rgb = value => (value.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
      const luminance = values => values.map(v => {
        v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
      }).reduce((total, v, i) => total + v * [.2126, .7152, .0722][i], 0);
      const a = luminance(rgb(getComputedStyle(document.querySelector(selector)).color));
      const b = luminance(rgb(getComputedStyle(document.querySelector(backgroundSelector)).backgroundColor));
      return (Math.max(a,b) + .05) / (Math.min(a,b) + .05);
    }''', [selector, background_selector])


def main():
    with tempfile.TemporaryDirectory(prefix='kcmc-browser-') as directory:
        temp = Path(directory)
        webroot = temp / 'web'
        app = webroot / 'kcmc-connect'
        private = temp / 'private'
        private.mkdir()
        shutil.copytree(ROOT / 'KCMC-Connect-Phase6-Recreated', app,
                        ignore=shutil.ignore_patterns('config.php', 'private', 'backups', 'newsletter'))
        password = secrets.token_urlsafe(32)
        password_hash = subprocess.check_output(
            ['php', '-r', 'echo password_hash(getenv("TEST_PASSWORD"), PASSWORD_DEFAULT);'],
            env={'PATH': os.environ['PATH'], 'TEST_PASSWORD': password}, text=True)
        users = [{'id': 'test_' + role, 'email': role + '@example.invalid',
                  'email_normalized': role + '@example.invalid', 'name': 'Synthetic ' + role,
                  'role': role, 'active': True, 'password_hash': password_hash}
                 for role in ['recovery_admin', 'member']]
        (private / 'users.json').write_text(json.dumps({'version': 1, 'users': users}))
        sentinel = 'SYNTHETIC_PRIVATE_PRAYER_DO_NOT_CACHE'
        (private / 'prayers.json').write_text(json.dumps({'version': 1, 'prayers': [
            {'id': 'test_prayer', 'body': sentinel, 'status': 'pending'}]}))
        # PHP's test server does not implement Apache .htaccess. The local router
        # prevents fixture-file exposure; production Apache checks remain separate.
        router = temp / 'router.php'
        router.write_text('''<?php
$path = rawurldecode((string)parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
if (str_contains($path, '..') || preg_match('~/(?:data|backups)(?:/|$)|(?:^|/)\\.|\\.(?:json|ndjson|lock)$~i', $path)) {
  http_response_code(403); exit('Test fixture path denied.');
}
return false;
''')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        base = origin + '/kcmc-connect/'
        env = {'PATH': os.environ['PATH'], 'KCMC_PRIVATE_DATA_DIR': str(private), 'KCMC_SETUP_KEY': ''}
        with (OUT / 'php-server.log').open('w') as logfile:
            def start_server():
                process = subprocess.Popen(['php', '-d', 'sendmail_path=/bin/false', '-S',
                    f'127.0.0.1:{port}', '-t', str(webroot), str(router)],
                    stdout=logfile, stderr=logfile, env=env)
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Disposable PHP server exited early.')
                    try:
                        with urllib.request.urlopen(base, timeout=1):
                            return process
                    except OSError:
                        time.sleep(.1)
                process.terminate()
                process.wait(timeout=5)
                raise RuntimeError('Disposable PHP server did not become ready.')

            server = start_server()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    try:
                        for width, height in [(390, 844), (1280, 900)]:
                            context = browser.new_context(viewport={'width': width, 'height': height})
                            # The browser must never contact the production app or third parties.
                            context.route('**/*', lambda route: route.continue_()
                                if urlsplit(route.request.url).netloc == f'127.0.0.1:{port}' else route.abort())
                            page = context.new_page()
                            page.set_default_timeout(10000)
                            errors = []
                            page.on('pageerror', lambda error: errors.append(str(error)))
                            page.goto(base)
                            page.evaluate('navigator.serviceWorker.ready')
                            page.reload()
                            routes = page.locator('[data-view]').evaluate_all('(els) => els.map(e=>e.dataset.view)')
                            for route in routes:
                                def view_test(route=route):
                                    page.goto(base + '#' + route)
                                    expect(page.locator('.view.active')).to_have_attribute('data-view', route)
                                    expect(page.locator('.view.active')).to_be_visible()
                                    require(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),
                                            f'Horizontal overflow on {route} at {width}px')
                                check(f'{width}px public route {route}', view_test)
                            page.goto(base)
                            page.screenshot(path=str(OUT / f'home-{width}.png'), full_page=True)
                            def share_test():
                                page.evaluate("Object.defineProperty(navigator, 'share', {configurable:true, value:undefined})")
                                control = page.locator('[data-share-app]')
                                control.focus()
                                page.keyboard.press('Enter')
                                field = page.locator('[data-share-url]')
                                expect(field).to_be_visible()
                                expect(field).to_have_value(PUBLIC_URL)
                                expect(field).to_be_focused()
                                require(field.get_attribute('readonly') is not None, 'Share field must be readonly')
                            check(f'{width}px keyboard sharing and manual fallback', share_test)
                            def cancel_test():
                                page.goto(base + '?code=SYNTHETIC_SECRET#home')
                                page.evaluate("""() => {
                                  window.testShares=[];
                                  Object.defineProperty(navigator,'share',{configurable:true,value:async data=>{
                                    window.testShares.push(data);throw new DOMException('Canceled','AbortError');
                                  }});
                                }""")
                                page.locator('[data-share-app]').click()
                                expect(page.locator('[data-share-status]')).to_contain_text('closed')
                                expect(page.locator('[data-share-fallback]')).to_be_hidden()
                                data = page.evaluate('window.testShares')
                                require(len(data) == 1 and data[0]['url'] == PUBLIC_URL,
                                        'Share payload must contain only the fixed public URL')
                                require('SYNTHETIC_SECRET' not in json.dumps(data), 'Share leaked current URL')
                            check(f'{width}px mocked native cancel and public-only payload', cancel_test)
                            def login():
                                page.goto(base + 'member/login.php?next=/kcmc-connect/admin/')
                                page.locator('[name=email]').fill('recovery_admin@example.invalid')
                                page.locator('[name=password]').fill(password)
                                page.get_by_role('button', name='Sign in securely').click()
                                expect(page.get_by_role('heading', name='Publishing Desk', exact=True)).to_be_visible()
                            check(f'{width}px synthetic owner sign-in', login)
                            def desk_test():
                                require(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),
                                        'Publishing Desk overflows viewport')
                                require(page.locator('html').get_attribute('lang') == 'en', 'Publishing Desk language is missing')
                                ratio = contrast(page, '.panel label', '.panel')
                                require(ratio >= 4.5, f'Publishing Desk label contrast is {ratio:.2f}:1, below 4.5:1')
                                require(contrast(page, '.desk h1', 'body') >= 3, 'Publishing Desk heading has inadequate contrast')
                            page.screenshot(path=str(OUT / f'desk-{width}.png'), full_page=True)
                            check(f'{width}px Publishing Desk layout, language, and contrast', desk_test)
                            def backup_test():
                                response = context.request.get(base + 'admin/backup.php')
                                require(response.status == 200, 'Authorized backup failed')
                                require('no-store' in response.headers.get('cache-control', ''), 'Backup lacks no-store')
                                body = response.text()
                                require('contact' in json.loads(body), 'Backup is not public-content JSON')
                                require(sentinel not in body and password_hash not in body, 'Backup included private fixture data')
                            check(f'{width}px synthetic owner content backup', backup_test)
                            def publish_test():
                                page.goto(base + 'admin/')
                                form = page.locator('form[action$="admin/save.php"]')
                                denied = context.request.post(base + 'admin/save.php', form={'csrf': 'invalid'})
                                require(denied.status == 403, 'Publishing accepted invalid CSRF')
                                title = f'LOCAL ACCEPTANCE ONLY {width}'
                                form.locator('[name=announcement_title]').fill(title)
                                form.locator('[name=announcement_body]').fill('Synthetic disposable acceptance content.')
                                form.locator('[name=announcement_priority]').fill('100')
                                form.locator('[name=announcement_status]').select_option('published')
                                form.locator('[name=announcement_expires]').fill('')
                                form.get_by_role('button', name='Publish changes').click()
                                expect(page.locator('.ok')).to_be_visible()
                                stored = json.loads((app / 'data/content.json').read_text())
                                require(any(x.get('title') == title for x in stored['announcements']), 'Save did not persist')
                                require(any((app / 'backups').glob('content-*.json')), 'Save did not create a backup')
                                page.goto(base)
                                expect(page.locator('.phase6-announcement')).to_contain_text(title)
                            check(f'{width}px local-only publish, backup, and public refresh', publish_test)
                            def privacy_test():
                                response = context.request.get(base)
                                require('no-store' in response.headers.get('cache-control', ''), 'Signed-in home is cacheable')
                                for route in ['member/prayer-team.php', 'admin/prayers.php']:
                                    require(context.request.get(base + route).status == 403,
                                            'Recovery role gained private prayer access')
                                state = page.evaluate("""async () => {
                                  const results=[];
                                  for(const name of await caches.keys()){
                                    const cache=await caches.open(name);
                                    for(const request of await cache.keys()){
                                      const response=await cache.match(request);
                                      results.push({url:request.url,body:await response.text()});
                                    }
                                  }
                                  return results;
                                }""")
                                require(all('/member/' not in x['url'] and '/admin/' not in x['url'] for x in state),
                                        'A private route entered Cache Storage')
                                require(sentinel not in json.dumps(state), 'Private fixture entered Cache Storage')
                                require('Member home' not in ''.join(x['body'] for x in state), 'Personalized home was cached')
                            check(f'{width}px signed-in caching and recovery prayer boundary', privacy_test)
                            def logout_test():
                                require(context.request.get(base + 'member/logout.php').status == 405, 'GET logout accepted')
                                require(context.request.post(base + 'member/logout.php', form={'csrf':'invalid'}).status == 403,
                                        'Invalid-CSRF logout accepted')
                                page.goto(base + 'admin/')
                                page.get_by_role('button', name='Sign out', exact=True).click()
                                expect(page.get_by_role('button', name='Sign in securely')).to_be_visible()
                                page.goto(base + 'admin/')
                                expect(page.get_by_role('button', name='Sign in securely')).to_be_visible()
                            check(f'{width}px protected sign-out and post-logout access', logout_test)
                            def offline_test():
                                nonlocal server
                                page.goto(base)
                                page.evaluate('navigator.serviceWorker.ready')
                                require(page.evaluate('Boolean(navigator.serviceWorker.controller)'),
                                        'Offline test requires a controlling service worker')
                                # Emulation alone left worker network requests reachable in the
                                # initial run. Stop OUR disposable origin, verify its port is closed,
                                # then require public fallback and private-request rejection.
                                server.terminate()
                                server.wait(timeout=5)
                                try:
                                    with socket.socket() as probe:
                                        probe.settimeout(1)
                                        require(probe.connect_ex(('127.0.0.1', port)) != 0,
                                                'Origin is still reachable; outage test is invalid')
                                    context.set_offline(True)
                                    page.reload(wait_until='domcontentloaded')
                                    expect(page.locator('[data-share-app]')).to_be_visible()
                                    require(sentinel not in page.content(), 'Offline home contains private fixture')
                                    require(page.locator('a.topbar-account').inner_text() == 'Member sign in',
                                            'Offline home is personalized')
                                    blocked = page.evaluate("""async () => {
                                      try { await fetch('./member/prayer-team.php'); return false; }
                                      catch (_) { return true; }
                                    }""")
                                    require(blocked, 'Private offline request unexpectedly returned content')
                                finally:
                                    context.set_offline(False)
                                    server = start_server()
                            check(f'{width}px actual-origin-outage public fallback/private network-only behavior', offline_test)
                            check(f'{width}px no uncaught page JavaScript errors', lambda: require(not errors, str(errors)))
                            context.close()
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    summary = {'scope':'Disposable localhost copy; synthetic users and content only',
               'not_tested':['real-device OS sharing','production Apache','production authenticated Publishing Desk'],
               'tests':RESULTS,'passed':sum(x['passed'] for x in RESULTS),'failed':sum(not x['passed'] for x in RESULTS)}
    (OUT / 'results.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'passed':summary['passed'],'failed':summary['failed']}), flush=True)
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
