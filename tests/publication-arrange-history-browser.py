#!/usr/bin/env python3
"""Publisher arrangement and undo/redo acceptance using exact editor + synthetic endpoints.

Exercises familiar desktop-publishing controls without contacting production.
"""
import importlib.util
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_fidelity_fixture', ROOT / 'tests/publication-fidelity-browser.py')
fidelity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fidelity)


def check(ok, message):
    if not ok:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def types(page):
    return page.locator('#page .item').evaluate_all("els => els.map(el => el.dataset.type)")


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
            check(page.locator('#undoBtn').is_disabled() and page.locator('#redoBtn').is_disabled(),
                  'Undo and Redo start disabled')
            for ident in ['duplicateItemBtn','bringFrontBtn','bringForwardBtn','sendBackwardBtn','sendBackBtn']:
                check(page.locator('#'+ident).is_disabled(), ident + ' starts disabled without selection')

            # Basic add -> undo -> redo.
            base_shapes = page.locator('#page .item[data-type="shape"]').count()
            page.locator('#addShape').click()
            check(page.locator('#page .item[data-type="shape"]').count() == base_shapes + 1, 'shape add creates history mutation')
            check(not page.locator('#undoBtn').is_disabled(), 'Undo enables after mutation')
            page.locator('#undoBtn').click()
            check(page.locator('#page .item[data-type="shape"]').count() == base_shapes, 'Undo reverses object add')
            check(not page.locator('#redoBtn').is_disabled(), 'Redo enables after Undo')
            page.locator('#redoBtn').click()
            check(page.locator('#page .item[data-type="shape"]').count() == base_shapes + 1, 'Redo restores object add')

            # Duplicate selected object and preserve offset.
            shape = page.locator('#page .item[data-type="shape"]').last
            shape.focus()
            before = shape.evaluate("el => [parseFloat(el.style.left),parseFloat(el.style.top)]")
            prior = page.locator('#page .item[data-type="shape"]').count()
            page.locator('#duplicateItemBtn').click()
            check(page.locator('#page .item[data-type="shape"]').count() == prior + 1, 'Duplicate object creates a second object')
            copy = page.locator('#page .item[data-type="shape"]').last
            after = copy.evaluate("el => [parseFloat(el.style.left),parseFloat(el.style.top)]")
            check(after == [before[0] + 12, before[1] + 12], 'Duplicate object offsets copy for visibility')
            page.locator('#undoBtn').click()
            check(page.locator('#page .item[data-type="shape"]').count() == prior, 'Undo removes duplicated object')
            page.locator('#redoBtn').click()
            check(page.locator('#page .item[data-type="shape"]').count() == prior + 1, 'Redo restores duplicated object')

            # Fresh blank page for deterministic layer ordering.
            page.locator('#newBtn').click()
            page.locator('#addPage').click()
            page.locator('#addText').click()
            page.locator('#addShape').click()
            page.locator('#assetLibrary [data-asset]').first.click()
            check(types(page) == ['text','shape','image'], 'blank page establishes text-shape-image layer order')

            text = page.locator('#page .item[data-type="text"]').first
            text.focus()
            page.locator('#bringFrontBtn').click()
            check(types(page) == ['shape','image','text'], 'Bring to front moves selected object to top layer')
            page.locator('#sendBackBtn').click()
            check(types(page) == ['text','shape','image'], 'Send to back moves selected object to bottom layer')
            page.locator('#bringForwardBtn').click()
            check(types(page) == ['shape','text','image'], 'Bring forward moves one layer')
            page.locator('#sendBackwardBtn').click()
            check(types(page) == ['text','shape','image'], 'Send backward moves one layer')

            # Layer order persists through save/reopen and print construction.
            page.locator('#projectName').fill('Arrange persistence')
            saved = f.save()
            check([item['type'] for item in saved['pages'][1]['items']] == ['text','shape','image'],
                  'Save preserves object layer order')
            page.locator('#newBtn').click()
            f.load('Arrange persistence')
            page.locator('#nextPage').click()
            check(types(page) == ['text','shape','image'], 'Reopen preserves object layer order')
            page.evaluate("window.__arrangePrinted=false;window.print=()=>{window.__arrangePrinted=true}")
            page.locator('#printBtn').click()
            page.wait_for_function("window.__arrangePrinted === true")
            printed = page.locator('#printPages .page').nth(1).locator('.item').evaluate_all("els => els.map(el => el.dataset.type)")
            check(printed == ['text','shape','image'], 'Print renderer preserves object layer order')

            # Load resets history; text edit becomes one undoable operation.
            check(page.locator('#undoBtn').is_disabled(), 'Loading a project resets document history')
            text = page.locator('#page .item[data-type="text"]').first
            old_text = text.inner_text()
            text.focus()
            page.keyboard.press('Enter')
            check(text.evaluate('el => el.isContentEditable && document.activeElement === el'), 'keyboard Enter opens overlapped text for editing')
            page.keyboard.press('ControlOrMeta+A')
            page.keyboard.type('Changed by history audit')
            page.keyboard.press('Escape')
            check(text.inner_text() == 'Changed by history audit', 'text edit applies before Undo')
            page.locator('#undoBtn').click()
            text = page.locator('#page .item[data-type="text"]').first
            check(text.inner_text() == old_text, 'Undo restores text before edit')
            page.locator('#redoBtn').click()
            check(page.locator('#page .item[data-type="text"]').first.inner_text() == 'Changed by history audit',
                  'Redo restores text edit')

            # Formatting history.
            text = page.locator('#page .item[data-type="text"]').first
            text.focus()
            original_weight = text.evaluate("el => getComputedStyle(el).fontWeight")
            page.locator('#boldBtn').click()
            bold_weight = text.evaluate("el => getComputedStyle(el).fontWeight")
            check(int(bold_weight) >= 700, 'Bold creates a history mutation')
            page.locator('#undoBtn').click()
            text = page.locator('#page .item[data-type="text"]').first
            check(text.evaluate("el => getComputedStyle(el).fontWeight") == original_weight, 'Undo restores prior formatting')

            # Delete can be recovered.
            page.locator('#page .item[data-type="shape"]').first.focus()
            shape_count = page.locator('#page .item[data-type="shape"]').count()
            page.locator('#deleteItem').click()
            check(page.locator('#page .item[data-type="shape"]').count() == shape_count - 1, 'Delete removes object before Undo')
            page.locator('#undoBtn').click()
            check(page.locator('#page .item[data-type="shape"]').count() == shape_count, 'Undo restores deleted object')

            # Page add/delete history.
            page.locator('#newBtn').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 1 of 1', 'New starts one-page history')
            page.locator('#addPage').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 2 of 2', 'Add page applies')
            page.locator('#undoBtn').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 1 of 1', 'Undo removes newly added page')
            page.locator('#redoBtn').click()
            check(page.locator('#pageIndicator').inner_text() == 'Page 2 of 2', 'Redo restores newly added page')

            # Keyboard Undo / Redo and Duplicate object shortcuts.
            page.locator('#prevPage').click()
            page.locator('#addShape').click()
            shape_count = page.locator('#page .item[data-type="shape"]').count()
            page.keyboard.press('ControlOrMeta+Z')
            check(page.locator('#page .item[data-type="shape"]').count() == shape_count - 1, 'Ctrl/Cmd+Z triggers document Undo')
            page.keyboard.press('ControlOrMeta+Shift+Z')
            check(page.locator('#page .item[data-type="shape"]').count() == shape_count, 'Ctrl/Cmd+Shift+Z triggers Redo')
            page.locator('#page .item[data-type="shape"]').last.focus()
            page.keyboard.press('ControlOrMeta+D')
            check(page.locator('#page .item[data-type="shape"]').count() == shape_count + 1, 'Ctrl/Cmd+D duplicates selected object')

            # Native form-field shortcuts are not hijacked by document history.
            page.locator('#projectName').focus()
            before_count = page.locator('#page .item[data-type="shape"]').count()
            page.keyboard.press('ControlOrMeta+Z')
            check(page.locator('#page .item[data-type="shape"]').count() == before_count,
                  'Ctrl/Cmd+Z in project-name field does not alter document history')

            # A new mutation after Undo clears Redo.
            page.locator('#page .item[data-type="shape"]').last.focus()
            page.keyboard.press('ControlOrMeta+Z')
            check(not page.locator('#redoBtn').is_disabled(), 'Redo available after document Undo')
            page.locator('#addText').click()
            check(page.locator('#redoBtn').is_disabled(), 'new mutation clears stale Redo stack')

            check(not f.errors, 'no JavaScript errors during arrange/history audit')
        finally:
            f.close()
            browser.close()
    print('Publisher arrange/history audit passed; exact editor, synthetic endpoints, no production changes.')


if __name__ == '__main__':
    run()
