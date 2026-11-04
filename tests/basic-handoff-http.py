#!/usr/bin/env python3
"""Exercise the handoff profile over HTTP using synthetic accounts and storage."""
import http.cookiejar, json, os, re, shutil, socket, subprocess, tempfile, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kcmc-basic-') as tmp:
    root = Path(tmp) / 'app'
    subprocess.run(['python3', str(repo / 'tools/basic-handoff/build.py'), str(root)], check=True)
    assert not (root / 'admin/publication-designer.php').exists()
    assert not (root / 'member/timeclock.php').exists()
    assert not (root / 'data/private').exists()
    assert not (root / 'config.php').exists()
    private = Path(tmp) / 'private'; private.mkdir(mode=0o700)
    password = 'synthetic-test-password-123'
    digest = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1], PASSWORD_DEFAULT);', password], text=True)
    users = [{'id': 'admin-1', 'email': 'admin@example.test', 'email_normalized': 'admin@example.test', 'display_name':'Test Admin', 'role':'recovery_admin', 'password_hash':digest, 'active':True}, {'id':'member-1','email':'member@example.test','email_normalized':'member@example.test','display_name':'Test Member','role':'member','password_hash':digest,'active':True}]
    (private / 'users.json').write_text(json.dumps({'version':1,'users':users}))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    env=os.environ.copy(); env['KCMC_PRIVATE_DATA_DIR']=str(private)
    # The PHP CLI server otherwise walks up to admin/index.php for a missing
    # filename, unlike the file-serving configuration this fixture models.
    # Refuse only nonexistent PHP paths; existing routes execute normally.
    router=Path(tmp) / 'router.php'
    router.write_text("""<?php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (str_ends_with($path, '.php') && !is_file($_SERVER['DOCUMENT_ROOT'] . $path)) {
    http_response_code(404);
    return true;
}
return false;
""")
    server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(root),str(router)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
    base=f'http://127.0.0.1:{port}'
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    def client(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
    def request(opener,path,data=None,headers=None):
        headers = headers or {}
        raw = None if data is None else (json.dumps(data).encode() if headers.get('Content-Type') == 'application/json' else urllib.parse.urlencode(data).encode())
        req=urllib.request.Request(base+path,data=raw,headers=headers)
        try:
            with opener.open(req,timeout=5) as res: return res.status,res.headers,res.read().decode('utf-8','replace')
        except urllib.error.HTTPError as err: return err.code,err.headers,err.read().decode('utf-8','replace')
    try:
        for _ in range(50):
            try: request(client(),'/'); break
            except OSError: time.sleep(.1)
        public=client()
        # Event artwork fallback is a public presentation requirement, not a data mutation.
        events_source=(repo / 'KCMC-Connect-Phase6-Recreated/events.php').read_text()
        assert "trunk-or-treat-2026.svg" in events_source, 'Trunk or Treat fallback artwork missing'
        assert (root / 'assets/visuals/trunk-or-treat-2026.svg').is_file(), 'fallback artwork absent from release candidate'
        for path in ['/','/care.php','/events.php','/bulletin.php','/member/login.php']:
            status,_,_=request(public,path); assert status==200,(path,status)
        for path in ['/member/index.php','/member/timeclock.php','/member/prayer-care.php','/member/work.php','/member/activate.php','/admin/publication-designer.php','/admin/publication-media.php','/admin/publication-projects.php','/admin/timecards.php','/admin/users.php','/admin/push.php','/api/team-workspace.php','/api/push-subscription.php']:
            status,_,_=request(public,path); assert status==404,(path,status)
        # Excluded endpoints must remain absent for both verbs and both roles.
        # These tests exercise the built candidate, not an existing live host.
        excluded = ['/member/index.php','/member/timeclock.php','/member/prayer-care.php',
                    '/member/work.php','/member/activate.php','/admin/publication-designer.php',
                    '/admin/publication-media.php','/admin/publication-projects.php',
                    '/admin/timecards.php','/admin/users.php','/admin/push.php',
                    '/api/team-workspace.php','/api/push-subscription.php']
        for path in excluded:
            for payload in (None, {'synthetic':'1'}):
                status,_,_=request(public,path,payload)
                assert status==404,(path,'POST' if payload else 'GET',status)
        status,_,body=request(public,'/member/login.php'); csrf=re.search(r'name="csrf" value="([^"]+)',body).group(1)
        status,_,body=request(public,'/member/login.php',{'csrf':csrf,'email':'member@example.test','password':password})
        assert status==200 and 'not recognized' in body, 'member account must not sign in'
        # A failed staff login must not create an authenticated administrator session.
        bad_admin=client()
        _,_,bad_form=request(bad_admin,'/member/login.php')
        bad_csrf=re.search(r'name="csrf" value="([^"]+)',bad_form).group(1)
        bad_status,_,bad_body=request(bad_admin,'/member/login.php',{'csrf':bad_csrf,'email':'admin@example.test','password':'incorrect-synthetic-password'})
        assert bad_status==200 and 'not recognized' in bad_body, 'invalid administrator credentials accepted'
        denied_status,_,_=request(bad_admin,'/admin/')
        assert denied_status==302, ('failed login reached administrator content',denied_status)
        anonymous_status,_,_=request(public,'/admin/')
        assert anonymous_status==302, ('anonymous visitor reached administrator content',anonymous_status)
        admin=client(); _,_,body=request(admin,'/member/login.php'); csrf=re.search(r'name="csrf" value="([^"]+)',body).group(1)
        status,headers,_=request(admin,'/member/login.php',{'csrf':csrf,'email':'admin@example.test','password':password,'next':'/member/timeclock.php'})
        assert status==302 and headers.get('Location')=='/admin/', (status,headers.get('Location'))
        status,_,body=request(admin,'/admin/'); assert status==200 and 'Church content' in body,(status,body[:200])
        for path in ['/admin/publication-designer.php','/member/timeclock.php','/api/team-workspace.php']:
            status,_,_=request(admin,path); assert status==404,(path,status)
        for path in excluded:
            for payload in (None, {'synthetic':'1'}):
                status,_,_=request(admin,path,payload)
                assert status==404,(path,'admin POST' if payload else 'admin GET',status)
        # Public forms use the real APIs and the isolated private store.
        connection_headers={'Content-Type':'application/json','X-KCMC-Connection':'1','Sec-Fetch-Site':'same-origin'}
        def post_json(path,payload,headers,expected):
            code,response,raw=request(public,path,payload,headers)
            assert code==expected,(path,code,raw[:240])
            assert 'no-store' in response.get('Cache-Control',''), (path,'private cache header absent')
            return json.loads(raw)
        forms=[
            {'kind':'visit','firstName':'Synthetic','lastName':'Visitor','email':'visit@example.test','service':'9:15 AM — Traditional Worship'},
            {'kind':'serve','name':'Synthetic Volunteer','email':'serve@example.test','interest':'Hospitality / Welcome'},
            {'kind':'groups','name':'Synthetic Group','email':'group@example.test','interest':'Small group / Bible study'},
        ]
        for form in forms:
            assert post_json('/api/connection.php',form,{'Content-Type':'application/json'},403)['ok'] is False
            assert post_json('/api/connection.php',dict(form,email='bad-email'),connection_headers,422)['ok'] is False
            result=post_json('/api/connection.php',form,connection_headers,201)
            assert result['ok'] and not result['duplicate']
            assert post_json('/api/connection.php',form,connection_headers,200)['duplicate']
            assert form['email'] not in request(public,'/api/content.php')[2]
        code,_,inbox=request(admin,'/admin/connections.php')
        assert code==200 and all(form['email'] in inbox for form in forms), 'connections not visible to authorized admin'
        code,_,csv=request(admin,'/admin/connections-export.php')
        assert code==200 and all(form['email'] in csv for form in forms), 'connections export is incomplete'
        for path in ('/admin/connections.php','/admin/connections-export.php','/admin/rsvps.php','/admin/rsvps-export.php'):
            assert request(public,path)[0] in (302,403), (path,'anonymous inbox access')
        print('PASS: visit, serve and group form validation, save, duplicate refusal, private inbox and export')
        # Exercise real content writes only against the temporary synthetic package.
        content_path = root / 'data/content.json'
        before_bytes = content_path.read_bytes()
        content = json.loads(before_bytes)
        version = re.search(r'name="version" value="([a-f0-9]{64})', body).group(1)
        csrf = re.search(r'name="csrf" value="([^"]+)', body).group(1)
        announcement_id = re.search(r'name="announcement_id" value="([^"]*)', body).group(1)
        announcement = next((a for a in content['announcements'] if a.get('id') == announcement_id), {})
        contact = content['contact']; bulletin = content['bulletin']
        payload = {'csrf':csrf, 'version':version, 'confirm_publish':'1',
                   'contact_email':contact['email'], 'contact_phone':contact.get('phone',''),
                   'contact_hours':contact.get('office_hours',''), 'contact_address':contact.get('address',''),
                   'announcement_id':announcement_id, 'announcement_title':announcement.get('title',''),
                   'announcement_body':announcement.get('body',''), 'announcement_priority':announcement.get('priority',50),
                   'announcement_status':announcement.get('status','hidden'), 'announcement_expires':'',
                   'bulletin_title':bulletin.get('title',''), 'bulletin_date':bulletin.get('date',''),
                   'bulletin_welcome':'Synthetic acceptance update', 'bulletin_notes':'\n'.join(bulletin.get('notes',[]))}
        invalid = dict(payload, csrf='invalid')
        status,_,_=request(admin,'/admin/save.php',invalid); assert status==403, status
        assert content_path.read_bytes()==before_bytes, 'invalid CSRF changed content'
        status,_,_=request(admin,'/admin/save.php',payload); assert status==302, status
        assert json.loads(content_path.read_text())['bulletin']['welcome']=='Synthetic acceptance update'
        assert any(p.read_bytes()==before_bytes for p in (root/'backups').glob('content-*.json')), 'original content backup missing'
        # Recovery proof: the saved pre-edit snapshot must parse and preserve its original bytes.
        saved_backups=list((root/'backups').glob('content-*.json'))
        assert saved_backups, 'no backup snapshot to restore'
        original_snapshot=next((p for p in saved_backups if p.read_bytes()==before_bytes),None)
        assert original_snapshot is not None, 'pre-edit snapshot cannot be recovered'
        assert json.loads(original_snapshot.read_text())==content, 'backup recovery content mismatch'
        # Restore drill on an isolated copy; never overwrite the running candidate.
        restored = Path(tmp) / 'restored-content.json'
        shutil.copyfile(original_snapshot, restored)
        assert restored.read_bytes() == before_bytes, 'restored snapshot differs from original content'
        assert json.loads(restored.read_text()) == content, 'restored JSON is invalid or incomplete'

        status,_,_=request(admin,'/admin/save.php',payload); assert status==409, status
        after_save=content_path.read_bytes()
        assert json.loads(after_save)['bulletin']['welcome']=='Synthetic acceptance update'
        status,_,body=request(admin,'/admin/event-create.php'); assert status==200
        csrf=re.search(r'name="csrf" value="([^"]+)',body).group(1)
        event={'csrf':csrf,'title':'Synthetic acceptance event','date':'2035-01-01','time':'4:30 PM','end_time':'6:30 PM','location':'Test hall','description':'Synthetic data','priority':'50','status':'published','expires':''}
        status,_,_=request(admin,'/admin/event-create.php',event); assert status==302, status
        assert any(e.get('title')=='Synthetic acceptance event' for e in json.loads(content_path.read_text())['events'])
        assert any(p.read_bytes()==after_save for p in (root/'backups').glob('content-*.json')), 'event backup missing'
        status,_,_=request(admin,'/admin/event-create.php',event); assert status==409, status
        rsvp_headers={'Content-Type':'application/json','X-KCMC-RSVP':'1','Sec-Fetch-Site':'same-origin'}
        rsvp={'event':event['title'],'event_date':event['date'],'name':'Synthetic RSVP','email':'rsvp@example.test'}
        assert post_json('/api/rsvp.php',rsvp,{'Content-Type':'application/json'},403)['ok'] is False
        assert post_json('/api/rsvp.php',dict(rsvp,email='bad-email'),rsvp_headers,422)['ok'] is False
        assert post_json('/api/rsvp.php',dict(rsvp,event='Missing synthetic event'),rsvp_headers,409)['ok'] is False
        assert post_json('/api/rsvp.php',rsvp,rsvp_headers,201)['ok']
        assert post_json('/api/rsvp.php',rsvp,rsvp_headers,200)['duplicate']
        for path in ('/admin/rsvps.php','/admin/rsvps-export.php'):
            code,_,result=request(admin,path)
            assert code==200 and rsvp['email'] in result, (path,code)
        assert rsvp['email'] not in request(public,'/api/content.php')[2]
        print('PASS: RSVP validation, event availability, private save, duplicate detection and export')
        status,_,_=request(admin,'/member/logout.php',{'csrf':csrf}); assert status==302, status
        status,_,_=request(admin,'/admin/'); assert status==302, status
        print('PASS: public pages, administrator authentication, extra-route denial, CSRF, content backup, stale-edit rejection, event creation and sign-out')
    finally:
        server.terminate(); server.wait(timeout=5)
