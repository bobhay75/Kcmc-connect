const CACHE='kcmc-connect-phase6-v2.1.3';
const CORE=[
  './','./styles.css','./app.js','./manifest.webmanifest',
  './bulletin.php','./news.php','./events.php','./care.php','./connect.php',
  './assets/icons/icon-192.png','./assets/icons/icon-512.png',
  './assets/newsletter/aug-2026-page-1.jpg','./assets/newsletter/aug-2026-page-2.jpg',
  './assets/newsletter/aug-2026-page-3.jpg','./assets/newsletter/aug-2026-page-4.jpg',
  './assets/newsletter/aug-2026-page-5.jpg',
  './assets/visuals/kcmc-ministry-group.jpg'
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
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET') return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then(response=>{
        if(response.ok){
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(event.request,copy));
        }
        return response;
      })
      .catch(()=>caches.match(event.request).then(cached=>cached||caches.match('./')))
  );
});
