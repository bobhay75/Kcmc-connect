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
    server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
    base=f'http://127.0.0.1:{port}'
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    def client(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
    def request(opener,path,data=None):
        req=urllib.request.Request(base+path,data=urllib.parse.urlencode(data).encode() if data is not None else None)
        try:
            with opener.open(req,timeout=5) as res: return res.status,res.headers,res.read().decode('utf-8','replace')
        except urllib.error.HTTPError as err: return err.code,err.headers,err.read().decode('utf-8','replace')
    try:
        for _ in range(50):
            try: request(client(),'/'); break
            except OSError: time.sleep(.1)
        public=client()
        for path in ['/','/care.php','/events.php','/bulletin.php','/member/login.php']:
            status,_,_=request(public,path); assert status==200,(path,status)
        for path in ['/member/index.php','/member/timeclock.php','/member/prayer-care.php','/member/work.php','/member/activate.php','/admin/publication-designer.php','/admin/publication-media.php','/admin/publication-projects.php','/admin/timecards.php','/admin/users.php','/admin/push.php','/api/team-workspace.php','/api/push-subscription.php']:
            status,_,_=request(public,path); assert status==404,(path,status)
        status,_,body=request(public,'/member/login.php'); csrf=re.search(r'name="csrf" value="([^"]+)',body).group(1)
        status,_,body=request(public,'/member/login.php',{'csrf':csrf,'email':'member@example.test','password':password})
        assert status==200 and 'not recognized' in body, 'member account must not sign in'
        admin=client(); _,_,body=request(admin,'/member/login.php'); csrf=re.search(r'name="csrf" value="([^"]+)',body).group(1)
        status,headers,_=request(admin,'/member/login.php',{'csrf':csrf,'email':'admin@example.test','password':password,'next':'/member/timeclock.php'})
        assert status==302 and headers.get('Location')=='/admin/', (status,headers.get('Location'))
        status,_,body=request(admin,'/admin/'); assert status==200 and 'Church content' in body,(status,body[:200])
        for path in ['/admin/publication-designer.php','/member/timeclock.php','/api/team-workspace.php']:
            status,_,_=request(admin,path); assert status==404,(path,status)
        print('PASS: public pages, administrator login, member denial and extra-route denial')
    finally:
        server.terminate(); server.wait(timeout=5)
