/* مركز شباب الحوراني — Service Worker
   Cache-first للـ static، network-first للصفحات مع صفحة offline كـ fallback. */
const VERSION = 'hourani-v7';
const STATIC_CACHE = `${VERSION}-static`;
const PAGE_CACHE = `${VERSION}-pages`;

const PRECACHE = [
  '/offline/',
  '/static/css/tailwind.css',
  '/static/css/tokens.css',
  '/static/css/app.css',
  '/static/css/forms.css',
  '/static/css/components.css',
  '/static/css/overrides.css',
  '/static/css/print.css',
  '/static/js/app.js',
  '/static/img/logo.png',
  '/static/img/favicon.png',
  '/static/icons/icon-192.png',
  '/static/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// API و لوحة التحكم: دائمًا الشبكة (لا caching) — و الفيديو كمان (حجمه كبير على ذاكرة الموبايل)
function bypass(url) {
  return url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/') || url.pathname.startsWith('/dashboard/') || url.pathname.startsWith('/i18n/')
    || url.pathname.endsWith('.mp4');
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (bypass(url)) return;

  // Static assets: cache first, ثم الشبكة
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
        }
        return response;
      }))
    );
    return;
  }

  // HTML pages: شبكة أولًا، fallback لـ cache وثم offline
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(PAGE_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          return cached || caches.match('/offline/');
        })
    );
  }
});
