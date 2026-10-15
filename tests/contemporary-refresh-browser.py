from pathlib import Path
import os,sys,tempfile,shutil,socket,subprocess,time,urllib.request,json,hashlib,importlib.util
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('refresh',ROOT/'contemporary_refresh.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OUT=ROOT/'screenshots';OUT.mkdir(exist_ok=True)
def check(ok,label):
 if not ok:raise AssertionError(label)
 print('PASS:',label,flush=True)
with tempfile.TemporaryDirectory() as d:
 root=Path(d);app=root/'app';shutil.copytree(ROOT/'repo/KCMC-Connect-Phase6-Recreated',app)
 backups=root/'backups';backups.mkdir();m.apply(app,backups)
 content=(app/'data/content.json').read_bytes(); image=(app/'assets/visuals/kcmc-worship-2017.webp').read_bytes()
 for n in m.FILES:
  if n.endswith('.js'):subprocess.run(['node','--check',str(app/n)],check=True)
 priv=root/'private';priv.mkdir();(priv/'users.json').write_text(json.dumps({'version':1,'users':[{'id':'test','email':'admin@example.invalid','email_normalized':'admin@example.invalid','display_name':'Test User','active':True,'role':'pastor_admin','password_hash':'inaccessible'}]}))
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 base=f'http://127.0.0.1:{port}/app/'
 env={**os.environ,'KCMC_PRIVATE_DATA_DIR':str(priv),'KCMC_SETUP_KEY':''}
 log=open(root/'php.log','w');server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(root)],stdout=log,stderr=log,env=env)
 try:
  for i in range(50):
   try:
    with urllib.request.urlopen(base) as r:
     html=r.read().decode();check(r.status==200,'full PHP homepage returns 200');check('Set-Cookie' not in r.headers,'anonymous public page does not create a session')
    break
   except OSError:time.sleep(.1)
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('KCMC_CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
   errors=[];fails=[]
   ctx=browser.new_context(reduced_motion='reduce',service_workers='block')
   ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
   page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('response',lambda r:fails.append(r.url) if r.url.startswith(base) and r.status>=400 else None)
   for w in [320,390,768,1024,1440]:
    page.set_viewport_size({'width':w,'height':950});page.goto(base,wait_until='networkidle')
    hero=page.locator('[data-contemporary-feature]');hero.scroll_into_view_if_needed()
    page.locator('.cw-media img').evaluate('(im)=>im.decode()')
    check(hero.is_visible(),f'new contemporary hero renders at {w}px')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'no horizontal overflow at {w}px')
    check(page.locator('.cw-media img').evaluate('(e)=>e.naturalWidth===640'),f'actual supplied worship photo decoded at {w}px')
    check(page.locator('[data-hero-caption]').evaluate('(e)=>getComputedStyle(e).display==="none"'),f'photo captions hidden at {w}px')
    check(page.locator('[data-hero-toggle]').inner_text()=='Play photos',f'reduced-motion pauses welcome hero at {w}px')
    check(page.locator('.cw-primary').bounding_box()['height']>=44,f'CTA tap size at {w}px')
    check(page.locator('.cw-copy').evaluate('(e)=>e.scrollWidth<=e.clientWidth'),f'contemporary text fits panel at {w}px')
    check(hero.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(247, 241, 231)',f'warm cream surrounding section at {w}px')
    check(page.locator('.cw-feature').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 253, 249)',f'light text panel at {w}px')
    check(page.locator('.cw-media img').evaluate('(e)=>getComputedStyle(e).filter')=='brightness(1.16) contrast(0.88) saturate(1.04)',f'photo display brightens shadows at {w}px')
    check(page.locator('.cw-media img').evaluate('(e)=>getComputedStyle(e).objectFit')=='contain',f'full photograph remains visible at {w}px')
    check(page.locator('.cw-media').evaluate('(e)=>getComputedStyle(e,"::after").content')=='none',f'no dark photo overlay at {w}px')

    hero.screenshot(path=str(OUT/f'contemporary-{w}.png'))
    page.locator('.cw-primary').click();page.wait_for_function("document.querySelector('[data-view=visit]').classList.contains('active')")
    check(page.locator('[data-view="visit"]').is_visible(),f'Plan your Sunday opens visitor form at {w}px')
   page.goto(base,wait_until='networkidle');page.locator('.cw-primary').focus();page.keyboard.press('Tab')
   check(page.locator('.cw-secondary').evaluate('(e)=>e===document.activeElement'),'keyboard tab reaches Watch messages')
   check(page.locator('.cw-secondary').get_attribute('href')=='https://www.facebook.com/KimberlingCityMethodistChurch/live_videos','official message link unchanged')
   page.locator('#siteMenu summary').click();page.keyboard.press('Escape')
   check(page.locator('#siteMenu').get_attribute('open') is None,'main navigation still closes on Escape')
   for path in ['member/','admin/health.php']:
    page.goto(base+path);check('/member/login.php' in page.url,f'{path} still requires sign-in')
   check(not errors,'no JavaScript errors in local runtime');check(not fails,'no failed same-origin assets in local runtime')
   ctx.close()
   ctx=browser.new_context(java_script_enabled=False,viewport={'width':390,'height':900},service_workers='block');pg=ctx.new_page();pg.goto(base)
   check(pg.locator('[data-contemporary-feature]').is_visible(),'contemporary section works without JavaScript')
   check(pg.locator('.cw-primary').get_attribute('href')=='#visit','native visitor anchor retained without JavaScript')
   ctx.close()
   ctx=browser.new_context(reduced_motion='no-preference',service_workers='block',viewport={'width':390,'height':900})
   ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
   pg=ctx.new_page();pg.clock.install(time=0);pg.goto(base,wait_until='networkidle');pg.clock.pause_at(10000)
   pg.mouse.move(0,0)
   pg.evaluate("window.dispatchEvent(new HashChangeEvent('hashchange'))")
   before=pg.locator('[data-hero-photo]:visible').get_attribute('src')
   pg.clock.run_for(419000)
   check(pg.locator('[data-hero-photo]:visible').get_attribute('src')==before,'welcome hero does not rotate before seven minutes')
   pg.clock.run_for(1000)
   check(pg.locator('[data-hero-photo]:visible').get_attribute('src')!=before,'welcome hero rotates at seven minutes (virtual clock)')
   pg.locator('[data-hero-toggle]').click();frozen=pg.locator('[data-hero-photo]:visible').get_attribute('src');pg.clock.run_for(421000)
   check(pg.locator('[data-hero-photo]:visible').get_attribute('src')==frozen,'Pause keeps image still beyond seven minutes')
   pg.locator('[data-hero-next]').click();check(pg.locator('[data-hero-photo]:visible').get_attribute('src')!=frozen,'Next still changes photo immediately')
   ctx.close();browser.close()
  check((app/'data/content.json').read_bytes()==content,'public editorial data unchanged by all browser checks')
  check((app/'assets/visuals/kcmc-worship-2017.webp').read_bytes()==image,'original photo bytes unchanged')
 finally:server.terminate();server.wait();log.close()
