#!/usr/bin/env python3
"""Visual checks of the hero markup with the verified live CSS and proposed CSS.

This is a representative fixture, not a full PHP application or real device.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

repo=Path(__file__).resolve().parents[1]
output=repo/'test-artifacts'/'host-hero';output.mkdir(parents=True,exist_ok=True)
logo=(repo/'KCMC-Connect-Phase6-Recreated/assets/visuals/kcmc-bridge-logo.jpg').as_uri()
base=(repo/'KCMC-Connect-Phase6-Recreated/styles.css').as_uri()
home=(repo/'tests/fixtures/basic-handoff/home-welcome.css').as_uri()
gold=(repo/'tests/fixtures/basic-handoff/kcmc-gold-theme.css').as_uri()
new=(repo/'tools/basic-handoff/website-hero.css').as_uri()
markup='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="%s"><link rel="stylesheet" href="%s"><link rel="stylesheet" href="%s"><link rel="stylesheet" href="%s"></head><body class="kcmc-welcome-design" data-office-email="fixture@example.test"><main><section data-view="home"><section class="hero hero-imagery home-cover"><img class="home-cover-photo" src="%s" alt="Kimberling City Methodist Church"><div class="wrap home-cover-layout"><div class="home-cover-card"><h1 class="sr-only">Kimberling City Methodist Church</h1><div class="welcome-hero-actions"><a class="btn gold" href="#visit">Plan Your Visit</a><a class="btn secondary" href="#watch">Watch Online</a></div></div></div></section><section class="home-worship-strip"><div class="home-worship-strip-inner"><div class="home-worship-times"><span class="eyebrow">Sunday Services</span><strong>8:00 AM • 9:15 AM • 10:30 AM</strong></div></div></section></section></main></body></html>''' % (base,home,gold,new,logo)
fixture=output/'fixture.html';fixture.write_text(markup,encoding='utf-8')
with sync_playwright() as p:
 browser=p.chromium.launch()
 for name,width,height in [('phone',390,844),('desktop',1440,900)]:
  page=browser.new_page(viewport={'width':width,'height':height})
  page.goto(fixture.as_uri(),wait_until='load')
  assert page.locator('.home-cover-photo').evaluate('(el)=>el.complete && el.naturalWidth>0')
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), name+' overflow'
  assert page.locator('.welcome-hero-actions a').count()==2
  for el in page.locator('.welcome-hero-actions a').all():
   assert el.is_visible() and el.bounding_box()['height']>=44
  page.screenshot(path=str(output/(name+'.png')),full_page=True)
  page.close()
 browser.close()
print('PASS: verified CSS fixture, logo load, actions and no horizontal overflow at phone and desktop widths')
