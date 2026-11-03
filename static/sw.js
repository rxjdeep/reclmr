// reclmr Service Worker
const CACHE_NAME = 'reclmr-v339';

self.addEventListener('install', e => {
  self.skipWaiting(); // activate immediately
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      // Nuke ALL caches on every SW update. (No forced reload of open pages: fetches are network-first and
      // scripts carry ?v=, so the next open is fresh anyway, and a reload here made the app load twice.)
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  // an old page may have been shown from the old saved copy: tell it, so it can reload into the new version
  e.waitUntil(self.clients.claim().then(() => self.clients.matchAll({ type: 'window' })).then(cs => cs.forEach(cl => cl.postMessage({ t: 'shell-updated' }))));
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  // Never cache API responses (personal data; server sends no-store anyway)
  if (url.pathname.startsWith('/api/') || url.origin !== location.origin) return;

  // Files with ?v= never change under the same URL: serve them from the cache with no network round trip.
  if (url.pathname.startsWith('/static/') && url.searchParams.has('v')) {
    e.respondWith(caches.open(CACHE_NAME).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => {
      if (r.ok) c.put(e.request, r.clone());
      return r;
    }))));
    return;
  }

  // The page itself: show the saved copy at once, fetch the new one in the background. When it changed, the page is told
  // (it reloads straight away if it was only just opened and nothing is playing, otherwise on the next resume).
  if (e.request.mode === 'navigate' && url.pathname === '/') {
    e.respondWith(caches.open(CACHE_NAME).then(async c => {
      const hit = await c.match('/shell');
      const fresh = fetch(e.request).then(async r => {
        if (r.ok && r.type === 'basic') {
          const copy = r.clone(), text = await r.clone().text();
          const old = hit ? await hit.clone().text() : null;
          await c.put('/shell', copy);
          if (old !== null && old !== text) {
            const cs = await self.clients.matchAll({ type: 'window' });
            cs.forEach(cl => cl.postMessage({ t: 'shell-updated' }));
          }
        }
        return r;
      });
      if (hit) { e.waitUntil(fresh.catch(() => {})); return hit; }
      return fresh;
    }));
    return;
  }

  // Everything else: network first, the cache when offline - or when the network has not answered in 8 s (a stalled connection used to hold the page
  // for minutes, the browser's own time-out being that long, while a saved copy sat right here)
  e.respondWith(new Promise(resolve => {
    let done = false;
    const answer = r => { if (!done) { done = true; resolve(r); } };
    const slow = setTimeout(() => caches.match(e.request).then(hit => { if (hit) answer(hit); }), 8000);
    fetch(e.request).then(response => {
      clearTimeout(slow);
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
      }
      answer(response);
    }).catch(() => { clearTimeout(slow); caches.match(e.request).then(hit => answer(hit || Response.error())); });
  }));
});
