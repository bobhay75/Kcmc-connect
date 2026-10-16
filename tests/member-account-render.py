#!/usr/bin/env python3
"""Render actual PHP HTML offline; test viewport fit and keyboard navigation.

Uses the route fixture (real PHP, isolated users/storage), then inlines the app's
unchanged CSS in Playwright. This does not test live hosting or device push.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('account_routes',ROOT/'tests/member-account-routes.py')
routes=importlib.util.module_from_spec(spec);spec.loader.exec_module(routes)
p=argparse.ArgumentParser();p.add_argument('--app',type=Path,default=routes.APP);p.add_argument('--output',type=Path,default=ROOT/'test-artifacts/member-account');args=p.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
f=routes.Fixture(args.app.resolve());evidence=[]
try:
    def inline_css(match):
        href=re.search(r'href="([^"]+)"',match.group(0)).group(1)
        path=urlparse(href).path.removeprefix('/app/')
        css=(f.app/path).read_text()
        return '<style'+(' media="screen"' if 'media="screen"' in match.group(0) else '')+'>'+css+'</style>'
    with sync_playwright() as browser_tool:
        browser=browser_tool.chromium.launch(executable_path=os.environ.get('KCMC_TEST_CHROMIUM') or shutil.which('chromium') or browser_tool.chromium.executable_path,headless=True,args=['--no-sandbox'])
        for width,height in [(390,844),(1365,900)]:
            page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
            page.route('**/*',lambda route: route.abort())
            for actor,route,label in [('owner','member/index.php','owner-account'),('member','member/index.php','member-account'),('owner','admin/home.php','owner-administration')]:
                status,html=f.route(route,actor)
                assert status==200
                html=re.sub(r'<link rel="stylesheet"[^>]*>',inline_css,html)
                page.set_content(html,wait_until='domcontentloaded')
                assert page.locator('h1').count()==1
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,label,'horizontal overflow')
                for element in page.locator('a,button').all():
                    box=element.bounding_box()
                    if box is None:
                        assert element.locator('xpath=ancestor::details[not(@open)]').count(), 'only collapsed group links may be hidden'
                        continue
                    assert box['x']>=-1 and box['x']+box['width']<=width+1,(width,label,element.inner_text(),box)
                if route=='member/index.php':
                    assert page.get_by_role('navigation',name='Personal settings').count()==1
                    assert page.get_by_role('link',name='Account security').count()==1
                    assert page.get_by_role('link',name='Notifications').count()==1
                    assert page.get_by_role('link',name='Administration',exact=True).count()==int(actor=='owner')
                    assert page.get_by_role('button',name='Sign out').count()==1
                    page.keyboard.press('Tab')
                    assert page.evaluate('document.activeElement.tagName')=='A'
                    assert page.locator('[data-kcmc-back]').evaluate('(el)=>el===document.activeElement')
                path=args.output/(label+'-'+str(width)+'.png');page.screenshot(path=str(path),full_page=True)
                evidence.append(dict(route=route,actor=actor,width=width,height=height,screenshot=str(path.resolve()),horizontal_overflow=False))
            page.close()
        browser.close()
finally:f.close()
(args.output/'render-results.json').write_text(json.dumps(dict(cases=evidence,live_host=False),indent=2)+'\n')
print('PASS: six real-PHP dashboard/admin renders at phone and desktop widths; no horizontal overflow, personal navigation and keyboard Home verified.')
