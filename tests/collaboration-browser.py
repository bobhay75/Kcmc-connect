#!/usr/bin/env python3
"""Offline real-browser editor conflicts and publishing review; synthetic fetch only."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
OUTPUT = Path(os.environ.get('KCMC_COLLABORATION_ARTIFACTS', 'collaboration-artifacts'))
OUTPUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('save_fixture', ROOT / 'tests/publication-save-race-browser.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def check(condition, message):
    if not condition: raise AssertionError(message)
    print('PASS: ' + message, flush=True)


def main():
    identifier = 'pub_' + 'a'*24
    store = {identifier: {'id':identifier,'revision':1,'name':'Shared publication','updated':'2031-01-01T00:00:00Z','updated_by':'synthetic-publisher',
        'pages':[{'pageSize':'letter','orientation':'portrait','items':[{'type':'text','text':'Original exact words\n\n________','x':20,'y':20,'w':400,'h':160}]}]}}
    requests = []
    def request(url, method, raw):
        parsed=urlparse(url); path=parsed.path
        if path=='/admin/publication-media.php': return {'status':200,'body':{'ok':True,'media':[]}}
        if path!='/admin/publication-projects.php': raise AssertionError('Unexpected synthetic URL '+url)
        if method=='GET':
            if parsed.query:
                from urllib.parse import parse_qs
                query=parse_qs(parsed.query); project=store[query['id'][0]]
                return {'status':200,'body':{'ok':True,'project':{k:project[k] for k in ['id','revision','updated']}}}
            return {'status':200,'body':{'ok':True,'projects':deepcopy(list(store.values()))}}
        project=json.loads(raw); requests.append(deepcopy(project))
        check(project.pop('csrf')==module.CSRF,'editor includes the synthetic CSRF token')
        project_id=project.get('id')
        if project_id is not None and (project_id not in store or project['revision']!=store[project_id]['revision']):
            return {'status':409,'body':{'ok':False,'error':'This publication changed. Your edits are still here. Save a copy or load the latest version.'}}
        project['id']=project_id or 'pub_'+format(len(store)+1,'024x')
        project['revision']=store[project_id]['revision']+1 if project_id else 1
        project['updated']='2031-01-01T00:00:01Z'; project['updated_by']='synthetic-publisher'
        store[project['id']]=deepcopy(project)
        return {'status':200,'body':{'ok':True,'project':deepcopy(project)}}

    with sync_playwright() as pw:
        executable=os.environ.get('KCMC_CHROMIUM_PATH') or shutil.which('chromium')
        options={'headless':True,'args':['--no-sandbox']}
        if executable: options['executable_path']=executable
        browser=pw.chromium.launch(**options)
        pages=[];errors=[]
        for _ in range(2):
            page=browser.new_page(viewport={'width':1440,'height':1000},service_workers='block')
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/*',lambda route:route.abort())
            page.expose_function('__collaborationRequest',request)
            page.evaluate('''() => { window.fetch=async (url,options={})=>{const r=await window.__collaborationRequest(String(url),options.method||'GET',options.body||null);return {status:r.status,ok:r.status>=200&&r.status<300,json:async()=>r.body};}; }''')
            page.clock.install()
            page.set_content(module.fixture_html((APP/'admin/publication-designer.php').read_text()))
            page.locator('#savedList button').filter(has=page.get_by_text('Shared publication',exact=True)).click()
            pages.append(page)
        a,b=pages
        a.locator('#projectName').fill('Saved by publisher A');a.locator('#saveBtn').click()
        a.wait_for_function("document.querySelector('#status').textContent==='Saved for KCMC admins'")
        b.locator('#projectName').fill('Publisher B unsaved work');b.locator('#saveBtn').click()
        b.wait_for_function("document.querySelector('#status').textContent.includes('Your edits are still here')")
        check(b.locator('#projectName').input_value()=='Publisher B unsaved work','real editor keeps the second publisher’s unsaved input after 409')
        check(store[identifier]['name']=='Saved by publisher A','stale editor does not replace the first publisher’s saved draft')
        b.once('dialog',lambda dialog:dialog.dismiss());b.locator('#loadLatestBtn').click()
        check(b.locator('#projectName').input_value()=='Publisher B unsaved work','canceling Load latest retains the unsaved draft')
        b.locator('#saveCopyBtn').click();b.wait_for_function("document.querySelector('#status').textContent==='Saved for KCMC admins'")
        check(len(store)==2 and store[identifier]['name']=='Saved by publisher A','Save a copy preserves both editors’ work as distinct projects')
        b.locator('#savedList button').filter(has=b.get_by_text('Saved by publisher A',exact=True)).click()
        b.locator('#projectName').fill('Local draft stays until I choose')
        a.locator('#projectName').fill('Newer saved version');a.locator('#saveBtn').click()
        a.wait_for_function("document.querySelector('#status').textContent==='Saved for KCMC admins'")
        b.clock.fast_forward(10001)
        b.wait_for_function("document.querySelector('#status').textContent.includes('newer version')")
        check(b.locator('#projectName').input_value()=='Local draft stays until I choose','visible-tab polling marks newer saved work without replacing local edits')
        b.once('dialog',lambda dialog:dialog.accept());b.locator('#loadLatestBtn').click()
        b.wait_for_function("document.querySelector('#projectName').value==='Newer saved version'")
        check(b.locator('#projectName').input_value()=='Newer saved version','explicit Load latest adopts the reviewed current draft')
        b.screenshot(path=str(OUTPUT/'publication-conflict-desktop.png'),full_page=True)

        # Exercise both actual scripts together: the existing review guard creates
        # the required confirmation; the new save handler preserves input on409.
        page=browser.new_page(viewport={'width':390,'height':844},service_workers='block')
        page.route('**/*',lambda route:route.abort());page.on('pageerror',lambda error:errors.append(str(error)))
        html='''<html><head><base href="https://kcmc-fixture.invalid/"></head><body><form data-publishing-form method="post" action="/admin/save.php"><input name="csrf" type="hidden" value="fixture"><input name="version" type="hidden" value="VERSION"><label>Message<textarea name="announcement_body">Original words</textarea></label><button type="submit">Publish changes</button></form><p data-publishing-save-status role="status"></p><a data-publishing-latest hidden target="_blank" rel="noopener" href="/admin/">Open latest</a></body></html>'''.replace('VERSION','a'*64)
        page.set_content(html)
        page.evaluate("() => {window.fetch=async()=>({status:409,ok:false,json:async()=>({ok:false,error:'Content changed. Your edits are still here.'})});}")
        page.add_script_tag(content=(APP/'admin/event-descriptions.js').read_text())
        page.add_script_tag(content=(APP/'admin/publishing-desk.js').read_text())
        check(page.locator('[name=confirm_publish]').count()==1,'existing review script supplies exactly one publication confirmation')
        page.locator('[name=announcement_body]').fill('My unlost phone draft')
        page.locator('[name=confirm_publish]').check();page.locator('button[type=submit]').click()
        page.wait_for_function("document.querySelector('[data-publishing-save-status]').textContent.includes('still here')")
        check(page.locator('[name=announcement_body]').input_value()=='My unlost phone draft','actual review/save scripts keep the phone form input after a publishing conflict')
        check(page.locator('[data-publishing-latest]').is_visible(),'comparison opens separately without replacing the current form')
        page.screenshot(path=str(OUTPUT/'publishing-conflict-phone.png'),full_page=True)
        # Render the real authorized compact hub with isolated PHP accounts,
        # then inspect its actual public styles without any hosting requests.
        account_spec=importlib.util.spec_from_file_location('account_fixture',ROOT/'tests/member-account-routes.py')
        accounts=importlib.util.module_from_spec(account_spec);account_spec.loader.exec_module(accounts)
        fixture=accounts.Fixture(APP)
        try:
            status,hub=fixture.route('admin/home.php','owner');check(status==200,'real owner hub renders for the browser fixture')
            for width in [390,1365]:
                hubpage=browser.new_page(viewport={'width':width,'height':900},service_workers='block')
                def hub_asset(route):
                    path=urlparse(route.request.url).path
                    if path in ['/app/styles.css','/app/app-theme.css']:route.fulfill(status=200,content_type='text/css',body=(APP/path.removeprefix('/app/')).read_text())
                    else:route.abort()
                hubpage.route('**/*',hub_asset)
                hubpage.set_content(hub.replace('<head>','<head><base href="https://kcmc-fixture.invalid/">',1))
                check(hubpage.evaluate('document.documentElement.scrollWidth <= innerWidth'),'grouped hub fits viewport '+str(width))
                check(hubpage.locator('.admin-group').count()==3,'compact owner hub has three authorized groups')
                if width==1365:check(hubpage.evaluate('document.documentElement.scrollHeight < 1100'),'desktop hub avoids the previous wall of tall tool cards')
                hubpage.locator('[data-kcmc-back]').focus();hubpage.keyboard.press('Tab')
                check(hubpage.get_by_role('navigation',name='Page controls').get_by_role('link',name='Home',exact=True).evaluate('(el)=>el===document.activeElement'),'Home is reachable by keyboard after Back')
                hubpage.screenshot(path=str(OUTPUT/('administration-'+str(width)+'.png')),full_page=True);hubpage.close()
        finally:fixture.close()
        check(not errors,'offline browser has no uncaught client errors')
        browser.close()


if __name__=='__main__':main()
