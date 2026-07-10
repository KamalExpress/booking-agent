// Force the waiting service worker to become the active service worker.
self.addEventListener('install', function(event) {
    self.skipWaiting();
});

// Tell the active service worker to take control of the page immediately.
self.addEventListener('activate', function(event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function(event) {
    if (event.data) {
        const payload = event.data.json();
        const title = payload.title || "Slot Alert!";
        const options = {
            body: payload.body,
            icon: 'https://cdn-icons-png.flaticon.com/512/1043/1043444.png',
            vibrate: [200, 100, 200, 100, 200, 100, 200],
            data: { url: payload.url || '/' }
        };
        event.waitUntil(self.registration.showNotification(title, options));
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    if (event.notification.data.url) {
        event.waitUntil(clients.openWindow(event.notification.data.url));
    }
});

// A fetch handler is strictly required by Chromium to trigger the PWA install prompt.
self.addEventListener('fetch', function(event) {
    // We can just fall back to network for now.
    event.respondWith(fetch(event.request));
});
