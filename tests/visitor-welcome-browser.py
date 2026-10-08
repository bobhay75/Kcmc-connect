#!/usr/bin/env python3
"""Local PHP + Chromium acceptance. Synthetic contacts; captured mail only."""
from pathlib import Path
import email, email.policy, hashlib, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'KCMC-Connect-Phase6-Recreated'
OUT=Path(os.environ.get('KCMC_WELCOME_REVIEW_OUTPUT','visitor-review-artifacts'))
OUT.mkdir(parents=True,exist_ok=True)
def check(ok,label):
    if not ok: raise AssertionError(label)
    print('PASS:',label,flush=True)
with tempfile.TemporaryDirectory(prefix='kcmc-visitor-review-') as td:
    work=Path(td); local=work/'app'; private=work/'private'; private.mkdir(); capture=work/'mail';capture.mkdir()
    shutil.copytree(APP,local,ignore=shutil.ignore_patterns('config.php','private','backups'))
    before=hashlib.sha256((local/'data/content.json').read_bytes()).hexdigest()
    def configure(enabled):
        (local/'config.php').write_text("<?php return ['visitor_welcome_mail_enabled'=>"+('true' if enabled else 'false')+",'visitor_welcome_from'=>'welcome@example.invalid','visitor_welcome_base_url'=>'https://public.example.invalid/app/'];\n")
    configure(True)
    # A local sendmail replacement captures the actual PHP mail() handoff. No SMTP or external mail.
    mailer=work/'capture.py'
    mailer.write_text('import pathlib,sys\np=pathlib.Path('+repr(str(capture))+')\nbody=sys.stdin.buffer.read()\nif (p/"fail").exists(): sys.exit(75)\n(p/("mail-%s.eml"%len(list(p.glob("*.eml"))))).write_bytes(body)\n')
    executable=work/'sendmail'
    executable.write_text('#!/bin/sh\nexec '+sys.executable+' '+str(mailer)+' "$@"\n');executable.chmod(0o700)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}/'
    env=os.environ.copy();env['KCMC_PRIVATE_DATA_DIR']=str(private)
    for key in list(env):
        if key.startswith('KCMC_VISITOR_WELCOME_'): del env[key]
    log=(work/'php.log').open('w')
    # cli-server can cache PHP configuration even when enable_cli=0. Disable
    # OPcache only in this temporary fixture so its same-second edits are real.
    server=subprocess.Popen(['php','-d','opcache.enable=0','-d','opcache.enable_cli=0','-d','sendmail_path='+str(executable),'-S',f'127.0.0.1:{port}','-t',str(local)],stdout=log,stderr=log,env=env)
    try:
        for _ in range(80):
            try: urllib.request.urlopen(base,timeout=1).read();break
            except Exception: time.sleep(.1)
        else: raise AssertionError('Local PHP server unavailable')
        errors=[]
        with sync_playwright() as p:
            options={'executable_path':os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}
            browser=p.chromium.launch(**options)
            for width in (1440,390,320):
                context=browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce',service_workers='block')
                context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
                context.add_init_script("Object.defineProperty(navigator,'share',{value:async data=>{window.sharedInvitation=data;},configurable:true});")
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base,wait_until='networkidle')
                photos=page.locator('[data-hero-photo]')
                check(photos.count()==8,f'{width}px eight retained hero photos')
                check(page.locator('[data-hero-photo][src*="stage-2014"]').count()==0,'rejected empty stage is absent')
                check(page.locator('[data-hero-photo]:visible').count()==1,'one hero photo plane')
                check(page.locator('.hero-church-photo,.hero-church-window,[data-hero-caption]').count()==0,'no nested hero image or source subtitle')
                check(page.locator('[data-hero-toggle]').inner_text()=='Play photos','reduced-motion preference preserved')
                check(page.locator('.hero').evaluate("el=>getComputedStyle(el).backgroundColor")=='rgb(247, 241, 231)','hero has a light rather than dark background')
                check(page.locator('.hero-photo').first.evaluate("el=>getComputedStyle(el).filter")=='none','hero photo is not darkened by a filter')
                check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'{width}px no horizontal overflow')
                page.screenshot(path=str(OUT/f'hero-{width}.png'),full_page=False)
                page.get_by_role('button',name='Invite someone this Sunday',exact=True).click()
                shared=page.evaluate('window.sharedInvitation')
                check(shared['url']==base+'#visit','member invitation points directly to the visit page')
                check('8:00, 9:15 or 10:30' in shared['text'],'member invitation names the three Sunday options')
                if width==390:
                    page.goto(base+'?token=synthetic#home',wait_until='networkidle')
                    page.get_by_role('button',name='Invite someone this Sunday',exact=True).click()
                    check(page.evaluate('window.sharedInvitation.url')==base+'#visit','sharing strips query strings and tokens')
                context.close()
            context=browser.new_context(viewport={'width':1280,'height':1000},service_workers='block')
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'#visit',wait_until='networkidle')
            form=page.locator('form[data-kcmc-form="visit"]')
            def submit(address):
                form.locator('[name="firstName"]').fill('Alex')
                form.locator('[name="lastName"]').fill('Visitor')
                form.locator('[name="email"]').fill(address)
                form.locator('[name="service"]').select_option(label='10:30 AM — Contemporary Worship')
                with page.expect_response(lambda r:r.url.endswith('/api/connection.php')) as response:
                    form.get_by_role('button',name='Tell the welcome team',exact=True).click()
                value=response.value.json()
                page.wait_for_function("!document.querySelector('[data-visit-next-steps]').hidden")
                return response.value.status,value
            status,result=submit('alex@example.invalid')
            check(status==201 and result['welcome_email']=='accepted','real PHP submission immediately hands off a welcome email')
            check(len(list(capture.glob('*.eml')))==1,'only one captured message exists')
            message=email.message_from_bytes(next(capture.glob('*.eml')).read_bytes(),policy=email.policy.default)
            check(message['To']=='alex@example.invalid' and message['Reply-To']=='secretary@umckc.org','actual email headers identify the visitor and church reply address')
            body=message.get_content()
            check('10:30 AM — Contemporary Worship' in body and '#partner' in body and '#serve' in body,'actual MIME body includes selected service and connection steps')
            check(form.locator('[data-visit-next-steps]').is_visible(),'next-step panel appears after success')
            page.screenshot(path=str(OUT/'visit-confirmation.png'),full_page=False)
            status,result=submit('alex@example.invalid')
            check(status==200 and result['duplicate'] and len(list(capture.glob('*.eml')))==1,'repeat submit saves no duplicate and sends no extra email')
            (capture/'fail').touch()
            status,result=submit('failure@example.invalid')
            check(status==201 and result['welcome_email']=='unavailable','transport failure still returns a saved visit')
            check('could not send' in form.locator('.form-status').inner_text(),'visitor gets honest email-failure feedback')
            check(form.get_by_role('link',name='Find a group').is_visible(),'email failure does not remove connection options')
            (capture/'fail').unlink();configure(False)
            status,result=submit('disabled@example.invalid')
            check(status==201 and result['welcome_email']=='not_configured' and len(list(capture.glob('*.eml')))==1,'disabled mail remains fail-closed without losing the visit: '+json.dumps(result))
            def api(payload,headers=None,method='POST'):
                request=urllib.request.Request(base+'api/connection.php',data=json.dumps(payload).encode() if method=='POST' else None,method=method,headers=headers or {})
                try:
                    with urllib.request.urlopen(request) as response:return response.status,json.load(response)
                except urllib.error.HTTPError as response:return response.code,json.load(response)
            payload={'kind':'visit','firstName':'Cross','lastName':'Site','email':'cross@example.invalid','service':'8:00 AM — Front Porch Gospel'}
            check(api(payload,{'Content-Type':'application/json','X-KCMC-CONNECTION':'1','Sec-Fetch-Site':'cross-site'})[0]==403,'cross-site request rejected')
            check(api(payload,{'Content-Type':'application/json'})[0]==403,'missing application header rejected')
            check(api({},method='GET')[0]==405,'GET cannot submit or send email')
            rows=json.loads((private/'connection-intake.json').read_text())['submissions']
            check(len(rows)==3,'accepted, failed-mail and disabled-mail requests all persist exactly once')
            states=json.loads((private/'visitor-welcome-delivery.json').read_text())['deliveries']
            check({entry['status'] for entry in states.values()}=={'accepted','unavailable','not_configured'},'staff delivery metadata matches the three actual outcomes')
            check(not errors,'no JavaScript page errors')
            context.close();browser.close()
        check(hashlib.sha256((local/'data/content.json').read_bytes()).hexdigest()==before,'published content file is unchanged by visit/email flow')
        print('Visitor welcome browser/API acceptance passed; all mail stayed in the local capture.',flush=True)
    finally:
        server.terminate();server.wait(timeout=10);log.close()
