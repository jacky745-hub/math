// 最小化 service worker：讓系統可「加入主畫面」成為 App；不快取動態頁面，確保分數永遠是最新的。
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {});
