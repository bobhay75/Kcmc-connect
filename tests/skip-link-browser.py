#!/usr/bin/env python3
"""Keyboard acceptance in temporary public copies; no production/form requests."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--html', type=Path, help='Previously rendered local fixture; otherwise render with PHP')
parser.add_argument('--app-js', type=Path, help='Explicit previous-source negative control')
parser.add_argument('--expect-defect', action='store_true')
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix='kcmc-skip-link-') as temporary:
    work = Path(temporary)
    app = work / 'app'
    shutil.copytree(ROOT / 'KCMC-Connect-Phase6-Recreated', app,
                    ignore=shutil.ignore_patterns('config.php', 'private', 'backups'))
    before = hashlib.sha256((app / 'data/content.json').read_bytes()).hexdigest()
    if args.app_js:
        (app / 'app.js').write_bytes(args.app_js.read_bytes())
    if args.html:
        html = args.html.read_bytes()
    else:
        env = {**os.environ, 'KCMC_PRIVATE_DATA_DIR': str(work / 'private'), 'KCMC_SETUP_KEY': ''}
        html = subprocess.run(['php', str(app / 'index.php')], cwd=app, env=env,
                              capture_output=True, check=True).stdout
    errors = []
    writes = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *values): pass
        def do_POST(self):
            writes.append(self.path); self.send_error(405)
        def do_GET(self):
            name = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip('/')
            if name in ('', 'index.php'):
                data, kind = html, 'text/html; charset=utf-8'
            elif name == 'api/content.php':
                data, kind = b'{"announcements":[]}', 'application/json'
            elif name in ('app.js','styles.css','public-presentation.js','public-presentation.css','home-welcome.css','app-theme.css','app-navigation.js') or name.startswith('assets/'):
                target = (app / name).resolve()
                if not target.is_relative_to(app) or not target.is_file():
                    self.send_error(404); return
                data = target.read_bytes()
                kind = 'text/css' if name.endswith('.css') else 'text/javascript' if name.endswith('.js') else 'image/svg+xml' if name.endswith('.svg') else 'image/png' if name.endswith('.png') else 'image/webp' if name.endswith('.webp') else 'image/jpeg'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port) + '/'
    cases = 0
    try:
        with sync_playwright() as p:
            options = {'executable_path': os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'], **options)
            for width in (320, 390, 1440):
                context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce', service_workers='block')
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
                for fragment in ('', '#home', '#visit', '#events'):
                    page.goto(base + fragment, wait_until='networkidle')
                    expected = fragment.lstrip('#') or 'home'
                    initial = page.evaluate('''() => ({hash:location.hash,title:document.title,history:history.length,current:[...document.querySelectorAll('[data-route][aria-current="page"]')].map(a=>a.dataset.route)})''')
                    page.locator('.skip-link').focus(); page.keyboard.press('Enter')
                    if args.expect_defect:
                        page.wait_for_function('location.hash === "#mainContent" && document.querySelector("[data-view].active").dataset.view === "home"')
                        assert page.locator('[data-view].active').get_attribute('data-view') == 'home'
                        assert page.evaluate('document.activeElement.id') != 'mainContent'
                        cases += 1; continue
                    assert page.evaluate('document.activeElement.id') == 'mainContent', 'Skip must focus main'
                    assert page.locator('[data-view].active').get_attribute('data-view') == expected, 'Skip must preserve current section'
                    assert page.evaluate('''() => ({hash:location.hash,title:document.title,history:history.length,current:[...document.querySelectorAll('[data-route][aria-current="page"]')].map(a=>a.dataset.route)})''') == initial, 'Skip must preserve route, title, history and navigation state'
                    assert page.evaluate('document.getElementById("mainContent").getBoundingClientRect().top >= document.querySelector(".topbar").getBoundingClientRect().bottom - 1'), 'Sticky header must not cover content start'
                    page.keyboard.press('Tab')
                    assert page.evaluate('''() => {const node=document.activeElement;return node.closest('[data-view]')?.dataset.view === document.querySelector('[data-view].active').dataset.view && node.getBoundingClientRect().top >= document.querySelector('.topbar').getBoundingClientRect().bottom - 1;}'''), 'Next Tab must enter visible current content below the menu'
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'No horizontal overflow'
                    page.locator('.skip-link').focus()
                    page.locator('.skip-link').click()
                    assert page.evaluate('document.activeElement.id') == 'mainContent', 'Repeated pointer activation must focus main'
                    cases += 1
                if not args.expect_defect:
                    page.goto(base + '#visit', wait_until='networkidle')
                    page.evaluate('location.hash="events"')
                    page.wait_for_function('document.querySelector("[data-view].active").dataset.view === "events"')
                    page.go_back(); page.wait_for_function('document.querySelector("[data-view].active").dataset.view === "visit"')
                    page.go_forward(); page.wait_for_function('document.querySelector("[data-view].active").dataset.view === "events"')
                context.close()
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert not errors, errors
    assert not writes, writes
    assert hashlib.sha256((app / 'data/content.json').read_bytes()).hexdigest() == before
    print('PASS:', cases, 'previous-source skip defects reproduced' if args.expect_defect else 'keyboard/route/focus/header/next-Tab cases; pointer and history navigation preserved; no form or data writes')
