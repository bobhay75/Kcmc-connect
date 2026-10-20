#!/usr/bin/env python3
"""Synthetic local acceptance: public controls and captured mail, no live users or mail."""
from pathlib import Path
import email, email.policy, hashlib, json, os, shutil, socket, subprocess, tempfile, time, urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'KCMC-Connect-Phase6-Recreated'
checks=0
def check(ok,label):
    global checks
    if not ok: raise AssertionError(label)
    checks+=1
    print('PASS:',label,flush=True)
with tempfile.TemporaryDirectory(prefix='kcmc-tony-functions-') as td:
    work=Path(td);local=work/'app';private=work/'private';capture=work/'mail'
    private.mkdir();capture.mkdir();shutil.copytree(APP,local,ignore=shutil.ignore_patterns('config.php','private','backups'))
    password='Synthetic-Functional-Review-2031!'
    password_hash=subprocess.check_output(['php','-r','echo password_hash($argv[1],PASSWORD_DEFAULT);',password],text=True).strip()
    (private/'users.json').write_text(json.dumps({'version':1,'users':[{'id':'synthetic_admin','email':'admin@example.invalid','email_normalized':'admin@example.invalid','display_name':'Synthetic Admin','role':'pastor_admin','active':True,'password_hash':password_hash}]}))
    document=json.loads((local/'data/content.json').read_text())
    # Fixture date is today's approved issue, never written to the repository or live host.
    document['bulletin']['date']=time.strftime('%Y-%m-%d')
    document['bulletin']['notes']=['The answer is ______.  Keep these spaces. <literal>']
    document['worship_streams']={key:'https://www.facebook.com/watch/?v='+str(i) for i,key in enumerate(['front-porch','traditional','contemporary'],111)}
    (local/'data/content.json').write_text(json.dumps(document))
    content_before=hashlib.sha256((local/'data/content.json').read_bytes()).hexdigest()
    (local/'config.php').write_text("<?php return ['visitor_welcome_mail_enabled'=>true,'visitor_welcome_from'=>'welcome@example.invalid'];")
    mailer=work/'capture.py';mailer.write_text('import pathlib,sys\np=pathlib.Path('+repr(str(capture))+')\n(p/("mail-%s.eml"%len(list(p.glob("*.eml"))))).write_bytes(sys.stdin.buffer.read())\n')
    sendmail=work/'sendmail';sendmail.write_text('#!/bin/sh\nexec '+shutil.which('python')+' '+str(mailer)+' "$@"\n');sendmail.chmod(0o700)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}/'
    log=(work/'php.log').open('w')
    env={**os.environ,'KCMC_PRIVATE_DATA_DIR':str(private)}
    server=subprocess.Popen(['php','-d','sendmail_path='+str(sendmail),'-d','opcache.enable=0','-S',f'127.0.0.1:{port}','-t',str(local)],env=env,stdout=log,stderr=log)
    try:
        for _ in range(80):
            try:urllib.request.urlopen(base,timeout=1).read();break
            except Exception:time.sleep(.1)
        with sync_playwright() as p:
            kwargs={'executable_path':os.environ['KCMC_CHROMIUM_PATH']} if os.environ.get('KCMC_CHROMIUM_PATH') else {}
            browser=p.chromium.launch(**kwargs)
            for width in [1440,390,320]:
                context=browser.new_context(viewport={'width':width,'height':950},service_workers='block')
                context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
                page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base,wait_until='networkidle')
                home=page.locator('[data-view=home]')
                check(home.locator('img').count()==1 and home.locator('[data-authentic-building]').count()==1,'landing galleries removed; approved building retained')
                check(page.locator('body').evaluate('el=>getComputedStyle(el).backgroundColor')=='rgb(13, 34, 53)','approved navy theme retained')
                check(home.get_by_role('link',name='Watch Online').get_attribute('href')=='https://www.facebook.com/KimberlingCityMethodistChurch/live_videos','Watch Online links directly to Facebook')
                for route in ['visit','watch','news','events','serve','partner','home']:
                    page.goto(base+'#'+route,wait_until='networkidle')
                    check(page.locator(f'[data-view={route}]').is_visible(),'route opens: '+route)
                    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'no horizontal overflow: '+route+' at '+str(width))
                page.goto(base+'#watch',wait_until='networkidle')
                check(page.locator('.sermon-card').count()==3 and page.locator('.sermon-card img').count()==3,'one photo for each of three services')
                for key in ['front-porch','traditional','contemporary']:
                    page.locator('#sermonFilter').select_option(key)
                    check(page.locator('.sermon-card:visible').count()==1 and page.locator('.sermon-card:visible').get_attribute('data-type')==key,'filter selects '+key)
                page.locator('#sermonFilter').select_option('all')
                urls=page.locator('.sermon-card a').evaluate_all('els=>els.map(el=>el.href)')
                check(len(set(urls))==3,'service actions have distinct verified fixture videos')
                for photo in page.locator('.sermon-card img').all():
                    photo.scroll_into_view_if_needed()
                    page.wait_for_function('img=>img.complete&&img.naturalWidth>0',arg=photo.element_handle())
                check(page.locator('.sermon-card img').evaluate_all('els=>els.every(el=>el.complete&&el.naturalWidth>0)'),'all three authentic service photos load')
                page.locator('#sermonSearch').fill('missing-service')
                check(page.locator('.sermon-card:visible').count()==0 and page.locator('.sermon-empty').is_visible(),'empty search explains result')
                page.goto(base+'#news',wait_until='networkidle');page.locator('[data-view=news]').get_by_role('link',name='← Back',exact=True).click()
                page.locator('[data-view=home]').wait_for(state='visible');check(page.locator('[data-view=home]').is_visible(),'Stay Connected Back returns home')
                page.goto(base+'#partner',wait_until='networkidle')
                check('Church Family' in page.locator('[data-view=partner] .eyebrow').first.text_content(),'Partner Hub is labeled Church Family')
                page.locator('#preferredService').select_option(label='9:15 AM — Traditional Worship');page.reload(wait_until='networkidle')
                check(page.locator('#preferredService').input_value()=='9:15 AM — Traditional Worship','service preference persists')
                page.goto(base+'#events',wait_until='networkidle')
                titles=page.locator('[data-view=events] .event-card h3').all_text_contents()
                check(titles[0].startswith('Trunk or Treat') and not any('Preschool' in t or 'Staff' in t for t in titles),'Trunk or Treat leads actual upcoming events')
                with page.expect_download() as dl:page.locator('.event-card .add-calendar').first.click()
                download=Path(dl.value.path()).read_text()
                check('BEGIN:VCALENDAR' in download and 'Trunk or Treat' in download,'event calendar downloads correct event')
                # No dangling same-document route or nonexistent local file.
                for href in page.locator('a[href]').evaluate_all('els=>els.map(el=>el.getAttribute("href"))'):
                    if href.startswith('#'):check(page.locator('[data-view="'+href[1:]+'"]').count()>0 or page.locator(href).count()>0,'internal target exists: '+href)
                    elif not (':' in href or href.startswith('?')):
                        target=href.split('#')[0].split('?')[0]
                        if target:check((local/target.lstrip('/')).exists(),'local destination exists: '+target)
                check(not errors,'no browser runtime errors')
                context.close()
            context=browser.new_context(service_workers='block');page=context.new_page()
            for kind in ['visit','groups','serve']:
                page.goto(base+'#'+{'visit':'visit','groups':'partner','serve':'serve'}[kind],wait_until='networkidle')
                form=page.locator(f'form[data-kcmc-form={kind}]')
                if kind=='visit':
                    form.locator('[name=firstName]').fill('Alex');form.locator('[name=lastName]').fill('Guest');form.locator('[name=service]').select_option(label='8:00 AM — Front Porch Gospel')
                else:form.locator('[name=name]').fill('Alex Guest')
                form.locator('[name=email]').fill(kind+'@example.invalid')
                with page.expect_response(lambda r:r.url.endswith('/api/connection.php')) as response:form.locator('button[type=submit]').click()
                check(response.value.status==201,'request HTTP response: '+response.value.text()[:500]);result=response.value.json()
                check(response.value.status==201 and result['welcome_email']=='accepted','saved '+kind+' request triggers welcome email')
            check(len(list(capture.glob('*.eml')))==3,'three requests produce three captured messages')
            for file in capture.glob('*.eml'):
                message=email.message_from_bytes(file.read_bytes(),policy=email.policy.default)
                check(message['Reply-To']=='secretary@umckc.org' and 'Welcome to KCMC' in message['Subject'],'captured email has church reply address and welcome subject')
            page.goto(base+'bulletin.php',wait_until='networkidle')
            check('The answer is ______.  Keep these spaces. <literal>' in page.locator('.bulletin-notes').inner_text(),'current bulletin preserves approved literal notes')
            page.get_by_role('link',name='← Back to KCMC Connect').click();page.locator('[data-view=home]').wait_for(state='visible');check(page.locator('[data-view=home]').is_visible(),'bulletin Stay Connected Back works')
            # Read-only page rendering must not alter the editorial store.
            check(hashlib.sha256((local/'data/content.json').read_bytes()).hexdigest()==content_before,'public functions never modify editorial content')
            document['bulletin']['date']='2020-01-01';document['bulletin']['title']='Old misleading title';(local/'data/content.json').write_text(json.dumps(document))
            page.goto(base+'bulletin.php',wait_until='networkidle')
            check('Weekly bulletin being updated' in page.locator('h1').inner_text() and page.locator('.bulletin-notes').count()==0,'old issue cannot masquerade as current bulletin')
            check('no-store' in urllib.request.urlopen(base+'bulletin.php').headers['Cache-Control'],'bulletin cannot be cached as a stale current issue')
            page.goto(base+'member/login.php',wait_until='networkidle')
            page.locator('[name=email]').fill('admin@example.invalid');page.locator('[name=password]').fill(password)
            page.locator('button[type=submit]').click();page.wait_for_url('**/member/**')
            page.goto(base+'admin/',wait_until='networkidle')
            check(page.locator('input[name^="worship_streams["]').count()==3,'Publishing Desk exposes all three broadcast fields')
            posted=page.locator('[data-publishing-form]').evaluate('el=>Object.fromEntries(new FormData(el))')
            posted['confirm_publish']='1'
            posted['worship_streams[traditional]']=posted['worship_streams[front-porch]']
            response=page.request.post(base+'admin/save.php',form=posted,headers={'Accept':'application/json'})
            check(response.status==422 and 'Duplicate' in response.json()['error'],'Publishing Desk refuses duplicate service recordings')
            posted['worship_streams[traditional]']='https://www.facebook.com/Church/videos/777/'
            response=page.request.post(base+'admin/save.php',form=posted,headers={'Accept':'application/json'})
            check(response.status==200 and response.json()['ok'],'Publishing Desk saves three independently verified service URLs')
            saved=json.loads((local/'data/content.json').read_text())
            check(saved['worship_streams']['traditional']=='https://www.facebook.com/watch/?v=777','saved recording URL is canonical and survives publication')
            page.goto(base+'#watch',wait_until='networkidle')
            check(page.locator('[data-type=traditional] a').get_attribute('href').endswith('v=777'),'published service recording is used by the actual watch button')
            browser.close()
    finally:server.terminate();server.wait(timeout=10);log.close()
print('TOTAL BROWSER CHECKS:',checks)
