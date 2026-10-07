#!/usr/bin/env python3
"""Offline Publication Designer save-response regression; no live records.

Runs the real editor JavaScript in Chromium with synthetic project/media endpoints.
The fixture persists a request before deliberately delaying its response. This
tests browser state ownership, not PHP authorization or production persistence.
Requires Playwright and Chromium; accepts --source for a baseline negative run.
"""
import argparse
import base64
from copy import deepcopy
import html
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'KCMC-Connect-Phase6-Recreated/admin/publication-designer.php'
CSRF = 'synthetic-save-race-fixture-csrf'
MEDIA_ID = 'pubmedia_' + 'a' * 24
PIXEL = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS9sAAAAASUVORK5CYII=')
FIRST_TEXT = 'Welcome\n\nPrelude\nOpening Hymn\nPrayer\nScripture\nMessage\nOffering\nClosing Hymn\nBenediction'
SECOND_TEXT = 'Second page\n\nScripture  \n\nGrace • peace ✝'


def fixture_html(source):
    source = re.sub(r'\A<\?php.*?\?>', '', source, count=1, flags=re.S)

    def replace(match):
        expr = match.group(1)
        path = re.search(r"kcmc_url\('([^']+)'\)", expr)
        if path:
            value = '/' + path.group(1)
            return json.dumps(value) if expr.startswith('json_encode(') else html.escape(value, quote=True)
        if expr == 'json_encode(kcmc_csrf(), JSON_UNESCAPED_SLASHES)':
            return json.dumps(CSRF)
        raise AssertionError('Unexpected PHP expression in browser fixture: ' + expr)

    rendered = re.sub(r'<\?=(.*?)\?>', replace, source, flags=re.S)
    assert '<?' not in rendered, 'Fixture must not leave executable PHP'
    return rendered.replace('<head>', '<head><base href="https://kcmc-fixture.invalid/">', 1)


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print('PASS:', label, flush=True)


def run(source_path):
    rendered = fixture_html(source_path.read_text())
    store, saves, errors = {}, [], []
    shared = {'id': MEDIA_ID, 'label': 'Synthetic shared church photo',
              'url': '/admin/publication-media.php?id=' + MEDIA_ID,
              'width': 1, 'height': 1, 'bytes': len(PIXEL)}

    def fixture_request(url, method, body):
        if url == '/admin/publication-projects.php':
            if method == 'POST':
                project = json.loads(body)
                assert project.pop('csrf') == CSRF
                project['id'] = project.get('id') or 'pub_' + format(len(store) + 1, '024x')
                project['updated'] = '2031-01-01T00:00:00Z'
                # Match the unchanged server's existing text normalization.
                for pg in project['pages']:
                    for item in pg['items']:
                        if item['type'] == 'text':
                            item['text'] = item['text'].strip(' \t\n\r\0\x0b')
                        if 'mediaId' in item:
                            assert item['mediaId'] == MEDIA_ID
                store[project['id']] = deepcopy(project)
                saves.append(deepcopy(project))
                return {'ok': True, 'project': deepcopy(project)}
            return {'ok': True, 'projects': deepcopy(list(store.values()))}
        if url == '/admin/publication-media.php' and method == 'GET':
            return {'ok': True, 'media': [shared]}
        raise AssertionError('Offline fixture: unexpected request ' + url)

    with sync_playwright() as pw:
        executable = os.environ.get('KCMC_CHROMIUM_PATH') or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        options = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            options['executable_path'] = executable
        browser = pw.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1500, 'height': 1100}, service_workers='block')
        page.on('pageerror', lambda error: errors.append(str(error)))

        def image_route(route):
            url = urlparse(route.request.url)
            if url.hostname == 'kcmc-fixture.invalid' and (
                    url.path.startswith('/assets/visuals/') or
                    (url.path == '/admin/publication-media.php' and url.query == 'id=' + MEDIA_ID)):
                route.fulfill(status=200, content_type='image/png', body=PIXEL)
            else:
                route.abort()

        page.route('**/*', image_route)
        page.expose_function('__fixtureRequest', fixture_request)
        page.evaluate('''() => {
            window.__holdNextSave = false;
            window.__failNextSave = false;
            window.__heldSave = null;
            window.__postCount = 0;
            window.fetch = async (url, options = {}) => {
                const method = options.method || 'GET';
                const hold = method === 'POST' && window.__holdNextSave;
                const fail = method === 'POST' && window.__failNextSave;
                if (method === 'POST') {
                    window.__postCount++;
                    window.__holdNextSave = false;
                    window.__failNextSave = false;
                }
                const payload = fail ? {ok: false, error: 'Synthetic Save failure'} :
                    await window.__fixtureRequest(url, method, options.body || null);
                if (hold) await new Promise(resolve => {
                    window.__heldSave = {release: resolve};
                });
                return {ok: !fail, json: async () => payload};
            };
        }''')
        page.set_content(rendered)
        page.wait_for_function("document.querySelector('#savedList').textContent.includes('No shared projects')")
        page.wait_for_function("document.querySelectorAll('#sharedMediaLibrary button').length === 1")

        def save_current():
            prior = len(saves)
            page.locator('#saveBtn').click()
            page.wait_for_function("document.querySelector('#status').textContent === 'Saved for KCMC admins' && !document.querySelector('#saveBtn').disabled")
            assert len(saves) == prior + 1, 'Save must issue exactly one project request'
            return deepcopy(saves[-1])

        def hold_save(fail=False):
            prior = len(saves)
            # Invoke the actual bound click handler and keep its completion
            # promise so release waits for the editor, rather than a sleep.
            page.evaluate('''fail => {
                window.__holdNextSave = true;
                window.__failNextSave = fail;
                window.__fixtureSaveCompletion = document.querySelector('#saveBtn').onclick();
            }''', fail)
            page.wait_for_function('window.__heldSave !== null')
            assert len(saves) == prior + (0 if fail else 1)
            return None if fail else deepcopy(saves[-1])

        def release_save():
            page.evaluate('''async () => {
                window.__heldSave.release();
                await window.__fixtureSaveCompletion;
                window.__heldSave = null;
            }''')

        def load(name):
            page.locator('#savedList button').filter(has=page.get_by_text(name, exact=True)).click()

        # Use real template BR nodes, distinct page paragraphs and reusable
        # shared-photo IDs; copying must preserve all three kinds of content.
        page.locator('[data-template="bulletin"]').click()
        page.locator('#sharedMediaLibrary button').click()
        page.locator('#duplicatePage').click()
        page.locator('#page .item[data-type="text"]').nth(1).evaluate('''(el, text) => {
            const handle = el.querySelector('.handle');
            el.textContent = text;
            el.appendChild(handle);
        }''', SECOND_TEXT)
        page.locator('#projectName').fill('Original publication')
        original = save_current()
        original_id = original['id']
        check([pg['items'][1]['text'] for pg in original['pages']] == [FIRST_TEXT, SECOND_TEXT],
              'synthetic original retains two distinct paragraph layouts')
        check(all(pg['items'][-1].get('mediaId') == MEDIA_ID for pg in original['pages']),
              'synthetic original retains shared photo IDs on both pages')

        hold_save()
        page.locator('#duplicateBtn').click()
        copy_name = page.locator('#projectName').input_value()
        copy_status = page.locator('#status').inner_text()
        release_save()
        check(page.locator('#projectName').input_value() == copy_name and
              page.locator('#status').inner_text() == copy_status,
              'late original Save response cannot replace copy identity or status')
        copy = save_current()
        check(copy['id'] != original_id and copy['pages'] == original['pages'],
              'copy Save uses a distinct ID and preserves pages, paragraphs and shared photos')
        check(store[original_id] == original,
              'saving the independent copy leaves the original project untouched')

        # Save is still pending when New establishes another editor identity.
        load('Original publication')
        hold_save()
        page.locator('#newBtn').click()
        new_status = page.locator('#status').inner_text()
        release_save()
        check(page.locator('#projectName').input_value() == 'Untitled publication' and
              page.locator('#status').inner_text() == new_status,
              'late Save response cannot replace New publication state')
        page.locator('#projectName').fill('New while saving')
        new_project = save_current()
        check(new_project['id'] not in [original_id, copy['id']] and store[original_id] == original,
              'New after a pending Save creates another ID without overwriting the original')

        # Loading an existing project owns both its editor state and next Save.
        load('Original publication')
        hold_save()
        load(copy_name)
        loaded_status = page.locator('#status').inner_text()
        release_save()
        check(page.locator('#projectName').input_value() == copy_name and
              page.locator('#status').inner_text() == loaded_status,
              'late Save response cannot replace a subsequently loaded project')
        loaded = save_current()
        check(loaded['id'] == copy['id'] and loaded['pages'] == copy['pages'] and store[original_id] == original,
              'saving the loaded copy retains its ID and leaves the original untouched')

        for action in ['Load', 'New', 'Duplicate']:
            load('Original publication')
            hold_save(fail=True)
            if action == 'Load':
                load(copy_name)
            else:
                page.locator('#newBtn' if action == 'New' else '#duplicateBtn').click()
            expected_name = page.locator('#projectName').input_value()
            expected_status = page.locator('#status').inner_text()
            release_save()
            check(page.locator('#projectName').input_value() == expected_name and
                  page.locator('#status').inner_text() == expected_status and
                  not page.locator('#saveBtn').is_disabled(),
                  'late failed Save retains ' + action + ' state and re-enables Save')
            if action != 'Load':
                page.locator('#projectName').fill(action + ' after failed Save')
            after_error = save_current()
            check((after_error['id'] == copy['id'] if action == 'Load' else
                   after_error['id'] not in [original_id, copy['id']]) and
                  store[original_id] == original,
                  action + ' after failed Save targets the current project without changing the original')

        # Burst clicks must not create duplicate server projects, including
        # direct calls to the bound handler while the visible button is busy.
        page.locator('#newBtn').click()
        page.locator('#projectName').fill('Burst Save publication')
        before = page.evaluate('window.__postCount')
        burst = hold_save()
        check(page.locator('#saveBtn').is_disabled(), 'Save button is disabled while its request is pending')
        count = page.evaluate('''async () => {
            const button = document.querySelector('#saveBtn');
            button.click();
            await Promise.all([button.onclick(), button.onclick()]);
            return window.__postCount;
        }''')
        check(count == before + 1, 'overlapping Save attempts issue only one HTTP request')
        release_save()
        check(not page.locator('#saveBtn').is_disabled() and store[burst['id']]['name'] == 'Burst Save publication',
              'Save becomes available after the pending request completes')

        # Reserving suffix space distinguishes even maximum-length names.
        page.locator('#newBtn').click()
        page.locator('#projectName').fill('L' * 80)
        long_original = save_current()
        page.locator('#duplicateBtn').click()
        long_copy_name = page.locator('#projectName').input_value()
        check(long_copy_name.endswith(' - Copy') and len(long_copy_name) <= 80,
              'maximum-length project name retains the complete copy suffix')
        long_copy = save_current()
        check(long_copy['id'] != long_original['id'] and store[long_original['id']] == long_original,
              'maximum-length named copy remains independent')
        check(errors == [], 'no browser JavaScript errors: ' + '; '.join(errors))
        browser.close()
    print('Publication Save races passed; synthetic endpoints only, no live storage touched.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    run(args.source)
