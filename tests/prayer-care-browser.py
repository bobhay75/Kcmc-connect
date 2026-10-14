"""Synthetic-only ministry acceptance. No live site, accounts, messages or records."""
import hashlib,json,os,shutil,socket,subprocess,tempfile,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
PHP=os.environ.get('PHP_BIN','php')
with tempfile.TemporaryDirectory(prefix='kcmc-care-browser-') as tmp:
    root=Path(tmp);app=root/'app';private=root/'private';private.mkdir()
    shutil.copytree(ROOT/'KCMC-Connect-Phase6-Recreated',app,ignore=shutil.ignore_patterns('private','backups','config.php'))
    secret='SyntheticPassword-2040!'
    password=subprocess.check_output([PHP,'-r','echo password_hash($argv[1],PASSWORD_DEFAULT);',secret]).decode()
    users=[{'id':name,'email':name+'@example.invalid','email_normalized':name+'@example.invalid','display_name':name.title()+' Example','role':role,'active':True,'password_hash':password} for name,role in [('alice','member'),('bob','member'),('pastor','pastor_admin'),('recovery','recovery_admin'),('owner','recovery_admin'),('team','prayer_team')]]
    (private/'users.json').write_text(json.dumps({'version':1,'users':users}))
    legacy=json.dumps({'version':1,'prayers':[{'id':'old-private','submitted_by':'bob','message':'LEGACY_PRIVATE_DO_NOT_IMPORT','status':'private','audience':'pastors_only','created_at':'2026-10-01T12:00:00Z'}]})
    (private/'prayers.json').write_text(legacy)
    content=(app/'data/content.json').read_bytes()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}';url=base+'/member/prayer-care.php'
    env={**os.environ,'KCMC_PRIVATE_DATA_DIR':str(private),'KCMC_SETUP_KEY':'','KCMC_OPERATIONS_OWNER_USER_ID':'owner'}
    proc=subprocess.Popen([PHP,'-S',f'127.0.0.1:{port}','-t',str(app)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.2):break
            except OSError:time.sleep(.1)
        with sync_playwright() as p:
            browser=p.chromium.launch();errors=[]
            def member(name):
                context=browser.new_context(viewport={'width':375,'height':850});page=context.new_page()
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/member/login.php');page.locator('[name=email]').fill(name+'@example.invalid');page.locator('[name=password]').fill(secret)
                page.locator('button[type=submit]').click();page.wait_for_url('**/member/')
                page.goto(url);return page
            anon=browser.new_page();anon.goto(url);assert '/login.php' in anon.url
            assert 'LEGACY_PRIVATE_DO_NOT_IMPORT' not in anon.content()
            alice=member('alice');bob=member('bob');pastor=member('pastor');team=member('team');recovery=member('recovery');owner=member('owner')
            assert recovery.goto(url).status==403
            for page in [alice,bob,pastor,team,owner]:
                response=page.goto(url);assert 'no-store' in response.headers['cache-control'];assert 'noindex' in response.headers['x-robots-tag']
                assert 'LEGACY_PRIVATE_DO_NOT_IMPORT' not in page.content()
            assert alice.goto(url+'?view=review').status==403;alice.goto(url)
            assert alice.request.post(url,data={'action':'join','revision':'0','confidential':'1'}).status==403
            alice.get_by_label('I will keep prayer requests confidential',exact=False).check();alice.get_by_role('button',name='Sign up to pray',exact=True).click()
            assert alice.get_by_text('Prayer warriors · Awaiting approval').is_visible()
            assert json.loads((private/'users.json').read_text())['users'][0]['role']=='member'
            assert owner.goto(base+'/admin/operations.php').status==200
            assert owner.goto(base+'/member/prayer-team.php').status==200
            assert recovery.goto(url+'?view=review').status==403
            owner.goto(url+'?view=review');owner.get_by_role('button',name='Approve signup',exact=True).click()
            out=os.environ.get('KCMC_OWNER_SCREENSHOT')
            if out:owner.screenshot(path=out,full_page=True)
            alice.goto(url);assert alice.get_by_text('Prayer warriors · You’re on the team').is_visible()
            # A signup never unlocks the legacy confidential inbox.
            assert alice.goto(base+'/member/prayer-team.php').status==403
            alice.goto(url)
            def submit(page,message,kind='need',audience='pastoral'):
                page.goto(url);page.get_by_text('Share a prayer need or praise report',exact=True).click()
                page.get_by_label('What would you like to share?').select_option(kind)
                page.get_by_label('Your words',exact=True).fill(message)
                page.get_by_label('Who may see this?').select_option(audience)
                if audience!='pastoral':page.get_by_label('If I choose group sharing',exact=False).check()
                page.get_by_role('button',name='Submit for care',exact=True).click()
            private_words='PRIVATE_NEW_REQUEST never shared with warriors.'
            need='Please pray for our community outreach this week.'
            praise='Thank you for praying. We are grateful for renewed hope.'
            submit(bob,private_words)
            submit(bob,need,audience='team')
            alice.goto(url);assert need not in alice.content() and private_words not in alice.content()
            pastor.goto(url+'?view=review');card=pastor.locator('article').filter(has_text=need)
            card.get_by_role('button',name='Approve chosen audience').click()
            alice.goto(url);assert alice.get_by_text(need,exact=True).is_visible();assert private_words not in alice.content()
            team.goto(url);assert need not in team.content()
            alice.get_by_role('button',name='I’ll pray for this').click()
            alice.get_by_role('link',name='My prayers',exact=True).click();assert alice.get_by_text(need,exact=True).is_visible()
            assert alice.get_by_role('button',name='Mark answered').count()==0
            for width in [320,375,1280]:
                alice.set_viewport_size({'width':width,'height':850});alice.goto(url)
                assert alice.evaluate('document.documentElement.scrollWidth<=innerWidth')
                alice.get_by_role('button',name='On my prayer list — remove').click(trial=True)
            # Revise shared words: old approval must not expose new text.
            bob.goto(url+'?view=mine');card=bob.locator('article').filter(has_text=need)
            card.get_by_text('Update my words').click();card.get_by_label('Updated words').fill(need+' Updated.')
            card.get_by_role('button',name='Save update for review').click()
            alice.goto(url+'?view=mine');assert need not in alice.content()
            pastor.goto(url+'?view=review');pastor.locator('article').filter(has_text=need).get_by_role('button',name='Approve chosen audience').click()
            bob.goto(url+'?view=mine');bob.locator('article').filter(has_text=need).get_by_role('button',name='Mark answered').click()
            alice.goto(url);assert need not in alice.content()
            alice.goto(url+'?view=praise');assert need not in alice.content()
            submit(bob,praise,kind='praise',audience='members')
            alice.goto(url+'?view=praise');assert praise not in alice.content()
            pastor.goto(url+'?view=review');pastor.locator('article').filter(has_text=praise).get_by_role('button',name='Approve chosen audience').click()
            alice.goto(url+'?view=praise');assert alice.get_by_text(praise,exact=True).is_visible()
            assert private_words not in alice.content() and need not in alice.content()
            alice.set_viewport_size({'width':375,'height':850})
            out=os.environ.get('KCMC_CARE_SCREENSHOT')
            if out:alice.screenshot(path=out,full_page=True)
            for route in ['/','/care.php','/api/content.php']:
                response=anon.goto(base+route);html=response.text()
                assert not any(words in html for words in [private_words,need,praise,'LEGACY_PRIVATE_DO_NOT_IMPORT'])
            # Store contains no surprise account role changes and no private source migration.
            assert (private/'prayers.json').read_text()==legacy
            assert (app/'data/content.json').read_bytes()==content
            assert all(u['role']==v['role'] for u,v in zip(json.loads((private/'users.json').read_text())['users'],users))
            assert not errors,errors
            browser.close()
        print('PASS: signup/approval, role isolation, CSRF, private audiences, prayer adoption, updates, answered/praise approval, mobile, public exclusion and unchanged legacy/content')
    finally:proc.terminate();proc.wait(timeout=10)
