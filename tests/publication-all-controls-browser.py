#!/usr/bin/env python3
"""Exhaustive Publisher control audit against the exact editor with synthetic endpoints.

Clicks every visible static Publisher button/control, verifies the resulting DOM/state,
exercises save/reopen and print preparation, and never contacts production.
"""
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


def style(page, selector, prop):
    return page.locator(selector).evaluate('(el, p) => getComputedStyle(el)[p]', prop)


def selected(page):
    return page.locator('#page .item.selected')


def run():
    with sync_playwright() as pw:
        executable = os.environ.get('KCMC_CHROMIUM_PATH') or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        launch = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            launch['executable_path'] = executable
        browser = pw.chromium.launch(**launch)
        f = fidelity.Fixture(browser, fidelity.DEFAULT_APP)
        page = f.page
        try:
            # Back link is a normal navigation control; verify destination without leaving fixture.
            back = page.locator('.brand > a.btn')
            check(back.get_attribute('href') == '/admin/', 'Publishing Desk back link targets protected admin desk')

            # New.
            page.locator('#projectName').fill('Changed name')
            page.locator('#addPage').click()
            page.locator('#newBtn').click()
            check(page.locator('#projectName').input_value() == 'Untitled publication', 'New resets project name')
            check(page.locator('#pageIndicator').inner_text() == 'Page 1 of 1', 'New resets document to one page')
            check(page.locator('#page .item').count() == 3, 'New restores flyer starter content')

            # Six template buttons.
            expected = {'flyer': 3, 'bulletin': 2, 'newsletter': 3, 'postcard': 2, 'memorial': 2, 'study': 2}
            for name, count in expected.items():
                page.locator(f'[data-template="{name}"]').click()
                check(page.locator('#page .item').count() == count, f'{name} template builds expected starter items')
                check(page.locator('#pageIndicator').inner_text() == 'Page 1 of 1', f'{name} template resets to one page')
            check(page.locator('#pageSize').input_value() == 'letter', 'Bible-study template uses letter size')

            # Text button and editable workflow.
            before = page.locator('#page .item[data-type="text"]').count()
            page.locator('#addText').click()
            check(page.locator('#page .item[data-type="text"]').count() == before + 1, 'Text button adds a text box')
            text = page.locator('#page .item[data-type="text"]').last
            text.dblclick()
            check(text.evaluate('el => el.isContentEditable && document.activeElement === el'), 'double-click enters text edit mode')
            page.keyboard.press('ControlOrMeta+A')
            page.keyboard.type('Watch Dawg control audit')
            page.keyboard.press('Escape')
            check(text.inner_text() == 'Watch Dawg control audit', 'Escape exits text edit and retains typed text')

            # Shape + Delete.
            shapes = page.locator('#page .item[data-type="shape"]').count()
            page.locator('#addShape').click()
            check(page.locator('#page .item[data-type="shape"]').count() == shapes + 1, 'Shape button adds a shape')
            page.locator('#deleteItem').click()
            check(page.locator('#page .item[data-type="shape"]').count() == shapes, 'Delete removes selected item')

            # Built-in asset buttons: every visible KCMC asset must add one image.
            asset_buttons = page.locator('#assetLibrary [data-asset]')
            asset_count = asset_buttons.count()
            check(asset_count >= 14, 'KCMC asset library exposes all expected built-in image buttons')
            for i in range(asset_count):
                prior = page.locator('#page .item[data-type="image"]').count()
                asset_buttons.nth(i).click()
                check(page.locator('#page .item[data-type="image"]').count() == prior + 1, f'built-in asset button {i+1} adds an image')

            # Photo button -> real file chooser -> synthetic upload -> shared library.
            prior_upload = page.evaluate('window.__uploadFinished')
            with page.expect_file_chooser() as fc:
                page.locator('#addImage').click()
            fc.value.set_files({'name': 'watch-dawg-audit.png', 'mimeType': 'image/png', 'buffer': fidelity.PNG})
            page.wait_for_function(f'window.__uploadFinished > {prior_upload}')
            check(page.locator('#sharedMediaLibrary button').count() >= 1, 'Photo button uploads into shared photo library')
            uploaded = page.locator('#page .item[data-type="image"]').last
            check(uploaded.get_attribute('data-media-id') is not None, 'uploaded photo is inserted using a validated media ID')

            # Shared-photo button reuses the uploaded image.
            prior = page.locator('#page .item[data-type="image"]').count()
            page.locator('#sharedMediaLibrary button').first.click()
            check(page.locator('#page .item[data-type="image"]').count() == prior + 1, 'Shared Photos button reuses stored photo')

            # Page size and orientation.
            page.locator('#pageSize').select_option('half')
            check(page.locator('#page').evaluate('el => [el.style.width, el.style.height]') == ['528px', '816px'], 'Half-sheet page size applies 5.5×8.5 dimensions')
            page.locator('#orientation').select_option('landscape')
            check(page.locator('#page').evaluate('el => [el.style.width, el.style.height]') == ['816px', '528px'], 'Landscape orientation swaps page dimensions')
            page.locator('#pageSize').select_option('postcard')
            check(page.locator('#page').evaluate('el => [el.style.width, el.style.height]') == ['576px', '384px'], 'Postcard landscape applies 6×4 dimensions')
            page.locator('#orientation').select_option('portrait')
            check(page.locator('#page').evaluate('el => [el.style.width, el.style.height]') == ['384px', '576px'], 'Postcard portrait applies 4×6 dimensions')

            # Page controls.
            check(page.locator('#prevPage').is_disabled() and page.locator('#nextPage').is_disabled(), 'Previous/Next disabled on one-page document')
            page.locator('#addPage').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 2 of 2', 'Add page creates and opens page 2')
            check(not page.locator('#prevPage').is_disabled(), 'Previous enabled after adding page')
            page.locator('#prevPage').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 1 of 2', 'Previous page navigates backward')
            page.locator('#nextPage').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 2 of 2', 'Next page navigates forward')
            page.locator('#duplicatePage').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 3 of 3', 'Duplicate page creates independent page copy')
            page.locator('#deletePage').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 2 of 2', 'Delete page removes current page')
            page.locator('#prevPage').click()

            # Formatting controls on a text item.
            target = page.locator('#page .item[data-type="text"]').last
            target.click(position={'x': 12, 'y': 12})
            page.locator('#fontFamily').select_option('Georgia')
            check('Georgia' in style(page, '#page .item.selected', 'fontFamily'), 'Font family control applies')
            page.locator('#fontSize').fill('36')
            page.locator('#fontSize').dispatch_event('input')
            check(style(page, '#page .item.selected', 'fontSize') == '36px', 'Font size control applies')
            page.locator('#boldBtn').click()
            check(int(style(page, '#page .item.selected', 'fontWeight')) >= 700, 'Bold button applies bold weight')
            page.locator('#italicBtn').click()
            check(style(page, '#page .item.selected', 'fontStyle') == 'italic', 'Italic button applies italic style')
            for align in ['left', 'center', 'right']:
                page.locator(f'[data-align="{align}"]').click()
                check(style(page, '#page .item.selected', 'textAlign') == align, f'{align.title()} alignment button applies')

            page.locator('#textColor').fill('#123456')
            page.locator('#textColor').dispatch_event('input')
            check(style(page, '#page .item.selected', 'color') == 'rgb(18, 52, 86)', 'Text color control applies')
            page.locator('#fillColor').fill('#abcdef')
            page.locator('#fillColor').dispatch_event('input')
            check(style(page, '#page .item.selected', 'backgroundColor') == 'rgb(171, 205, 239)', 'Fill color control applies')
            page.locator('#borderColor').fill('#654321')
            page.locator('#borderColor').dispatch_event('input')
            check(style(page, '#page .item.selected', 'borderColor') == 'rgb(101, 67, 33)', 'Border color control applies')
            page.locator('#borderWidth').fill('4')
            page.locator('#borderWidth').dispatch_event('input')
            check(style(page, '#page .item.selected', 'borderWidth') == '4px', 'Border width control applies')
            page.locator('#opacity').fill('60')
            page.locator('#opacity').dispatch_event('input')
            check(abs(float(style(page, '#page .item.selected', 'opacity')) - 0.6) < 0.001, 'Opacity control applies')

            # Movement and resize.
            before_geom = target.evaluate('el => [parseFloat(el.style.left),parseFloat(el.style.top),parseFloat(el.style.width),parseFloat(el.style.height)]')
            box = target.bounding_box()
            page.mouse.move(box['x'] + 20, box['y'] + 20)
            page.mouse.down(); page.mouse.move(box['x'] + 50, box['y'] + 45, steps=5); page.mouse.up()
            moved = target.evaluate('el => [parseFloat(el.style.left),parseFloat(el.style.top),parseFloat(el.style.width),parseFloat(el.style.height)]')
            check(moved[0] > before_geom[0] and moved[1] > before_geom[1], 'mouse drag moves selected item')
            handle = target.locator(':scope > .handle')
            hb = handle.bounding_box()
            page.mouse.move(hb['x'] + hb['width']/2, hb['y'] + hb['height']/2)
            page.mouse.down(); page.mouse.move(hb['x'] + hb['width']/2 + 24, hb['y'] + hb['height']/2 + 16, steps=5); page.mouse.up()
            resized = target.evaluate('el => [parseFloat(el.style.width),parseFloat(el.style.height)]')
            check(resized[0] > moved[2] and resized[1] > moved[3], 'resize handle changes item dimensions')
            x_before = target.evaluate('el => parseFloat(el.style.left)')
            page.keyboard.press('Shift+ArrowRight')
            check(target.evaluate('el => parseFloat(el.style.left)') == x_before + 10, 'keyboard movement nudges selected item')

            # Save, Saved Projects open, project Duplicate, and New.
            page.locator('#projectName').fill('Watch Dawg Full Control Audit')
            saved = f.save()
            check(len(saved['pages']) == 2, 'Save persists both pages')
            check(page.locator('#savedList button').filter(has_text='Watch Dawg Full Control Audit').count() == 1, 'Saved project appears in Saved projects')
            page.locator('#newBtn').click()
            f.load('Watch Dawg Full Control Audit')
            check(page.locator('#projectName').input_value() == 'Watch Dawg Full Control Audit', 'Saved-project button reopens project')
            original_id = saved['id']
            page.locator('#duplicateBtn').click()
            check(page.locator('#projectName').input_value().endswith(' - Copy'), 'Duplicate project creates copy name')
            copied = f.save()
            check(copied['id'] != original_id, 'Duplicate project saves under independent project ID')

            # Print / Save PDF preparation.
            page.evaluate('window.__auditPrinted = false; window.print = () => {window.__auditPrinted = true}')
            page.locator('#printBtn').click()
            page.wait_for_function('window.__auditPrinted === true')
            check(page.locator('#printPages .page').count() == 2, 'Print / Save PDF prepares every page')
            check(page.locator('#printPages .handle').count() == 0, 'Print output excludes editing handles')

            check(not f.errors, 'no JavaScript page errors during exhaustive control audit')
        finally:
            f.close()
            browser.close()
    print('Watch-Dawg Publisher control audit passed; exact editor, synthetic endpoints, no production changes.')


if __name__ == '__main__':
    run()
