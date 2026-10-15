'use strict';
// Runs the actual browser client in a minimal DOM, with synthetic API and clock.
// No dependencies, sockets, production requests or private data are used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SOURCE = fs.readFileSync(process.argv[2] || path.join(__dirname, '../KCMC-Connect-Phase6-Recreated/member/workspace.js'), 'utf8');
const ID = 'teamtask_' + 'a'.repeat(24), SECOND = 'teamtask_' + 'b'.repeat(24), PUB = 'pub_' + 'c'.repeat(24);
class Element {
  constructor(tag, doc) { this.tagName = tag.toUpperCase(); this.doc=doc; this.childNodes=[]; this.listeners={}; this.attrs={}; this.dataset={}; this._text=''; this.value=''; this.hidden=false; this.checked=false; this.disabled=false; }
  appendChild(child) { child.parentElement=this; this.childNodes.push(child); return child; }
  replaceChildren(...children) { this.childNodes=[]; this._text=''; children.forEach(c=>this.appendChild(c)); }
  set textContent(value) { this.childNodes=[]; this._text=String(value); }
  get textContent() { return this._text + this.childNodes.map(c=>c.textContent).join(''); }
  get options() { return this.childNodes; }
  set innerHTML(_) { throw new Error('Unsafe HTML insertion attempted'); }
  setAttribute(name,value) { this.attrs[name]=String(value); }
  getAttribute(name) { return this.attrs[name] ?? null; }
  addEventListener(name,fn) { (this.listeners[name] ||= []).push(fn); }
  dispatch(name) { for (const fn of this.listeners[name]||[]) fn.call(this,{type:name,target:this,preventDefault(){}}); }
  focus() { this.doc.activeElement=this; }
  reportValidity() { return true; }
  querySelectorAll(selector) {
    const match = selector==='[data-task-id]' ? e=>!!e.dataset.taskId : selector==='button[type=submit]' ? e=>e.tagName==='BUTTON' && e.type==='submit' : ()=>false;
    const result=[]; const walk=e=>{ for(const child of e.childNodes){if(match(child))result.push(child);walk(child);} };walk(this);return result;
  }
}
const tick = async () => { for(let i=0;i<12;i++) await new Promise(resolve=>setImmediate(resolve)); };
async function fixture(publisher=true) {
  const elements={}, document={hidden:false, listeners:{}, activeElement:null, getElementById:id=>elements[id], createElement(tag){return new Element(tag,document);},addEventListener(name,fn){(this.listeners[name]||=[]).push(fn);},dispatch(name){for(const fn of this.listeners[name]||[])fn();}};
  const ids=['workspace','work-preferences','work-editor','work-comment-form','work-notice','work-count','work-tasks','work-detail','work-no-selection','work-context-title','work-task-summary','work-edit','work-status','work-task-status','work-editor-heading','work-editor-note','work-replying','work-replying-label','work-comment-status','work-thread','work-thread-title','work-comments','work-thread-notice','work-new','work-publication-context','work-intro','work-publication-thread','work-preference-status','work-editor-close','work-status-form','work-reply-cancel'];
  for(const id of ids){elements[id]=new Element(id.endsWith('form') || ['work-preferences','work-editor'].includes(id)?'form':'div',document);elements[id].id=id;}
  for(const id of ['work-editor','work-detail','work-thread','work-new','work-edit','work-publication-context','work-replying'])elements[id].hidden=true;
  const forms={'work-preferences':['view','sort','statusfilter'],'work-editor':['title','body','assigned_to','start_date','due_date','priority','status','publication_id','blocked'],'work-comment-form':['body'],'work-status-form':['status']};
  for(const [id,names] of Object.entries(forms)) {
    const fields={};for(const name of names){fields[name]=name==='status'&&id==='work-status-form'?elements['work-status']:new Element(['view','sort','statusfilter','assigned_to','priority','status','publication_id'].includes(name)?'select':'input',document);fields[name].name=name;elements[id].appendChild(fields[name]);}
    elements[id].elements={namedItem:name=>fields[name]};
    const button=new Element('button',document);button.type='submit';elements[id].appendChild(button);
  }
  for(const [name,value] of Object.entries({view:'list',sort:'smart',statusfilter:'open'}))elements['work-preferences'].elements.namedItem(name).value=value;
  elements.workspace.dataset={api:'/api/team-workspace.php',csrf:'synthetic-csrf'};
  let now=0,timerId=0;const timers=new Map();
  const task=(id,values={})=>Object.assign({id,revision:1,title:'Prepare Sunday slides',body:'Approved words only',assigned_to:'alice',assignee_name:'Alice Example',start_date:'2026-10-15',due_date:'2026-10-18',priority:'high',status:'open',blocked:false,publication_id:'',created_at:1792000000,updated_at:1792000000,comment_count:0},values);
  const server={tasks:[task(ID),task(SECOND,{title:'Completed task',status:'done'})],comments:[],prefs:{revision:0,view:'list',sort:'smart',statusfilter:'all'},revision:1,calls:[],failures:{},conflict:false,active:0,maxActive:0,hold:'',release:null};
  const fetch=async(url,options={})=>{
    server.active++;server.maxActive=Math.max(server.maxActive,server.active);
    try {
      const data=options.body?JSON.parse(options.body):Object.fromEntries(new URL(url).searchParams);server.calls.push(structuredClone(data));
      if(server.hold===data.action){server.hold='';await new Promise(resolve=>{server.release=resolve;});}
      const failure=(server.failures[data.action]||[]).shift();
      if(failure)return{ok:false,status:failure,json:async()=>({ok:false,error:'<script>untrusted server detail</script>',code:'fixture'})};
      let result={ok:true};
      if(data.action==='list')result={...result,tasks:structuredClone(server.tasks),users:publisher?[{id:'alice',name:'Alice Example'}]:[],publications:publisher?[{id:PUB,name:'Sunday bulletin'}]:[],preferences:{...server.prefs},can_manage:publisher,actor_id:publisher?'owner':'alice',server_today:'2026-10-15',revision:server.revision};
      if(data.action==='thread')result={...result,context:{kind:data.kind,id:data.id,label:'Task'},comments:structuredClone(server.comments),revision:server.revision};
      if(data.action==='preferences'){server.prefs={revision:server.prefs.revision+1,...data.preferences};result.preferences={...server.prefs};}
      if(['update','create','status'].includes(data.action)){
        if(server.conflict){server.conflict=false;server.tasks[0].revision++;server.tasks[0].title='Latest remote title';server.revision++;return{ok:false,status:409,json:async()=>({ok:false,code:'revision_conflict'})};}
        let t=data.action==='create'?task('teamtask_'+'d'.repeat(24),data.task):server.tasks.find(t=>t.id===data.task_id);
        if(data.action!=='create'&&(!t||data.revision!==t.revision))return{ok:false,status:t?409:404,json:async()=>({ok:false,code:t?'revision_conflict':'not_found'})};
        if(data.action==='create')server.tasks.push(t);else{Object.assign(t,data.action==='status'?{status:data.status}:data.task);t.revision++;}
        server.revision++;result.task=structuredClone(t);
      }
      if(data.action==='comment'){const comment={id:'teamcomment_'+String(server.comments.length+1).padStart(24,'0'),body:data.body,parent_id:data.parent_id,author_id:'alice',author_name:'Alice Example',created_at:1792000000};server.comments.push(comment);server.revision++;result={...result,comment,duplicate:false};}
      return{ok:true,status:200,json:async()=>result};
    } finally{server.active--;}
  };
  const window={location:{href:'https://workspace.test/member/work.php'},crypto:{getRandomValues(array){for(let i=0;i<array.length;i++)array[i]=Math.floor(Math.random()*256);return array;}},setTimeout(fn,delay){const id=++timerId;timers.set(id,{at:now+delay,fn});return id;},clearTimeout(id){timers.delete(id);},listeners:{},addEventListener(name,fn){(this.listeners[name]||=[]).push(fn);}};
  vm.runInNewContext(SOURCE,{window,document,fetch,URL,AbortController,Uint8Array,Map,Date,Number,Math,Promise,Array,JSON,Object,String,console}, {filename:'workspace.js'});
  await tick();
  const field=(form,name)=>elements[form].elements.namedItem(name);
  const count=action=>server.calls.filter(c=>c.action===action).length;
  async function advance(amount){const target=now+amount;for(;;){const next=[...timers].filter(([,t])=>t.at<=target).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;now=next[1].at;timers.delete(next[0]);next[1].fn();await tick();}now=target;await tick();}
  async function select(id=ID){const button=elements['work-tasks'].querySelectorAll('[data-task-id]').find(b=>b.dataset.taskId===id);assert.ok(button,'task button exists');button.dispatch('click');await tick();}
  async function input(form,name,value,event='input'){const el=field(form,name);el.value=value;elements[form].dispatch(event);await tick();}
  async function submit(form){elements[form].dispatch('submit');await tick();}
  return {elements,document,window,server,field,count,advance,select,input,submit,tick};
}
async function main(){
  let f=await fixture(false);assert.equal(f.elements['work-new'].hidden,true);assert.equal(f.elements['work-publication-context'].hidden,true);await f.select();assert.equal(f.elements['work-edit'].hidden,true);
  await f.input('work-preferences','view','board','change');assert.equal(f.count('preferences'),0);assert.equal(f.elements['work-tasks'].childNodes[0].className,'work-board');
  await f.input('work-preferences','statusfilter','done','change');assert.equal(f.elements['work-tasks'].querySelectorAll('[data-task-id]').length,1);await f.submit('work-preferences');assert.equal(f.server.prefs.view,'board');assert.equal(f.server.prefs.statusfilter,'done');
  await f.input('work-preferences','view','timeline','change');assert.equal(f.elements['work-tasks'].childNodes[0].className,'work-schedule');
  f=await fixture();f.server.tasks[0].title='<script>task()</script>';f.server.comments=[{id:'teamcomment_'+'e'.repeat(24),body:'<img src=x onerror=bad()>',parent_id:'',author_id:'alice',author_name:'<svg>name</svg>',created_at:1792000000}];await f.advance(10000);await f.select();assert.ok(f.elements['work-context-title'].textContent.includes('<script>'));assert.ok(f.elements['work-comments'].textContent.includes('<img'));assert.equal(f.elements['work-comments'].querySelectorAll('img').length,0);
  await f.input('work-comment-form','body','Task draft');f.elements['work-publication-thread'].value=PUB;f.elements['work-publication-thread'].dispatch('change');await f.tick();assert.equal(f.field('work-comment-form','body').value,'');await f.input('work-comment-form','body','Publication draft');await f.select();assert.equal(f.field('work-comment-form','body').value,'Task draft');
  f.server.failures.comment=[503];await f.submit('work-comment-form');assert.equal(f.field('work-comment-form','body').value,'Task draft');assert.ok(f.elements['work-comment-status'].textContent.includes('draft is kept'));const nonce=f.server.calls.find(c=>c.action==='comment').nonce;await f.submit('work-comment-form');assert.equal(f.server.calls.filter(c=>c.action==='comment').at(-1).nonce,nonce);assert.equal(f.field('work-comment-form','body').value,'');
  f=await fixture();await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Exact draft');await f.input('work-editor','body','Exact body');f.server.conflict=true;await f.submit('work-editor');assert.equal(f.field('work-editor','title').value,'Exact draft');assert.equal(f.field('work-editor','body').value,'Exact body');assert.equal(f.elements['work-context-title'].textContent,'Latest remote title');assert.ok(f.elements['work-editor-note'].textContent.includes('your draft below is unchanged'));assert.equal(f.count('update'),1);await f.submit('work-editor');assert.equal(f.server.calls.filter(c=>c.action==='update').at(-1).revision,2);assert.equal(f.server.tasks[0].title,'Exact draft');
  f=await fixture();await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Unsaved words');await f.input('work-comment-form','body','Unsent comment');f.elements['work-status'].value='in_progress';f.elements['work-status'].dispatch('change');f.elements['work-status'].focus();f.server.tasks[0].title='Remote update';f.server.tasks[0].revision=2;f.server.revision++;await f.advance(10000);assert.equal(f.elements['work-context-title'].textContent,'Remote update');assert.equal(f.field('work-editor','title').value,'Unsaved words');assert.equal(f.field('work-comment-form','body').value,'Unsent comment');assert.equal(f.elements['work-status'].value,'in_progress');assert.equal(f.document.activeElement.id,'work-status');
  let before=f.count('list');f.document.hidden=true;f.document.dispatch('visibilitychange');await f.advance(60000);assert.equal(f.count('list'),before);f.server.hold='list';f.document.hidden=false;f.document.dispatch('visibilitychange');await f.tick();assert.ok(f.server.release);await f.advance(60000);assert.equal(f.server.maxActive,1);f.server.release();await f.tick();
  f.server.failures.list=[503];before=f.count('list');await f.advance(10000);assert.equal(f.count('list'),before+1);await f.advance(10000);assert.equal(f.count('list'),before+1);await f.advance(10000);assert.equal(f.count('list'),before+2);
  f.server.failures.list=[401];await f.advance(10000);assert.ok(f.elements['work-notice'].textContent.includes('Your session ended'));before=f.count('list');await f.advance(120000);assert.equal(f.count('list'),before);assert.equal(f.field('work-editor','title').value,'Unsaved words');assert.equal(f.field('work-comment-form','body').value,'Unsent comment');
  f=await fixture(false);await f.select();await f.input('work-comment-form','body','Removed task draft');f.server.tasks=[f.server.tasks[1]];f.server.revision++;await f.advance(10000);assert.equal(f.elements['work-detail'].hidden,true);assert.equal(f.elements['work-thread'].hidden,true);assert.ok(f.elements['work-notice'].textContent.includes('no longer available'));
  // An edit made during a successful save is preserved instead of erased.
  f=await fixture();await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Saved version');f.server.hold='update';f.elements['work-editor'].dispatch('submit');await f.tick();await f.input('work-editor','title','Newer unsaved words');f.server.release();await f.tick();f.elements['work-edit'].dispatch('click');assert.equal(f.field('work-editor','title').value,'Newer unsaved words');
  // Edits made after a failed/uncertain comment use a new idempotency nonce.
  f=await fixture(false);await f.select();await f.input('work-comment-form','body','First words');f.server.failures.comment=[503];await f.submit('work-comment-form');const old=f.server.calls.filter(c=>c.action==='comment').at(-1).nonce;await f.input('work-comment-form','body','Changed words');await f.submit('work-comment-form');assert.notEqual(f.server.calls.filter(c=>c.action==='comment').at(-1).nonce,old);
  // Saving a new task must carry any newer edits forward onto that created task.
  f=await fixture();f.elements['work-new'].dispatch('click');await f.input('work-editor','title','Initial new task');f.server.hold='create';f.elements['work-editor'].dispatch('submit');await f.tick();await f.input('work-editor','title','Newer new-task draft');f.server.release();await f.tick();f.elements['work-edit'].dispatch('click');assert.equal(f.field('work-editor','title').value,'Newer new-task draft');assert.equal(f.server.tasks.at(-1).title,'Initial new task');
  // Changing choices during an explicit save must remain visibly unsaved.
  f=await fixture();await f.input('work-preferences','view','board','change');f.server.hold='preferences';f.elements['work-preferences'].dispatch('submit');await f.tick();await f.input('work-preferences','view','timeline','change');f.server.release();await f.tick();assert.equal(f.server.prefs.view,'board');assert.equal(f.field('work-preferences','view').value,'timeline');assert.ok(f.elements['work-preference-status'].textContent.includes('newer choices are not saved'));
  // Server/network errors do not expose raw details or erase an editor form.
  f=await fixture();await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Keep this form');f.server.failures.update=[503];await f.submit('work-editor');assert.equal(f.field('work-editor','title').value,'Keep this form');assert.ok(f.elements['work-editor-note'].textContent.includes('draft is kept'));assert.ok(!f.elements['work-editor-note'].textContent.includes('<script>'));
  // A queued save keeps A's loaded revision even if B becomes the open editor
  // before the preceding poll completes. Model real server-side CAS as well.
  f=await fixture();f.server.tasks[1].revision=7;f.server.revision++;await f.advance(10000);await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Stale A draft');f.server.hold='list';await f.advance(10000);assert.ok(f.server.release);f.elements['work-editor'].dispatch('submit');await f.tick();await f.select(SECOND);f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Untouched B draft');f.server.tasks[0].revision=7;f.server.tasks[0].title='Unseen remote A';f.server.revision++;f.server.release();await f.tick();
  assert.equal(f.server.calls.filter(c=>c.action==='update').at(-1).revision,1,'A must send its captured revision, never B revision7');assert.equal(f.server.tasks[0].title,'Unseen remote A','stale A cannot overwrite unseen server work');assert.equal(f.field('work-editor','title').value,'Untouched B draft');assert.equal(f.elements['work-editor-note'].textContent,'');await f.submit('work-editor');assert.equal(f.server.calls.filter(c=>c.action==='update').at(-1).revision,7,'A background conflict cannot change B editor revision');
  // Success for A must retain its newer keyed draft and leave B's current form
  // and context alone, even though B was opened before A's response arrived.
  f=await fixture();await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Saved A snapshot');f.server.hold='update';f.elements['work-editor'].dispatch('submit');await f.tick();await f.input('work-editor','title','Newer A draft');await f.select(SECOND);f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','B stays open');f.server.release();await f.tick();assert.equal(f.field('work-editor','title').value,'B stays open');assert.equal(f.elements['work-context-title'].textContent,'Completed task');assert.equal(f.elements['work-editor'].hidden,false);await f.select(ID);f.elements['work-edit'].dispatch('click');assert.equal(f.field('work-editor','title').value,'Newer A draft');await f.submit('work-editor');assert.equal(f.server.calls.filter(c=>c.action==='update').at(-1).revision,2);await f.select(SECOND);f.elements['work-edit'].dispatch('click');assert.equal(f.field('work-editor','title').value,'B stays open');
  // A background409 records a conflict on A's draft; it never rebases B. Opening
  // A again presents its latest details above the unchanged draft for review.
  f=await fixture();f.server.tasks[1].revision=7;f.server.revision++;await f.advance(10000);await f.select();f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Conflict A draft');f.server.hold='update';f.elements['work-editor'].dispatch('submit');await f.tick();await f.select(SECOND);f.elements['work-edit'].dispatch('click');await f.input('work-editor','title','Conflict must not touch B');f.server.conflict=true;f.server.release();await f.tick();assert.equal(f.field('work-editor','title').value,'Conflict must not touch B');assert.equal(f.elements['work-editor-note'].textContent,'');await f.submit('work-editor');assert.equal(f.server.calls.filter(c=>c.action==='update').at(-1).revision,7);await f.select(ID);f.elements['work-edit'].dispatch('click');assert.equal(f.field('work-editor','title').value,'Conflict A draft');assert.equal(f.elements['work-context-title'].textContent,'Latest remote title');assert.ok(f.elements['work-editor-note'].textContent.includes('Review both'));await f.submit('work-editor');assert.equal(f.server.calls.filter(c=>c.action==='update').at(-1).revision,2);
  // A status response cannot reset a newer status choice in another task.
  f=await fixture(false);await f.select();f.elements['work-status'].value='in_progress';f.elements['work-status'].dispatch('change');f.server.hold='status';f.elements['work-status-form'].dispatch('submit');await f.tick();await f.select(SECOND);f.elements['work-status'].value='open';f.elements['work-status'].dispatch('change');f.server.release();await f.tick();assert.equal(f.elements['work-status'].value,'open','A response must not reset B unsaved choice to done');assert.equal(f.elements['work-task-status'].textContent,'');await f.submit('work-status-form');assert.equal(f.server.tasks.find(t=>t.id===SECOND).status,'open');
  // Newer choices on A itself also remain unsaved until their own explicit save.
  f=await fixture(false);await f.select();f.elements['work-status'].value='in_progress';f.elements['work-status'].dispatch('change');f.server.hold='status';f.elements['work-status-form'].dispatch('submit');await f.tick();f.elements['work-status'].value='done';f.elements['work-status'].dispatch('change');f.server.release();await f.tick();assert.equal(f.elements['work-status'].value,'done');assert.equal(f.server.tasks[0].status,'in_progress');assert.ok(f.elements['work-task-status'].textContent.includes('newer choice is not saved'));await f.submit('work-status-form');assert.equal(f.server.calls.filter(c=>c.action==='status').at(-1).revision,2);assert.equal(f.server.tasks[0].status,'done');
  console.log('PASS: 17 actual-client VM scenarios, including captured revisions across queued refreshes, keyed draft/revision handling across context switches and preserved same/other-task status choices.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
