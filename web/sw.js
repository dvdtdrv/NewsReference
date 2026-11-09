// Offline helper for the News Reference web app.
// Pages: always try the internet first (the news must be fresh); if there's no connection,
// show the last copy we saved. Icons and the manifest: kept from the first visit.
// Photos and fonts come from other websites and are left alone; so is the search index.

const CACHE = "news-reference-v3";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.includes("/pagefind/")) return;   // search index: always from the internet, not saved
  event.respondWith(
    // pages are always asked from the server again (cheap: an unchanged page answers "not modified"),
    // so a copy the browser kept for 10 minutes never shows an older design (9 Nov 2026)
    fetch(req, req.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname.endsWith("/") ? { cache: "no-cache" } : {})
      .then(res => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then(hit => hit || caches.match("./index.html")))
  );
});
