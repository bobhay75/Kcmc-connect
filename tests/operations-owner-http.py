#!/usr/bin/env python3
"""Exercise real PHP routes with isolated users, storage and HTTP sessions."""
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

APP = Path(__file__).resolve().parents[1] / 'KCMC-Connect-Phase6-Recreated'
ROUTES = ['operations.php', 'health.php', 'audit.php', 'audit-export.php',
          'push.php', 'backup.php', 'restore.php', 'timecards.php',
          'timecards-export.php', 'timecards-print.php']

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

def request(client, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    try:
        response = client.open(url, body, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    return response.code, response.headers, response.read().decode('utf-8')

def check(condition, label):
    assert condition, label
    print('PASS:', label, flush=True)

def run():
    password = 'Synthetic-Owner-Audit-2031!'
    hashed = subprocess.check_output(['php', '-r', 'echo password_hash($argv[1], PASSWORD_DEFAULT);', password], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='kcmc-owner-http-') as tmp:
        work = Path(tmp)
        shutil.copytree(APP, work / 'app')
        private = work / 'private'
        private.mkdir()
        users = [dict(id=uid, email=uid+'@example.invalid', email_normalized=uid+'@example.invalid',
                      display_name='Synthetic '+uid, role=role, active=True, password_hash=hashed)
                 for uid, role in [('owner','pastor_admin'),('other_admin','pastor_admin'),
                                   ('recovery','recovery_admin'),('staff','member')]]
        (private / 'users.json').write_text(json.dumps({'version':1,'users':users}), encoding='utf-8')
        period_start='2026-09-23'; period_end='2026-10-22'
        seeded_timeclock={'version':1,'entries':[{'id':'time_owner_1','user_id':'owner','work_date':'2026-10-13','clock_in_at':'2026-10-13T15:00:00+00:00','clock_out_at':'2026-10-13T16:00:00+00:00','breaks':[],'category':'KCMC Connect / IT','description':'Synthetic owner work','status':'submitted','created_at':'2026-10-13T15:00:00+00:00','updated_at':'2026-10-13T16:00:00+00:00','net_minutes':60,'corrections':[]}], 'periods':[{'user_id':'owner','start':period_start,'end':period_end,'status':'submitted','submitted_at':'2026-10-13T16:05:00+00:00','approved_at':None,'approved_by':None,'returned_at':None,'return_reason':None}], 'adjustments':[], 'correction_requests':[]}
        (private / 'timeclock.json').write_text(json.dumps(seeded_timeclock), encoding='utf-8')
        # Repeat with missing configuration and with a non-administrator ID.
        for configured in ['owner', '', 'staff']:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port=sock.getsockname()[1]
            base=f'http://127.0.0.1:{port}/app'
            env={k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
            env.update(KCMC_PRIVATE_DATA_DIR=str(private), KCMC_SETUP_KEY='', KCMC_OPERATIONS_OWNER_USER_ID=configured)
            with (work / 'server.log').open('w') as log:
                server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(work)], env=env, stdout=log, stderr=log)
                try:
                    for _ in range(60):
                        try:
                            urllib.request.urlopen(base+'/',timeout=1).close(); break
                        except Exception: time.sleep(.1)
                    else: raise AssertionError('PHP server did not start')
                    anonymous=urllib.request.build_opener(NoRedirect())
                    for route in ROUTES:
                        status,headers,_=request(anonymous,base+'/admin/'+route)
                        check(status==302 and '/member/login.php' in headers.get('Location',''), 'anonymous redirected: '+route)
                    for uid in ['owner','other_admin','recovery','staff']:
                        jar=http.cookiejar.CookieJar()
                        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),NoRedirect())
                        _,_,html=request(client,base+'/member/login.php')
                        csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
                        status,_,_=request(client,base+'/member/login.php',dict(csrf=csrf,email=uid+'@example.invalid',password=password))
                        check(status==302, 'real sign-in: '+uid)
                        allowed=uid=='owner' and configured=='owner'
                        for route in ROUTES:
                            status,headers,html=request(client,base+'/admin/'+route)
                            check(status in ([200,404] if allowed else [403]), f'{configured or "unset"}/{uid}: GET {route} status {status}')
                            check('no-store' in headers.get('Cache-Control',''), 'private response: '+route)
                            if not allowed:
                                status,_,_=request(client,base+'/admin/'+route,dict(action='approve',csrf='invalid',user_id='owner'))
                                check(status==403, f'{uid}: POST denied before action: '+route)
                        if uid in ['other_admin','recovery']:
                            check(request(client,base+'/admin/')[0]==200,'non-owner administrator retains Publishing Desk')
                            check(request(client,base+'/admin/publication-designer.php')[0]==200,'non-owner administrator retains Publisher')
                        check(request(client,base+'/member/timeclock.php')[0]==200,'member retains own Time Clock')
                        if uid=='owner' and configured=='owner':
                            status,_,html=request(client,base+'/admin/timecards.php')
                            csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
                            status,_,html=request(client,base+'/admin/timecards.php',dict(csrf=csrf,action='approve',user_id='owner',start=period_start,end=period_end))
                            check(status==200 and 'Owner self-approval is disabled' in html,'self-approval defaults to disabled policy')
                            stored=json.loads((private/'timeclock.json').read_text(encoding='utf-8'))
                            check(stored['periods'][0]['status']=='submitted','disabled self-approval leaves payroll record unchanged')
                finally:
                    server.terminate();server.wait(timeout=10)
        # Explicit policy activation permits only the configured owner to self-approve and records immutable review metadata.
        (private / 'timeclock.json').write_text(json.dumps(seeded_timeclock), encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}/app'
        env={k:v for k,v in os.environ.items() if not k.startswith('KCMC_')}
        env.update(KCMC_PRIVATE_DATA_DIR=str(private), KCMC_SETUP_KEY='', KCMC_OPERATIONS_OWNER_USER_ID='owner', KCMC_TIMECARD_SELF_APPROVAL_ENABLED='1')
        with (work / 'server-self-approval.log').open('w') as log:
            server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(work)], env=env, stdout=log, stderr=log)
            try:
                for _ in range(60):
                    try:
                        urllib.request.urlopen(base+'/',timeout=1).close(); break
                    except Exception: time.sleep(.1)
                jar=http.cookiejar.CookieJar(); client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),NoRedirect())
                _,_,html=request(client,base+'/member/login.php'); csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
                check(request(client,base+'/member/login.php',dict(csrf=csrf,email='owner@example.invalid',password=password))[0]==302,'owner sign-in for enabled self-approval')
                _,_,html=request(client,base+'/admin/timecards.php'); csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
                status,_,html=request(client,base+'/admin/timecards.php',dict(csrf=csrf,action='approve',user_id='owner',start=period_start,end=period_end))
                check(status==200 and 'Time card approved.' in html,'explicit policy enables owner self-approval')
                stored=json.loads((private/'timeclock.json').read_text(encoding='utf-8')); period=stored['periods'][0]
                check(period['status']=='approved' and period['approved_by']=='owner' and period.get('self_approved') is True,'self-approved period stores actor and explicit flag')
                history=period.get('review_history',[])
                check(len(history)==1 and history[0]['actor_id']=='owner' and history[0]['self_approved'] is True and bool(history[0]['at']),'self-approval appends timestamped review history')
            finally:
                server.terminate();server.wait(timeout=10)
        print('Operations owner HTTP acceptance passed; no production traffic or records.')

if __name__=='__main__': run()
