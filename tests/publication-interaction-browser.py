#!/usr/bin/env python3
"""Real mouse/keyboard Publisher editing regression, with synthetic endpoints.

Uses the actual editor plus PHP item validation from the existing fidelity
fixture. Never contacts production or reads real accounts. --app/--case support
independent pinned-baseline failures; these are not host-acceptance claims.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_fidelity_fixture', ROOT / 'tests/publication-fidelity-browser.py')
fidelity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fidelity)


def check(ok, message):
    if not ok:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def title(page):
    return page.locator('#page .item[data-type="text"]').first


def dimensions(item):
    return item.evaluate('el => ["left", "top", "width", "height"].map(k => parseFloat(el.style[k]))')


def type_text(page, item, text):
    item.dblclick()
    check(item.evaluate('el => document.activeElement === el && el.isContentEditable'),
          'double-click must focus an editable text box')
    page.keyboard.press('ControlOrMeta+A')
    for index, line in enumerate(text.split('\n')):
        if index:
            page.keyboard.press('Enter')
        page.keyboard.type(line)
    page.keyboard.press('Escape')


def typing(f):
    page = f.page
    message = 'Sunday study\n\nBring your Bible.'
    type_text(page, title(page), message)
    saved = f.save('Typed publication')
    check(saved['pages'][0]['items'][0]['borderWidth'] == 0, 'selection border is not publication content')
    check(saved['pages'][0]['items'][0]['text'] == message,
          'real keyboard text and blank lines survive real PHP validation')
    page.locator('#newBtn').click()
    f.load('Typed publication')
    check(title(page).inner_text() == message, 'typed text survives Save and reopen')
    title(page).click(position={'x': 14, 'y': 14})
    page.keyboard.press('Enter')
    check(title(page).evaluate('el => document.activeElement === el && el.isContentEditable'),
          'keyboard Enter activates text editing')
    page.keyboard.press('ControlOrMeta+A')
    page.keyboard.type('Keyboard only')
    page.keyboard.press('Escape')
    check(not title(page).evaluate('el => el.isContentEditable'), 'Escape exits editing without losing text')
    page.locator('#addText').click()
    fresh = page.locator('#page .item[data-type="text"]').last
    type_text(page, fresh, 'A new text box')
    check(fresh.inner_text() == 'A new text box', 'newly added text can be edited with real input')


def handles(f):
    page = f.page
    for template in ['flyer', 'bulletin', 'newsletter', 'postcard', 'memorial', 'study']:
        page.locator(f'[data-template="{template}"]').click()
        item = title(page)
        item.click(position={'x': 12, 'y': 12})
        handle = item.locator(':scope > .handle')
        check(handle.count() == 1, 'selected template text must retain one resize handle: ' + template)
        expect(handle).to_be_visible()
        check(handle.get_attribute('contenteditable') == 'false', 'resize handle is not editable text: ' + template)
    type_text(page, title(page), 'Replace all text')
    check(title(page).locator('.handle').count() == 1, 'Select All and typing retain a working handle')
    saved = f.save('Handle preservation')
    page.locator('#newBtn').click()
    f.load('Handle preservation')
    title(page).click(position={'x': 10, 'y': 10})
    check(title(page).locator('.handle').count() == 1, 'reopened text retains its resize handle')
    check(saved['pages'][0]['items'][0]['text'] == 'Replace all text', 'handle never enters saved text')


def drag(page, start, dx, dy):
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0] + dx, start[1] + dy, steps=6)
    page.mouse.up()


def movement(f):
    page = f.page
    for kind in ['text', 'shape', 'image']:
        page.locator('#newBtn').click()
        if kind == 'shape':
            page.locator('#addShape').click()
            item = page.locator('#page .item[data-type="shape"]').last
        elif kind == 'image':
            page.locator('#assetLibrary [data-asset]').first.click()
            item = page.locator('#page .item[data-type="image"]').last
        else:
            item = title(page)
        item.click(position={'x': 12, 'y': 12})
        before = dimensions(item)
        box = item.bounding_box()
        drag(page, (box['x'] + 25, box['y'] + 20), 32, 21)
        moved = dimensions(item)
        check(abs(moved[0] - before[0] - 32) <= 1 and abs(moved[1] - before[1] - 21) <= 1,
              kind + ': real mouse drag moves the item without editing content')
        h = item.locator('.handle').bounding_box()
        check(h is not None, kind + ': resize handle has a visible hit target')
        drag(page, (h['x'] + h['width'] / 2, h['y'] + h['height'] / 2), 24, 18)
        resized = dimensions(item)
        check(abs(resized[2] - moved[2] - 24) <= 1 and abs(resized[3] - moved[3] - 18) <= 1,
              kind + ': real mouse drag resizes using the current handle')
        before_nudge = dimensions(item)
        page.keyboard.press('Shift+ArrowRight')
        check(dimensions(item)[0] == before_nudge[0] + 10, kind + ': keyboard can nudge the selected item')
        saved = f.save('Moved ' + kind)
        expected = saved['pages'][0]['items'][-1 if kind != 'text' else 0]
        page.locator('#newBtn').click()
        f.load('Moved ' + kind)
        restored = page.locator('#page .item[data-type="' + kind + '"]').last if kind != 'text' else title(page)
        check(dimensions(restored) == [expected[k] for k in ['x', 'y', 'w', 'h']], kind + ': moved/resized geometry survives reopen')


def literal_paste(f):
    page = f.page
    item = title(page)
    item.dblclick()
    check(item.evaluate('el => el.isContentEditable && document.activeElement === el'), 'paste target is actively being edited')
    page.keyboard.press('ControlOrMeta+A')
    # Dispatch the actual clipboard event with both representations; insertion
    # is done only by the editor handler, not by fixture DOM manipulation.
    item.evaluate(r'''el => {
        const clipboard = new DataTransfer();
        clipboard.setData('text/plain', '<b>Literal pasted text</b>\nSecond line');
        clipboard.setData('text/html', '<b>Rich pasted text</b><img src="https://not-requested.invalid/photo.png">');
        el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: clipboard, bubbles: true, cancelable: true}));
    }''')
    page.keyboard.press('Escape')
    want = '<b>Literal pasted text</b>\nSecond line'
    check(item.inner_text() == want and item.locator('b,img').count() == 0, 'paste is plain text and cannot introduce HTML or remote photos')
    f.save('Literal paste')
    page.locator('#duplicatePage').click()
    f.save()
    page.evaluate('window.print = () => {window.__interactionPrint = true}')
    page.locator('#printBtn').click()
    page.wait_for_function('window.__interactionPrint === true')
    check(page.locator('#printPages .page').count() == 2, 'typed publication prints both pages')
    check(page.locator('#printPages .handle').count() == 0, 'editing handles never appear in print')
    for printed in page.locator('#printPages .page').all():
        check(printed.locator('.item[data-type="text"]').first.text_content() == want, 'literal pasted text remains exact in print')


def run(app, case, screenshot):
    cases = {'typing': typing, 'handles': handles, 'movement': movement, 'paste': literal_paste}
    with sync_playwright() as p:
        options = {'headless': True, 'args': ['--no-sandbox']}
        executable = os.environ.get('KCMC_CHROMIUM_PATH') or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        if executable:
            options['executable_path'] = executable
        browser = p.chromium.launch(**options)
        for name, test in cases.items():
            if case != 'all' and case != name:
                continue
            f = fidelity.Fixture(browser, app)
            try:
                test(f)
                check(not f.errors, name + ': no JavaScript errors')
                if screenshot and name == 'typing':
                    f.page.screenshot(path=str(screenshot), full_page=True)
            finally:
                f.close()
        browser.close()
    print('Publisher interaction checks passed; actual mouse/keyboard, synthetic endpoints, no production changes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=fidelity.DEFAULT_APP)
    parser.add_argument('--case', choices=['all', 'typing', 'handles', 'movement', 'paste'], default='all')
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    run(args.app, args.case, args.screenshot)
