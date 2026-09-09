const CACHE='essentials-marked-shell-v4';
const PREFIX='essentials-marked-';
const SHELL=['/','/classroom','/site.webmanifest','/favicon.svg'];
const fresh=request=>fetch(request,{cache:'reload'});
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(async cache=>{
  // Precache only the offline emergency shell. A deployment still asks the
  // network for current HTML and hashed assets first.
  await cache.addAll(['/','/site.webmanifest','/favicon.svg']);
  const response=await fresh('/classroom');
  if(response.ok){await cache.put('/classroom',response.clone());const html=await response.text();const assets=[...html.matchAll(/(?:src|href)="(\/assets\/[^"?]+)"/g)].map(match=>match[1]);if(assets.length)await cache.addAll([...new Set(assets)])}
}).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith(PREFIX)&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
 if(request.mode==='navigate'){
  event.respondWith(fresh(request).catch(()=>caches.match('/classroom')));
  return;
 }
 const staticRequest=['script','style','font','image','manifest'].includes(request.destination)||SHELL.includes(url.pathname);
 if(!staticRequest)return;
 // Network-first prevents scripts/styles staying indefinitely stale; cache is
 // retained only as the offline emergency fallback.
 event.respondWith(fresh(request).then(response=>{if(response.ok)caches.open(CACHE).then(cache=>cache.put(request,response.clone()));return response}).catch(()=>caches.match(request)));
});
