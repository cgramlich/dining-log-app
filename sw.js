/* MenuCaptain service worker - OFFLINE PHASE 1 (app shell only).
   ===========================================================================
   Goal: the app reliably OPENS with a poor or missing connection, and is a
   real installable PWA. It deliberately does NOT cache user data or the map
   yet - those are later phases.

   The one rule that matters most: never trap a tester on a stale build.
   - The app document (index.html) is NETWORK-FIRST: online users always get
     the freshest file, so the in-app version checker keeps working untouched;
     the cached copy is only served when the network truly fails.
   - Cache names are tied to VERSION, and `activate` deletes every cache that
     does not match, so each deploy cleanly rolls the cache.
   - VERSION is bumped together with APP_VERSION in index.html, which changes
     this file's bytes and makes the browser install the new worker.

   Scope by request type:
   - app document          -> network-first, fall back to cached shell
   - version check (?vcheck=) -> NOT intercepted (always real network)
   - GET /api/collection/* -> network-first, fall back to cached data (PHASE 2:
                              makes saved lists/meta/splits + any collection
                              survive offline; PUT writes are never intercepted)
   - immutable assets (cdnjs libs, Google Fonts, our own images) -> cache-first
   - OSM map tiles -> cache-first into a size-capped cache (PHASE 4: maps you've
                      already viewed render offline). PASSIVE only - we never
                      pre-fetch areas, which would violate OSM's tile policy.
   - everything else (other API, list pages) -> default network
*/

const VERSION = "1.219.0";                 // keep in lockstep with APP_VERSION
const SHELL_CACHE = "mc-shell-" + VERSION;
const ASSET_CACHE = "mc-assets-" + VERSION;
const DATA_CACHE  = "mc-data-v1";           // user collections; UN-versioned so it
                                            // survives app updates (only a manual
                                            // clearCache / logout wipes it)
const TILE_CACHE  = "mc-tiles-v1";          // OSM tiles, UN-versioned, size-capped
const TILE_MAX    = 400;                     // ~400 tiles (~6-12MB); FIFO trim
const SHELL_URL   = "/";                    // canonical key for the app document

// Primed on install so even the very first offline open works.
const CRITICAL_ASSETS = [
  "https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.6/babel.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
  // Self-hosted fonts: primed so even a first offline open renders in-brand.
  "/fonts/fonts.css",
  "/fonts/f0.woff2", "/fonts/f1.woff2", "/fonts/f2.woff2", "/fonts/f3.woff2", "/fonts/f4.woff2",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    // Prime immutable assets - allSettled so a single CDN hiccup can't fail install.
    const assets = await caches.open(ASSET_CACHE);
    await Promise.allSettled(CRITICAL_ASSETS.map((u) => assets.add(u)));
    // Prime the app shell from the network (best-effort).
    try {
      const shell = await caches.open(SHELL_CACHE);
      const r = await fetch(SHELL_URL, { cache: "no-store" });
      if (r && r.ok) await shell.put(SHELL_URL, r.clone());
    } catch (e) { /* offline at install time - fine, fill on first online load */ }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== SHELL_CACHE && k !== ASSET_CACHE &&
                         k !== DATA_CACHE && k !== TILE_CACHE)
          .map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

// Lets the app force a full cache wipe (e.g. on a manual "Check for updates").
self.addEventListener("message", (event) => {
  const data = event.data;
  if (data === "clearCache" || (data && data.type === "clearCache")) {
    event.waitUntil((async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    })());
  }
});

function isImmutableAsset(url) {
  if (url.hostname === "cdnjs.cloudflare.com") return true;            // versioned libs
  if (url.hostname === "fonts.googleapis.com") return true;            // font css (legacy, no longer used)
  if (url.hostname === "fonts.gstatic.com") return true;              // font files (legacy, no longer used)
  if (url.origin === self.location.origin &&
      url.pathname.indexOf("/fonts/") === 0) return true;             // self-hosted font css + woff2
  if (url.origin === self.location.origin &&
      /\.(png|jpe?g|webp|gif|svg|ico|woff2?)$/i.test(url.pathname)) return true;  // our images/icons
  return false;
}

async function shellNetworkFirst(req) {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) cache.put(SHELL_URL, fresh.clone());       // store under canonical key (no ?query pollution)
    return fresh;
  } catch (e) {
    const cached = await cache.match(SHELL_URL);
    return cached || Response.error();
  }
}

// Network-first for user collections, with a short timeout so a flaky
// connection falls back to the last saved copy instead of hanging. Online
// always revalidates, so cached data is only a fallback - never stale-on-screen
// while connected.
async function dataNetworkFirst(req) {
  const cache = await caches.open(DATA_CACHE);
  const cached = await cache.match(req);
  try {
    // Only race the 5s timeout when we actually have a cached copy to fall back
    // to. With NO cache (e.g. first load on a cold Railway backend), abandoning
    // the request at 5s just produces an error - so wait for the real response.
    const fresh = cached
      ? await Promise.race([
          fetch(req),
          new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 5000)),
        ])
      : await fetch(req);
    if (fresh && fresh.ok) cache.put(req, fresh.clone());
    return fresh;
  } catch (e) {
    if (cached) return cached;
    throw e;                                  // no cache -> surface the real error to the app
  }
}

// Keep a cache from growing without bound: Cache Storage preserves insertion
// order, so deleting the first entries is a simple FIFO eviction.
async function trimCache(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  const over = keys.length - max;
  for (let i = 0; i < over; i++) await cache.delete(keys[i]);
}

// OSM tiles: cache-first (tiles change very rarely), bounded by TILE_MAX. Tiles
// are loaded by Leaflet <img> as no-cors, so responses are opaque - still fine
// to cache and serve back.
async function cacheTile(req) {
  const cache = await caches.open(TILE_CACHE);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const fresh = await fetch(req);
    if (fresh && (fresh.ok || fresh.type === "opaque")) {
      await cache.put(req, fresh.clone());
      trimCache(TILE_CACHE, TILE_MAX);      // fire-and-forget bound
    }
    return fresh;
  } catch (e) {
    return cached || Response.error();
  }
}

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const fresh = await fetch(req);
    if (fresh && (fresh.ok || fresh.type === "opaque")) cache.put(req, fresh.clone());
    return fresh;
  } catch (e) {
    return cached || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                                    // never cache writes
  let url;
  try { url = new URL(req.url); } catch (e) { return; }

  const isAppDoc = url.origin === self.location.origin &&
                   (url.pathname === "/" || url.pathname === "/index.html");

  // The app document: network-first. A navigation always counts; a plain
  // (query-less) GET of the doc counts too. The version check (?vcheck=) is a
  // query'd, non-navigation fetch, so it is excluded here and hits the network.
  if (isAppDoc && (req.mode === "navigate" || !url.search)) {
    event.respondWith(shellNetworkFirst(req));
    return;
  }

  // User collections (saved lists, meta, splits, and the core files) -> keep the
  // last good copy for offline reads. Only GETs reach here (writes returned above).
  if (url.pathname.indexOf("/api/collection/") !== -1) {
    event.respondWith(dataNetworkFirst(req));
    return;
  }

  // OSM map tiles -> cache-first, size-capped (passive offline maps).
  if (url.hostname === "tile.openstreetmap.org") {
    event.respondWith(cacheTile(req));
    return;
  }

  if (isImmutableAsset(url)) {
    event.respondWith(cacheFirst(req, ASSET_CACHE));
    return;
  }
  // Everything else (API calls, OSM tiles, per-list pages) -> default network.
});
