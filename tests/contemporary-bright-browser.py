"""Render the reviewed public section offline; no host access or submissions."""
import base64
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'

def check(ok, label):
    if not ok:
        raise AssertionError(label)
    print('PASS:', label, flush=True)

source = (APP / 'index.php').read_text()
section = source.split('<!-- KCMC_CONTEMPORARY_FEATURE_20261002 BEGIN -->', 1)[1].split('<!-- KCMC_CONTEMPORARY_FEATURE_20261002 END -->', 1)[0]
image = (APP / 'assets/visuals/kcmc-worship-2017.webp').read_bytes()
section = section.replace('assets/visuals/kcmc-worship-2017.webp', 'data:image/webp;base64,' + base64.b64encode(image).decode())
css = (APP / 'styles.css').read_text() + (APP / 'public-presentation.css').read_text()
html = '<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><style>' + css + '</style>' + section
with sync_playwright() as p:
    options = {'executable_path': os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}
    browser = p.chromium.launch(**options)
    context = browser.new_context(java_script_enabled=False, service_workers='block')
    context.route('**/*', lambda route: route.abort())
    page = context.new_page()
    for width in (320, 390, 768, 1024, 1440):
        page.set_viewport_size({'width': width, 'height': 1000})
        page.set_content(html)
        page.locator('.cw-media img').evaluate('(img) => img.decode()')
        check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{width}px: no horizontal overflow')
        check(page.locator('.cw-copy').evaluate('(el) => el.scrollWidth <= el.clientWidth'), f'{width}px: text fits')
        check(page.locator('.cw-media img').evaluate('(el) => el.naturalWidth > 0 && getComputedStyle(el).objectFit === "contain"'), f'{width}px: original photograph loads without cropping')
        check(page.locator('.cw-media').evaluate('(el) => getComputedStyle(el, "::after").content === "none"'), f'{width}px: no dark image overlay')
        check(page.locator('.cw-section').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(13, 34, 53)', f'{width}px: consistent blue section')
        check(page.locator('.cw-primary').bounding_box()['height'] >= 44, f'{width}px: usable tap target')
        ratios = page.evaluate('''() => {
            const rgb = s => s.match(/[\\d.]+/g).slice(0,3).map(Number);
            const lum = a => a.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
            return [...document.querySelectorAll('.cw-copy p, .cw-copy h2, .cw-copy h2 span, .cw-kicker span, .cw-button')].map(el => {
                let parent=el, bg;
                while(parent){bg=getComputedStyle(parent).backgroundColor;if(bg!=='rgba(0, 0, 0, 0)')break;parent=parent.parentElement;}
                const a=lum(rgb(getComputedStyle(el).color)), b=lum(rgb(bg));
                return {text:el.innerText, ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
            });
        }''')
        check(all(row['ratio'] >= 4.5 for row in ratios), f'{width}px: section text contrast meets 4.5:1')
    check(page.locator('.cw-primary').get_attribute('href') == '#visit', 'native visit route retained without JavaScript')
    check(page.locator('.cw-secondary').get_attribute('href') == 'https://www.facebook.com/KimberlingCityMethodistChurch/live_videos', 'official message destination retained')
    page.locator('.cw-primary').focus()
    page.keyboard.press('Tab')
    check(page.locator('.cw-secondary').evaluate('(el) => el === document.activeElement'), 'keyboard reaches message link')
    check(page.locator('.cw-secondary').evaluate('(el) => parseFloat(getComputedStyle(el).outlineWidth) >= 3'), 'visible keyboard focus')
    browser.close()
