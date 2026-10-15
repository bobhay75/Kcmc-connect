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
    base=f'http://127.0.0.1:{port}';url=base+'/member/prayer-care.php';admin_url=base+'/admin/prayer-care.php'
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
                assert 'My Account' in page.title()
                assert page.get_by_role('navigation',name='Personal settings').count()==1
                assert page.get_by_role('button',name='Send private request',exact=True).count()==0
                assert page.get_by_role('link',name='Administration',exact=True).count()==int(name in ['pastor','recovery','owner'])
                assert page.get_by_role('link',name='Ministry work',exact=True).count()==int(name=='team')
                assert page.locator('a[href*="/admin/"]').count()==int(name in ['pastor','recovery','owner','team'])
                page.goto(url);return page
            anon=browser.new_page();anon.goto(url);assert '/login.php' in anon.url
            assert 'LEGACY_PRIVATE_DO_NOT_IMPORT' not in anon.content()
            alice=member('alice');bob=member('bob');pastor=member('pastor');team=member('team');recovery=member('recovery');owner=member('owner')
            assert recovery.goto(url).status==403
            for page in [alice,bob,pastor,team,owner]:
                response=page.goto(url);assert 'no-store' in response.headers['cache-control'];assert 'noindex' in response.headers['x-robots-tag']
                assert 'LEGACY_PRIVATE_DO_NOT_IMPORT' not in page.content()
            assert alice.goto(url+'?view=review').status==403;alice.goto(url)
            assert alice.request.post(url,form={'action':'join','revision':'0','confidential':'1'}).status==403
            assert pastor.request.post(admin_url,form={'action':'approve_warrior','revision':'0','target':'alice'}).status==403
            alice.get_by_label('I will keep prayer requests confidential',exact=False).check();alice.get_by_role('button',name='Sign up to pray',exact=True).click()
            assert alice.get_by_text('Prayer warriors · Awaiting approval').is_visible()
            assert json.loads((private/'users.json').read_text())['users'][0]['role']=='member'
            assert owner.goto(base+'/admin/operations.php').status==200
            assert owner.goto(base+'/member/prayer-team.php').status==200
            assert owner.url==base+'/admin/prayer-inbox.php'
            assert owner.goto(base+'/admin/home.php').status==200
            assert team.goto(base+'/admin/home.php').status==200
            assert team.get_by_role('link',name='Open Confidential prayer inbox',exact=True).count()==1
            assert team.get_by_role('link',name='Open Prayer & Care review',exact=True).count()==0
            assert recovery.goto(url+'?view=review').status==403
            assert recovery.goto(admin_url).status==403
            # Old GET bookmarks redirect safely; personal Care has no admin UI.
            owner.goto(url+'?view=review');assert owner.url==admin_url+'?view=review'
            for personal in [alice,bob,pastor,team,owner]:
                personal.goto(url)
                assert personal.get_by_role('link',name='Pastoral review',exact=True).count()==0
                assert personal.get_by_role('button',name='Approve signup',exact=True).count()==0
                assert personal.get_by_role('button',name='Approve chosen audience',exact=True).count()==0
            assert alice.goto(admin_url).status==403
            assert team.goto(admin_url).status==403
            owner.goto(admin_url)
            # A still-open legacy approval form gets a method-preserving redirect,
            # not an implicit approval or a discarded POST. The new admin form
            # then performs the same permitted action with a fresh CSRF check.
            before_redirect=(private/'prayer-care.json').read_bytes()
            old_post=owner.request.post(url,form={
                'action':'approve_warrior','target':'alice',
                'csrf':owner.locator('input[name=csrf]').first.input_value(),
                'revision':owner.locator('input[name=revision]').first.input_value(),
            },max_redirects=0)
            assert old_post.status==307 and old_post.headers['location']=='/admin/prayer-care.php?view=review'
            assert (private/'prayer-care.json').read_bytes()==before_redirect
            owner.get_by_role('button',name='Approve signup',exact=True).click()
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
            pastor.goto(admin_url);card=pastor.locator('article').filter(has_text=need)
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
            pastor.goto(admin_url);pastor.locator('article').filter(has_text=need).get_by_role('button',name='Approve chosen audience').click()
            bob.goto(url+'?view=mine');bob.locator('article').filter(has_text=need).get_by_role('button',name='Mark answered').click()
            alice.goto(url);assert need not in alice.content()
            alice.goto(url+'?view=praise');assert need not in alice.content()
            submit(bob,praise,kind='praise',audience='members')
            alice.goto(url+'?view=praise');assert praise not in alice.content()
            pastor.goto(admin_url);pastor.locator('article').filter(has_text=praise).get_by_role('button',name='Approve chosen audience').click()
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
        print('PASS: personal/admin separation, signup/approval, owner override, role isolation, CSRF, private audiences, prayer adoption, updates, answered/praise approval, mobile, public exclusion and unchanged legacy/content')
    finally:proc.terminate();proc.wait(timeout=10)
