const CACHE = 'jaguar-technologies-v1';
const ASSETS = ['/', '/assets/styles.css', '/assets/app.js', '/manifest.webmanifest', '/assets/icon.svg'];
self.addEventListener('install', (event) => event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS))));
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
