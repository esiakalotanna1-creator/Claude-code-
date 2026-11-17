/* Loading screen: the #loader overlay lives in index.html so it shows while the CDN libraries download;
 * run() then preloads every picture the game uses and fades the overlay out once they are in. */

// fraction shown on the bar: a small head start for the libraries already being loaded, never past 1
export function loadFraction(done, total) {
  if (!(total > 0)) return 1;
  return Math.min(1, 0.15 + 0.85 * Math.max(0, done) / total);
}

// waits for every url (failures count as done) or the timeout, reporting progress along the way
export function preloadImages(urls, onProgress, timeoutMs = 10000) {
  const list = [...new Set(urls.filter(Boolean))];
  let done = 0;
  onProgress(loadFraction(0, list.length));
  if (!list.length) return Promise.resolve();
  const each = list.map((u) => new Promise((res) => {
    const im = new Image(); im.crossOrigin = 'anonymous';
    const fin = () => { done++; onProgress(loadFraction(done, list.length)); res(); };
    im.onload = fin; im.onerror = fin; im.src = u;
  }));
  return Promise.race([Promise.all(each), new Promise((res) => setTimeout(res, timeoutMs))]);
}

let shownAt = Date.now(), hidden = false;
export function setLoaderProgress(f) {
  const bar = document.getElementById('ldbar'), pct = document.getElementById('ldpct');
  if (bar) bar.style.transform = 'scaleX(' + f + ')';
  if (pct) pct.textContent = Math.round(f * 100) + '%';
}
export function hideLoader(minMs = 700, onHide) {
  if (hidden) return; hidden = true;
  const el = document.getElementById('loader'); if (!el) return;
  setLoaderProgress(1);
  setTimeout(() => { el.classList.add('done'); if (onHide) try { onHide(); } catch (e) {} setTimeout(() => el.remove(), 500); }, Math.max(0, minMs - (Date.now() - shownAt)));
}
