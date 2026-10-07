#!/usr/bin/env python3
"""Exercise supplied assets with synthetic accounts and temporary storage only."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
ASSETS = json.loads((ROOT / 'docs/supplied-images-2026-10-06.json').read_text())

with tempfile.TemporaryDirectory(prefix='kcmc-publication-images-') as td:
    work = Path(td)
    site = work / 'app'
    shutil.copytree(APP, site, ignore=shutil.ignore_patterns('config.php', 'private', 'backups'))
    before = (site / 'data/content.json').read_bytes()
    private = work / 'private'
    private.mkdir()
    password = 'Synthetic-Image-Review-2031!'
    hashed = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1], PASSWORD_DEFAULT);', password]).decode()
    (private / 'users.json').write_text(json.dumps({'version': 1, 'users': [{
        'id': 'image_review_admin', 'email': 'images@example.invalid',
        'email_normalized': 'images@example.invalid', 'display_name': 'Synthetic Image Reviewer',
        'role': 'pastor_admin', 'active': True, 'password_hash': hashed,
        'created_at': '2031-01-01T00:00:00Z',
    }]}))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}/app'
    env = {**os.environ, 'KCMC_PRIVATE_DATA_DIR': str(private), 'KCMC_SETUP_KEY': ''}
    with open(work / 'server.log', 'w') as log:
        server = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(work)], env=env, stdout=log, stderr=log)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(base + '/', timeout=2).close()
                    break
                except OSError:
                    time.sleep(.1)
            with sync_playwright() as p:
                options = {'executable_path': os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}
                browser = p.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                def login(target):
                    target.goto(base + '/member/login.php')
                    target.locator('[name=email]').fill('images@example.invalid')
                    target.locator('[name=password]').fill(password)
                    target.locator('button[type=submit]').click()
                    target.wait_for_url('**/member/**')
                    target.goto(base + '/admin/publication-designer.php')
                login(page)
                page.locator('#projectName').fill('All supplied KCMC images')
                page.locator('#addPage').click()
                for asset in ASSETS:
                    page.locator(f'[data-asset$="/{asset["file"]}"]').click()
                    img = page.locator('#page .item img').last
                    expect(img).to_have_attribute('alt', asset['alt'])
                    img.evaluate('(img) => img.decode()')
                with page.expect_response('**/publication-projects.php') as saved:
                    page.locator('#saveBtn').click()
                response = saved.value
                assert response.status == 200, response.text()
                project = response.json()['project']
                assert len(project['pages']) == 2
                assert {Path(i['src']).name for i in project['pages'][1]['items']} == {a['file'] for a in ASSETS}
                print('PASS: all nine approved assets and alt text survive shared project validation')
                # A fresh browser context proves the project is not browser-local.
                second = browser.new_context()
                other = second.new_page()
                login(other)
                other.locator('#savedList button').filter(has_text='All supplied KCMC images').click()
                other.locator('#nextPage').click()
                expect(other.locator('#page .item img')).to_have_count(9)
                for asset in ASSETS:
                    img = other.locator(f'#page img[src$="/{asset["file"]}"]')
                    expect(img).to_have_attribute('alt', asset['alt'])
                    img.evaluate('(img) => img.decode()')
                print('PASS: all nine images reload and decode in an independent admin session')
                other.evaluate('window.print = () => { window.imageReviewPrinted = true; }')
                other.locator('#printBtn').click()
                other.wait_for_function('window.imageReviewPrinted === true')
                assert other.locator('#printPages img').count() >= 9
                assert other.locator('#printPages img').evaluate_all('(imgs) => imgs.every(i => i.complete && i.naturalWidth > 0)')
                print('PASS: complete-document print renderer loads the supplied images')
                assert not errors, errors
                browser.close()
            assert (site / 'data/content.json').read_bytes() == before
            assert not (private / 'publication-media.json').exists()
            print('PASS: content unchanged and built-in assets require no private media upload records')
        finally:
            server.terminate()
            server.wait(timeout=10)
