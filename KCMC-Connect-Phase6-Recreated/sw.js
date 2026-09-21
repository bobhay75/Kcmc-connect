const CACHE='kcmc-connect-v3.0.1-public-only';
const CORE=[
  './','./styles.css?v=3.0.1','./app.js?v=3.0.1','./manifest.webmanifest?v=3.0.1',
  './bulletin.php','./news.php','./events.php','./care.php','./connect.php',
  './assets/icons/icon-192.png','./assets/icons/icon-512.png',
  './assets/visuals/kimberling-city-missouri-bridge-2024.jpg',
  './assets/visuals/kcmc-ministry-group.jpg',
  './assets/visuals/trunk-or-treat-2026.webp'
];
const PUBLIC_PATHS=new Set(CORE.map(path=>new URL(path,self.location.href).pathname));
PUBLIC_PATHS.add(new URL('./index.php',self.location.href).pathname);
const isAsset=url=>/\.(?:css|js|webmanifest|png|jpe?g|webp)$/i.test(url.pathname);

function cacheableRequest(url){
  if(url.origin!==self.location.origin||!PUBLIC_PATHS.has(url.pathname)) return false;
  // Page query strings can contain access or invitation tokens. Only static asset version tags are cacheable.
  return !url.search||(isAsset(url)&&/^\?v=[A-Za-z0-9._-]+$/.test(url.search));
}

function cacheableResponse(response){
  const policy=response.headers.get('Cache-Control')||'';
  return response.status===200&&!response.redirected&&
    !/no-store|private|no-cache/i.test(policy)&&!response.headers.has('Set-Cookie');
}

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>Promise.allSettled(CORE.map(async path=>{
        // cache.add() ignores HTTP no-store. Fetch anonymously, then apply our response policy.
        const request=new Request(new URL(path,self.location.href),{credentials:'omit',cache:'reload'});
        const response=await fetch(request);
        if(cacheableResponse(response)) await cache.put(request,response);
      })))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key.startsWith('kcmc-connect-')&&key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET') return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin) return;
  const privateRoute=/\/(?:member|admin)(?:\/|$)/.test(url.pathname);

  // Private, unknown, API/data/backup, and token-bearing URLs stay network-only.
  if(privateRoute||!cacheableRequest(url)){
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response=>{
        if(cacheableResponse(response)){
          const copy=response.clone();
          event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)).catch(()=>{}));
        }
        return response;
      })
      .catch(async()=>{
        try{
          const cache=await caches.open(CACHE);
          // Versioned static assets may ignore only their version query; pages never ignore query strings.
          const cached=await cache.match(event.request,isAsset(url)?{ignoreSearch:true}:{});
          if(cached) return cached;
          if(event.request.mode==='navigate'){
            return (await cache.match(new URL('./',self.location.href).href))||Response.error();
          }
        }catch(_){
          // Storage may be blocked or full. Fail closed rather than searching unrelated caches.
        }
        return Response.error();
      })
  );
});
