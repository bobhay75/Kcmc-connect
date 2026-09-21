const CACHE='kcmc-connect-v3.0.1';
const CORE=[
  './','./styles.css?v=3.0.1','./app.js?v=3.0.1','./manifest.webmanifest?v=3.0.1',
  './bulletin.php','./news.php','./events.php','./care.php','./connect.php',
  './assets/icons/icon-192.png','./assets/icons/icon-512.png',
  './assets/visuals/kimberling-city-missouri-bridge-2024.jpg',
  './assets/visuals/kcmc-ministry-group.jpg',
  './assets/visuals/trunk-or-treat-2026.webp'
];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>Promise.allSettled(CORE.map(url=>cache.add(url))))
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
  if(privateRoute){
    event.respondWith(fetch(event.request));
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then(response=>{
        const cacheControl=response.headers.get('Cache-Control')||'';
        const setsCookie=response.headers.has('Set-Cookie');
        if(response.ok&&!/no-store|private/i.test(cacheControl)&&!setsCookie){
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(event.request,copy));
        }
        return response;
      })
      .catch(()=>caches.match(event.request,{ignoreSearch:true}).then(cached=>cached||(event.request.mode==='navigate'?caches.match('./'):Response.error())))
  );
});
