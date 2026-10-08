#!/usr/bin/env python3
"""Publisher fidelity regressions using real editor JS and PHP item validators.

All accounts, projects, photos, and fetch responses are synthetic. No production
requests or records are used. --app selects a pinned baseline or patched app;
--case allows each baseline defect to fail independently as a negative control.
Requires PHP 8.2, Playwright, and Chromium. This does not certify host auth/storage.
"""
import argparse
from copy import deepcopy
import html
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from urllib.parse import urlparse
import zlib

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
CSRF = 'synthetic-fidelity-fixture-csrf'
AUTHOR_TEXT = '\n \t  Prayer \t \n\nScripture  \n\t\n________\n\n \t  '


def png_fixture():
    def chunk(kind, body):
        return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(b'\x00\x00\x00\x00\x00')) + chunk(b'IEND', b''))


PNG = png_fixture()


def fixture_html(source):
    source = re.sub(r'\A<\?php.*?\?>', '', source, count=1, flags=re.S)

    def replace(match):
        expression = match.group(1)
        path = re.search(r"kcmc_url\('([^']+)'\)", expression)
        if path:
            value = '/' + path.group(1)
            return json.dumps(value) if expression.startswith('json_encode(') else html.escape(value, quote=True)
        if expression == 'json_encode(kcmc_csrf(), JSON_UNESCAPED_SLASHES)':
            return json.dumps(CSRF)
        raise AssertionError('Unexpected PHP expression in editor fixture: ' + expression)

    rendered = re.sub(r'<\?=(.*?)\?>', replace, source, flags=re.S)
    assert '<?' not in rendered
    return rendered.replace('<head>', '<head><base href="https://publisher-fixture.invalid/">', 1)


class Fixture:
    def __init__(self, browser, app):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-publication-fidelity-')
        self.private = Path(self.temp.name)
        (self.private / 'publication-media').mkdir()
        self.php = os.environ.get('KCMC_PHP_PATH') or shutil.which('php')
        if not self.php:
            self.temp.cleanup()
            raise RuntimeError('PHP is required to exercise the actual project text validator')
        projects = (app / 'admin/publication-projects.php').read_text()
        begin, end = projects.index('function pub_fail('), projects.index('$method =')
        # Execute the actual pinned pub_* validator helpers. Only infrastructure
        # helpers are synthetic; no bootstrap, session, HTTP, or audit runs here.
        driver = '''<?php
declare(strict_types=1);
define('KCMC_PRIVATE_DATA', $argv[1]);
function kcmc_text_length(string $text): int { return function_exists('mb_strlen') ? mb_strlen($text, 'UTF-8') : strlen($text); }
function kcmc_url(string $path): string { return '/' . $path; }
function kcmc_read_json_store(string $path, array $default): array {
    $raw = @file_get_contents($path);
    $value = $raw === false ? null : json_decode($raw, true);
    return is_array($value) ? $value : $default;
}
''' + projects[begin:end] + '''
$input = json_decode(stream_get_contents(STDIN), true, 512, JSON_THROW_ON_ERROR);
$output = ['name' => pub_text($input['name'], 120), 'pages' => []];
foreach ($input['pages'] as $page) $output['pages'][] = pub_page($page);
echo json_encode($output, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
'''
        self.driver = self.private / 'normalize.php'
        self.driver.write_text(driver)
        self.store, self.saves, self.media, self.errors = {}, [], [], []
        self.context = browser.new_context(viewport={'width': 1500, 'height': 1100}, service_workers='block')
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

        def route_image(route):
            url = urlparse(route.request.url)
            if url.hostname == 'publisher-fixture.invalid' and (
                    url.path.startswith('/assets/visuals/') or url.path == '/admin/publication-media.php'):
                route.fulfill(status=200, content_type='image/png', body=PNG)
            else:
                route.abort()

        self.page.route('**/*', route_image)
        self.page.expose_function('__fixtureProject', self.project_request)
        self.page.expose_function('__fixtureMedia', self.media_request)
        self.page.evaluate('''() => {
            window.__heldUpload = null;
            window.__holdNextUpload = false;
            window.__uploadFinished = 0;
            window.print = () => {window.__printed = true};
            window.fetch = async (url, options = {}) => {
                const method = options.method || 'GET';
                if(url === '/admin/publication-projects.php') {
                    const payload = await window.__fixtureProject(method, options.body || null);
                    return {ok: true, json: async () => payload};
                }
                if(url === '/admin/publication-media.php') {
                    const hold = method === 'POST' && window.__holdNextUpload;
                    if(method === 'POST') window.__holdNextUpload = false;
                    const payload = await window.__fixtureMedia(method);
                    if(hold) await new Promise(resolve => {window.__heldUpload = {release: resolve}});
                    return {ok: true, json: async () => payload};
                }
                throw new Error('Unexpected synthetic fetch: ' + url);
            };
        }''')
        self.page.set_content(fixture_html((app / 'admin/publication-designer.php').read_text()))
        self.page.wait_for_function("document.querySelector('#savedList').textContent.includes('No shared projects')")
        self.page.wait_for_function("document.querySelector('#sharedMediaLibrary').textContent.includes('No shared uploads')")
        # Observe completion of the real event handler, including library refresh.
        self.page.evaluate('''() => {
            const picker = document.querySelector('#imagePicker'), actual = picker.onchange;
            picker.onchange = async event => {try {await actual(event)} finally {window.__uploadFinished++}};
        }''')

    def close(self):
        self.context.close()
        self.temp.cleanup()

    def normalize(self, project):
        result = subprocess.run([self.php, str(self.driver), str(self.private)],
                                input=json.dumps(project, ensure_ascii=False), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return json.loads(result.stdout)

    def project_request(self, method, body):
        if method == 'GET':
            return {'ok': True, 'projects': deepcopy(list(self.store.values()))}
        assert method == 'POST'
        project = json.loads(body)
        assert project.pop('csrf') == CSRF
        normalized = self.normalize(project)
        normalized['id'] = project.get('id') or 'pub_' + format(len(self.store) + 1, '024x')
        normalized['updated'] = '2031-01-01T00:00:00Z'
        self.store[normalized['id']] = deepcopy(normalized)
        self.saves.append(deepcopy(normalized))
        return {'ok': True, 'project': deepcopy(normalized)}

    def media_request(self, method):
        if method == 'GET':
            return {'ok': True, 'media': deepcopy(self.media)}
        assert method == 'POST'
        media_id = 'pubmedia_' + format(len(self.media) + 1, '024x')
        filename = media_id + '.png'
        (self.private / 'publication-media' / filename).write_bytes(PNG)
        item = {'id': media_id, 'label': 'Delayed upload fixture', 'file': filename,
                'url': '/admin/publication-media.php?id=' + media_id,
                'mime': 'image/png', 'bytes': len(PNG), 'width': 1, 'height': 1}
        self.media.append(item)
        (self.private / 'publication-media.json').write_text(json.dumps({'version': 1, 'media': self.media}))
        return {'ok': True, 'media': deepcopy(item)}

    def save(self, name=None):
        if name is not None:
            self.page.locator('#projectName').fill(name)
        prior = len(self.saves)
        self.page.locator('#saveBtn').click()
        self.page.wait_for_function("document.querySelector('#status').textContent === 'Saved for KCMC admins' && !document.querySelector('#saveBtn').disabled")
        assert len(self.saves) == prior + 1
        return deepcopy(self.saves[-1])

    def load(self, name):
        self.page.locator('#savedList button').filter(has=self.page.get_by_text(name, exact=True)).click()

    def print_pages(self):
        self.page.evaluate('window.__printed = false')
        self.page.locator('#printBtn').click()
        self.page.wait_for_function('window.__printed === true')

    def held_upload(self):
        self.page.evaluate('window.__holdNextUpload = true')
        self.page.locator('#imagePicker').set_input_files({'name': 'synthetic-approved.png',
                                                          'mimeType': 'image/png', 'buffer': PNG})
        self.page.wait_for_function('window.__heldUpload !== null')

    def release_upload(self):
        prior = self.page.evaluate('window.__uploadFinished')
        self.page.evaluate('window.__heldUpload.release()')
        self.page.wait_for_function('window.__uploadFinished > ' + str(prior))
        self.page.evaluate('window.__heldUpload = null')


def whitespace(fixture):
    page = fixture.page
    page.locator('#page').evaluate('el => el.innerHTML = ""')
    page.locator('#addText').click()
    page.locator('#page .item[data-type="text"]').evaluate('''(el, text) => {
        const handle = el.querySelector('.handle');el.textContent = text;el.appendChild(handle);
    }''', AUTHOR_TEXT)
    saved = fixture.save('  Whitespace fixture  ')
    assert saved['pages'][0]['items'][0]['text'] == AUTHOR_TEXT, 'Authored boundary tabs/spaces/blank lines lost by real PHP validator'
    assert saved['pages'][0]['items'][0]['fill'] == '#ffffff', 'Transparent text background should retain the existing white print fallback'
    assert saved['name'] == 'Whitespace fixture', 'Project name metadata must remain trimmed'
    metadata = fixture.normalize({'name': ' \t Synthetic name \t ', 'pages': saved['pages']})
    assert metadata['name'] == 'Synthetic name' and metadata['pages'][0]['items'][0]['text'] == AUTHOR_TEXT
    page.locator('#newBtn').click()
    fixture.load('Whitespace fixture')
    restored = page.locator('#page .item[data-type="text"]')
    assert restored.text_content() == AUTHOR_TEXT, 'Reopen changed authored boundary whitespace'
    assert restored.evaluate('el => getComputedStyle(el).whiteSpace') == 'pre-wrap'
    fixture.print_pages()
    assert page.locator('#printPages .item[data-type="text"]').text_content() == AUTHOR_TEXT, 'Print changed authored whitespace'
    assert page.locator('#printPages .handle').count() == 0
    print('PASS: real PHP Save/reopen/print preserve authored whitespace while metadata remains trimmed', flush=True)


def black(fixture):
    page = fixture.page
    page.locator('#page').evaluate('el => el.innerHTML = ""')
    page.locator('#addShape').click()
    page.locator('#fillColor').evaluate('''el => {el.value = '#000000';el.dispatchEvent(new Event('input', {bubbles:true}))}''')
    assert page.locator('#page .item').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgb(0, 0, 0)'
    saved = fixture.save('Black fill fixture')
    assert saved['pages'][0]['items'][0]['fill'] == '#000000', 'Opaque black was serialized as white'
    page.locator('#newBtn').click()
    fixture.load('Black fill fixture')
    assert page.locator('#page .item').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgb(0, 0, 0)', 'Reopen changed black fill'
    page.locator('#page .item').click(position={'x': 20, 'y': 20})
    assert page.locator('#fillColor').input_value() == '#000000', 'Selecting an opaque black item changed its Fill control to white'
    fixture.print_pages()
    assert page.locator('#printPages .item').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgb(0, 0, 0)', 'Print changed black fill'
    print('PASS: opaque black survives serialization, real PHP normalization, reopen and print', flush=True)


def postcard(fixture):
    page = fixture.page
    page.locator('[data-template="postcard"]').click()
    assert page.locator('#orientation').input_value() == 'landscape'
    dimensions = page.locator('#page').evaluate('el => [el.style.width, el.style.height]')
    assert dimensions == ['576px', '384px'], ('Postcard landscape must be 6×4 inches', dimensions)
    bounds = page.locator('#page').evaluate('''el => [...el.querySelectorAll('.item')].map(item => ({
        right: parseFloat(item.style.left) + parseFloat(item.style.width),
        bottom: parseFloat(item.style.top) + parseFloat(item.style.height)
    }))''')
    assert bounds and all(item['right'] <= 576 and item['bottom'] <= 384 for item in bounds), 'Postcard template overflows its canvas'
    saved = fixture.save('Postcard fixture')
    assert saved['pages'][0]['pageSize'] == 'postcard' and saved['pages'][0]['orientation'] == 'landscape'
    page.locator('#newBtn').click()
    fixture.load('Postcard fixture')
    assert page.locator('#page').evaluate('el => [el.style.width, el.style.height]') == ['576px', '384px']
    fixture.print_pages()
    assert page.locator('#printPages .page').evaluate('el => [el.style.width, el.style.height]') == ['576px', '384px']
    page.locator('#orientation').select_option('portrait')
    assert page.locator('#page').evaluate('el => [el.style.width, el.style.height]') == ['384px', '576px']
    print('PASS: 6×4 postcard template fits landscape canvas through Save/reopen/print; portrait is 4×6', flush=True)


def upload(fixture):
    page = fixture.page
    # An unchanged canvas still receives its uploaded image, proving the repair
    # preserves the normal Photo action rather than suppressing all insertions.
    fixture.held_upload()
    fixture.release_upload()
    assert page.locator('#page .item[data-type="image"]').count() == 1
    normal = fixture.save('Normal uploaded photo')
    assert any(item.get('mediaId') for item in normal['pages'][0]['items'])
    for action in ['New', 'Load', 'Duplicate', 'Page', 'Template']:
        page.locator('#newBtn').click()
        if action == 'Load':
            fixture.save('Load destination')
            page.locator('#newBtn').click()
        if action == 'Page':
            page.locator('#addPage').click()
            page.locator('#prevPage').click()
        fixture.held_upload()
        if action == 'Load':
            fixture.load('Load destination')
        elif action == 'Page':
            page.locator('#nextPage').click()
        elif action == 'Template':
            page.locator('[data-template="study"]').click()
        else:
            page.locator('#newBtn' if action == 'New' else '#duplicateBtn').click()
        name = page.locator('#projectName').input_value()
        status = page.locator('#status').inner_text()
        images = page.locator('#page .item[data-type="image"]').count()
        fixture.release_upload()
        assert page.locator('#projectName').input_value() == name
        assert page.locator('#status').inner_text() == status, action + ': stale upload overwrote the current editor status'
        assert page.locator('#page .item[data-type="image"]').count() == images, action + ': stale upload inserted a photo into the changed canvas'
        # Uploaded bytes remain available for deliberate reuse from the library.
        assert page.locator('#sharedMediaLibrary button').count() == len(fixture.media)
        captured = fixture.save(action + ' after delayed upload')
        assert all(item['type'] != 'image' for pg in captured['pages'] for item in pg['items']), action + ': stale upload changed a stored publication/page'
        print('PASS:', action, 'retains editor/page state while delayed upload remains in shared library', flush=True)


CASES = {'whitespace': whitespace, 'black': black, 'postcard': postcard, 'upload': upload}


def run(app, selected):
    with sync_playwright() as pw:
        executable = os.environ.get('KCMC_CHROMIUM_PATH') or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        launch = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            launch['executable_path'] = executable
        browser = pw.chromium.launch(**launch)
        try:
            for name in CASES if selected == 'all' else [selected]:
                fixture = Fixture(browser, app)
                try:
                    CASES[name](fixture)
                    assert fixture.errors == [], fixture.errors
                finally:
                    fixture.close()
        finally:
            browser.close()
    print('Publication fidelity passed; synthetic endpoints and real pinned PHP validators, no host acceptance claimed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=DEFAULT_APP)
    parser.add_argument('--case', choices=['all'] + list(CASES), default='all')
    args = parser.parse_args()
    run(args.app, args.case)
