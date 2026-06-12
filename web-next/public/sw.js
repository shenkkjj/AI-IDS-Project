/* AI-CyberSentinel service worker — minimal offline cache for static assets.
 *
 * Strategy:
 *   - Pre-cache the app shell on install.
 *   - Network-first for `/api/*` (the data is never safe to serve stale).
 *   - Cache-first for static assets (Next.js chunks, fonts, icons).
 *   - On install, take over from any previous service worker immediately.
 */
const CACHE_VERSION = "v1";
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const SHELL = ["/", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== STATIC_CACHE).map((key) => caches.delete(key)),
      ),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws")) {
    // Always go to the network for live data; fall back to cache only when
    // the network is unreachable AND we already have a cached response.
    event.respondWith(
      fetch(request).catch(() => caches.match(request)),
    );
    return;
  }

  // Static assets: cache-first.
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok && (url.origin === self.location.origin)) {
        const copy = response.clone();
        caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
      }
      return response;
    })),
  );
});
