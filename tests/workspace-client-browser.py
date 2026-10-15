#!/usr/bin/env python3
"""Offline browser checks of the real workspace client against a synthetic API.

Every request is intercepted. This intentionally tests UI behavior, not backend
authorization, real account access, hosting, delivery, payroll or private stores.
"""
import copy
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
HTML = (APP / 'member/work.php').read_text().split('<!doctype html>', 1)[1]
def php_value(match):
    body = match.group(0)
    path = re.search(r"kcmc_url\('([^']*)'\)", body)
    return '/'+path.group(1) if path else 'synthetic-csrf' if 'kcmc_csrf' in body else '/'
HTML = '<!doctype html>' + re.sub(r'<\?=.*?\?>', php_value, HTML, flags=re.S)

TASK_ID = 'teamtask_'+'a'*24
SECOND_ID = 'teamtask_'+'b'*24
PUB_ID = 'pub_'+'c'*24
def task(uid=TASK_ID, **values):
    result = dict(id=uid, revision=1, title='Prepare Sunday slides', body='Check the approved announcements.', assigned_to='alice', assignee_name='Alice Example', start_date='2026-10-15', due_date='2026-10-18', priority='high', status='open', blocked=False, created_at=1792000000, updated_at=1792000000, comment_count=0, publication_id='')
    result.update(values)
    return result

class SyntheticAPI:
    def __init__(self, page, publisher=True):
        self.page=page; self.publisher=publisher; self.tasks=[task(), task(SECOND_ID,title='Completed setup',status='done',priority='low')]
        self.preferences=dict(revision=0,view='list',sort='smart',statusfilter='all')
        self.comments=[]; self.calls=[]; self.failures={}; self.revision=1; self.conflict=False
        page.route('https://workspace.test/**', self.route)
    def route(self, route):
        request=route.request; parsed=urlparse(request.url)
        if parsed.path == '/member/work.php': return route.fulfill(status=200,content_type='text/html',body=HTML)
        if parsed.path.endswith('.js'): return route.fulfill(status=200,content_type='text/javascript',body=(APP/parsed.path.lstrip('/')).read_text())
        if parsed.path.endswith('.css'): return route.fulfill(status=200,content_type='text/css',body=(APP/parsed.path.lstrip('/')).read_text())
        if parsed.path != '/api/team-workspace.php': return route.fulfill(status=404,body='Not found')
        data=json.loads(request.post_data) if request.method=='POST' else {k:v[0] for k,v in parse_qs(parsed.query).items()}
        action=data.get('action'); self.calls.append(copy.deepcopy(data))
        failures=self.failures.get(action,[])
        if failures:
            status=failures.pop(0)
            return route.fulfill(status=status,content_type='application/json',body=json.dumps(dict(ok=False,error='<script>unsafe server details</script>',code='synthetic_failure')))
        result=dict(ok=True)
        if action=='list':
            tasks=copy.deepcopy(self.tasks)
            if not self.publisher:
                tasks=[t for t in tasks if t['assigned_to']=='alice']
                for t in tasks:t.pop('publication_id',None)
            result.update(tasks=tasks,users=[dict(id='alice',name='Alice Example'),dict(id='owner',name='Owner Example')] if self.publisher else [],publications=[dict(id=PUB_ID,name='Sunday bulletin')] if self.publisher else [],preferences=copy.deepcopy(self.preferences),can_manage=self.publisher,actor_id='owner' if self.publisher else 'alice',server_today='2026-10-15',revision=self.revision)
        elif action=='thread':result.update(context=dict(kind=data['kind'],id=data['id'],label='Task'),comments=copy.deepcopy(self.comments),revision=self.revision)
        elif action=='preferences':
            self.preferences=dict(revision=self.preferences['revision']+1,**data['preferences']);result['preferences']=copy.deepcopy(self.preferences)
        elif action in ['create','update','status']:
            if self.conflict:
                self.conflict=False;self.tasks[0]['revision']+=1;self.tasks[0]['title']='Latest task from another editor';self.revision+=1
                return route.fulfill(status=409,content_type='application/json',body=json.dumps(dict(ok=False,code='revision_conflict',error='Reload')))
            if action=='create':
                t=task('teamtask_'+'d'*24,**data['task']);self.tasks.append(t)
            else:
                t=next(t for t in self.tasks if t['id']==data['task_id'])
                t.update(data['task'] if action=='update' else {'status':data['status']});t['revision']+=1
            self.revision+=1;result['task']=copy.deepcopy(t)
        elif action=='comment':
            comment=dict(id='teamcomment_'+str(len(self.comments)+1).zfill(24),body=data['body'],parent_id=data['parent_id'],author_id='alice',author_name='Alice Example',created_at=1792000000)
            self.comments.append(comment);self.revision+=1;result.update(comment=comment,duplicate=False)
        return route.fulfill(status=200,content_type='application/json',body=json.dumps(result))
    def count(self, action):return sum(call['action']==action for call in self.calls)

INIT = r'''(() => {
  window.__hidden = false;
  Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.__hidden});
  const original = window.fetch;
  window.__active = 0; window.__maxActive = 0; window.__held = null; window.__holdAction = '';
  window.fetch = async function(url, options) {
    let action = options && options.body ? JSON.parse(options.body).action : new URL(url).searchParams.get('action');
    window.__active++; window.__maxActive = Math.max(window.__maxActive, window.__active);
    try {
      if (window.__holdAction === action) { window.__holdAction=''; await new Promise(resolve => { window.__held=resolve; }); }
      return await original(url, options);
    } finally {window.__active--;}
  };
})();'''

def ready(page):page.wait_for_function("document.getElementById('work-tasks').getAttribute('aria-busy') === 'false'")
def selected(page):page.locator('[data-task-id="'+TASK_ID+'"]').click();page.wait_for_function("document.getElementById('work-thread-notice').textContent !== 'Loading conversation…'")
def wait_text(page, selector, text):page.wait_for_function('(v) => document.querySelector(v[0]).textContent.includes(v[1])',arg=[selector,text])

def main():
    evidence=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('KCMC_TEST_CHROMIUM') or shutil.which('chromium') or p.chromium.executable_path,headless=True,args=['--no-sandbox'])
        def open_page(publisher=True,width=1280):
            page=browser.new_page(viewport=dict(width=width,height=900));page.add_init_script(INIT);page.clock.install()
            api=SyntheticAPI(page,publisher);page.goto('https://workspace.test/member/work.php');ready(page);return page,api
        # Actual forms, immediate local views and explicit preferences; no member manager controls.
        page,api=open_page(False)
        assert page.locator('#work-new').is_hidden() and page.locator('#work-publication-context').is_hidden()
        selected(page);assert page.locator('#work-edit').is_hidden() and page.locator('#work-editor').is_hidden()
        assert page.get_by_role('link',name='← My account').count()==1 and page.get_by_role('link',name='Home',exact=True).count()==1
        page.get_by_label('View',exact=True).select_option('board');assert page.locator('.work-board').count()==1 and api.count('preferences')==0
        page.get_by_label('Show',exact=True).select_option('done');assert page.locator('.work-task').count()==1
        page.get_by_role('button',name='Save choices').click();wait_text(page,'#work-preference-status','Choices saved');assert api.preferences['view']=='board' and api.preferences['statusfilter']=='done'
        page.get_by_label('View',exact=True).select_option('timeline');assert page.locator('.work-schedule').count()==1
        evidence.append('ordinary UI, immediate list/board/schedule/filter changes, explicit per-user preference save and Back/Home')
        page.close()
        # Plain-text rendering and context-preserved drafts across task/publication switches.
        page,api=open_page();api.tasks[0]['title']='<script>window.__xss=1</script>'
        api.comments=[dict(id='teamcomment_'+'e'*24,body='<img src=x onerror=window.__xss=1>',parent_id='',author_id='alice',author_name='<svg onload=window.__xss=1>',created_at=1792000000)]
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))");page.wait_for_function("document.querySelector('.work-task-title').textContent.startsWith('<script>')")
        selected(page);assert page.locator('#work-comments img,#work-comments svg').count()==0 and page.evaluate('window.__xss === undefined')
        page.get_by_label('Add a comment',exact=True).fill('Draft stays with this task')
        page.get_by_label('Publication conversation',exact=True).select_option(PUB_ID);page.wait_for_function("document.getElementById('work-thread-title').textContent.includes('Sunday bulletin')")
        assert page.get_by_label('Add a comment',exact=True).input_value()==''
        page.get_by_label('Add a comment',exact=True).fill('Publication draft')
        page.locator('[data-task-id="'+TASK_ID+'"]').click();assert page.get_by_label('Add a comment',exact=True).input_value()=='Draft stays with this task'
        api.failures['comment']=[503];page.get_by_role('button',name='Post comment',exact=True).click();wait_text(page,'#work-comment-status','draft is kept')
        assert page.get_by_label('Add a comment',exact=True).input_value()=='Draft stays with this task'
        first_nonce=next(c['nonce'] for c in api.calls if c['action']=='comment')
        page.get_by_role('button',name='Post comment',exact=True).click();wait_text(page,'#work-comment-status','Comment posted')
        assert [c for c in api.calls if c['action']=='comment'][-1]['nonce']==first_nonce
        assert page.get_by_label('Add a comment',exact=True).input_value()==''
        evidence.append('plain-text task/name/comment rendering, separate task/publication drafts, failed comment retention and stable retry nonce')
        page.close()
        # Publisher edit CAS conflict loads latest details while preserving the exact draft.
        page,api=open_page();selected(page);page.get_by_role('button',name='Edit task',exact=True).click()
        page.get_by_label('Title',exact=True).fill('My unchanged conflict draft');page.get_by_label('Details',exact=True).fill('My long draft details')
        api.conflict=True;page.get_by_role('button',name='Save task',exact=True).click();wait_text(page,'#work-editor-note','your draft below is unchanged')
        assert page.get_by_label('Title',exact=True).input_value()=='My unchanged conflict draft'
        assert page.get_by_label('Details',exact=True).input_value()=='My long draft details'
        assert page.locator('#work-context-title').inner_text()=='Latest task from another editor'
        assert api.count('update')==1
        page.get_by_role('button',name='Save task',exact=True).click();wait_text(page,'#work-notice','Task saved.')
        assert [c for c in api.calls if c['action']=='update'][-1]['revision']==2 and api.tasks[0]['title']=='My unchanged conflict draft'
        evidence.append('publisher recipient editor and task CAS conflict: latest detail, exact draft kept, explicit second save at latest revision')
        page.close()
        # Polling never overwrites dirty editor/comment/status, never overlaps, pauses hidden, backs off and stops on 401.
        page,api=open_page();selected(page);page.get_by_role('button',name='Edit task',exact=True).click()
        page.get_by_label('Title',exact=True).fill('Unsaved editor words');page.get_by_label('Add a comment',exact=True).fill('Unsaved conversation words')
        page.locator('#work-status').select_option('in_progress');api.tasks[0]['title']='Fresh remote task';api.tasks[0]['revision']=2;api.revision+=1
        page.clock.fast_forward(10000);page.wait_for_function("document.getElementById('work-context-title').textContent === 'Fresh remote task'")
        assert page.get_by_label('Title',exact=True).input_value()=='Unsaved editor words' and page.get_by_label('Add a comment',exact=True).input_value()=='Unsaved conversation words'
        assert page.locator('#work-status').input_value()=='in_progress'
        assert page.evaluate('document.activeElement.id')=='work-status'
        before=api.count('list');page.evaluate("window.__hidden=true;document.dispatchEvent(new Event('visibilitychange'))");page.clock.fast_forward(60000);page.wait_for_timeout(30);assert api.count('list')==before
        page.evaluate("window.__holdAction='list';window.__hidden=false;document.dispatchEvent(new Event('visibilitychange'))");page.wait_for_function('window.__held !== null');page.clock.fast_forward(60000)
        assert page.evaluate('window.__maxActive')==1
        page.evaluate('window.__held();window.__held=null');page.wait_for_function('window.__active === 0')
        api.failures['list']=[503];before=api.count('list');page.clock.fast_forward(10000);page.wait_for_function("document.getElementById('work-notice').textContent.includes('could not connect')");assert api.count('list')==before+1
        page.clock.fast_forward(10000);page.wait_for_timeout(30);assert api.count('list')==before+1
        page.clock.fast_forward(10000);page.wait_for_function('window.__active === 0');assert api.count('list')==before+2
        api.failures['list']=[401];page.clock.fast_forward(10000);wait_text(page,'#work-notice','Your session ended');before=api.count('list');page.clock.fast_forward(120000);page.wait_for_timeout(30);assert api.count('list')==before
        assert page.get_by_label('Title',exact=True).input_value()=='Unsaved editor words' and page.get_by_label('Add a comment',exact=True).input_value()=='Unsaved conversation words'
        evidence.append('10-second visible-only serialized polling, focus and dirty drafts/status kept, hidden pause, failure backoff and 401 stop')
        page.close()
        # A disappearing assignment closes the context but keeps an unsent draft out of new contexts.
        page,api=open_page(False);selected(page);page.get_by_label('Add a comment',exact=True).fill('Unsent private assignment draft')
        api.tasks=[api.tasks[1]];api.revision+=1;page.clock.fast_forward(10000);wait_text(page,'#work-notice','no longer available')
        assert page.locator('#work-detail').is_hidden() and page.locator('#work-thread').is_hidden()
        evidence.append('assignment removal closes former task/thread without showing old draft in another context')
        page.close()
        # Phone and desktop layout and keyboard reachability using the actual shell and styles.
        for width in [320,390,1365]:
            page,api=open_page(width=width);selected(page);page.get_by_role('button',name='Edit task',exact=True).click()
            page.get_by_label('View',exact=True).select_option('board')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
            page.get_by_role('link',name='Home',exact=True).focus();assert page.evaluate('document.activeElement.textContent')=='Home'
            out=os.environ.get('KCMC_WORKSPACE_SCREENSHOT')
            if out and width==390:page.screenshot(path=out,full_page=True)
            page.close()
        evidence.append('320/390/1365px layouts without horizontal page overflow and keyboard Home')
        browser.close()
    print(json.dumps(dict(result='PASS',synthetic_only=True,cases=evidence),indent=2))

if __name__=='__main__':main()
