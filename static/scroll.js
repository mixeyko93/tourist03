// Stable scrolling helpers for iOS/Android WebView/Safari/Chrome.
// Keeps scroll inside intended containers and prevents rubber-band scroll chaining.
(function () {
  function isTouchable() {
    return 'ontouchstart' in window || (navigator.maxTouchPoints || 0) > 0;
  }

  function enableStableOverflowScroll(container) {
    if (!container || container.__stableScroll) return;
    container.__stableScroll = true;

    let startX = 0;
    let startY = 0;

    container.addEventListener('touchstart', (e) => {
      if (!e.touches || e.touches.length !== 1) return;
      const t = e.touches[0];
      startX = t.clientX || 0;
      startY = t.clientY || 0;
    }, { passive: true });

    // Non-passive so we can prevent scroll chaining at edges.
    container.addEventListener('touchmove', (e) => {
      if (!e.touches || e.touches.length !== 1) return;
      const t = e.touches[0];
      const x = t.clientX || 0;
      const y = t.clientY || 0;
      const dx = x - startX;
      const dy = y - startY;

      // Ignore mostly-horizontal gestures (e.g. sliders)
      if (Math.abs(dx) > Math.abs(dy)) return;

      const el = container;
      const scrollTop = el.scrollTop || 0;
      const maxScroll = Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));

      // If container can't scroll, prevent background from moving.
      if (maxScroll <= 0) {
        e.preventDefault();
        return;
      }

      const atTop = scrollTop <= 0;
      const atBottom = scrollTop >= (maxScroll - 1);

      // dy > 0 => finger goes down => content should go up (scrollTop decreases)
      // dy < 0 => finger goes up => content should go down (scrollTop increases)
      if ((atTop && dy > 0) || (atBottom && dy < 0)) {
        e.preventDefault();
      }
    }, { passive: false });
  }

  function initStableScroll() {
    if (!isTouchable()) return;
    // Main scroll containers.
    const modalCard = document.getElementById('modalCard');
    if (modalCard) enableStableOverflowScroll(modalCard);

    const tabAccount = document.getElementById('tab-account');
    if (tabAccount) enableStableOverflowScroll(tabAccount);

    const tabServices = document.getElementById('tab-services');
    if (tabServices) enableStableOverflowScroll(tabServices);

    const tabHelp = document.getElementById('tab-help');
    if (tabHelp) enableStableOverflowScroll(tabHelp);
  }

  window.__enableStableOverflowScroll = enableStableOverflowScroll;
  document.addEventListener('DOMContentLoaded', initStableScroll, { once: true });
})();

