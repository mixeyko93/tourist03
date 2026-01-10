// Stable scrolling helpers for iOS/Android WebView/Safari/Chrome.
// Important: do NOT call preventDefault() on touchmove for single-finger scroll.
// That can cancel scrolling for the whole gesture and manifests as "stuck scroll",
// while two-finger scroll still works (because it bypasses our 1-touch logic).
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

  function nudgeFromEdges(el) {
    if (!el) return;
    const maxScroll = Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
    if (maxScroll <= 1) return;
    const top = Number(el.scrollTop) || 0;
    if (top <= 0) {
      el.scrollTop = 1;
      return;
    }
    if (top >= maxScroll) {
      el.scrollTop = maxScroll - 1;
    }
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

      // iOS overflow scroll edge-fix without preventDefault():
      // keep the nearest scrollable away from exact edges to avoid rubber-band / chain glitches.
      if (chain && chain[0]) {
        try { nudgeFromEdges(chain[0]); } catch (_) {}
      }
    }, { passive: true, capture: true });

    document.addEventListener('touchend', () => { chain = null; }, { passive: true, capture: true });
    document.addEventListener('touchcancel', () => { chain = null; }, { passive: true, capture: true });
  }

  document.addEventListener('DOMContentLoaded', initStableScroll, { once: true });
})();
