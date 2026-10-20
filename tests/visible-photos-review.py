#!/usr/bin/env python3
"""Read-only visual acceptance and portable preview; never deploys or uses real accounts."""
from __future__ import annotations
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from PIL import Image
from playwright.sync_api import sync_playwright
from welcome_home_assertions import welcome_home

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
OUT = ROOT / 'photo-review-artifacts'
OUT.mkdir(exist_ok=True)
PHOTOS = {'kids-group.jpg': './assets/visuals/kcmc-kids-summer-group.jpg'}

def check(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)
    print('PASS:', message, flush=True)

def export_preview(html: str, photos: dict[str, bytes]) -> None:
    # Export actual public markup/styles. No app.js, service worker, API writes or working forms.
    html = re.sub(r'<script\b[^>]*\bsrc=[^>]*>\s*</script>', '', html, flags=re.I)
    html = re.sub(r'<link\b[^>]*>', '', html, flags=re.I)
    css = '\n'.join((APP / name).read_text() for name in ('styles.css', 'public-presentation.css', 'app-theme.css', 'home-welcome.css'))
    js = (APP / 'public-presentation.js').read_text()
    def uri(blob: bytes, mime: str) -> str:
        return 'data:' + mime + ';base64,' + base64.b64encode(blob).decode()
    for url, blob in photos.items():
        js = js.replace(url, uri(blob, 'image/jpeg'))
    def inline_asset(match: re.Match) -> str:
        prefix, asset = match.group(1), match.group(2)
        path = APP / asset
        return prefix + uri(path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream') if path.is_file() else match.group(0)
    pattern = r'''(["'(])(?:\./)?(assets/[^"')\s]+)'''
    html = re.sub(pattern, inline_asset, html)
    css = re.sub(pattern, inline_asset, css)
    router = """function showPreviewRoute(){const allowed=['home','visit','watch','news','events','serve','partner'];let r=location.hash.slice(1);if(!allowed.includes(r))r='home';document.querySelectorAll('[data-view]').forEach(v=>v.classList.toggle('active',v.dataset.view===r));window.scrollTo(0,0);}window.addEventListener('hashchange',showPreviewRoute);showPreviewRoute();document.querySelectorAll('form').forEach(f=>{f.addEventListener('submit',e=>e.preventDefault());f.querySelectorAll('input,textarea,select,button').forEach(x=>x.disabled=true);});document.querySelectorAll('a').forEach(a=>{if(/^(?!https?:|mailto:|tel:|#).*\\.php/.test(a.getAttribute('href')||'')){a.removeAttribute('href');a.setAttribute('aria-disabled','true');a.title='Available in the deployed app; this is a local preview.';}});document.querySelectorAll('[data-install-app],[data-share-app]').forEach(b=>{if(b.tagName==='BUTTON'){b.disabled=true;b.title='Available in the deployed app.';}});"""
    notice = '<div style="padding:12px 20px;background:#f6dfa9;color:#102436;font:700 14px/1.4 system-ui" role="note">LOCAL REVIEW — New church hero and kids photo. Not deployed. Forms disabled.</div>'
    html = html.replace('</head>', '<style>' + css + '</style></head>')
    html = re.sub(r'(<body[^>]*>)', r'\1' + notice, html, count=1)
    html = html.replace('</body>', '<script>' + js + '\n' + router + '</script></body>')
    check('navigator.serviceWorker.register' not in html, 'portable preview does not install a service worker')
    check('<script src=' not in html, 'portable preview has no external script dependency')
    (OUT / 'KCMC-Tony-Visible-Preview.html').write_text(html)

photo_bytes: dict[str, bytes] = {}
manifest = {}
for name, url in PHOTOS.items():
    blob = (APP / url.removeprefix('./')).read_bytes()
    check(len(blob) <= 600_000, name + ' is under the 600 KB mobile image budget')
    path = OUT / name
    path.write_bytes(blob)
    with Image.open(path) as image:
        check(image.format == 'JPEG', name + ' is a valid JPEG')
        check(image.width >= 900 and image.height >= 500, name + ' has adequate display dimensions')
        dimensions = [image.width, image.height]
        image.verify()
    photo_bytes[url] = blob
    manifest[name] = {'source': url, 'dimensions': dimensions, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}
(OUT / 'photo-sources.json').write_text(json.dumps(manifest, indent=2) + '\n')

with tempfile.TemporaryDirectory(prefix='kcmc-photos-review-') as td:
    work = Path(td)
    site = work / 'app'
    shutil.copytree(APP, site, ignore=shutil.ignore_patterns('config.php', 'private', 'backups'))
    data = site / 'data/content.json'
    before = data.read_bytes()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}/app/'
    env = {**os.environ, 'KCMC_PRIVATE_DATA_DIR': str(work / 'private'), 'KCMC_SETUP_KEY': ''}
    with open(work / 'php.log', 'w+') as log:
        server = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(work)], stdout=log, stderr=log, env=env)
        try:
            for _ in range(60):
                try:
                    with urllib.request.urlopen(base, timeout=2) as response:
                        html = response.read().decode()
                        check(not response.headers.get('Set-Cookie'), 'anonymous page creates no session')
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Local fixture server did not start')
            export_preview(html, photo_bytes)
            with sync_playwright() as p:
                options = {}
                if os.environ.get('KCMC_CHROMIUM_PATH'):
                    options['executable_path'] = os.environ['KCMC_CHROMIUM_PATH']
                browser = p.chromium.launch(**options)
                errors = []
                for width in [320, 390, 1440]:
                    context = browser.new_context(viewport={'width': width, 'height': 960}, reduced_motion='reduce')
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    for url, blob in photo_bytes.items():
                        page.route('**/' + url.removeprefix('./'), lambda route, request, body=blob: route.fulfill(status=200, content_type='image/jpeg', body=body))
                    page.goto(base, wait_until='networkidle')
                    check(page.locator('.hero-church-photo, .hero-church-window, .hero-card-with-photo').count() == 0, f'{width}px no nested picture-on-picture hero')
                    welcome_home(page,width,check)
                    check(page.locator('[data-hero-caption]').count() == 0, f'{width}px no hero source caption element')
                    check(page.locator('section[aria-label="KCMC kids and family photos"] [data-kcmc-photo-gallery] img').count() == 3, 'three supplied family activity photos remain in their original public gallery')
                    family = page.locator('[data-family-welcome]')
                    family.scroll_into_view_if_needed()
                    page.wait_for_function("document.querySelector('.family-photo')?.naturalWidth > 0")
                    page.locator('.family-photo').evaluate('(img) => img.decode()')
                    check(family.count() == 1, f'{width}px one family section')
                    check(page.locator('.family-photo').get_attribute('src') == PHOTOS['kids-group.jpg'], f'{width}px new kids photo loads')
                    check('summer kick-off' in page.locator('.family-photo').get_attribute('alt'), f'{width}px useful supplied photo description')
                    check(page.locator('.family-photo-frame .photo-source, .family-photo-frame figcaption').count() == 0, f'{width}px family photo has no visible source caption')
                    check(page.locator('.family-welcome-copy').is_hidden(), f'{width}px family photo stays free of extra navigation and promotional copy')
                    page.locator('#siteMenu summary').click()
                    check(page.locator('#siteMenu').get_by_role('link', name='Kids & youth', exact=True).get_attribute('href') == 'https://www.kimberlingcitymethodist.com/youth', f'{width}px youth ministry destination retained inside the fish')
                    page.keyboard.press('Escape')
                    check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{width}px no horizontal overflow')
                    page.evaluate('document.activeElement?.blur(); window.scrollTo(0,0)')
                    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                    screenshot = OUT / f'homepage-{width}.png'
                    page.screenshot(path=str(screenshot), full_page=True)
                    with Image.open(screenshot) as full:
                        for selector, name in [('.hero', 'new-hero'), ('[data-family-welcome]', 'new-kids')]:
                            box = page.locator(selector).bounding_box()
                            check(box is not None, f'{width}px {name} has a rendered box')
                            left, top = round(box['x']), round(box['y'])
                            full.crop((left, top, left + round(box['width']), top + round(box['height']))).save(OUT / f'{name}-{width}.png')
                    page.locator('#siteMenu summary').click()
                    page.locator('#siteMenu [data-route="visit"]').click()
                    page.locator('[data-view="visit"]').wait_for(state='visible', timeout=10000)
                    check(page.url.endswith('#visit'), f'{width}px fish visit link navigates')
                    page.goto(base, wait_until='networkidle')
                    page.locator('#siteMenu summary').click()
                    page.keyboard.press('Escape')
                    check(page.locator('#siteMenu').get_attribute('open') is None, f'{width}px menu keyboard control retained')
                    context.close()
                fallback = browser.new_context(service_workers='block', viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
                page = fallback.new_page()
                for url in photo_bytes:
                    page.route('**/' + url.removeprefix('./'), lambda route: route.abort())
                page.goto(base, wait_until='networkidle')
                # Trigger the lazy photo request without scrolling a section
                # that deliberately disappears as soon as its image fails.
                page.locator('.family-photo').evaluate("img => { img.loading = 'eager'; }")
                page.wait_for_function("document.querySelector('.family-photo-frame')?.hidden === true")
                check(page.locator('[data-family-welcome]').is_hidden(), 'failed family photo leaves no empty homepage section')
                check(page.locator('.hero-church-window').count() == 0, 'failed remote hero does not replace the local fallback')
                check('kcmc-building-original-20261018.jpg' in page.locator('[data-authentic-building]').get_attribute('src'), 'original church photo survives family photo failure')
                check(page.locator('[data-authentic-building]').evaluate('(img)=>img.complete&&img.naturalWidth===1536'), 'original church photograph still decodes')
                check(page.locator('[data-hero-caption],[data-hero-controls]').count() == 0, 'no retired carousel or caption appears after family photo failure')
                check(page.locator('.family-welcome-copy').is_hidden(), 'failed family photo does not restore homepage promotional copy')
                check(page.locator('.family-photo-frame').is_hidden(), 'failed kids photo does not leave a broken-image placeholder')
                page.locator('#siteMenu summary').click()
                check(page.locator('#siteMenu [data-route="visit"]').is_visible() and page.locator('#siteMenu').get_by_role('link', name='Kids & youth', exact=True).is_visible(), 'visit and youth destinations survive photo failure in the fish')
                fallback.close()
                check(not errors, 'no JavaScript errors: ' + '; '.join(errors))
                browser.close()
            check(data.read_bytes() == before, 'no editorial content was changed')
            print('Portable preview and source photos exported.', flush=True)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
print('Visible photo refresh acceptance passed.', flush=True)
