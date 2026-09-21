'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const root=path.resolve(__dirname,'..');
const swSource=fs.readFileSync(path.join(root,'KCMC-Connect-Phase6-Recreated/sw.js'),'utf8');
const PUBLIC_URL='https://bobsome1.com/kcmc-connect/';

function harness(options={}){
  const listeners={};
  const stores=new Map();
  const calls={fetch:[],put:[],match:[],deleted:[],skip:0,claim:0};
  const workerURL=PUBLIC_URL+'sw.js';
  const urlOf=input=>new URL(typeof input==='string'?input:input.url,workerURL).href;

  async function fetcher(input){
    const request=input instanceof Request?input:new Request(urlOf(input));
    calls.fetch.push(request);
    if(options.offline) throw new Error('offline');
    return options.response?options.response(request):new Response('public',{status:200});
  }

  async function open(name){
    if(!stores.has(name)) stores.set(name,new Map());
    const store=stores.get(name);
    return {
      async put(request,response){
        const url=urlOf(request);
        store.set(url,response.clone());
        calls.put.push({name,url});
      },
      async match(request,settings={}){
        const url=urlOf(request);
        calls.match.push({name,url,settings});
        for(const [key,response] of store){
          if(key===url||(settings.ignoreSearch&&key.split('?')[0]===url.split('?')[0])) return response.clone();
        }
        return undefined;
      }
    };
  }

  const caches={
    open,
    keys:async()=>[...stores.keys()],
    delete:async name=>{calls.deleted.push(name);return stores.delete(name);}
  };
  const self={
    location:new URL(workerURL),
    clients:{claim:async()=>{calls.claim++;}},
    skipWaiting:async()=>{calls.skip++;},
    addEventListener:(type,fn)=>{listeners[type]=fn;}
  };
  const context=vm.createContext({self,caches,fetch:fetcher,URL,Request,Response});
  vm.runInContext(swSource,context);
  const cacheName=vm.runInContext('CACHE',context);

  async function lifecycle(type){
    let task;
    listeners[type]({waitUntil:p=>{task=p;}});
    await task;
  }

  async function dispatch(relative,opts={}){
    const request=new Request(new URL(relative,PUBLIC_URL),{method:opts.method||'GET',credentials:'include'});
    if(opts.navigate) Object.defineProperty(request,'mode',{value:'navigate'});
    let responsePromise;
    const jobs=[];
    listeners.fetch({
      request,
      respondWith:p=>{responsePromise=p;},
      waitUntil:p=>{jobs.push(p);}
    });
    if(!responsePromise) return {handled:false};
    const response=await responsePromise;
    await Promise.all(jobs);
    return {handled:true,response};
  }

  async function seed(name,relative,body='cached'){
    const store=await open(name);
    await store.put(urlOf(relative),new Response(body));
    calls.put.length=0;
    calls.match.length=0;
  }

  return {calls,stores,cacheName,lifecycle,dispatch,seed};
}

test('precache fetches anonymously and reloads from network',async()=>{
  const h=harness();
  await h.lifecycle('install');
  assert.ok(h.calls.fetch.length>0);
  assert.ok(h.calls.fetch.every(request=>request.credentials==='omit'&&request.cache==='reload'));
});

for(const policy of ['no-store','private, max-age=0','no-cache']){
  test(`precache refuses ${policy} responses`,async()=>{
    const h=harness({response:()=>new Response('private',{headers:{'Cache-Control':policy}})});
    await h.lifecycle('install');
    assert.equal(h.calls.put.length,0);
    assert.equal(h.calls.skip,1);
  });
}

test('runtime refuses to cache a private public-route response',async()=>{
  const h=harness({response:()=>new Response('private',{headers:{'Cache-Control':'no-store, private'}})});
  const result=await h.dispatch('events.php');
  assert.equal(await result.response.text(),'private');
  assert.equal(h.calls.put.length,0);
});

for(const route of [
  'member/',
  'admin/backup.php',
  'api/content.php',
  'data/private/accounts.json',
  'backups/sample.json',
  './?token=TEST_SECRET',
  'index.php?code=TEST_SECRET',
  'app.js?v=3.0.1&token=TEST_SECRET',
  'unknown.php'
]){
  test(`${route} is network-only and receives no offline fallback`,async()=>{
    const h=harness({offline:true});
    await h.seed(h.cacheName,'./','PUBLIC HOME');
    await h.seed('other-project-cache',route,'PRIVATE');
    await assert.rejects(h.dispatch(route,{navigate:true}),/offline/);
    assert.equal(h.calls.match.length,0);
  });
}

test('versioned static asset offline lookup stays inside the current KCMC cache',async()=>{
  const h=harness({offline:true});
  await h.seed('other-project-cache','app.js?v=old','WRONG');
  await h.seed(h.cacheName,'app.js?v=3.0.1','EXPECTED');
  const result=await h.dispatch('app.js?v=3.0.2');
  assert.equal(await result.response.text(),'EXPECTED');
  assert.ok(h.calls.match.every(call=>call.name===h.cacheName));
});

test('offline public navigation falls back only to current public home',async()=>{
  const h=harness({offline:true});
  await h.seed(h.cacheName,'./','PUBLIC HOME');
  const result=await h.dispatch('news.php',{navigate:true});
  assert.equal(await result.response.text(),'PUBLIC HOME');
  assert.ok(h.calls.match.every(call=>call.name===h.cacheName));
});

test('successful public runtime response is cached and awaited',async()=>{
  const h=harness();
  await h.dispatch('events.php');
  assert.equal(h.calls.put.length,1);
});

test('non-GET and cross-origin requests are untouched',async()=>{
  const h=harness();
  assert.equal((await h.dispatch('./',{method:'POST'})).handled,false);
  assert.equal((await h.dispatch('https://example.org/')).handled,false);
  assert.equal(h.calls.fetch.length,0);
});

test('activation removes only old KCMC caches',async()=>{
  const h=harness();
  await h.seed('kcmc-connect-v3.0.1','./');
  await h.seed('project-unveiled-cache','./');
  await h.seed(h.cacheName,'./');
  await h.lifecycle('activate');
  assert.deepEqual(h.calls.deleted,['kcmc-connect-v3.0.1']);
  assert.ok(h.stores.has('project-unveiled-cache'));
  assert.ok(h.stores.has(h.cacheName));
  assert.equal(h.calls.claim,1);
});
