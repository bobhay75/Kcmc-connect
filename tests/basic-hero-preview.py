#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

repo=Path(__file__).resolve().parents[1]
output=repo/'test-artifacts'/'basic-hero-preview'
output.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch()
    for name,width,height in [('phone',390,844),('desktop',1440,900)]:
        page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        page.goto((repo/'tools/basic-handoff/hero-preview.html').as_uri(),wait_until='load')
        assert page.locator('.logo').evaluate('(img) => img.complete && img.naturalWidth > 0'), 'Logo did not load'
        assert page.locator('h1').inner_text()=='Welcome home.'
        assert page.locator('.actions a').count()==2
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
        page.screenshot(path=str(output/(name+'.png')),full_page=True)
        page.close()
    browser.close()
print('PASS: hero concept image loading, actions and viewport overflow at phone and desktop sizes')
