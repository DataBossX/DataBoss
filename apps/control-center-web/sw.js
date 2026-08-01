/* Service worker: installability plus an offline-safe READ view.
 *
 * Deliberate limits:
 *  - Only the app shell is precached. Control-plane responses are never cached,
 *    because a stale posture that looks live is worse than no posture at all.
 *  - API GETs fall back to a clearly-labelled stale response only when offline,
 *    and the client shows it as an error rather than as truth.
 *  - No POST is ever queued for replay. Replaying a consequential action after
 *    a reconnect would defeat the approval and fencing model.
 */
'use strict';

const CACHE = 'dbx-cc-shell-v1';
const SHELL = [
  '/',
  '/static/app.css',
  '/static/app.js',
  '/manifest.webmanifest',
  '/icons/icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;             // never intercept state changes

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;  // same-origin only

  if (url.pathname.startsWith('/api/')) {
    // Network-first, and an offline miss is an explicit error payload rather
    // than a silently stale success.
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({
            error: 'OFFLINE',
            message: 'Offline. Control-plane state is not available and is never served stale.',
          }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) =>
      cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      }).catch(() => caches.match('/'))
    )
  );
});
