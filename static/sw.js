// reclmr Service Worker
const CACHE_NAME = 'reclmr-v379';

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
  e.waitUntil(self.clients.claim());
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

  // The page itself: never cached. Always straight from the server, so every start is the current version.
  if (e.request.mode === 'navigate' && url.pathname === '/') {
    // A hung connection used to hold the page for minutes (the browser's own time-out). Give each try a few seconds, then start a fresh one.
    e.respondWith((async () => {
      for (const ms of [4000, 4000, 15000]) {
        const ac = new AbortController(), t = setTimeout(() => ac.abort(), ms);
        try { const r = await fetch(e.request, { cache: 'no-store', signal: ac.signal }); clearTimeout(t); return r; } catch (_) { clearTimeout(t); }
      }
      return Response.error();
    })());
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
