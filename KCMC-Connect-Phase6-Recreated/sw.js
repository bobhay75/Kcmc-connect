const CACHE='kcmc-connect-phase6-v2.0.0';
const CORE=['./','./index.html','./styles.css','./app.js','./manifest.webmanifest','./assets/icons/icon-192.png','./assets/icons/icon-512.png',
  '/bulletin', '/church-news', '/events', '/care', '/connect','./assets/newsletter/aug-2026-page-1.jpg','./assets/newsletter/aug-2026-page-2.jpg','./assets/newsletter/aug-2026-page-3.jpg','./assets/newsletter/aug-2026-page-4.jpg','./assets/newsletter/aug-2026-page-5.jpg','./assets/newsletter/kcmc-church-news-august-2026.png','./assets/visuals/kcmc-vision-lake.png','./assets/visuals/kcmc-ministry-group.jpg','./assets/visuals/cross-over-lake.jpg','./assets/visuals/table-rock-bridge.jpg'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const url=new URL(e.request.url);
  if(url.origin!==location.origin)return;
  e.respondWith(caches.match(e.request).then(cached=>cached||fetch(e.request).then(resp=>{const copy=resp.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return resp}).catch(()=>caches.match('./index.html'))));
});
