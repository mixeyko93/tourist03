// web/ui.js
// Оболочка мини-приложения: тема Telegram, плавность, анти-зум, фикс таббара, микровзаимодействия.
(function () {
  const isTG = !!(window.Telegram && window.Telegram.WebApp);

  // --- 1) Инициализация и синхронизация темы с Telegram ---
  try {
    if (isTG) {
      Telegram.WebApp.ready();
      // цвета шапки/фона берём из текущей темы Telegram
      Telegram.WebApp.setHeaderColor("bg_color");
      Telegram.WebApp.setBackgroundColor("secondary_bg_color");

      // Проставим data-theme для CSS, если пользователь сам не выбирал
      const cs = Telegram.WebApp.colorScheme; // 'light' | 'dark'
      document.documentElement.setAttribute('data-theme', cs === 'dark' ? 'dark' : 'light');
    }
  } catch (_) {}

  // --- 2) Фикс компоновки нижнего таббара (иконки/лейблы не «съезжают») ---
  (function fixTabbarLayout(){
    const tabs = document.querySelectorAll('.tabbar .tab');
    tabs.forEach(it => {
      it.style.minWidth = '0';
      it.style.flex = '1 1 0';
      it.style.display = it.style.display || 'flex';
      it.style.flexDirection = it.style.flexDirection || 'column';
      it.style.alignItems = it.style.alignItems || 'center';
      it.style.justifyContent = it.style.justifyContent || 'center';
    });
  })();

  // --- 3) Лёгкий «нажатие-эффект» (ощущение нативного приложения) ---
  const pressableSel = '.button, .tabbar .tab, button, .fab';
  document.addEventListener('pointerdown', (e) => {
    const t = e.target.closest(pressableSel);
    if (!t) return;
    t.style.transform = 'scale(0.97)';
    t.style.transition = 'transform .08s ease';
  });
  ['pointerup','pointercancel','pointerleave'].forEach(ev=>{
    document.addEventListener(ev, (e) => {
      const t = e.target.closest(pressableSel);
      if (!t) return;
      t.style.transform = '';
    });
  });

  // --- 4) Плавный визуальный отклик при переключении вкладок ---
  (function smoothTabSwitch(){
    const tabs = document.querySelectorAll('.tabbar .tab');
    tabs.forEach(tab=>{
      tab.addEventListener('click', ()=>{
        const active = document.querySelector('.tabbar .tab.active');
        if (active && active !== tab) active.classList.remove('active');
        tab.classList.add('active');
        document.body.classList.add('tab-transition');
        setTimeout(()=>document.body.classList.remove('tab-transition'), 250);
      });
    });
  })();

  // --- 5) Блок двойного «тап-зума» на iOS (дополнительно к мета-viewport) ---
  let lastTouch = 0;
  document.addEventListener('touchend', (e) => {
    const now = Date.now();
    if (now - lastTouch <= 280) {
      e.preventDefault();
    }
    lastTouch = now;
  }, { passive: false });

  // --- 6) Лёгкая тактильная отдача (если доступна в Telegram) ---
  if (isTG && Telegram.WebApp.HapticFeedback) {
    document.addEventListener('click', (e) => {
      const t = e.target.closest(pressableSel);
      if (!t) return;
      try { Telegram.WebApp.HapticFeedback.impactOccurred('light'); } catch(_) {}
    });
  }
})();

// Блок "резинки" WebView (pull-to-close) — ВАЖНО:
// не должен мешать скроллу внутри модалок/контейнеров (у нас document обычно не скроллится).
(function preventRubberBand(){
  const tg = window.Telegram && window.Telegram.WebApp;
  // Не Telegram — не нужно.
  if (!tg) return;
  // На новых клиентах Telegram используем нативное отключение свайпов (делается в app.js).
  if (typeof tg.disableVerticalSwipes === 'function') return;

  const root = document.scrollingElement;
  if (!root) return;

  const isDocScrollable = () => {
    const maxScroll = (root.scrollHeight || 0) - (root.clientHeight || 0);
    return maxScroll > 1;
  };
  // Если документ не скроллится — не вмешиваемся (иначе ломаем скролл внутренних контейнеров).
  if (!isDocScrollable()) return;

  let y = 0;
  document.addEventListener('touchstart', (e)=>{ y = e.touches?.[0]?.clientY || 0; }, {passive:true});
  document.addEventListener('touchmove', (e)=>{
    if (!isDocScrollable()) return;
    const dy = (e.touches?.[0]?.clientY || 0) - y;
    const atTop = (root.scrollTop || 0) <= 0;
    if (atTop && dy > 0) e.preventDefault();
  }, {passive:false});
})();
