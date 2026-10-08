#!/usr/bin/env python3
"""Real-worker warm offline and missing-photo regression on localhost only.

Use the approved public hero/JS/SW and image bytes, with synthetic public pages.
No PHP, accounts, church content files, remote browser requests or submissions.
"""
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
BASE = '61c70f590735522adbfd6be02dab6888924a54fd'
PINS = {
    'index.php': '0cd9bee7066cbcd3d18941b749ca5990f65e9ce3124f8330703add0143808a8f',
    'public-presentation.js': '5dfe8c3dc99e5c8771f383157cdfc1f3def1f4e72810094a16e6203dbaf4c150',
    'sw.js': '11091e96760a045f952650a8e720ed02607307cb87173f5978cd9f246c6fdfd0',
}
MISSING = 'assets/visuals/kcmc-ministry-group.jpg'


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print('PASS:', label, flush=True)


def baseline(name):
    if os.environ.get('KCMC_PHOTO_BASELINE_DIR'):
        content = (Path(os.environ['KCMC_PHOTO_BASELINE_DIR']) / name).read_bytes()
    else:
        content = subprocess.check_output(['git', 'show', BASE + ':KCMC-Connect-Phase6-Recreated/' + name], cwd=ROOT)
    check(hashlib.sha256(content).hexdigest() == PINS[name], name + ': stale negative-control source remains pinned')
    return content


def build_site(site, sources):
    site.mkdir()
    index = sources['index.php'].decode()
    hero = re.search(r'<section class="hero hero-imagery" data-hero-gallery.*?</section>', index, re.S).group()
    paths = re.findall(r'data-hero-photo[^>]*src="\./([^"]+)"', hero)
    check(len(paths) == 9 and MISSING in paths, 'fixture retains all nine real public hero paths')
    script = re.search(r'<script src="(public-presentation\.js\?v=[^"]+)" defer>', index).group(1)
    html = ('<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="stylesheet" href="styles.css?v=3.0.3"><link rel="stylesheet" href="public-presentation.css?v=contemporary-bright-20261007"></head>'
            '<body><header style="height:100px">Synthetic offline review</header><main><section class="view active" data-view="home">'
            + hero + '<div data-family-welcome></div></section></main>'
            + '<script src="' + script + '" defer></script>'
            + '<script>navigator.serviceWorker.register("./sw.js");</script></body></html>')
    (site / 'index.html').write_text(html)
    (site / 'index.php').write_text(html)
    for name in ('public-presentation.js', 'sw.js'):
        (site / name).write_bytes(sources[name])
    for name in ('styles.css', 'public-presentation.css'):
        shutil.copyfile(APP / name, site / name)
    # Cache the real public images/icons, never copy data/, config or private code.
    shutil.copytree(APP / 'assets', site / 'assets')
    for name in ('bulletin.php', 'news.php', 'events.php', 'care.php', 'connect.php'):
        (site / name).write_text('<!doctype html><p>Synthetic public page</p>')
    (site / 'app.js').write_text('/* Synthetic unused public bundle. */\n')
    (site / 'manifest.webmanifest').write_text(json.dumps({'name': 'Synthetic offline review', 'start_url': './'}))


# Capture only the real gallery timer. Invoking its stored callback avoids a
# seven-minute wall-clock sleep while preserving and checking its actual delay.
TIMER_HARNESS = '''(() => {
 const set = window.setTimeout.bind(window), clear = window.clearTimeout.bind(window);
 const timers = new Map(); let serial = 0;
 window.setTimeout = (fn, delay, ...args) => {
   if (delay !== 420000) return set(fn, delay, ...args);
   const id = 'photo-review-' + (++serial); timers.set(id, {fn, delay, args}); return id;
 };
 window.clearTimeout = id => { if (timers.has(id)) timers.delete(id); else clear(id); };
 window.photoReview = {
   delays: () => [...timers.values()].map(timer => timer.delay),
   advance: () => { const entry = timers.entries().next().value; if (!entry) throw Error('No gallery timer');
     const [id, timer] = entry; timers.delete(id); timer.fn(...timer.args); }
 };
})();'''


def eventually(page, expression, label, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        time.sleep(.05)
    raise AssertionError(label)


def current(page):
    return page.locator('[data-hero-photo]').evaluate_all('(photos) => photos.findIndex(photo => !photo.hidden)')


def assert_one_photo(page, expected, label):
    check(current(page) == expected, label)
    check(page.locator('[data-hero-photo]:not([hidden])').count() == 1, label + ': single hero image plane')


def warm_offline(browser, base, missing=False):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, service_workers='allow')
    context.add_init_script(TIMER_HARNESS)
    # A browser or worker can contact only this local synthetic fixture.
    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base.rsplit('/', 2)[0] + '/') else route.abort())
    warm = context.new_page()
    warm.goto(base, wait_until='load')
    eventually(warm, 'Boolean(navigator.serviceWorker.controller)', 'real worker must control fixture')
    eventually(warm, '[...document.querySelectorAll("[data-hero-photo]")].every(img => img.complete && img.naturalWidth > 0)', 'all real public images must decode online')
    if missing:
        removed = warm.evaluate('''async name => {
          const keys = await caches.keys(); let count = 0;
          for (const key of keys) { const cache = await caches.open(key); count += await cache.delete(new URL(name, location.href)); }
          return count;
        }''', MISSING)
        check(removed == 1, 'missing-photo case removes only the fourth frame from the actual worker cache')
    # Clear the ordinary HTTP cache so it cannot hide the worker cache bug.
    session = context.new_cdp_session(warm)
    session.send('Network.clearBrowserCache')
    warm.close()
    context.set_offline(True)
    page = context.new_page()
    session = context.new_cdp_session(page)
    session.send('Network.setCacheDisabled', {'cacheDisabled': True})
    page.goto(base, wait_until='load')
    eventually(page, '[...document.querySelectorAll("[data-hero-photo]")].every(img => img.complete)', 'offline image requests must finish')
    check(page.locator('[data-hero-caption], figcaption').count() == 0, 'offline public hero has no visible caption payload')
    return context, page


with tempfile.TemporaryDirectory(prefix='kcmc-public-photo-offline-') as td:
    work = Path(td)
    stale = {name: baseline(name) for name in PINS}
    fixed = {name: (APP / name).read_bytes() for name in PINS}
    for label, sources in [('stale', stale), ('fixed', fixed), ('missing', fixed)]:
        build_site(work / label, sources)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(work), **kwargs)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            options = {'executable_path': os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}
            browser = p.chromium.launch(**options)
            origin = 'http://127.0.0.1:' + str(server.server_port)
            context, page = warm_offline(browser, origin + '/stale/')
            check(page.locator('[data-hero-photo]').nth(3).evaluate('(img) => img.naturalWidth') == 0, 'stale worker reproduces fourth-frame offline loss')
            for _ in range(4):
                page.locator('[data-hero-next]').click()
            assert_one_photo(page, 2, 'stale gallery reproduces rotation freeze before supplied bridge images')
            context.close()

            context, page = warm_offline(browser, origin + '/fixed/')
            check(page.locator('[data-hero-photo]').evaluate_all('(imgs) => imgs.every(img => img.naturalWidth > 0)'), 'fixed real worker serves all nine hero images after a warm offline reload')
            for expected in list(range(1, 9)) + [0]:
                page.locator('[data-hero-next]').click()
                assert_one_photo(page, expected, 'offline Next reaches photo ' + str(expected + 1))
            page.locator('[data-hero-previous]').click()
            assert_one_photo(page, 8, 'offline Previous wraps backward to final supplied bridge artwork')
            check(page.locator('[data-hero-toggle]').inner_text() == 'Play photos', 'manual navigation pauses automatic changes')
            check(page.locator('[data-hero-status]').inner_text().startswith('Photo 9 of 9.'), 'manual navigation announces the actual selected frame')
            for relative in ['member/login.php', 'admin/publication-designer.php', 'api/public-content.php', 'data/content.json', 'backups/test.json', '?token=synthetic', MISSING + '?token=synthetic']:
                result = page.evaluate('''async path => {
                    const url = new URL(path, location.href); let resolved = false;
                    try { await fetch(url); resolved = true; } catch (_) {}
                    const keys = await caches.keys(); let cached = false;
                    for (const key of keys) cached ||= Boolean(await (await caches.open(key)).match(url));
                    return {resolved, cached};
                }''', relative)
                check(result == {'resolved': False, 'cached': False}, relative + ': private/token route stays network only offline')
            context.close()

            context, page = warm_offline(browser, origin + '/missing/', missing=True)
            check(page.locator('[data-hero-photo]').nth(3).evaluate('(img) => img.naturalWidth') == 0, 'missing-frame regression has a real decoded-image failure')
            page.mouse.move(10, 10)
            check(page.evaluate('photoReview.delays()') == [420000], 'automatic rotation retains one seven-minute timer')
            for expected in (1, 2, 4):
                page.evaluate('photoReview.advance()')
                assert_one_photo(page, expected, 'automatic rotation skips missing frame without blocking later photos')
                check(page.evaluate('photoReview.delays()') == [420000], 'automatic advance schedules the next seven-minute interval')
            check(page.locator('[data-hero-status]').inner_text() == '', 'automatic changes keep the accessibility live region quiet')
            page.locator('[data-hero-previous]').click()
            assert_one_photo(page, 2, 'Previous skips missing fourth frame backward')
            page.locator('[data-hero-next]').click()
            assert_one_photo(page, 4, 'Next skips missing fourth frame forward')
            for expected in (5, 6, 7, 8, 0):
                page.locator('[data-hero-next]').click()
                assert_one_photo(page, expected, 'missing-frame recovery reaches remaining supplied artwork')
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
