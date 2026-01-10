// Stable scrolling helpers for iOS/Android WebView/Safari/Chrome.
// Goal: prevent scroll chaining / rubber-band ONLY when nothing can scroll further,
// and never block real scroll inside nested scroll areas (fixes "down ok, up stuck").
(function () {
  function isTouchable() {
    return 'ontouchstart' in window || (navigator.maxTouchPoints || 0) > 0;
  }

  function isMapTarget(node) {
    const el = node && node.nodeType === 1 ? node : (node && node.parentElement);
    if (!el || !el.closest) return false;
    return !!el.closest('#map, .leaflet-container');
  }

  function isScrollable(el) {
    if (!el || el === document.body || el === document.documentElement) return false;
    let oy = '';
    try {
      const st = window.getComputedStyle(el);
      oy = String(st.overflowY || '');
    } catch (_) {
      return false;
    }
    // "overlay" exists on some WebKit builds and behaves like "auto"
    if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') return false;
    const maxScroll = Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
    return maxScroll > 1;
  }

  function getScrollableChain(node) {
    if (isMapTarget(node)) return null;
    const chain = [];
    let el = node && node.nodeType === 1 ? node : (node && node.parentElement);
    while (el && el !== document.body && el !== document.documentElement) {
      if (el.id === 'map' || (el.classList && el.classList.contains('leaflet-container'))) return null;
      if (isScrollable(el)) chain.push(el);
      el = el.parentElement;
    }
    return chain.length ? chain : null;
  }

  function canScrollInDirection(el, dir) {
    const scrollTop = Number(el.scrollTop) || 0;
    const maxScroll = Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
    const eps = 1; // avoids fractional edge jitter on iOS
    if (dir === 'up') return scrollTop > eps;
    if (dir === 'down') return scrollTop < (maxScroll - eps);
    return false;
  }

  function initStableScroll() {
    if (!isTouchable()) return;

    let chain = null;
    let lastX = 0;
    let lastY = 0;
    let moved = false;

    document.addEventListener('touchstart', (e) => {
      if (!e.touches || e.touches.length !== 1) { chain = null; return; }
      const t = e.touches[0];
      lastX = t.clientX || 0;
      lastY = t.clientY || 0;
      moved = false;
      chain = getScrollableChain(e.target);
    }, { passive: true, capture: true });

    // Non-passive to allow edge prevention (iOS rubber-band / Android overscroll).
    document.addEventListener('touchmove', (e) => {
      if (!chain || !e.touches || e.touches.length !== 1) return;

      const t = e.touches[0];
      const x = t.clientX || 0;
      const y = t.clientY || 0;
      const dx = x - lastX;
      const dy = y - lastY;
      lastX = x;
      lastY = y;

      if (!moved && (Math.abs(dx) + Math.abs(dy)) < 2) return;
      moved = true;

      // Ignore mostly-horizontal gestures (carousels, horizontal lists)
      if (Math.abs(dx) > Math.abs(dy)) return;

      // dy > 0 => finger moved down => user scrolls UP (towards top)
      // dy < 0 => finger moved up   => user scrolls DOWN (towards bottom)
      const dir = dy > 0 ? 'up' : (dy < 0 ? 'down' : '');
      if (!dir) return;

      // If *any* scrollable in the chain can scroll further in that direction, do not block.
      for (let i = 0; i < chain.length; i++) {
        const el = chain[i];
        // layout can change while dragging; skip stale elements
        if (!el || !el.isConnected || !isScrollable(el)) continue;
        if (canScrollInDirection(el, dir)) return;
      }

      // Nothing can scroll further => prevent rubber-band/chaining to background
      e.preventDefault();
    }, { passive: false, capture: true });

    document.addEventListener('touchend', () => { chain = null; }, { passive: true, capture: true });
    document.addEventListener('touchcancel', () => { chain = null; }, { passive: true, capture: true });
  }

  document.addEventListener('DOMContentLoaded', initStableScroll, { once: true });
})();
