#!/usr/bin/env python3
"""Real HTTP acceptance for personal/admin separation and legacy redirects.

Runs only against an isolated PHP server with synthetic accounts and data. It
never contacts production, sends mail/push or grants stored account roles.
"""
import argparse
import http.cookiejar
import importlib.util
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('account_routes',ROOT/'tests/member-account-routes.py')
routes=importlib.util.module_from_spec(spec);spec.loader.exec_module(routes)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None

def request(client,url,data=None):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    try: response=client.open(url,body,timeout=8)
    except urllib.error.HTTPError as error: response=error
    return response.code,response.headers,response.read().decode('utf-8')

checks=0
def check(ok,label):
    global checks
    if not ok: raise AssertionError(label)
    checks+=1;print('PASS:',label,flush=True)

def run(app):
    f=routes.Fixture(app)
    server=None
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base='http://127.0.0.1:'+str(port)+'/app'
        env={k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(f.private),KCMC_SETUP_KEY='',KCMC_OPERATIONS_OWNER_USER_ID='owner')
        with (f.root/'server.log').open('w') as log:
            server=subprocess.Popen([routes.PHP,'-S','127.0.0.1:'+str(port),'-t',str(f.root)],env=env,stdout=log,stderr=log)
            for _ in range(60):
                try: urllib.request.urlopen(base+'/member/login.php',timeout=1).close();break
                except Exception: time.sleep(.1)
            else: raise AssertionError('Isolated PHP server did not start')
            anon=urllib.request.build_opener(NoRedirect())
            for route in ['member/','member/prayers.php','admin/home.php','admin/prayer-inbox.php','admin/prayer-care.php']:
                status,headers,html=request(anon,base+'/'+route)
                check(status==302 and '/member/login.php' in headers.get('Location',''),'anonymous private route '+route)
                check('no-store' in headers.get('Cache-Control','') and 'SECRET' not in html,'anonymous privacy '+route)
            private_before={p.name:p.read_bytes() for p in f.private.iterdir() if p.is_file()}
            for payload in [None,{}]:
                status,headers,html=request(anon,base+'/admin/timeclock-period-close.php',payload)
                check(status==404,'period cutoff refuses HTTP '+('GET' if payload is None else 'POST'))
                check({p.name:p.read_bytes() for p in f.private.iterdir() if p.is_file()}==private_before,'HTTP cutoff leaves private stores unchanged')
            clients={}
            for uid in ['owner','pastor','recovery','prayer','member']:
                client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect());clients[uid]=client
                _,_,page=request(client,base+'/member/login.php');csrf=re.search(r'name="csrf" value="([^"]+)"',page).group(1)
                status,headers,_=request(client,base+'/member/login.php',dict(csrf=csrf,email=uid+'@example.invalid',password='Synthetic-Fixture-2031!'))
                check(status==302,'real sign-in '+uid)
                status,headers,page=request(client,base+'/member/')
                check(status==200 and '<title>My Account' in page and 'no-store' in headers.get('Cache-Control',''),'personal landing '+uid)
                check('SECRET' not in page and 'Send private request' not in page,'landing has no prayer payload '+uid)
                status,headers,page=request(client,base+'/member/timeclock.php')
                check(status==200 and 'Clock In' in page,'clock remains available to signed-in '+uid)
                status,headers,page=request(client,base+'/admin/home.php')
                check(status==(403 if uid=='member' else 200),'hub role '+uid)
                status,headers,page=request(client,base+'/admin/prayer-inbox.php')
                check(status==(200 if uid in ['owner','pastor','prayer'] else 403),'inbox role '+uid)
                status,headers,page=request(client,base+'/admin/prayer-care.php')
                check(status==(200 if uid in ['owner','pastor'] else 403),'care review role '+uid)
            for uid in ['owner','pastor']:
                status,headers,_=request(clients[uid],base+'/member/prayer-care.php?view=review')
                check(status==303 and headers.get('Location')=='/app/admin/prayer-care.php?view=review','old care review GET redirect '+uid)
            status,headers,_=request(clients['prayer'],base+'/member/prayer-team.php')
            check(status==303 and headers.get('Location')=='/app/admin/prayer-inbox.php','old inbox GET redirect')
            client=clients['pastor'];_,_,page=request(client,base+'/admin/prayer-care.php')
            csrf=re.search(r'name="csrf" value="([^"]+)"',page).group(1)
            post=dict(csrf=csrf,revision='0',action='approve_warrior',target='member')
            before=(f.private/'prayer-care.json').read_bytes()
            status,headers,_=request(client,base+'/member/prayer-care.php',post)
            check(status==307 and headers.get('Location')=='/app/admin/prayer-care.php?view=review','old moderation POST preserves method/payload')
            check((f.private/'prayer-care.json').read_bytes()==before,'redirect performs no mutation')
            status,_,_=request(client,base+headers['Location'][len('/app'):],post)
            check(status==303,'new admin route performs original POST')
            state=f.read('prayer-care.json')
            check(state['revision']==1 and state['warriors']['member']['status']=='approved','exactly one approved mutation')
            status,headers,_=request(client,base+'/admin/prayer-care.php',dict(post,csrf='invalid'))
            check(status==403 and f.read('prayer-care.json')==state,'admin CSRF rechecked')
            member=clients['member'];_,_,page=request(member,base+'/member/prayers.php')
            csrf=re.search(r'name="csrf" value="([^"]+)"',page).group(1)
            status,headers,_=request(member,base+'/member/submit-prayer.php',dict(csrf=csrf,message='Synthetic private request via retained form.'))
            check(status==302 and headers.get('Location')=='/app/member/prayers.php?submitted=1','earlier prayer submission returns to retained history')
            check(f.read('prayers.json')['prayers'][-1]['status']=='private','private submission default unchanged')
        print(str(checks)+' member-account HTTP checks passed; no production data or delivery.')
    finally:
        if server is not None: server.terminate();server.wait(timeout=10)
        f.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--app',type=Path,default=routes.APP);a=p.parse_args();run(a.app.resolve())
