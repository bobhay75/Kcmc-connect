"""Exercise calendar navigation and downloads on an isolated public-content fixture."""
import hashlib,json,os,shutil,socket,subprocess,tempfile,time
from pathlib import Path
from datetime import datetime,timedelta
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kcmc-calendar-') as tmp:
    app=Path(tmp)/'app'
    shutil.copytree(ROOT/'KCMC-Connect-Phase6-Recreated',app,ignore=shutil.ignore_patterns('private','backups','config.php'))
    stamp=subprocess.check_output([os.environ.get('PHP_BIN','php'),'-r','echo (new DateTimeImmutable("now",new DateTimeZone("America/Chicago")))->format("Y-m-d");']).decode()
    today=datetime.strptime(stamp,'%Y-%m-%d').date()
    start=today+timedelta(days=7-((today.weekday()+1)%7))
    wed=start+timedelta(days=3)
    data=json.loads((app/'data/content.json').read_text(encoding='utf-8'))
    data['meta']['content_release']='3.0.0'
    data['events']=[
      {'id':'test-weekly','title':'Weekly fixture','date':str(wed-timedelta(days=7)),'time':'5:17 PM','repeat':'weekly','status':'published','rsvp':False},
      {'id':'test-once','title':'One-time fixture','date':str(wed),'time':'6:00 PM','status':'published','rsvp':False},
      {'id':'test-hidden','title':'PRIVATE HIDDEN FIXTURE','date':str(wed),'time':'7:00 PM','repeat':'weekly','status':'hidden'},
      {'id':'test-outside','title':'Outside-week fixture','date':str(start+timedelta(days=9)),'time':'4:30 PM','rsvp':False},
    ]
    for event in data['events']: event['public_event']=True  # Explicit synthetic community-event fixtures.
    (app/'data/content.json').write_text(json.dumps(data),encoding='utf-8')
    before=hashlib.sha256((app/'data/content.json').read_bytes()).hexdigest()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env={**os.environ,'KCMC_PRIVATE_DATA_DIR':str(Path(tmp)/'private'),'KCMC_SETUP_KEY':''}
    proc=subprocess.Popen([os.environ.get('PHP_BIN','php'),'-S',f'127.0.0.1:{port}','-t',str(app)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.2):break
            except OSError:time.sleep(.1)
        with sync_playwright() as p:
            browser=p.chromium.launch(**({'executable_path':os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}))
            page=browser.new_page();errors=[];writes=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:writes.append(r.url) if r.method!='GET' else None)
            for width in [1280,375]:
                page.set_viewport_size({'width':width,'height':850})
                page.goto(f'http://127.0.0.1:{port}/#events')
                nav=page.get_by_role('navigation',name='Event calendar view')
                nav.get_by_role('link',name='Next week',exact=True).focus()
                page.keyboard.press('Enter')
                page.wait_for_url('**/?event_view=next-week#events')
                assert nav.get_by_role('link',name='Next week',exact=True).get_attribute('aria-current')=='page'
                card=page.locator('.event-card').filter(has=page.get_by_role('heading',name='Weekly fixture',exact=True))
                assert card.get_attribute('data-date')==str(wed)
                assert page.get_by_role('heading',name='One-time fixture',exact=True).is_visible()
                assert page.get_by_role('heading',name='PRIVATE HIDDEN FIXTURE',exact=True).count()==0
                assert page.get_by_role('heading',name='Outside-week fixture',exact=True).count()==0
                with page.expect_download() as dl:card.get_by_role('button',name='Add Weekly fixture to calendar').click()
                text=Path(dl.value.path()).read_text()
                assert f'DTSTART;TZID=America/Chicago:{wed:%Y%m%d}T171700' in text
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                if width==375:
                    out=os.environ.get('KCMC_CALENDAR_SCREENSHOT')
                    if out:page.screenshot(path=out,full_page=True)
                nav.get_by_role('link',name='Upcoming',exact=True).click()
                assert page.get_by_role('heading',name='Outside-week fixture',exact=True).is_visible()
            page.goto(f'http://127.0.0.1:{port}/events.php?event_view=next-week#events')
            assert page.get_by_role('heading',name='Weekly fixture',exact=True).is_visible()
            assert page.get_by_role('heading',name='Outside-week fixture',exact=True).count()==0
            assert not errors,errors
            assert not writes,writes
            browser.close()
        assert hashlib.sha256((app/'data/content.json').read_bytes()).hexdigest()==before
        assert not (Path(tmp)/'private').exists(),'Public navigation created private storage'
        print('PASS: desktop/mobile keyboard navigation, projected ICS, one-time visibility, hidden privacy, standalone view, zero writes')
    finally:proc.terminate();proc.wait(timeout=10)
