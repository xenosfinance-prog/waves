// XenosFinance Service Worker v1.0
// Caches shell pages for offline access, sempre fetch live per prezzi e news

const CACHE_NAME = 'xenos-v1';
const SHELL_URLS = [
  '/',
  '/dashboard',
  '/trading-signals',
  '/elliottwave',
  '/calendar',
  '/XenosBlog',
  '/xenoswaves_charts',
  '/favicon.ico',
  '/favicon-192.png',
  '/favicon-32.png',
];

// Install — pre-cache shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(SHELL_URLS).catch(err => {
        console.warn('SW: some shell URLs failed to cache', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch strategy:
// - API calls (Worker, Yahoo, Finnhub) → always network, never cache
// - HTML pages → network first, fallback to cache
// - Static assets (fonts, icons) → cache first
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Never cache API/Worker calls
  if (
    url.hostname.includes('workers.dev') ||
    url.hostname.includes('tradingview') ||
    url.hostname.includes('telegram') ||
    url.hostname.includes('finnhub') ||
    url.hostname.includes('yahoo') ||
    url.hostname.includes('frankfurter') ||
    url.hostname.includes('coingecko') ||
    url.hostname.includes('googleapis') ||
    url.hostname.includes('gstatic.com') ||
    event.request.method !== 'GET'
  ) {
    return; // let browser handle normally
  }

  // HTML pages — network first, fallback to cache
  if (event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Static assets — cache first
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    })
  );
});
