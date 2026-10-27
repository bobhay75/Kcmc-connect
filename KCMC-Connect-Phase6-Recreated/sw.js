const CACHE='kcmc-connect-basic-handoff-20261026';
// Connection-intake client refresh: worker install reruns cache:'reload' and overwrites cached app.js.
const CORE=[
  './','./home-welcome.css?v=20261023-bridge-gradient','./styles.css?v=3.0.3','./public-presentation.css?v=fish-only-home-20261014','./public-presentation.js?v=blue-fish-menu-20261009','./app.js?v=visitor-welcome-20261008','./manifest.webmanifest?v=20261019',
  './bulletin.php','./news.php','./events.php','./care.php','./connect.php',
  './assets/icons/icon-192.png','./assets/icons/icon-512.png',
  './assets/visuals/kcmc-bridge-logo-sunset-hero-20261023.webp','./assets/visuals/kcmc-building-retouched-20261009.jpg','./assets/visuals/kcmc-worship-2017.webp',
  './assets/visuals/trunk-or-treat-2026.svg',
  './assets/visuals/kcmc-congregation-gathering.jpg',
  './assets/visuals/kcmc-family-outdoor-event.jpg',
  './assets/visuals/kcmc-kids-safari.jpg',
  './assets/visuals/kcmc-kids-game-room.jpg',
  './assets/visuals/kcmc-kids-summer-group.jpg',
];
const PUBLIC_PATHS=new Set(CORE.map(path=>new URL(path,self.location.href).pathname));
PUBLIC_PATHS.add(new URL('./index.php',self.location.href).pathname);
const isAsset=url=>/\.(?:css|js|webmanifest|png|jpe?g|webp|svg)$/i.test(url.pathname);

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
  let request=event.request;
  let url=new URL(request.url);
  if(url.origin!==self.location.origin) return;
  // Older rendered pages may still request the photographed flyer. Serve the
  // illustration instead, online or offline, without caching the old image.
  if(url.pathname===new URL('./assets/visuals/trunk-or-treat-2026.webp',self.location.href).pathname&&!url.search){
    url=new URL('./assets/visuals/trunk-or-treat-2026.svg',self.location.href);
    request=new Request(url,{credentials:'omit'});
  }
  const privateRoute=/\/(?:member|admin)(?:\/|$)/.test(url.pathname);

  // Private, unknown, API/data/backup, and token-bearing URLs stay network-only.
  if(privateRoute||!cacheableRequest(url)){
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    fetch(request)
      .then(response=>{
        if(cacheableResponse(response)){
          const copy=response.clone();
          event.waitUntil(caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{}));
        }
        return response;
      })
      .catch(async()=>{
        try{
          const cache=await caches.open(CACHE);
          // Versioned static assets may ignore only their version query; pages never ignore query strings.
          const cached=await cache.match(request,isAsset(url)?{ignoreSearch:true}:{});
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
