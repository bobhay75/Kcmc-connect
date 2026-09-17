'use strict';
// Offline, dependency-free regression tests. No live accounts or messages are used.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const appSource=fs.readFileSync(process.env.KCMC_APP_SOURCE||path.join(root,'KCMC-Connect-Phase6-Recreated/app.js'),'utf8');
const swSource=fs.readFileSync(process.env.KCMC_SW_SOURCE||path.join(root,'KCMC-Connect-Phase6-Recreated/sw.js'),'utf8');
const PUBLIC_URL='https://bobsome1.com/kcmc-connect/';

function appHarness(options={}){
  const made=[],documentEvents={},windowEvents={},calls={share:[],copy:[],register:[]};
  let document;
  class Element{
    constructor(tag='div'){
      this.tagName=tag.toUpperCase();this.dataset={};this.style={};this.attributes={};
      this.children=[];this.events={};this.hidden=false;this.disabled=false;
      this.value='';this.textContent='';this.classList={add(){},remove(){},toggle(){}};
      made.push(this);
    }
    setAttribute(k,v){this.attributes[k]=String(v);}
    removeAttribute(k){delete this.attributes[k];}
    addEventListener(k,fn){this.events[k]=fn;}
    append(...children){this.children.push(...children);}
    insertAdjacentElement(position,element){assert.equal(position,'afterend');this.after=element;}
    querySelector(){return null;}
    querySelectorAll(){return [];}
    focus(){document.activeElement=this;}
    select(){this.selected=true;}
    async fire(type,event={}){return this.events[type]?.(event);}
  }
  const anchor=options.noHost?null:new Element();
  const preferred=new Element('select'),banner=new Element();
  document={
    body:{dataset:{officeEmail:'secretary@umckc.org'}},title:'KCMC',activeElement:null,
    documentElement:{classList:{add(){},remove(){}}},
    querySelector(selector){
      if(selector==='[data-install-callout]')return anchor;
      if(selector==='[data-public-share]')return made.find(e=>'publicShare'in e.dataset)||null;
      return null;
    },
    querySelectorAll(){return [];},
    getElementById(id){return id==='preferredService'?preferred:id==='offlineBanner'?banner:null;},
    createElement(tag){return new Element(tag);},
    addEventListener(type,fn){documentEvents[type]=fn;}
  };
  const navigator={userAgent:'test',platform:'test',maxTouchPoints:0,onLine:true,
    serviceWorker:{register:async(...args)=>calls.register.push(args)}};
  if(!options.noNative)navigator.share=async data=>{calls.share.push({...data});return options.share?.(data);};
  if(!options.noClipboard)navigator.clipboard={writeText:async text=>{calls.copy.push(text);return options.copy?.(text);}};
  const location={href:PUBLIC_URL+'?token=TEST_SECRET#private-request',hash:'#home'};
  const window={location,scrollTo(){},matchMedia:()=>({matches:!!options.standalone,addEventListener(){}}),addEventListener:(type,fn)=>{windowEvents[type]=fn;}};
  const localStorage={
    getItem(){if(options.blockStorage)throw new Error('blocked');return '';},
    setItem(){if(options.blockStorage)throw new Error('blocked');}
  };
  const context=vm.createContext({window,document,navigator,location,localStorage,URL,Blob,FormData,setTimeout,
    fetch:async()=>({ok:true,json:async()=>({announcements:[]})})});
  vm.runInContext(appSource,context);
  const byData=name=>made.find(e=>name in e.dataset);
  return {made,document,documentEvents,windowEvents,calls,navigator,anchor,preferred,byData,context};
}

test('app: loading performs no sharing or clipboard action',()=>{
  const h=appHarness();assert.ok(h.byData('shareApp'));assert.deepEqual(h.calls.share,[]);assert.deepEqual(h.calls.copy,[]);
});
test('app: native share contains only fixed public metadata, never current URL or page text',async()=>{
  const h=appHarness();h.document.title='PRIVATE PRAYER TEST_SECRET';
  h.context.location.href='https://bobsome1.com/kcmc-connect/member/first-login.php?code=TEST_SECRET#token';
  await h.byData('shareApp').fire('click');
  assert.equal(h.calls.share.length,1);assert.equal(h.calls.share[0].url,PUBLIC_URL);
  assert.equal(h.calls.share[0].title,'KCMC Connect');assert.doesNotMatch(JSON.stringify(h.calls.share),/TEST_SECRET|member\/|first-login|token|PRIVATE/);
  assert.deepEqual(h.calls.copy,[]);assert.equal(h.byData('shareApp').disabled,false);
});
test('app: missing native sharing exposes a labeled read-only URL; copying requires another click',async()=>{
  const h=appHarness({noNative:true});await h.byData('shareApp').fire('click');
  const field=h.byData('shareUrl');assert.equal(field.readOnly,true);assert.equal(field.value,PUBLIC_URL);
  assert.equal(h.byData('shareFallback').hidden,false);assert.equal(h.document.activeElement,field);
  assert.deepEqual(h.calls.copy,[]);field.value='TEST_SECRET';await h.byData('copyShareUrl').fire('click');
  assert.deepEqual(h.calls.copy,[PUBLIC_URL]);
});
test('app: canceling native sharing never copies or exposes fallback automatically',async()=>{
  const h=appHarness({share:()=>{throw {name:'AbortError'};}});await h.byData('shareApp').fire('click');
  assert.deepEqual(h.calls.copy,[]);assert.equal(h.byData('shareFallback').hidden,true);
  assert.match(h.byData('shareStatus').textContent,/closed/);assert.equal(h.byData('shareApp').disabled,false);
});
test('app: denied native sharing opens only manual fallback and does not print raw errors',async()=>{
  const h=appHarness({share:()=>{throw new Error('TEST_SECRET');}});await h.byData('shareApp').fire('click');
  assert.equal(h.byData('shareFallback').hidden,false);assert.deepEqual(h.calls.copy,[]);
  assert.doesNotMatch(h.byData('shareStatus').textContent,/TEST_SECRET/);
});
for(const unavailable of ['missing','denied'])test(`app: ${unavailable} clipboard has manual selection fallback`,async()=>{
  const h=appHarness({noNative:true,noClipboard:unavailable==='missing',copy:()=>{throw new Error('denied');}});
  await h.byData('shareApp').fire('click');await h.byData('copyShareUrl').fire('click');
  assert.equal(h.byData('shareUrl').selected,true);assert.match(h.byData('shareStatus').textContent,/manually/);
  assert.equal(h.byData('copyShareUrl').disabled,false);
});
test('app: overlapping share clicks open only one chooser',async()=>{
  let finish;const h=appHarness({share:()=>new Promise(resolve=>{finish=resolve;})});
  const first=h.byData('shareApp').fire('click');await h.byData('shareApp').fire('click');
  assert.equal(h.calls.share.length,1);finish();await first;assert.equal(h.byData('shareApp').disabled,false);
});
test('app: installed mode hides install callout but not public sharing',()=>{
  const h=appHarness({standalone:true});assert.equal(h.anchor.hidden,true);
  assert.equal(h.anchor.after,h.byData('publicShare'));assert.equal(h.byData('publicShare').hidden,false);
});
test('app: pages without the public home anchor get no sharing controls',()=>{
  const h=appHarness({noHost:true});assert.equal(h.byData('publicShare'),undefined);
});
test('app: Tab and Escape are safe on pages without an install dialog',()=>{
  const h=appHarness();assert.doesNotThrow(()=>h.documentEvents.keydown({key:'Tab'}));
  assert.doesNotThrow(()=>h.documentEvents.keydown({key:'Escape'}));
});
test('app: blocked preference storage does not stop service worker registration or sharing',async()=>{
  const h=appHarness({blockStorage:true});await h.preferred.fire('change');await h.windowEvents.load();
  assert.equal(h.calls.register.length,1);assert.ok(h.byData('shareApp'));
});
test('app: fallback field has an explicit label and status is announced accessibly',()=>{
  const h=appHarness(),status=h.byData('shareStatus');
  assert.ok(h.made.some(e=>e.tagName==='LABEL'&&e.htmlFor===h.byData('shareUrl').id));
  assert.equal(status.attributes.role,'status');assert.equal(status.attributes['aria-live'],'polite');
  assert.equal(h.byData('shareApp').attributes['aria-describedby'],status.id);
});

function swHarness(options={}){
  const listeners={},stores=new Map(),calls={fetch:[],put:[],match:[],deleted:[],skip:0,claim:0};
  const workerURL=PUBLIC_URL+'sw.js';
  const urlOf=input=>new URL(typeof input==='string'?input:input.url,workerURL).href;
  async function fetcher(input){
    const request=input instanceof Request?input:new Request(urlOf(input));calls.fetch.push(request);
    if(options.offline)throw new Error('offline');
    return options.response?options.response(request):new Response('public',{status:200});
  }
  async function open(name){
    if(!stores.has(name))stores.set(name,new Map());const store=stores.get(name);
    return {
      async put(request,response){const url=urlOf(request);store.set(url,response.clone());calls.put.push({name,url});},
      async add(request){const response=await fetcher(new Request(urlOf(request)));if(response.ok)await this.put(request,response);},
      async match(request,settings={}){
        const url=urlOf(request);calls.match.push({name,url,settings});
        for(const [key,response] of store){
          if(key===url||(settings.ignoreSearch&&key.split('?')[0]===url.split('?')[0]))return response.clone();
        }
        return undefined;
      }
    };
  }
  const caches={open,keys:async()=>[...stores.keys()],delete:async name=>{calls.deleted.push(name);return stores.delete(name);},
    async match(request,settings){for(const name of stores.keys()){const response=await (await open(name)).match(request,settings);if(response)return response;}}};
  const self={location:new URL(workerURL),clients:{claim:async()=>{calls.claim++;}},skipWaiting:async()=>{calls.skip++;},addEventListener:(type,fn)=>{listeners[type]=fn;}};
  const context=vm.createContext({self,caches,fetch:fetcher,URL,Request,Response});vm.runInContext(swSource,context);
  const cacheName=vm.runInContext('CACHE',context);
  async function lifecycle(type){let task;listeners[type]({waitUntil:p=>{task=p;}});await task;}
  async function dispatch(pathname,opts={}){
    const request=new Request(new URL(pathname,PUBLIC_URL),{method:opts.method||'GET',credentials:'include'});
    if(opts.navigate)Object.defineProperty(request,'mode',{value:'navigate'});
    let result;const jobs=[];listeners.fetch({request,respondWith:p=>{result=p;},waitUntil:p=>{jobs.push(p);}});
    if(!result)return {handled:false};const response=await result;await Promise.all(jobs);return {handled:true,response};
  }
  async function seed(name,relative,body='cached'){await (await open(name)).put(urlOf(relative),new Response(body));calls.put.length=0;}
  return {calls,stores,cacheName,lifecycle,dispatch,seed};
}

test('worker: precache requests omit credentials and reload from network',async()=>{
  const h=swHarness();await h.lifecycle('install');assert.ok(h.calls.fetch.length>0);
  assert.ok(h.calls.fetch.every(r=>r.credentials==='omit'&&r.cache==='reload'));
});
for(const policy of ['no-store','private, max-age=0','no-cache'])test(`worker: install never caches ${policy} responses`,async()=>{
  const h=swHarness({response:()=>new Response('PRIVATE',{headers:{'Cache-Control':policy}})});
  await h.lifecycle('install');assert.equal(h.calls.put.length,0);assert.equal(h.calls.skip,1);
});
test('worker: install never caches redirected responses',async()=>{
  const h=swHarness({response:()=>{const r=new Response('LOGIN');Object.defineProperty(r,'redirected',{value:true});return r;}});
  await h.lifecycle('install');assert.equal(h.calls.put.length,0);
});
test('worker: unavailable precache resources do not crash installation',async()=>{
  const h=swHarness({offline:true});await h.lifecycle('install');assert.equal(h.calls.put.length,0);assert.equal(h.calls.skip,1);
});
test('worker: runtime respects private response policy',async()=>{
  const h=swHarness({response:()=>new Response('PRIVATE',{headers:{'Cache-Control':'no-store, private'}})});
  const result=await h.dispatch('./');assert.equal(await result.response.text(),'PRIVATE');assert.equal(h.calls.put.length,0);
});
for(const route of ['member/','admin/backup.php','member/prayer-team.php','api/content.php','data/private/accounts.json','backups/sample.json','./?token=TEST_SECRET','index.php?code=TEST_SECRET','app.js?v=3&token=TEST_SECRET','../truth/']){
  test(`worker: ${route} never receives offline fallback`,async()=>{
    const h=swHarness({offline:true});await h.seed(h.cacheName,'./');await h.seed('other-project-cache',route,'PRIVATE');
    await assert.rejects(h.dispatch(route,{navigate:true}),/offline/);assert.equal(h.calls.match.length,0);
  });
}
test('worker: versioned asset offline lookup uses only current KCMC cache',async()=>{
  const h=swHarness({offline:true});await h.seed('other-project-cache','app.js?v=old','WRONG');
  await h.seed(h.cacheName,'app.js?v=3.0.0','EXPECTED');
  const result=await h.dispatch('app.js?v=3.0.1');assert.equal(await result.response.text(),'EXPECTED');
  assert.ok(h.calls.match.every(c=>c.name===h.cacheName));
});
test('worker: offline public navigation falls back only to current public home',async()=>{
  const h=swHarness({offline:true});await h.seed(h.cacheName,'./','PUBLIC HOME');
  const result=await h.dispatch('news.php',{navigate:true});assert.equal(await result.response.text(),'PUBLIC HOME');
  assert.ok(h.calls.match.every(c=>c.name===h.cacheName));
});
test('worker: runtime public response cache writes are awaited',async()=>{
  const h=swHarness();await h.dispatch('events.php');assert.equal(h.calls.put.length,1);
});
test('worker: non-GET and other origins are untouched',async()=>{
  const h=swHarness();assert.equal((await h.dispatch('./',{method:'POST'})).handled,false);
  assert.equal((await h.dispatch('https://example.org/')).handled,false);assert.equal(h.calls.fetch.length,0);
});
test('worker: activation removes old KCMC caches, preserving other projects',async()=>{
  const h=swHarness();await h.seed('kcmc-connect-v3.0.0-trunk-or-treat','./');await h.seed('project-unveiled-cache','./');await h.seed(h.cacheName,'./');
  await h.lifecycle('activate');assert.deepEqual(h.calls.deleted,['kcmc-connect-v3.0.0-trunk-or-treat']);
  assert.ok(h.stores.has('project-unveiled-cache'));assert.ok(h.stores.has(h.cacheName));assert.equal(h.calls.claim,1);
});
