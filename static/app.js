// === Tourist_03 • Telegram WebApp: анти-свайпы и защита от случайного закрытия ===
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  if (!tg) return;

  try { tg.expand(); } catch (_) {}

  // Если клиент Telegram поддерживает, полностью гасим «подтягивание шторки»
  try {
    if (typeof tg.disableVerticalSwipes === 'function') {
      tg.disableVerticalSwipes();
    }
  } catch (_) {}

  // Просим Telegram показывать системное подтверждение при попытке закрыть
  try { tg.enableClosingConfirmation(); } catch (_) {}
          // Подавляем показ тоста "Черновик сохранён" при техническом закрытии
          window.__suppressDraftToastOnce = true;

  // Подстраховка: если высота «схлопнулась», снова расширяем
  try {
    tg.onEvent && tg.onEvent('viewportChanged', () => {
      try { tg.expand(); } catch (_) {}
    });
  } catch (_) {}
})();   // ← вот это закрывает первую функцию!


// === Локальная защита: тапы/свайпы внутри балуна не «прокидываем» вверх к Телеграму ===
(function swallowPopupGestures(){
  const swallow = (e) => {
    if (e.target && e.target.closest && e.target.closest('.leaflet-popup')) {
      e.stopPropagation(); // даём Leaflet'у обработать, но не отдаём событие в Telegram
    }
  };
  document.addEventListener('touchstart', swallow, { capture: true, passive: true });
  document.addEventListener('touchmove',  swallow, { capture: true, passive: true });
})();


// ==== Telegram WebApp — полноэкранный режим ====
const isTG = !!(window.Telegram && window.Telegram.WebApp);
if (isTG) {
  Telegram.WebApp.ready();
    // включаем системное подтверждение закрытия после ready()
  try { Telegram.WebApp.enableClosingConfirmation(); } catch(_) {}
  const expand = () => Telegram.WebApp.expand();
  expand(); Telegram.WebApp.onEvent('viewportChanged', expand);
  document.addEventListener('click', expand, { once:true });
}

// --- Жёсткое авто-вытягивание при каждом фокусе/видимости (п.2)
if (isTG) {
  const forceExpand = () => { try { Telegram.WebApp.expand(); } catch(e){} };
  document.addEventListener('visibilitychange', ()=>{ if (!document.hidden) forceExpand(); });
  window.addEventListener('focus', forceExpand);
  setTimeout(forceExpand, 150);
}

// Быстрый рендер HTML
const h = (strings, ...vals) => strings.reduce((s, str, i) => s + str + (vals[i] ?? ''), '');

// --- мини-лоадер для коротких операций (детали базы) — БЕЗ текста, только крупные эмодзи ---
// Фишка: мы можем ПЕРЕХВАТИТЬ этот оверлей под модалку «Подробнее», не удаляя его (чтобы не мигала карта).
let __miniLoader = null, __miniLoaderTimer = null;

function showMiniLoader() {
  // если уже есть — просто перезапустим анимацию эмодзи
  if (__miniLoader) { startMiniEmojiLoop(); return; }

  __miniLoader = document.createElement('div');
  __miniLoader.className = 'modal show';           // перекрывает всё
  __miniLoader.id = 't03-mini-loader';

  // полностью прозрачная карточка, по центру только крупное эмодзи
  __miniLoader.innerHTML = `
    <div class="modal-card"
         style="background:transparent;border:none;box-shadow:none;padding:0;min-width:auto">
      <div style="
          display:flex;align-items:center;justify-content:center;
          width:120px;height:120px;margin:auto;
        ">
        <span id="miniEmoji" style="font-size:64px;line-height:1;">🏖️</span>
      </div>
    </div>`;
  document.body.appendChild(__miniLoader);
  startMiniEmojiLoop();
}

function startMiniEmojiLoop(){
  if (__miniLoaderTimer) clearInterval(__miniLoaderTimer);
  const list = ['🏖️','⛺','🏕️','🏔️','🌊','🚣‍♀️','🗺️','🌞','🌲','🔥'];
  let i = 0;
  __miniLoaderTimer = setInterval(() => {
    i = (i + 1) % list.length;
    const el = __miniLoader?.querySelector('#miniEmoji');
    if (el) el.textContent = list[i];
  }, 500);
}

// Перехват: отдаём наружу готовый .modal, НЕ удаляя узел (чтобы не было просвета карты)
function takeoverMiniLoaderAsModal(){
  if (!__miniLoader) return null;
  if (__miniLoaderTimer) clearInterval(__miniLoaderTimer);
  __miniLoaderTimer = null;

  // добавим плавное проявление для будущей модалки
  __miniLoader.style.opacity = '0';
  __miniLoader.style.transition = 'opacity .12s ease-out';
  const el = __miniLoader;

  // обнулим ссылку, но сам DOM-узел оставляем — его сразу наполнят контентом «Подробнее»
  __miniLoader = null;
  return el;
}

function hideMiniLoader() {
  if (__miniLoaderTimer) clearInterval(__miniLoaderTimer);
  __miniLoaderTimer = null;
  if (__miniLoader && __miniLoader.parentNode) __miniLoader.parentNode.removeChild(__miniLoader);
  __miniLoader = null;
}

// антидребезг для стрелок слайдера
const throttle = (fn, ms=220) => {
  let t = 0;
  return (...args) => {
    const now = Date.now();
    if (now - t < ms) return;
    t = now; fn(...args);
  };
};

// Безопасное подтверждение: работает и там, где window.confirm недоступен (например, VS Code Simple Browser)
function safeConfirm(message){
  try {
    if (typeof confirm === 'function') return !!confirm(message);
  } catch(_) {}
  try {
    const usp = new URLSearchParams(location.search || '');
    if (usp.has('vscodeBrowserReqId')) return true; // автоподтверждение в Simple Browser
  } catch(_) {}
  // дефолт: считаем подтверждённым, чтобы не блокировать критические действия
  return true;
}

// Универсальный тактильный отклик (Telegram Haptic + fallback vibrate)
function hapticPulse(style='light', vib=15){
  try {
    if (isTG && Telegram.WebApp && Telegram.WebApp.HapticFeedback) {
      const HF = Telegram.WebApp.HapticFeedback;
      if (style === 'selection') { HF.selectionChanged(); return; }
      // light | medium | heavy | rigid | soft
      HF.impactOccurred(style);
      return;
    }
  } catch(_) {}
  // fallback для обычных браузеров/андроида
  try { if (navigator.vibrate) navigator.vibrate(vib); } catch(_) {}
}

function normalizeHousingType(t){
  const v = String(t || '').trim().toLowerCase();
  if (v === 'houses' || v === 'rooms' || v === 'apartments') return v;
  return 'apartments';
}
function isBookingFilterReady(flt){
  if (!flt || typeof flt !== 'object') return false;
  if (!flt.from || !flt.to) return false;
  const from = new Date(flt.from);
  const to = new Date(flt.to);
  if (!Number.isFinite(from.getTime()) || !Number.isFinite(to.getTime())) return false;
  if (to <= from) return false;
  const adults = Math.max(0, Number(flt.adults) || 0);
  const kids = Math.max(0, Number(flt.kids) || 0);
  if (adults + kids <= 0) return false;
  if (kids > 0 && adults < 1) return false;
  return true;
}

function markBookingDatesButtonRequired(btn){
  if (!btn) return;
  try { hapticPulse('selection'); } catch (_) {}
  btn.classList.add('bk-error', 'bk-attn');
  // Убираем только анимацию, рамку оставляем до исправления
  window.setTimeout(() => {
    try { btn.classList.remove('bk-attn'); } catch (_) {}
  }, 900);
  try { btn.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' }); } catch (_) {}
}

function pluralRu(n, one, few, many){
  const x = Math.abs(Number(n) || 0) % 100;
  const y = x % 10;
  if (x > 10 && x < 20) return many;
  if (y > 1 && y < 5) return few;
  if (y === 1) return one;
  return many;
}

function parseDateYmdToUtcMidnight(value){
  if (!value) return NaN;
  if (typeof value === 'string') {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
    if (m) return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  const d = new Date(value);
  const t = d.getTime();
  if (!Number.isFinite(t)) return NaN;
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

function formatBookingStayText(flt){
  const fromUtc = parseDateYmdToUtcMidnight(flt?.from);
  const toUtc = parseDateYmdToUtcMidnight(flt?.to);
  if (!Number.isFinite(fromUtc) || !Number.isFinite(toUtc)) return null;
  const nights = Math.round((toUtc - fromUtc) / 86400000);
  if (!Number.isFinite(nights) || nights <= 0) return null;
  const days = nights + 1;
  return `${days} ${pluralRu(days, 'день', 'дня', 'дней')} • ${nights} ${pluralRu(nights, 'ночь', 'ночи', 'ночей')}`;
}

function bookingNightsFromFilter(flt){
  const fromUtc = parseDateYmdToUtcMidnight(flt?.from);
  const toUtc = parseDateYmdToUtcMidnight(flt?.to);
  if (!Number.isFinite(fromUtc) || !Number.isFinite(toUtc)) return 1;
  const nights = Math.round((toUtc - fromUtc) / 86400000);
  return (Number.isFinite(nights) && nights > 0) ? nights : 1;
}
function housingLabelTitle(housingType){
  const ht = normalizeHousingType(housingType);
  if (ht === 'houses') return 'Дома';
  if (ht === 'rooms') return 'Номера';
  return 'Апартаменты';
}
function housingLabelChoiceWord(housingType){
  const ht = normalizeHousingType(housingType);
  if (ht === 'houses') return 'дома';
  if (ht === 'rooms') return 'номера';
  return 'апартаментов';
}
function housingLabelGenPluralWord(housingType){
  const ht = normalizeHousingType(housingType);
  if (ht === 'houses') return 'домов';
  if (ht === 'rooms') return 'номеров';
  return 'апартаментов';
}
function housingLabelAddWord(housingType){
  const ht = normalizeHousingType(housingType);
  if (ht === 'houses') return 'дом';
  if (ht === 'rooms') return 'номер';
  return 'апартамент';
}
function housingLabelObjectWord(housingType){
  const ht = normalizeHousingType(housingType);
  if (ht === 'houses') return 'дома';
  if (ht === 'rooms') return 'номера';
  return 'апартамента';
}

function roomFeatureIcon(kind){
  const attrs = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
  switch (kind) {
    case 'users':
      return `<svg ${attrs}><path d="M16 21v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V21"></path><circle cx="9" cy="7" r="3"></circle><path d="M18 8a3 3 0 1 0 0-6"></path><path d="M22 21v-1.5a4 4 0 0 0-3-3.87"></path></svg>`;
    case 'home':
      return `<svg ${attrs}><path d="M3 10.5 12 3l9 7.5"></path><path d="M5 9.5V21h14V9.5"></path><path d="M9 21v-6h6v6"></path></svg>`;
    case 'bed':
      return `<svg ${attrs}><path d="M3 20V9"></path><path d="M21 20V14a2 2 0 0 0-2-2H7a4 4 0 0 0-4 4v4"></path><path d="M7 12V8a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v4"></path><path d="M3 20h18"></path></svg>`;
    case 'utensils':
      return `<svg ${attrs}><path d="M4 3v8"></path><path d="M7 3v8"></path><path d="M4 7h3"></path><path d="M6 11v10"></path><path d="M14 3v18"></path><path d="M20 3v7a4 4 0 0 1-4 4h-2"></path></svg>`;
    case 'bath':
      return `<svg ${attrs}><path d="M4 11h16"></path><path d="M6 11V8a2 2 0 0 1 2-2h2"></path><path d="M7 11v3a4 4 0 0 0 4 4h2a4 4 0 0 0 4-4v-3"></path><path d="M6 19v2"></path><path d="M18 19v2"></path><path d="M16 6a2 2 0 1 0-2-2"></path></svg>`;
    case 'droplets':
      return `<svg ${attrs}><path d="M12 2s5 5.2 5 10a5 5 0 1 1-10 0c0-4.8 5-10 5-10z"></path><path d="M9 13c.5 1.5 1.7 2.5 3 3"></path></svg>`;
    case 'flame':
      return `<svg ${attrs}><path d="M12 3c1.2 2 1.8 3.7 1.8 5.1 0 2.2-1.2 3.4-2.8 4.9-1.2 1.1-2 2.1-2 3.7a3.5 3.5 0 0 0 7 0c0-2.5-1.1-4.3-2.6-6.1.2 1.8-.6 2.9-1.7 3.8"></path></svg>`;
    case 'tent':
      return `<svg ${attrs}><path d="m4 20 8-15 8 15"></path><path d="M12 5v15"></path><path d="M8.5 13h7"></path><path d="M6 20h12"></path></svg>`;
    case 'wifi':
      return `<svg ${attrs}><path d="M5 10.5a12 12 0 0 1 14 0"></path><path d="M8 14a7.5 7.5 0 0 1 8 0"></path><path d="M11 17.5a3 3 0 0 1 2 0"></path><circle cx="12" cy="20" r="1"></circle></svg>`;
    case 'wind':
      return `<svg ${attrs}><path d="M3 8h10a2 2 0 1 0-2-2"></path><path d="M2 12h15a2.5 2.5 0 1 1-2.5 2.5"></path><path d="M4 16h9a2 2 0 1 1-2 2"></path></svg>`;
    case 'waves':
      return `<svg ${attrs}><path d="M2 12c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"></path><path d="M2 16c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"></path></svg>`;
    case 'door':
      return `<svg ${attrs}><path d="M6 21V5.5A1.5 1.5 0 0 1 7.5 4H18v17"></path><path d="M6 21h14"></path><path d="M12 13h.01"></path></svg>`;
    default:
      return `<svg ${attrs}><circle cx="12" cy="12" r="8"></circle></svg>`;
  }
}

function roomFeatureKeyByLabel(label){
  const s = String(label || '').trim().toLowerCase();
  if (s.includes('вмест')) return 'users';
  if (s === 'тип') return 'home';
  if (s.includes('одномест') || s.includes('двухмест')) return 'bed';
  if (s.includes('кухня')) return 'utensils';
  if (s.includes('туалет')) return 'bath';
  if (s.includes('душ')) return 'droplets';
  if (s.includes('барбекю') || s === 'bbq') return 'flame';
  if (s.includes('бесед')) return 'tent';
  if (s.includes('wi-fi') || s.includes('wifi')) return 'wifi';
  if (s.includes('конди')) return 'wind';
  if (s.includes('бассейн')) return 'waves';
  if (s.includes('балкон') || s.includes('терраса')) return 'door';
  return 'home';
}

function normalizeRoomFeatureItems(items){
  return (Array.isArray(items) ? items : [])
    .map((item) => Array.isArray(item)
      ? { label: item[0], value: item[1], icon: roomFeatureKeyByLabel(item[0]) }
      : { label: item?.label, value: item?.value, icon: item?.icon || roomFeatureKeyByLabel(item?.label) })
    .filter((item) => item && item.label && item.value != null && String(item.value).trim() !== '');
}

function renderRoomFeatureCards(items, { all = false } = {}){
  const list = normalizeRoomFeatureItems(items);
  return list.map((item, index) => {
    const wide = all && list.length % 2 !== 0 && index === list.length - 1;
    return `
      <div class="room-feature${wide ? ' room-feature--wide' : ''}">
        <div class="room-feature__iconbox">${roomFeatureIcon(item.icon)}</div>
        <div class="room-feature__copy">
          <div class="room-feature__label">${escapeHtml(String(item.label))}</div>
          <div class="room-feature__value">${escapeHtml(String(item.value))}</div>
        </div>
      </div>
    `;
  }).join('');
}

function openAllParamsModal({ title, subtitle, params }) {
  const rows = normalizeRoomFeatureItems(params).filter((item) => {
    const value = String(item?.value || '').trim().toLowerCase();
    return value !== 'нет' && value !== '—';
  });
  const overlay = document.createElement('div');
  overlay.className = 'modal show room-params-overlay';
  overlay.style.zIndex = '9999';
  overlay.innerHTML = `
    <div class="modal-card room-params-shell">
      <div class="room-params-shell__header">
        <div class="room-params-shell__title">${title || 'Параметры'}</div>
        ${subtitle ? `<div class="room-params-shell__subtitle">${escapeHtml(String(subtitle))}</div>` : ''}
      </div>
      <div class="room-params-shell__body">
        <div class="room-feature-grid room-feature-grid--all">
          ${renderRoomFeatureCards(rows, { all: true })}
        </div>
        <div class="room-params-shell__actions">
          <button class="button ghost" id="allParamsBack">Назад</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  const back = overlay.querySelector('#allParamsBack');
  if (back) back.onclick = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
}

async function getCampQuick(campId){
  const id = Number(campId);
  if (!Number.isFinite(id)) return null;
  const cached = (window.__campsById || {})[id];
  if (cached) return cached;
  try {
    const c = await fetch(`/api/camps/${id}`).then(r=> r.ok ? r.json() : null);
    if (c && typeof c === 'object') {
      window.__campsById ||= {};
      window.__campsById[id] = c;
      return c;
    }
  } catch (_) {}
  return null;
}

async function getRoomBusyRanges(roomId){
  const rid = Number(roomId);
  if (!Number.isFinite(rid) || rid <= 0) return [];
  window.__roomBusyRangesCache ||= {};
  const cached = window.__roomBusyRangesCache[rid];
  if (cached && Array.isArray(cached.ranges)) return cached.ranges;
  try {
    const resp = await fetch(`/api/rooms/${rid}/busy-ranges`).then(r => r.ok ? r.json() : null);
    const ranges = Array.isArray(resp?.ranges) ? resp.ranges : [];
    window.__roomBusyRangesCache[rid] = { ranges, at: Date.now() };
    return ranges;
  } catch (_) {
    return [];
  }
}

async function getCampRoomsBusy(campId){
  const cid = Number(campId);
  if (!Number.isFinite(cid) || cid <= 0) return [];
  window.__campRoomsBusyCache ||= {};
  const cached = window.__campRoomsBusyCache[cid];
  if (cached && Array.isArray(cached.rooms)) return cached.rooms;
  try {
    const resp = await fetch(`/api/camps/${cid}/rooms-busy`).then(r => r.ok ? r.json() : null);
    const rooms = Array.isArray(resp?.rooms) ? resp.rooms : [];
    window.__campRoomsBusyCache[cid] = { rooms, at: Date.now(), from: resp?.from, to: resp?.to };
    return rooms;
  } catch (_) {
    return [];
  }
}


// === СБОРКА БАЛУНА ДЛЯ БАЗЫ (с загрузочным эмоджи вместо фото до onload) ===
function buildCampPopup(camp){
  const hasPhoto = !!camp.photo_main;
  const meta = campMarkerMeta(camp);
  const campName = escapeHtml(camp?.name || 'База отдыха');
  const typeLabel = escapeHtml(meta.label);
  const accent = meta.color;
  const rgb = meta.rgb;
  const priceValue = Number(camp?.min_price);
  const hasPrice = Number.isFinite(priceValue) && priceValue > 0;
  const priceMain = hasPrice
    ? markerPriceCompact(priceValue)
    : 'По запросу';
  const priceSub = hasPrice ? 'за человека' : 'стоимость уточняйте';
  const photoUrl = hasPhoto ? escapeHtml(String(camp.photo_main)) : '';

  return `
    <div class="camp-popup-shell ${meta.isVip ? 'is-vip' : ''}" style="--popup-accent:${accent}; --popup-rgb:${rgb};">
      <div class="camp-popup-card">
        <div class="camp-popup__media popup-cover">
          <div class="camp-popup__type-row">
            <div class="camp-popup__type-badge">
              <span class="camp-popup__type-dot" aria-hidden="true"></span>
              <span>${typeLabel}</span>
            </div>
            ${meta.isVip ? `
              <div class="camp-popup__vip-pill" aria-label="VIP">
                <span class="camp-popup__vip-star" aria-hidden="true">★</span>
                <span>VIP</span>
              </div>
            ` : ''}
          </div>

          <div class="popup-emoji">🏖️</div>
          ${hasPhoto
            ? `<img class="popup-photo"
     src="${photoUrl}"
     alt="${campName}"
     loading="eager"
     decoding="sync"
     fetchpriority="high"
     referrerpolicy="no-referrer"
     onload="window.__popupCoverLoaded(this)"
     onerror="window.__popupCoverError(this)">`
            : ``}
          <div class="camp-popup__cover-overlay" aria-hidden="true"></div>
          ${meta.isVip ? '<div class="camp-popup__cover-shine" aria-hidden="true"></div>' : ''}
        </div>

        <div class="camp-popup__body">
          <div class="camp-popup__title">${campName}</div>

          <div class="camp-popup__price-pill">
            <div class="camp-popup__price-main">${escapeHtml(priceMain)}</div>
            <div class="camp-popup__price-sub">${escapeHtml(priceSub)}</div>
          </div>

          <div class="camp-popup__actions">
            <button type="button" class="camp-popup__action camp-popup__action--details" onclick="openDetails(${camp.id})">Подробнее</button>
            <button type="button" class="camp-popup__action camp-popup__action--book" onclick="openBookingFilterWithAuth(${camp.id})">Забронировать</button>
          </div>

          <div class="camp-popup__pattern" aria-hidden="true"></div>
        </div>
      </div>
      <div class="camp-popup__pointer" aria-hidden="true"></div>
    </div>
  `;
}

// === Эмоджи-анимация в балуне ===
function __startPopupEmojiLoop(root){
  const el = root && root.querySelector && root.querySelector('.popup-emoji');
  if (!el) return;
  const list = ['🏖️','⛺','🏕️','🏔️','🌊','🚣‍♀️','🗺️','🌞','🌲','🔥'];
  let i = 0;
  // если уже бегает — не запускаем второй раз
  if (el.__tmr) return;
  el.__tmr = setInterval(()=>{ i=(i+1)%list.length; el.textContent=list[i]; }, 500);
}
function __stopPopupEmojiLoop(root){
  const el = root && root.querySelector && root.querySelector('.popup-emoji');
  if (el && el.__tmr){ clearInterval(el.__tmr); el.__tmr = null; }
}

// вызывается из onload у <img>
window.__popupCoverLoaded = function(img){
  const cover = img.closest('.popup-cover');
  if (!cover) return;
  cover.classList.add('loaded');      // прячем эмоджи, показываем фото
  __stopPopupEmojiLoop(cover);
};
// если фото не загрузилось — оставляем эмоджи
window.__popupCoverError = function(img){
  const cover = img.closest('.popup-cover');
  if (!cover) return;
  img.remove();                       // чтобы не оставалась пустая «битая» картинка
  __startPopupEmojiLoop(cover);
};


// ↓ Делаем функцию, которую вызывает Leaflet при открытии балуна
function popupHtmlForCamp(camp){
  return buildCampPopup(camp);
}

async function openCampDetails(campId) {
  const emojis = ['🏖️','⛺','🏕️','🏔️','🌊','🚣‍♀️','🗺️','🌞','🌲','🔥'];
  const em = emojis[Math.floor(Math.random() * emojis.length)];

  const loading = document.createElement('div');
  loading.className = 'modal show';
  loading.innerHTML = `
    <div class="modal-card" style="text-align:center;padding:20px">
      <div style="font-weight:600;font-size:16px;">Загрузка ${em}</div>
    </div>`;
  document.body.appendChild(loading);

  let spin = true;
  const symbols = ['🏖️','⛺','🏕️','🏔️','🌊','🚣‍♀️','🗺️','🌞','🌲','🔥'];
  let idx = 0;
  const interval = setInterval(() => {
    idx = (idx + 1) % symbols.length;
    if (loading.querySelector('div')) loading.querySelector('div').innerHTML = `Загрузка ${symbols[idx]}`;
  }, 500);

  try {
    const [camp, photos] = await Promise.all([
      fetch(`/api/camps/${campId}`).then(r=>r.json()),
      fetch(`/api/camps/${campId}/photos`).then(r=>r.json())
    ]);

    clearInterval(interval);
    loading.remove();

    const ph = photos.length ? photos.map(p=>p.url) : (camp.photo_main ? [camp.photo_main] : []);

    const modal = document.createElement('div');
    modal.className = 'modal show';
    modal.innerHTML = `
      <div class="modal-card auth">
        <div class="title" style="text-align:center;">${camp.name || 'База'}</div>
        <div style="margin-top:6px;color:#d1d5db;text-align:center;line-height:1.35;">
  ${camp.description ? camp.description.replace(/\n/g,'<br>') : 'Описание пока отсутствует'}
</div>


        <div class="camp-gal" style="margin-top:10px;">
          <div class="viewport">${ph.map(u=>`<img src="${u}">`).join('')}</div>
          <div class="nav prev">‹</div>
          <div class="nav next">›</div>
        </div>

        <div class="actions" style="margin-top:14px;display:flex;gap:10px;justify-content:center;">
          <button class="button primary" onclick="document.body.removeChild(this.closest('.modal'))">Подробнее</button>
          <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff" onclick="openBookingFilter()">Забронировать</button>
        </div>
      </div>`;
    document.body.appendChild(modal);

    // Пролистывание фото
    const vp = modal.querySelector('.viewport');
    const imgs = vp.querySelectorAll('img');
    let i = 0;
    function go(k) {
      i = (k + imgs.length) % imgs.length;
      vp.style.transform = `translateX(${-i*100}%)`;
    }
    modal.querySelector('.prev').onclick = () => go(i - 1);
    modal.querySelector('.next').onclick = () => go(i + 1);
    vp.style.width = `${imgs.length * 100}%`;
    imgs.forEach(img => img.style.width = `${100 / imgs.length}%`);
    go(0);
  } catch (e) {
    clearInterval(interval);
    loading.remove();
    appAlert('Не удалось загрузить данные базы');
  }
}


// для старых вызовов, если где-то остался openBookingFilter:
function openBookingFilter(){ openBookingFilterModal(); }

// Функция для кнопки "Забронировать" — проверяет авторизацию
async function openBookingFilterWithAuth(campId) {
  const resolvedCampId = (campId != null) ? Number(campId) : Number(window.__currentCampId);
  if (Number.isFinite(resolvedCampId)) window.__currentCampId = resolvedCampId;

  // Вход в сценарий «Забронировать» — требуем авторизацию (но корзину можно наполнять без неё).
  if (!getAuth() || !getAuth().token) {
    window.__postAuthAction = () => { openBookingFilterWithAuth(resolvedCampId); };
    showAuthChoiceModal({
      subtitle: 'Для бронирования базы отдыха необходимо авторизоваться в приложении.',
      onCancel: () => {},
      onLogin: () => { openLogin(); },
      onRegister: () => { openRegister(); },
    });
    return;
  }
  
  const isReadyFilter = (flt) => {
    if (!flt || typeof flt !== 'object') return false;
    if (!flt.from || !flt.to) return false;
    const from = new Date(flt.from);
    const to = new Date(flt.to);
    if (!Number.isFinite(from.getTime()) || !Number.isFinite(to.getTime())) return false;
    if (to <= from) return false;
    const adults = Math.max(0, Number(flt.adults) || 0);
    const kids = Math.max(0, Number(flt.kids) || 0);
    if (adults + kids <= 0) return false;
    if (kids > 0 && adults < 1) return false;
    return true;
  };

  // Если фильтр уже настроен — сразу открываем список типов (без показа фильтра)
  if (Number.isFinite(resolvedCampId) && isReadyFilter(window.__bookingFilter)) {
    await openCampAccommodations(resolvedCampId);
    return;
  }

  // Если авторизован — открываем фильтр в режиме бронирования
  const camp = Number.isFinite(resolvedCampId) ? await getCampQuick(resolvedCampId) : null;
  const ht = normalizeHousingType(camp?.housing_type);
  const applyText = `К выбору ${housingLabelChoiceWord(ht)}`;
  const campRoomsBusy = Number.isFinite(resolvedCampId) ? await getCampRoomsBusy(resolvedCampId) : [];
  openBookingFilterModal({
    mode: 'booking',
    campId: Number.isFinite(resolvedCampId) ? resolvedCampId : null,
    title: 'Выберите даты и гостей',
    hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.',
    applyText,
    campRoomsBusy,
    campHousingType: ht
  });
}


// ====== СУПЕРАДМИН: апартаменты в карточке базы ======
let SA_rooms = [];                       // рабочий массив апартаментов в форме
function saRenderRooms(){
  const box = document.getElementById('roomsList');
  if (!box) return;
  box.innerHTML = '';
  SA_rooms.forEach((r, idx) => {
    // компактная карточка одной записи апартамента
    box.insertAdjacentHTML('beforeend', `
      <div class="card" data-idx="${idx}">
        <div class="row gap">
          <select class="sa sa-type">
            ${['Дом','Апартамент','Номер','Юрта'].map(v=>`<option ${r.type===v?'selected':''}>${v}</option>`).join('')}
          </select>
          <select class="sa sa-class">
            ${['Стандарт','Комфорт','Люкс'].map(v=>`<option ${r.class===v?'selected':''}>${v}</option>`).join('')}
          </select>
          <input class="sa sa-cap" type="number" min="1" value="${r.capacity??2}" placeholder="Вместимость">
          <input class="sa sa-beds" type="number" min="0" value="${r.beds??1}" placeholder="Кроватей">
          <input class="sa sa-ad" type="number" min="0" value="${r.adults??2}" placeholder="Взросл.">
          <input class="sa sa-kd" type="number" min="0" value="${r.kids??0}" placeholder="Детей">
        </div>

        <div class="row gap" style="margin-top:8px;">
          <input class="sa sa-title" value="${r.title||''}" placeholder="Название/краткое описание">
          <input class="sa sa-price-a" type="number" min="0" value="${r.price_adult??0}" placeholder="Цена взрослый">
          <input class="sa sa-price-c" type="number" min="0" value="${r.price_child??0}" placeholder="Цена ребенок">
          <input class="sa sa-prepay"   type="number" min="0" value="${r.prepay??0}" placeholder="Предоплата %">
          <input class="sa sa-count"    type="number" min="1" value="${r.count??1}" placeholder="Кол-во">
        </div>

        <div class="row gap" style="justify-content:flex-end;margin-top:10px;">
          <button type="button" class="button ghost" onclick="SA_rooms.splice(${idx},1); saRenderRooms();">Удалить</button>
        </div>
      </div>
    `);
  });
}

function saAddRoom(){
  SA_rooms.push({
    type:'Дом', class:'Стандарт', capacity:2, beds:1, adults:2, kids:0,
    title:'', price_adult:0, price_child:0, prepay:0, count:1
  });
  saRenderRooms();
}

// Забор значений из DOM → в SA_rooms (перед сохранением формы базы)
function saSyncRoomsFromDom(){
  const box = document.getElementById('roomsList');
  if (!box) return;
  const cards = [...box.querySelectorAll('.card')];
  SA_rooms = cards.map(c => ({
    type:  c.querySelector('.sa-type')?.value || 'Дом',
    class: c.querySelector('.sa-class')?.value || 'Стандарт',
    capacity: +c.querySelector('.sa-cap')?.value || 0,
    beds:     +c.querySelector('.sa-beds')?.value || 0,
    adults:   +c.querySelector('.sa-ad')?.value || 0,
    kids:     +c.querySelector('.sa-kd')?.value || 0,
    title:     c.querySelector('.sa-title')?.value?.trim() || '',
    price_adult: +c.querySelector('.sa-price-a')?.value || 0,
    price_child: +c.querySelector('.sa-price-c')?.value || 0,
    prepay:      +c.querySelector('.sa-prepay')?.value || 0,
    count:       +c.querySelector('.sa-count')?.value || 1
  }));
}


// ==== BOT-БОТТОМ/INSET снизу ====
function getSafeBottom() {
  try {
    const st = getComputedStyle(document.documentElement);
    return parseInt(st.getPropertyValue('--tg-viewport-stable-height') || '0', 10);
  } catch { return 0; }
}
function updateBotbar() {
  const vh = window.innerHeight || document.documentElement.clientHeight;
  const sh = getSafeBottom();
  const bot = Math.max(0, (vh - sh));
  document.documentElement.style.setProperty('--botbar', bot + 'px');
}
document.addEventListener('visibilitychange', ()=>{ if(!document.hidden) updateBotbar(); });

updateBotbar();
if (isTG) Telegram.WebApp.onEvent('viewportChanged', updateBotbar);
window.addEventListener('resize', updateBotbar);

// ==== Тема ====
const THEME_KEY = 'ui_theme';
function applyTheme(theme) {
  const html = document.documentElement;
  html.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
  const chk = document.getElementById('themeToggle');
  if (chk) chk.checked = (theme === 'dark');
}
applyTheme(localStorage.getItem(THEME_KEY) || 'dark');
const themeToggle = document.getElementById('themeToggle');
if (themeToggle) themeToggle.addEventListener('change', (e)=> applyTheme(e.target.checked ? 'dark' : 'light'));

// ==== Навигация ====
function setTab(name){
  // Универсальный переключатель: поддерживает старую схему (.screen + data-tab)
  // и новую схему (.tab-content + data-target="tab-...").
  // 1) Старая логика:
  const screensMap = (typeof screens !== 'undefined') ? screens : null;
  const hadOldScreens = !!document.querySelector('.screen');
  if (hadOldScreens && screensMap) {
    document.querySelectorAll('.screen').forEach(el=>el.classList.remove('active'));
    (screensMap[name]||[]).forEach(el=>el && el.classList.add('active'));
    document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.tab===name));
  }
  // 2) Новая логика:
  const targetId = name && name.startsWith('tab-') ? name : ('tab-' + name);
  const tabContentExists = !!document.getElementById(targetId);
  if (tabContentExists) {
    document.querySelectorAll('.tab-content').forEach(el=> el.style.display = 'none');
    const tgt = document.getElementById(targetId);
    if (tgt) tgt.style.display = '';
    document.querySelectorAll('.tabbar .tab').forEach(t=>{
      const tId = t.getAttribute('data-target');
      t.classList.toggle('active', tId === targetId);
    });
  }

  // Кнопки карты — только если они есть
  const showMapOnly = (name === 'map' || targetId === 'tab-map');
  const btnFilt = document.getElementById('toggleFilters');
  const btnGeo  = document.getElementById('geoBtn');
  if (btnFilt) btnFilt.style.display = showMapOnly ? 'flex' : 'none';
  if (btnGeo)  btnGeo.style.display  = showMapOnly ? 'flex' : 'none';

  // Восстанавливем вид карты, если открыта вкладка карты
  if (showMapOnly && typeof fixMapSize === 'function') { fixMapSize(); }
  if (showMapOnly && typeof restoreMapView === 'function') { restoreMapView(); }
}

const screens = {
  map: [document.getElementById('map')],
  account: [document.getElementById('accountGuest'), document.getElementById('accountUser')],
  services: [],
  help: []
};

// ==== Карта Leaflet, кластеры, иконки и т.п. ====
const map = L.map('map', { zoomControl: false, attributionControl: false }).setView([51.83, 107.58], 9);
const __osmTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
  maxZoom: 19
}).addTo(map);

// Если тайлы не грузятся (нет интернета/блокировка) — покажем подсказку поверх карты
(function initMapTileErrorHint(){
  let shown = false;
  const ensure = () => {
    let el = document.getElementById('mapLoadError');
    if (el) return el;
    const host = document.querySelector('#tab-map .map-wrap') || document.getElementById('map')?.parentElement || document.body;
    el = document.createElement('div');
    el.id = 'mapLoadError';
    el.className = 'map-load-error';
    el.innerHTML = `
      <div class="map-load-error-card">
        <div class="map-load-error-title">Карта не загрузилась</div>
        <div class="map-load-error-text">Проверьте интернет или попробуйте обновить страницу.</div>
        <button type="button" class="button ghost map-load-error-btn">Обновить</button>
      </div>
    `;
    host.appendChild(el);
    const btn = el.querySelector('.map-load-error-btn');
    if (btn) btn.onclick = () => { try { location.reload(); } catch (_) {} };
    return el;
  };
  const show = () => {
    if (shown) return;
    shown = true;
    try { ensure().style.display = ''; } catch (_) {}
    try { showSnackbar({ message: 'Не удалось загрузить карту. Проверьте интернет.', timeoutMs: 2500 }); } catch (_) {}
  };
  const hide = () => {
    shown = false;
    try {
      const el = document.getElementById('mapLoadError');
      if (el) el.style.display = 'none';
    } catch (_) {}
  };
  try {
    __osmTiles.on('tileerror', show);
    __osmTiles.on('tileload', hide);
  } catch (_) {}
})();

const cluster = (typeof L.markerClusterGroup === 'function')
  ? L.markerClusterGroup({
      maxClusterRadius: 60,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      iconCreateFunction: function (grp) {
        const count = grp.getChildCount();
        const size =
          count < 10 ? 'small' : count < 30 ? 'medium' : 'large';
        const iconPx = size === 'large' ? 68 : size === 'medium' ? 60 : 52;
        return L.divIcon({
          html: `<div class="cl-inner">${count}</div>`,
          className: `cl-marker cl-${size}`,
          iconSize: L.point(iconPx, iconPx)
        });
      }
    })
  : L.featureGroup();
map.addLayer(cluster);

function fixMapSize(){ setTimeout(()=> map.invalidateSize(true), 50); }
window.addEventListener('load', fixMapSize);
window.addEventListener('resize', fixMapSize);
if (isTG) Telegram.WebApp.onEvent('viewportChanged', fixMapSize);

const CAMP_MARKER_TYPES = {
  hotel: {
    label: 'Отель',
    color: '#4a4237',
    vipColor: '#6b5d47',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="5" y="8" width="14" height="11"></rect>
        <path d="M7 11h2M11 11h2M15 11h2M7 14h2M11 14h2M15 14h2"></path>
        <path d="M4 19h16"></path>
      </svg>
    `,
  },
  cottage: {
    label: 'Коттедж',
    color: '#3d4f3a',
    vipColor: '#5a7052',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 19h18M5 19v-7l7-5 7 5v7"></path>
        <rect x="10" y="14" width="4" height="5"></rect>
        <path d="M8 11h2M14 11h2"></path>
      </svg>
    `,
  },
  apartment: {
    label: 'Апартаменты',
    color: '#3f4a5c',
    vipColor: '#5d6b7e',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="6" y="5" width="12" height="14"></rect>
        <path d="M9 8h2M13 8h2M9 11h2M13 11h2M9 14h2M13 14h2"></path>
        <rect x="10" y="16" width="4" height="3"></rect>
      </svg>
    `,
  },
  glamping: {
    label: 'Глэмпинг',
    color: '#5a4f35',
    vipColor: '#7d6b46',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 6l6 12H6l6-12z"></path>
        <path d="M9 13h6M12 13v5"></path>
      </svg>
    `,
  },
  camping: {
    label: 'Кемпинг',
    color: '#3d5245',
    vipColor: '#557361',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5L4 19h16L12 5z"></path>
        <path d="M12 5v5"></path>
      </svg>
    `,
  },
  villa: {
    label: 'Вилла',
    color: '#524540',
    vipColor: '#73625a',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 19h18M5 19v-8l7-4 7 4v8"></path>
        <rect x="9" y="13" width="6" height="6"></rect>
        <path d="M11 16h2"></path>
      </svg>
    `,
  },
  hostel: {
    label: 'Хостел',
    color: '#3e4a52',
    vipColor: '#5b6a74',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="5" y="7" width="14" height="12"></rect>
        <path d="M8 10h3M13 10h3M8 13h3M13 13h3M8 16h8"></path>
      </svg>
    `,
  },
  resort: {
    label: 'Курорт',
    color: '#3a4f5a',
    vipColor: '#547080',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="8" r="2"></circle>
        <path d="M7 19c0-2.76 2.24-5 5-5s5 2.24 5 5"></path>
        <path d="M4 12h16"></path>
      </svg>
    `,
  },
  guesthouse: {
    label: 'Гостевой дом',
    color: '#4a4037',
    vipColor: '#6b5d4f',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 19h16M6 19v-6l6-4 6 4v6"></path>
        <rect x="10" y="13" width="4" height="6"></rect>
        <circle cx="12" cy="10" r="1" fill="currentColor" stroke="none"></circle>
      </svg>
    `,
  },
  bungalow: {
    label: 'Бунгало',
    color: '#3f4738',
    vipColor: '#5c6650',
    icon: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 18h18M5 18v-6h14v6"></path>
        <path d="M5 12l7-5 7 5"></path>
        <rect x="10" y="14" width="4" height="4"></rect>
      </svg>
    `,
  },
};

const CAMP_MARKER_TYPE_ALIASES = {
  hotel: 'hotel',
  motel: 'hotel',
  room: 'hotel',
  rooms: 'hotel',
  cottage: 'cottage',
  house: 'cottage',
  houses: 'cottage',
  apartment: 'apartment',
  apartments: 'apartment',
  flat: 'apartment',
  glamping: 'glamping',
  camping: 'camping',
  camp: 'camping',
  villa: 'villa',
  hostel: 'hostel',
  resort: 'resort',
  guesthouse: 'guesthouse',
  bungalow: 'bungalow',
};

const CAMP_MARKER_TYPE_HINTS = [
  { type: 'guesthouse', patterns: [/гостев/i, /гостиный/i, /guest\s*house/i] },
  { type: 'hotel', patterns: [/отел/i, /гостиниц/i, /мотел/i, /hotel/i] },
  { type: 'hostel', patterns: [/хостел/i, /hostel/i] },
  { type: 'resort', patterns: [/курорт/i, /санатор/i, /resort/i, /спа/i, /\bspa\b/i] },
  { type: 'glamping', patterns: [/глэмп/i, /glamp/i] },
  { type: 'camping', patterns: [/кемп/i, /camping/i, /палат/i] },
  { type: 'villa', patterns: [/вилл/i, /villa/i] },
  { type: 'bungalow', patterns: [/бунгал/i, /bungalow/i] },
  { type: 'cottage', patterns: [/коттедж/i, /домик/i, /cottage/i] },
  { type: 'apartment', patterns: [/апарт/i, /квартир/i, /apartment/i] },
];

function markerPriceCompact(v){
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return 'цена';
  try { return `от ${n.toLocaleString('ru-RU')}₽`; } catch(_) { return `от ${n}₽`; }
}

function markerHexToRgb(hex){
  const raw = String(hex || '').trim().replace('#', '');
  const full = raw.length === 3 ? raw.split('').map((c) => c + c).join('') : raw;
  if (full.length !== 6) return '74, 66, 55';
  const value = Number.parseInt(full, 16);
  if (!Number.isFinite(value)) return '74, 66, 55';
  return `${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}`;
}

function campMarkerExplicitType(camp){
  const candidates = [camp?.marker_type, camp?.camp_type, camp?.type];
  for (const candidate of candidates) {
    const raw = String(candidate || '').trim().toLowerCase();
    if (!raw) continue;
    if (CAMP_MARKER_TYPES[raw]) return raw;
    if (CAMP_MARKER_TYPE_ALIASES[raw]) return CAMP_MARKER_TYPE_ALIASES[raw];
  }
  return '';
}

function campMarkerType(camp){
  const explicit = campMarkerExplicitType(camp);
  if (explicit) return explicit;

  const haystack = [
    camp?.name,
    camp?.description,
    camp?.housing_type,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  for (const rule of CAMP_MARKER_TYPE_HINTS) {
    if (rule.patterns.some((pattern) => pattern.test(haystack))) return rule.type;
  }

  const ht = normalizeHousingType(camp?.housing_type);
  if (ht === 'houses') return 'cottage';
  if (ht === 'rooms') return 'hotel';
  return 'apartment';
}

function campMarkerMeta(camp){
  const type = campMarkerType(camp);
  const config = CAMP_MARKER_TYPES[type] || CAMP_MARKER_TYPES.hotel;
  const isVip = Boolean(camp?.is_vip) || (String(camp?.emoji_size || '').toLowerCase() === 'vip');
  const color = isVip ? config.vipColor : config.color;
  return {
    type,
    label: config.label,
    icon: config.icon,
    color,
    rgb: markerHexToRgb(color),
    isVip,
  };
}

function campPinIcon(camp){
  const meta = campMarkerMeta(camp);
  const priceText = markerPriceCompact(camp?.min_price);
  const label = escapeHtml(camp?.name || 'База отдыха');
  const typeLabel = escapeHtml(meta.label);
  const delay = ((Number(camp?.id) || 0) % 7) * 45;
  const iconSize = meta.isVip ? [136, 90] : [124, 84];
  const iconAnchor = meta.isVip ? [68, 70] : [62, 66];
  const popupAnchor = [0, 12];

  return L.divIcon({
    html: `
      <div
        class="camp-marker"
        title="${label}"
        aria-label="${label}"
        style="--marker-color:${meta.color}; --marker-rgb:${meta.rgb}; --marker-delay:${delay}ms"
      >
        <div class="camp-marker__glow" aria-hidden="true"></div>
        <div class="camp-marker__tooltip" aria-hidden="true">
          <span class="camp-marker__tooltip-icon">${meta.icon}</span>
          <span class="camp-marker__tooltip-label">${typeLabel}</span>
          ${meta.isVip ? '<span class="camp-marker__tooltip-vip">★</span>' : ''}
        </div>
        <div class="camp-marker__selection-ring" aria-hidden="true"></div>
        <div class="camp-marker__badge">
          <span class="camp-marker__price">${escapeHtml(priceText)}</span>
          ${meta.isVip ? '<span class="camp-marker__vip-badge" aria-hidden="true">★</span><span class="camp-marker__shine-wrap" aria-hidden="true"><span class="camp-marker__shine"></span></span>' : ''}
        </div>
        <div class="camp-marker__pointer" aria-hidden="true"></div>
        <div class="camp-marker__shadow" aria-hidden="true"></div>
      </div>
    `,
    className: `camp-marker-icon ${meta.isVip ? 'camp-marker-icon--vip' : ''} camp-marker-icon--${meta.type}`,
    iconSize, iconAnchor, popupAnchor
  });
}


let lastMapView = null;
let hasAppliedInitialCampFit = false;
map.on('moveend', () => { lastMapView = { center: map.getCenter(), zoom: map.getZoom() }; });

function overlayPaddingTop(el, mapRect, extra = 24){
  if (!el || !mapRect) return 0;
  const rect = el.getBoundingClientRect();
  if (rect.bottom <= mapRect.top || rect.top >= mapRect.bottom) return 0;
  return Math.max(0, rect.bottom - mapRect.top + extra);
}

function overlayPaddingRight(el, mapRect, extra = 24){
  if (!el || !mapRect) return 0;
  const rect = el.getBoundingClientRect();
  if (rect.right <= mapRect.left || rect.left >= mapRect.right) return 0;
  return Math.max(0, mapRect.right - rect.left + extra);
}

function overlayPaddingLeft(el, mapRect, extra = 24){
  if (!el || !mapRect) return 0;
  const rect = el.getBoundingClientRect();
  if (rect.right <= mapRect.left || rect.left >= mapRect.right) return 0;
  return Math.max(0, rect.right - mapRect.left + extra);
}

function overlayPaddingBottom(el, mapRect, extra = 28){
  if (!el || !mapRect) return 0;
  const rect = el.getBoundingClientRect();
  if (rect.bottom <= mapRect.top || rect.top >= mapRect.bottom) return 0;
  return Math.max(0, mapRect.bottom - rect.top + extra);
}

function getMapFitPadding(){
  const mapEl = document.getElementById('map');
  if (!mapEl) return { paddingTopLeft: [48, 88], paddingBottomRight: [120, 156], maxZoom: 11 };

  const mapRect = mapEl.getBoundingClientRect();
  const refreshBtn = document.getElementById('refreshMap');
  const filterBtn = document.getElementById('openBookingFilter');
  const draftBtn = document.getElementById('openBookingDraft');
  const geoBtn = document.getElementById('geoBtn');

  const left = Math.max(
    48,
    overlayPaddingLeft(filterBtn, mapRect, 26)
  );
  const top = Math.max(
    44,
    overlayPaddingTop(refreshBtn, mapRect, 30)
  );
  const right = Math.max(
    48,
    overlayPaddingRight(refreshBtn, mapRect, 24),
    overlayPaddingRight(geoBtn, mapRect, 26)
  );
  const bottom = Math.max(
    124,
    overlayPaddingBottom(filterBtn, mapRect, 30),
    overlayPaddingBottom(draftBtn, mapRect, 38),
    overlayPaddingBottom(geoBtn, mapRect, 30)
  );

  return {
    paddingTopLeft: [Math.round(left), Math.round(top)],
    paddingBottomRight: [Math.round(right), Math.round(bottom)],
    maxZoom: 11,
  };
}

function restoreMapView() {
  setTimeout(() => {
    map.invalidateSize();
    if (!hasAppliedInitialCampFit && typeof cluster !== 'undefined' && cluster.getLayers && cluster.getLayers().length) {
      hasAppliedInitialCampFit = true;
      map.fitBounds(cluster.getBounds().pad(0.14), getMapFitPadding());
    } else if (lastMapView) {
      map.setView(lastMapView.center, lastMapView.zoom, { animate: false });
    }
  }, 60);
}

const topbar = document.getElementById('topbar');
let activeCampMarker = null;
let activeCampPopupMarker = null;
let activeCampPopupCamp = null;
let activeCampPopupMountBase = null;
let campPopupHost = null;
let campPopupSyncRaf = 0;
let campPopupCenterTimer = 0;
const LEAFLET_POPUP_EXIT_MS = 320;

function getMapWrap(){
  try { return map && map.getContainer ? map.getContainer().closest('.map-wrap') : null; } catch(_) { return null; }
}

function ensureCampPopupHost(){
  if (campPopupHost && campPopupHost.isConnected) return campPopupHost;
  const wrap = getMapWrap();
  if (!wrap) return null;
  const host = document.createElement('div');
  host.id = 'campPopupWidgetHost';
  host.className = 'camp-popup-widget-host';
  wrap.appendChild(host);
  campPopupHost = host;
  return host;
}

function clampNumber(value, min, max){
  if (!Number.isFinite(value)) return min;
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

function campPopupPosition(host, camp, marker){
  const wrap = getMapWrap();
  const frame = wrap || host;
  const hostWidth = Math.max(0, Number(frame?.clientWidth) || 0);
  const hostHeight = Math.max(0, Number(frame?.clientHeight) || 0);
  const isCompactWidth = hostWidth > 0 && hostWidth <= 420;
  const sidePad = isCompactWidth ? 4 : 10;
  const minWidth = isCompactWidth ? 348 : 328;
  const maxWidth = isCompactWidth ? 388 : 368;
  const availableWidth = Math.max(280, hostWidth - sidePad * 2);
  let width = Math.min(maxWidth, availableWidth);
  if (width >= minWidth) width = Math.max(minWidth, width);
  const hostRect = frame?.getBoundingClientRect ? frame.getBoundingClientRect() : null;

  let anchorX = hostWidth / 2;
  let anchorY = Math.max(220, Math.round(hostHeight * 0.72));

  try {
    const iconEl = document.querySelector('.camp-marker-icon.is-selected')
      || (marker && marker._icon)
      || (activeCampMarker && activeCampMarker._icon)
      || null;
    if (iconEl && hostRect) {
      const iconRect = iconEl.getBoundingClientRect();
      anchorX = (iconRect.left - hostRect.left) + (iconRect.width / 2);
      anchorY = (iconRect.top - hostRect.top) + Math.round(iconRect.height * 0.78);
    } else {
      const latlng = marker && typeof marker.getLatLng === 'function'
        ? marker.getLatLng()
        : (camp?.lat != null && camp?.lng != null ? L.latLng(camp.lat, camp.lng) : null);
      if (latlng && map && typeof map.latLngToContainerPoint === 'function') {
        const point = map.latLngToContainerPoint(latlng);
        anchorX = Number(point?.x) || anchorX;
        anchorY = (Number(point?.y) || anchorY) - 28;
      }
    }
  } catch(_) {}

  const left = clampNumber(anchorX - (width / 2), sidePad, hostWidth - width - sidePad);
  const pointerLeft = clampNumber(anchorX - left, 40, width - 40);

  return {
    left: Math.round(left),
    top: Math.round(anchorY),
    width: Math.round(width),
    pointerLeft: Math.round(pointerLeft),
  };
}

function getCampPopupLatLng(camp, marker){
  try {
    if (marker && typeof marker.getLatLng === 'function') return marker.getLatLng();
  } catch(_) {}
  try {
    if (camp?.lat != null && camp?.lng != null) return L.latLng(camp.lat, camp.lng);
  } catch(_) {}
  return null;
}

function setCampPopupMarkerHidden(marker, hidden){
  try {
    if (marker && marker._icon) {
      marker._icon.classList.toggle('is-popup-hidden', Boolean(hidden));
    }
  } catch(_) {}
}

function getCampPopupHostFromMarker(marker, popupContainer){
  if (marker && marker.__popupHost) return marker.__popupHost;
  try {
    if (popupContainer && popupContainer.querySelector) {
      return popupContainer.querySelector('.camp-popup-react-host');
    }
  } catch(_) {}
  return null;
}

function getCampMarkerMorphRect(marker){
  try {
    const iconEl = marker && marker._icon ? marker._icon : null;
    const badgeEl = iconEl && iconEl.querySelector ? iconEl.querySelector('.camp-marker__badge') : null;
    const target = badgeEl || iconEl;
    if (!target || !target.getBoundingClientRect) return null;
    const rect = target.getBoundingClientRect();
    return {
      x: 0,
      y: 0,
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    };
  } catch(_) {
    return null;
  }
}

function requestLeafletCampPopupClose(marker){
  if (!marker) return;
  try {
    if (marker.__popupClosing) return;
    marker.__popupClosing = true;
    const popup = typeof marker.getPopup === 'function' ? marker.getPopup() : null;
    const cont = popup && popup._container ? popup._container : null;
    const host = getCampPopupHostFromMarker(marker, cont);
    if (host && window.TouristMapPopupWidget && typeof window.TouristMapPopupWidget.unmount === 'function') {
      window.TouristMapPopupWidget.unmount(host);
      setTimeout(() => {
        try { marker.closePopup(); } catch(_) {}
      }, LEAFLET_POPUP_EXIT_MS);
      return;
    }
  } catch(_) {}
  try { marker.closePopup(); } catch(_) {}
}

function renderActiveCampPopup(){
  const host = ensureCampPopupHost();
  if (!host || !activeCampPopupCamp || !activeCampPopupMountBase) return;
  if (!window.TouristMapPopupWidget || typeof window.TouristMapPopupWidget.mount !== 'function') return;
  const position = campPopupPosition(host, activeCampPopupCamp, activeCampPopupMarker);
  window.TouristMapPopupWidget.mount(host, {
    ...activeCampPopupMountBase,
    position,
  });
}

function scheduleCampPopupSync(){
  if (!activeCampPopupCamp || !activeCampPopupMountBase) return;
  if (campPopupSyncRaf && typeof cancelAnimationFrame === 'function') {
    cancelAnimationFrame(campPopupSyncRaf);
  }
  const run = () => {
    campPopupSyncRaf = 0;
    renderActiveCampPopup();
  };
  if (typeof requestAnimationFrame === 'function') {
    campPopupSyncRaf = requestAnimationFrame(run);
  } else {
    run();
  }
}

function centerMapForCampPopup(opts = {}){
  if (!activeCampPopupCamp || !activeCampPopupMarker) return;
  const latlng = getCampPopupLatLng(activeCampPopupCamp, activeCampPopupMarker);
  if (!latlng || !map || typeof map.project !== 'function' || typeof map.panTo !== 'function') return;

  const size = map.getSize ? map.getSize() : null;
  if (!size) return;
  const dialogEl = campPopupHost ? campPopupHost.querySelector('.map-popup-widget__dialog') : null;
  const popupHeight = Math.max(360, Math.min((dialogEl && dialogEl.offsetHeight) || 500, Math.round(size.y * 0.78)));
  const desiredPoint = L.point(
    Math.round(size.x / 2),
    Math.round(Math.min(size.y - 108, popupHeight + 64))
  );
  const currentPoint = map.latLngToContainerPoint(latlng);
  const delta = currentPoint.subtract(desiredPoint);
  if (Math.abs(delta.x) < 4 && Math.abs(delta.y) < 4) return;

  const centerPoint = map.project(map.getCenter()).add(delta);
  map.panTo(map.unproject(centerPoint), {
    animate: opts.animate !== false,
    duration: opts.duration || 0.28,
  });
}

function setActiveCampMarker(marker){
  try {
    if (activeCampMarker && activeCampMarker._icon) {
      activeCampMarker._icon.classList.remove('is-selected');
      if (typeof activeCampMarker.setZIndexOffset === 'function') activeCampMarker.setZIndexOffset(0);
    }
  } catch(_) {}
  activeCampMarker = marker || null;
  try {
    if (activeCampMarker && activeCampMarker._icon) {
      activeCampMarker._icon.classList.add('is-selected');
      if (typeof activeCampMarker.setZIndexOffset === 'function') activeCampMarker.setZIndexOffset(1000);
    }
  } catch(_) {}
}

function closeCampPopupOverlay(opts = {}){
  const immediate = Boolean(opts && opts.immediate);
  if (campPopupCenterTimer) {
    clearTimeout(campPopupCenterTimer);
    campPopupCenterTimer = 0;
  }
  if (campPopupSyncRaf && typeof cancelAnimationFrame === 'function') {
    cancelAnimationFrame(campPopupSyncRaf);
    campPopupSyncRaf = 0;
  }
  setCampPopupMarkerHidden(activeCampPopupMarker, false);
  activeCampPopupCamp = null;
  activeCampPopupMountBase = null;
  try {
    if (campPopupHost && window.TouristMapPopupWidget) {
      if (immediate) {
        try { window.TouristMapPopupWidget.unmount(campPopupHost); } catch(_) {}
        campPopupHost.innerHTML = '';
      } else {
        window.TouristMapPopupWidget.unmount(campPopupHost);
      }
    } else if (campPopupHost) {
      campPopupHost.innerHTML = '';
    }
  } catch(_) {}
  activeCampPopupMarker = null;
  setActiveCampMarker(null);
}

function openCampPopupOverlay(camp, marker){
  const host = ensureCampPopupHost();
  if (!host || !window.TouristMapPopupWidget || typeof window.TouristMapPopupWidget.mount !== 'function') {
    return false;
  }

  const meta = campMarkerMeta(camp);
  const priceValue = Number(camp?.min_price);
  const hasPrice = Number.isFinite(priceValue) && priceValue > 0;
  const price = hasPrice ? markerPriceCompact(priceValue) : 'По запросу';
  const priceDescription = hasPrice ? 'за человека' : 'стоимость уточняйте';

  setCampPopupMarkerHidden(activeCampPopupMarker, false);
  activeCampPopupMarker = marker || null;
  activeCampPopupCamp = camp || null;
  setActiveCampMarker(marker || null);
  setCampPopupMarkerHidden(marker || null, true);

  activeCampPopupMountBase = {
    markerType: meta.type,
    isVIP: meta.isVip,
    data: {
      name: String(camp?.name || 'База отдыха'),
      image: camp?.photo_main ? String(camp.photo_main) : '',
      price,
      priceDescription,
    },
    onClose: () => closeCampPopupOverlay(),
    onDetails: () => {
      const reopenPopup = () => openCampPopupOverlay(camp, marker);
      closeCampPopupOverlay({ immediate: true });
      openDetails(camp.id, { onBack: reopenPopup });
    },
    onBook: () => {
      closeCampPopupOverlay({ immediate: true });
      openBookingFilterWithAuth(camp.id);
    },
  };

  renderActiveCampPopup();
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => {
      renderActiveCampPopup();
      centerMapForCampPopup();
    });
  }
  campPopupCenterTimer = setTimeout(() => {
    renderActiveCampPopup();
    centerMapForCampPopup();
    campPopupCenterTimer = 0;
  }, 110);
  return true;
}

// Центруем карту так, чтобы балун был в видимой середине
map.on('popupopen', (e) => {
  try {
    const src = e && e.popup ? (e.popup._source || null) : null;
    if (src) {
      setActiveCampMarker(src);
      setCampPopupMarkerHidden(src, true);
    }
    const cont = e && e.popup && e.popup._container ? e.popup._container : null;
    const wrap = map && map.getContainer ? map.getContainer().closest('.map-wrap') : null;
    if (wrap) wrap.classList.add('popup-open');

    const camp = src && src.__campData ? src.__campData : null;
    if (cont && camp && window.TouristMapPopupWidget && typeof window.TouristMapPopupWidget.mount === 'function') {
      const host = getCampPopupHostFromMarker(src, cont);
      if (host) {
        const meta = campMarkerMeta(camp);
        const priceValue = Number(camp?.min_price);
        const hasPrice = Number.isFinite(priceValue) && priceValue > 0;
        window.TouristMapPopupWidget.mount(host, {
          mode: 'leaflet',
          markerType: meta.type,
          isVIP: meta.isVip,
          markerRect: getCampMarkerMorphRect(src),
          data: {
            name: String(camp?.name || 'База отдыха'),
            image: camp?.photo_main ? String(camp.photo_main) : '',
            price: hasPrice ? markerPriceCompact(priceValue) : 'По запросу',
            priceDescription: hasPrice ? 'за человека' : 'стоимость уточняйте',
          },
          onClose: () => {
            requestLeafletCampPopupClose(src);
          },
          onDetails: () => {
            const reopenPopup = () => {
              try { src.openPopup(); } catch(_) {}
            };
            try { src.closePopup(); } catch(_) {}
            openDetails(camp.id, { onBack: reopenPopup });
          },
          onBook: () => {
            try { src.closePopup(); } catch(_) {}
            openBookingFilterWithAuth(camp.id);
          },
        });
      }
    }

    const syncPopupGeometry = () => {
      try { if (e && e.popup && typeof e.popup.update === 'function') e.popup.update(); } catch(_) {}

      const size = map && map.getSize ? map.getSize() : null;
      const popupCont = e && e.popup && e.popup._container ? e.popup._container : cont;
      if (!size) return;
      const h = popupCont ? popupCont.offsetHeight : 260;
      const latlng = e.popup.getLatLng();
      const currentPoint = map.latLngToContainerPoint(latlng);
      const popupAnchorY = Math.abs(
        Number(src && src.options && src.options.icon && src.options.icon.options && src.options.icon.options.popupAnchor
          ? src.options.icon.options.popupAnchor[1]
          : 0) || 0
      );
      const desiredY = clampNumber(
        Math.round((size.y + h) / 2 + popupAnchorY),
        Math.round(h + 20),
        Math.round(size.y - 28)
      );
      const desiredPoint = L.point(
        Math.round(size.x / 2),
        desiredY
      );
      const delta = currentPoint.subtract(desiredPoint);
      if (Math.abs(delta.x) > 4 || Math.abs(delta.y) > 4) {
        const centerPoint = map.project(map.getCenter()).add(delta);
        map.panTo(map.unproject(centerPoint), { animate: true, duration: 0.22 });
      }
    };

    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => requestAnimationFrame(syncPopupGeometry));
    } else {
      setTimeout(syncPopupGeometry, 0);
    }

    // 2) запускаем перебор эмоджи для только что открытого балуна
    if (cont) __startPopupEmojiLoop(cont);
  } catch(_) {}
});

// Чистим таймер, когда балун закрыли
map.on('popupclose', (e) => {
  try {
    const src = e && e.popup ? (e.popup._source || null) : null;
    const closingAnimated = Boolean(src && src.__popupClosing);
    if (src) {
      setCampPopupMarkerHidden(src, false);
    }
    if (!src || src === activeCampMarker) setActiveCampMarker(null);
    const cont = e && e.popup && e.popup._container ? e.popup._container : null;
    const wrap = map && map.getContainer ? map.getContainer().closest('.map-wrap') : null;
    if (wrap) wrap.classList.remove('popup-open');
    try {
      const host = getCampPopupHostFromMarker(src, cont);
      if (host && window.TouristMapPopupWidget && typeof window.TouristMapPopupWidget.unmount === 'function' && !closingAnimated) {
        window.TouristMapPopupWidget.unmount(host);
      }
    } catch(_) {}
    if (src) src.__popupClosing = false;
    if (cont) __stopPopupEmojiLoop(cont);
  } catch(_) {}
});



// ==== AUTH: простая модель на токенах ====
const AUTH_KEY = 'auth_profile';
const AUTH_TOKEN_CLOUD_KEY = 't03_auth_token';
function getAuth(){ try { return JSON.parse(localStorage.getItem(AUTH_KEY) || ''); } catch { return null; } }

function _tgCloud() {
  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg || !tg.CloudStorage) return null;
    return tg.CloudStorage;
  } catch (_) { return null; }
}

function cloudSetToken(token) {
  const cloud = _tgCloud();
  if (!cloud) return;
  try {
    cloud.setItem(AUTH_TOKEN_CLOUD_KEY, String(token || ''), () => {});
  } catch (_) {}
}

function cloudRemoveToken() {
  const cloud = _tgCloud();
  if (!cloud) return;
  try {
    cloud.removeItem(AUTH_TOKEN_CLOUD_KEY, () => {});
  } catch (_) {}
}

function cloudGetToken() {
  return new Promise((resolve) => {
    const cloud = _tgCloud();
    if (!cloud) return resolve('');
    try {
      cloud.getItem(AUTH_TOKEN_CLOUD_KEY, (err, value) => {
        if (err) return resolve('');
        resolve(String(value || ''));
      });
    } catch (_) {
      resolve('');
    }
  });
}

function setAuth(p){
  localStorage.setItem(AUTH_KEY, JSON.stringify(p));
  if (p && p.token) cloudSetToken(p.token);
}
window.__postAuthAction = null;
function runPostAuthAction(){
  const fn = window.__postAuthAction;
  if (typeof fn !== 'function') return;
  window.__postAuthAction = null;
  try { fn(); } catch (e) { console.error('postAuthAction error:', e); }
}
function clearAuth(){
  localStorage.removeItem(AUTH_KEY);
  cloudRemoveToken();
}

// Одноразовый выход по флагу в URL: ?forceLogout=1
(function forceLogoutFromQuery(){
  try {
    const usp = new URLSearchParams(location.search || '');
    if (usp.get('forceLogout') === '1') {
      const cur = getAuth();
      if (cur && cur.token) {
        try {
          fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${cur.token}` }
          }).catch(()=>{});
        } catch (_) {}
      }
      clearAuth();
      // убираем параметр из адресной строки, чтобы не зациклиться
      try {
        const url = new URL(location.href);
        url.searchParams.delete('forceLogout');
        history.replaceState(null, '', url.toString());
      } catch(_) {}
    }
  } catch(_) {}
})();

function renderAccount(){
  const profile = getAuth();
  const guest = document.getElementById('accountGuest');
  const user  = document.getElementById('accountUser');
  const actions = document.getElementById('accountActions');
  const title = document.getElementById('accountTitle');
  const data  = document.getElementById('yourData');
  if (!guest || !user) { return; } // защита: новой разметки может не быть
  guest.style.display = profile ? 'none' : 'block';
  user.style.display  = profile ? 'block' : 'none';
  if (actions) actions.style.display = profile ? 'block' : 'none';
  if (data) data.style.display = 'none';

  const setGreetingTitle = (text, emoji) => {
    if (!title) return;
    title.classList.add('greet-title');
    title.innerHTML = `<span class="greet-core">${escapeHtml(text)}<span class="greet-emoji" aria-hidden="true">${escapeHtml(emoji)}</span></span>`;
  };

  if (profile) {
    const name = profile.user?.name?.split(' ')[0] || 'гость';
    const hr = new Date().getHours();
    const phrase = hr < 6 ? 'Доброй ночи' : hr < 12 ? 'Доброе утро' : hr < 18 ? 'Добрый день' : 'Добрый вечер';
    const emoji  = hr < 6 ? '🌙' : hr < 12 ? '☀️' : hr < 18 ? '🌤️' : '🌙';
    setGreetingTitle(`${phrase}, ${name}!`, emoji);
  } else {
    const hr = new Date().getHours();
    const phrase = hr < 6 ? 'Доброй ночи' : hr < 12 ? 'Доброе утро' : hr < 18 ? 'Добрый день' : 'Добрый вечер';
    const emoji  = hr < 6 ? '🌙' : hr < 12 ? '☀️' : hr < 18 ? '🌤️' : '🌙';
    setGreetingTitle(`${phrase}!`, emoji);
  }
}

function formatPhoneRu(phone){
  const raw = String(phone || '');
  const digits = raw.replace(/\D/g,'');
  if (!digits) return raw;
  let d = digits;
  if (d.length === 11 && d.startsWith('8')) d = '7' + d.slice(1);
  if (d.length === 11 && d.startsWith('7')) {
    return `+7 ${d.slice(1,4)} ${d.slice(4,7)} ${d.slice(7,9)} ${d.slice(9,11)}`;
  }
  return raw;
}

// === showModal / closeModal и формы регистрации/входа (как были) ===
const modal = document.getElementById('modal');
const modalCard = document.getElementById('modalCard');

function closeTransientOverlays({ keepMainModal = false } = {}){
  // Никогда не удаляем основной `#modal` из DOM — иначе сломаются ссылки `modal/modalCard`.
  try {
    document.querySelectorAll('.modal.show').forEach((m) => {
      if (!m || m.id === 'modal') return;
      try { m.remove(); } catch (_) {}
    });
  } catch (_) {}
  if (!keepMainModal) {
    try { closeModal(); } catch (_) {}
  }
}

function closeAllWindows(){
  try { closeTransientOverlays({ keepMainModal: false }); } catch (_) {}
  try {
    document.querySelectorAll('.fs-modal').forEach(el => { try { el.remove(); } catch (_) {} });
  } catch (_) {}
}

function closeAllWindowsAndShowMap(){
  closeAllWindows();
  try { setTabById('tab-map'); } catch (_) {}
  try {
    if (typeof fixMapSize === 'function') fixMapSize();
    if (typeof restoreMapView === 'function') restoreMapView();
  } catch (_) {}
}

function updateModalTallClass(){
  if (!modal || !modalCard) return;
  const vh = window.innerHeight || document.documentElement?.clientHeight || 0;
  if (!vh) return;
  // modal has vertical padding (top+bottom) in CSS
  const available = vh - 36;
  const h = modalCard.scrollHeight || 0;
  modal.classList.toggle('is-tall', h > available);
}

// Fix WebView scroll edge detection - ensure scroll container is never exactly at boundary
function fixScrollEdge(scrollEl){
  if (!scrollEl) return;
  const maxScroll = scrollEl.scrollHeight - scrollEl.clientHeight;
  if (maxScroll <= 0) return;
  // If at exact top, nudge down 1px
  if (scrollEl.scrollTop <= 0) {
    scrollEl.scrollTop = 1;
  }
  // If at exact bottom, nudge up 1px
  else if (scrollEl.scrollTop >= maxScroll) {
    scrollEl.scrollTop = maxScroll - 1;
  }
}

function showModal(html){
  try { delete modalCard.dataset.view; } catch (_) {}
  try { modal.classList.remove('auth-modal'); } catch (_) {}
  modalCard.innerHTML = html;
  modal.style.display = 'flex';
  try { modal.classList.add('show'); } catch (_) {}
  // Reset scroll position
  try { modal.scrollTop = 0; } catch (_) {}
  try {
    if (modalCard.__ro && typeof modalCard.__ro.disconnect === 'function') modalCard.__ro.disconnect();
    modalCard.__ro = null;
  } catch (_) {}
  try {
    if (modalCard.__onResize) window.removeEventListener('resize', modalCard.__onResize);
    modalCard.__onResize = null;
  } catch (_) {}
  updateModalTallClass();
  // After layout, fix scroll edge
  requestAnimationFrame(() => fixScrollEdge(modal));
  if (typeof ResizeObserver === 'function') {
    try {
      modalCard.__ro = new ResizeObserver(() => {
        updateModalTallClass();
        fixScrollEdge(modal);
      });
      modalCard.__ro.observe(modalCard);
    } catch (_) {}
  }
  try {
    modalCard.__onResize = () => updateModalTallClass();
    window.addEventListener('resize', modalCard.__onResize, { passive: true });
  } catch (_) {}
}
function showAuthModal(html){ 
  modalCard.innerHTML = html; 
  modal.style.display = 'flex'; 
  modal.classList.add('auth-modal');
  try { modal.classList.add('show'); } catch (_) {}
  // Reset scroll position
  try { modal.scrollTop = 0; } catch (_) {}
  try {
    if (modalCard.__ro && typeof modalCard.__ro.disconnect === 'function') modalCard.__ro.disconnect();
    modalCard.__ro = null;
  } catch (_) {}
  try {
    if (modalCard.__onResize) window.removeEventListener('resize', modalCard.__onResize);
    modalCard.__onResize = null;
  } catch (_) {}
  updateModalTallClass();
  requestAnimationFrame(() => fixScrollEdge(modal));
  if (typeof ResizeObserver === 'function') {
    try {
      modalCard.__ro = new ResizeObserver(() => {
        updateModalTallClass();
        fixScrollEdge(modal);
      });
      modalCard.__ro.observe(modalCard);
    } catch (_) {}
  }
  try {
    modalCard.__onResize = () => updateModalTallClass();
    window.addEventListener('resize', modalCard.__onResize, { passive: true });
  } catch (_) {}
}

// Setup scroll edge fix on scroll end for WebView
if (modal) {
  try { modal.addEventListener('scrollend', () => fixScrollEdge(modal), { passive: true }); } catch (_) {}
  // Fallback for browsers without scrollend
  let scrollTimeout = null;
  modal.addEventListener('scroll', () => {
    if (scrollTimeout) clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => fixScrollEdge(modal), 150);
  }, { passive: true });
}
function showAuthChoiceModal({ title = 'Необходима авторизация', subtitle = '', onCancel, onLogin, onRegister } = {}){
  const prev = document.getElementById('authChoiceModal');
  if (prev) prev.remove();
  const wrap = document.createElement('div');
  wrap.id = 'authChoiceModal';
  wrap.className = 'modal show';
  wrap.style.zIndex = '9999';
  wrap.innerHTML = `
    <div class="modal-scroll">
      <div class="modal-card auth">
        <div class="auth-card" style="text-align:center">
          <div class="auth-head" style="justify-content:center">
            <div class="auth-title">${escapeHtml(title)}</div>
          </div>
          ${subtitle ? `<div class="auth-subtitle" style="color:#fff;margin:12px 0 16px;line-height:1.5;font-size:15px">${escapeHtml(subtitle)}</div>` : ''}
          <div class="auth-actions" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
            <button class="button primary" id="authChoiceLogin" style="background:#2a9df4;border-color:#2a9df4">Вход</button>
            <button class="button primary" id="authChoiceRegister" style="background:#22c55e;border-color:#22c55e">Регистрация</button>
          </div>
          <button class="button ghost" id="authChoiceCancel" style="width:100%">Отмена</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);

  const scrollEl = wrap.querySelector('.modal-scroll');
  const close = () => { try { wrap.remove(); } catch (_) {} };
  const cancel = () => { close(); try { if (typeof onCancel === 'function') onCancel(); } catch (_) {} };
  if (scrollEl) scrollEl.addEventListener('click', (e) => { if (e.target === scrollEl) cancel(); });
  const btnCancel = wrap.querySelector('#authChoiceCancel');
  const btnLogin = wrap.querySelector('#authChoiceLogin');
  const btnRegister = wrap.querySelector('#authChoiceRegister');
  if (btnCancel) btnCancel.onclick = cancel;
  if (btnLogin) btnLogin.onclick = () => { close(); try { if (typeof onLogin === 'function') onLogin(); } catch (_) {} };
  if (btnRegister) btnRegister.onclick = () => { close(); try { if (typeof onRegister === 'function') onRegister(); } catch (_) {} };
  return { close, cancel };
}

function showConfirmModal({
  title = 'Подтвердите действие',
  message = '',
  confirmText = 'Да',
  cancelText = 'Нет',
  danger = true,
} = {}){
  return new Promise((resolve) => {
    const prev = document.getElementById('appConfirmModal');
    if (prev) prev.remove();

    const wrap = document.createElement('div');
    wrap.id = 'appConfirmModal';
    wrap.className = 'modal show';
    wrap.style.zIndex = '10000';
    wrap.innerHTML = `
      <div class="modal-scroll">
        <div class="modal-card">
          <div class="auth-card" style="text-align:center">
            <div class="auth-head" style="justify-content:center">
              <div class="auth-title">${escapeHtml(title)}</div>
            </div>
            ${message ? `<div class="auth-subtitle" style="margin:8px 0 6px">${escapeHtml(message)}</div>` : ''}
            <div class="auth-actions" style="grid-template-columns: 1fr 1fr;">
              <button type="button" class="button ghost" id="appConfirmNo">${escapeHtml(cancelText)}</button>
              <button type="button" class="button ${danger ? 'danger' : 'primary'}" id="appConfirmYes">${escapeHtml(confirmText)}</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(wrap);

    const scrollEl = wrap.querySelector('.modal-scroll');
    const close = (val) => {
      try { wrap.remove(); } catch (_) {}
      resolve(!!val);
    };
    if (scrollEl) scrollEl.addEventListener('click', (e) => { if (e.target === scrollEl) close(false); });
    const yes = wrap.querySelector('#appConfirmYes');
    const no = wrap.querySelector('#appConfirmNo');
    if (yes) yes.addEventListener('click', () => close(true));
    if (no) no.addEventListener('click', () => close(false));
  });
}

const BOOKING_DRAFT_KEY = 'bookingDraft:v1';
// Multi-cart временно отключён
const MULTI_CART_ENABLED = false;
const BOOKING_MULTI_KEY = 'bookingDraftMulti:v2';
const BOOKING_FILTER_KEY = 'bookingFilter:v1';
window.__bookingDraft = null;
window.__suppressDraftToastOnce = false;
window.__bookingFilter = window.__bookingFilter || null;

function loadBookingFilter(){
  try {
    const raw = localStorage.getItem(BOOKING_FILTER_KEY);
    if (!raw) return null;
    const f = JSON.parse(raw);
    if (!f || typeof f !== 'object') return null;
    const fromRaw = String(f.from || '').trim();
    const toRaw = String(f.to || '').trim();
    const adults = Math.max(0, Number(f.adults) || 0);
    const kids = Math.max(0, Number(f.kids) || 0);
    const allowSplitRooms = !!f.allowSplitRooms;
    if (kids > 0 && adults < 1) return null;

    let from = fromRaw || null;
    let to = toRaw || null;
    if (from && to) {
      const a = new Date(from);
      const b = new Date(to);
      if (!Number.isFinite(a.getTime()) || !Number.isFinite(b.getTime()) || b <= a) {
        from = null;
        to = null;
      }
    } else {
      from = null;
      to = null;
    }

    const total = Number(f.total) || (adults + kids) || 0;
    const hasAny = (from && to) || total > 0 || adults > 0 || kids > 0 || allowSplitRooms;
    if (!hasAny) return null;
    return {
      from,
      to,
      adults,
      kids,
      total: total || undefined,
      allowSplitRooms,
    };
  } catch (_) {
    return null;
  }
}

function saveBookingFilter(filter){
  if (!filter || typeof filter !== 'object') return;
  try { localStorage.setItem(BOOKING_FILTER_KEY, JSON.stringify(filter)); } catch (_) {}
}

function clearBookingFilter(){
  try { localStorage.removeItem(BOOKING_FILTER_KEY); } catch (_) {}
}

// Поднимаем последний фильтр пользователя при перезапуске (если он сам не сбрасывал)
try {
  const persisted = loadBookingFilter();
  if (persisted) window.__bookingFilter = persisted;
} catch (_) {}

function escapeHtml(str){
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function loadBookingDraft(){
  try {
    const raw = localStorage.getItem(BOOKING_DRAFT_KEY);
    if (!raw) { window.__bookingDraft = null; return null; }
    const d = JSON.parse(raw);
    if (!d || typeof d !== 'object') { window.__bookingDraft = null; return null; }
    window.__bookingDraft = d;
    return d;
  } catch (_) {
    window.__bookingDraft = null;
    return null;
  }
}

function loadBookingMultiDraft(){
  if (!MULTI_CART_ENABLED) return null;
  try {
    const raw = localStorage.getItem(BOOKING_MULTI_KEY);
    if (!raw) return null;
    const d = JSON.parse(raw);
    if (!d || typeof d !== 'object') return null;
    // v2: carts identified by key (campId can repeat for different variants)
    if (d.v === 2 || d.activeKey != null) {
      const carts = Array.isArray(d.carts) ? d.carts : [];
      const normalized = carts
        .map(c => ({
          v: 2,
          key: String(c?.key || ''),
          campId: Number(c?.campId),
          campName: String(c?.campName || ''),
          lakeName: String(c?.lakeName || ''),
          label: String(c?.label || ''),
          filter: (c?.filter && typeof c.filter === 'object') ? c.filter : {},
          items: Array.isArray(c?.items) ? c.items : [],
          updatedAt: Number(c?.updatedAt) || 0,
        }))
        .filter(c => c.key && Number.isFinite(c.campId));
      const activeKey = String(d.activeKey || '');
      return {
        v: 2,
        activeKey: activeKey && normalized.some(c => c.key === activeKey) ? activeKey : (normalized[0]?.key ?? ''),
        carts: normalized,
      };
    }

    // v1 migration (if user still has old key) — best-effort
    const carts = Array.isArray(d.carts) ? d.carts : [];
    const normalizedV1 = carts
      .map(c => ({
        campId: Number(c?.campId),
        campName: String(c?.campName || ''),
        lakeName: String(c?.lakeName || ''),
        filter: (c?.filter && typeof c.filter === 'object') ? c.filter : {},
        items: Array.isArray(c?.items) ? c.items : [],
        updatedAt: Number(c?.updatedAt) || 0,
      }))
      .filter(c => Number.isFinite(c.campId));
    const activeCampId = Number(d.activeCampId);
    const normalized = normalizedV1.map(c => ({
      v: 2,
      key: `${Number(c.campId)}:main`,
      campId: Number(c.campId),
      campName: c.campName || '',
      lakeName: c.lakeName || '',
      label: '',
      filter: c.filter || {},
      items: Array.isArray(c.items) ? c.items : [],
      updatedAt: Number(c.updatedAt) || 0,
    }));
    const activeKey = Number.isFinite(activeCampId) ? `${activeCampId}:main` : (normalized[0]?.key ?? '');
    return { v: 2, activeKey, carts: normalized };
  } catch (_) {
    return null;
  }
}

function saveBookingMultiDraft(draft){
  if (!MULTI_CART_ENABLED) return;
  if (!draft || typeof draft !== 'object') return;
  try {
    localStorage.setItem(BOOKING_MULTI_KEY, JSON.stringify(draft));
  } catch (_) {}
}

function syncActiveSingleDraftFromMulti(){
  if (!MULTI_CART_ENABLED) return null;
  const m = loadBookingMultiDraft();
  if (!m || !Array.isArray(m.carts) || m.carts.length === 0) return null;
  const activeKey = String(m.activeKey || '');
  const active = (activeKey && m.carts.find(c => String(c?.key) === activeKey)) || m.carts[0];
  if (!active) return null;
  const single = {
    v: 1,
    campId: Number(active.campId),
    campName: active.campName || '',
    filter: active.filter || {},
    items: Array.isArray(active.items) ? active.items : [],
    updatedAt: Number(active.updatedAt) || Date.now(),
  };
  try {
    window.__bookingDraft = single;
    localStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify(single));
    window.__bookingMultiActiveKey = String(active.key || '');
  } catch (_) {}
  return single;
}

function upsertBookingMultiCart({ campId, campName, lakeName, label, filter, items, key }){
  if (!MULTI_CART_ENABLED) return;
  const cid = Number(campId);
  if (!Number.isFinite(cid)) return;
  const cartKey = String(key || `${cid}:main`);
  const m = loadBookingMultiDraft() || { v: 2, activeKey: cartKey, carts: [] };
  const now = Date.now();
  const carts = Array.isArray(m.carts) ? m.carts.slice() : [];
  const idx = carts.findIndex(c => String(c?.key) === cartKey);
  const prev = idx >= 0 ? carts[idx] : null;
  const next = {
    v: 2,
    key: cartKey,
    campId: cid,
    campName: String(campName || ''),
    lakeName: String(lakeName || ''),
    label: (label != null) ? String(label || '') : String(prev?.label || ''),
    filter: (filter && typeof filter === 'object') ? filter : {},
    items: Array.isArray(items) ? items : [],
    updatedAt: now,
  };
  // ВАЖНО: порядок вкладок должен быть стабильным (без «скачков»).
  // Поэтому НЕ сортируем по updatedAt и не двигаем вкладку при обновлении.
  if (idx >= 0) {
    carts[idx] = { ...carts[idx], ...next };
  } else {
    carts.push(next);
  }

  // Ограничиваем до 6 корзин: если внезапно стало больше — удаляем самую старую по updatedAt.
  while (carts.length > 6) {
    let oldestIdx = 0;
    let oldestAt = Number(carts[0]?.updatedAt) || 0;
    for (let i = 1; i < carts.length; i++) {
      const at = Number(carts[i]?.updatedAt) || 0;
      if (at < oldestAt) { oldestAt = at; oldestIdx = i; }
    }
    carts.splice(oldestIdx, 1);
  }

  const out = { v: 2, activeKey: cartKey, carts };
  saveBookingMultiDraft(out);
  syncActiveSingleDraftFromMulti();
  updateBookingDraftUi();
}

function setActiveBookingMultiCart(idOrKey){
  if (!MULTI_CART_ENABLED) return;
  const asStr = String(idOrKey || '');
  const isKey = asStr.includes(':');
  const cid = isKey ? Number(asStr.split(':')[0]) : Number(idOrKey);
  const key = isKey ? asStr : (Number.isFinite(cid) ? `${cid}:main` : '');
  if (!key) return;
  const m = loadBookingMultiDraft();
  if (!m || !Array.isArray(m.carts) || m.carts.length === 0) return;
  const exists = m.carts.some(c => String(c?.key) === key);
  if (!exists) return;
  m.activeKey = key;
  saveBookingMultiDraft(m);
  syncActiveSingleDraftFromMulti();
  updateBookingDraftUi();
}

function removeBookingMultiCart(idOrKey){
  if (!MULTI_CART_ENABLED) return;
  const asStr = String(idOrKey || '');
  const isKey = asStr.includes(':');
  const cid = isKey ? Number(asStr.split(':')[0]) : Number(idOrKey);
  const key = isKey ? asStr : (Number.isFinite(cid) ? `${cid}:main` : '');
  if (!key) return;
  const m = loadBookingMultiDraft();
  if (!m || !Array.isArray(m.carts)) return;
  const next = m.carts.filter(c => String(c?.key) !== key);
  if (next.length === 0) {
    try { localStorage.removeItem(BOOKING_MULTI_KEY); } catch (_) {}
    return;
  }
  const activeKey = String(m.activeKey || '');
  const newActive = (activeKey === key) ? String(next[0]?.key || '') : activeKey;
  saveBookingMultiDraft({ v: 2, activeKey: newActive, carts: next });
  syncActiveSingleDraftFromMulti();
  updateBookingDraftUi();
}

function saveBookingDraft(draft){
  if (!draft || typeof draft !== 'object') return;
  try {
    window.__bookingDraft = draft;
    localStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify(draft));
    updateBookingDraftUi();
  } catch (_) {}
  // Multi-cart отключён — сохраняем только один черновик
}

function clearBookingDraft(){
  try { localStorage.removeItem(BOOKING_DRAFT_KEY); } catch (_) {}
  window.__bookingDraft = null;
  updateBookingDraftUi();
}

async function confirmReplaceBookingDraftIfDifferentCamp({ nextCampId, nextCampName, willAddRooms } = {}){
  const nextId = Number(nextCampId);
  if (!Number.isFinite(nextId)) return true;
  if (!willAddRooms) return true;

  const cur = window.__bookingDraft || loadBookingDraft();
  const curItems = Array.isArray(cur?.items) ? cur.items : [];
  if (!cur || curItems.length === 0) return true;

  const curId = Number(cur?.campId);
  if (!Number.isFinite(curId) || curId === nextId) return true;

  const curName = String(cur?.campName || '').trim() || `База #${curId}`;
  const nextName = String(nextCampName || '').trim() || `База #${nextId}`;

  const ok = await showConfirmModal({
    title: 'Заменить корзину?',
    message: `Если вы добавите в корзину апартаменты базы «${nextName}», то апартаменты базы «${curName}» будут удалены.`,
    confirmText: 'Добавить в корзину',
    cancelText: 'Отмена',
    danger: true,
  });
  if (!ok) return false;
  clearBookingDraft();
  return true;
}

function updateBookingDraftUi(){
  const btn = document.getElementById('openBookingDraft');
  const badge = document.getElementById('bookingDraftBadge');
  if (!btn) return;
  // Кнопка корзины теперь всегда видна
  btn.style.display = '';
  const d = window.__bookingDraft || loadBookingDraft();
  const has = !!d && Number.isFinite(Number(d.campId));
  if (has && badge) {
    const n = Array.isArray(d.items) ? d.items.length : 0;
    badge.textContent = String(n);
    badge.style.display = n > 0 ? '' : 'none';
    return;
  }
  if (badge) badge.style.display = 'none';
}

function renderBookingMultiTabs({ mountId, activeKey, onSwitch } = {}){
  if (!MULTI_CART_ENABLED) return;
  const el = mountId ? document.getElementById(mountId) : null;
  if (!el) return;
  const m = loadBookingMultiDraft();
  const carts = (m && Array.isArray(m.carts)) ? m.carts : [];
  if (carts.length <= 1) {
    el.innerHTML = '';
    el.style.display = 'none';
    return;
  }
  const aKey = String(activeKey || m?.activeKey || '');

  el.style.display = '';
  el.innerHTML = carts.map(c => {
    const cid = Number(c?.campId);
    const name = escapeHtml(String(c?.campName || 'База'));
    const lake = String(c?.lakeName || '').trim();
    const label = String(c?.label || '').trim();
    const lakeTextRaw = lake ? `озеро ${lake}` : '';
    const subRaw = [lakeTextRaw, label].filter(Boolean).join(' • ');
    const subText = subRaw ? escapeHtml(subRaw) : '';
    const key = String(c?.key || (Number.isFinite(cid) ? `${cid}:main` : ''));
    const isActive = aKey && key && key === aKey;
    return `
      <button type="button" class="multi-tab ${isActive ? 'active' : ''}" data-cart-key="${escapeHtml(key)}">
        <div class="multi-tab-title">${name}</div>
        ${subText ? `<div class="multi-tab-sub">${subText}</div>` : ''}
      </button>
    `;
  }).join('');

  el.querySelectorAll('.multi-tab').forEach((btn) => {
    const cartKey = String(btn.getAttribute('data-cart-key') || '');
    if (!cartKey) return;

    let pressTimer = null;
    let didLongPress = false;
    let ignoreClickUntil = 0;
    let startX = 0;
    let startY = 0;

    const clearTimer = () => {
      if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
    };

    const handleLongPress = async () => {
      didLongPress = true;
      ignoreClickUntil = Date.now() + 800;
      const campName = btn.querySelector('.multi-tab-title')?.textContent || 'База';
      const sub = btn.querySelector('.multi-tab-sub')?.textContent || '';
      const ok = await showConfirmModal({
        title: 'Удалить корзину?',
        message: `Удалить корзину «${campName}${sub ? ' • ' + sub : ''}» со всеми апартаментами?`,
        confirmText: 'Удалить',
        cancelText: 'Отмена',
        danger: true,
      });
      if (ok) {
        removeBookingMultiCart(cartKey);
        updateBookingDraftUi();
        const nm = loadBookingMultiDraft();
        if (nm && Array.isArray(nm.carts) && nm.carts.length > 0) {
          window.__suppressDraftToastOnce = true;
          openBookingDraft({ dontChangeTab: true });
        } else {
          openEmptyBookingConfirmationModal();
        }
      }
    };

    const handleTap = () => {
      if (aKey && cartKey === aKey) return;
      try { setActiveBookingMultiCart(cartKey); } catch (_) {}
      if (typeof onSwitch === 'function') { onSwitch(cartKey); return; }
      try {
        window.__suppressDraftToastOnce = true;
        openBookingDraft({ dontChangeTab: true });
      } catch (_) {}
    };

    // Use Pointer Events to avoid blocking native horizontal scrolling on iOS/Android.
    btn.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      didLongPress = false;
      startX = e.clientX || 0;
      startY = e.clientY || 0;
      clearTimer();
      pressTimer = setTimeout(handleLongPress, 600);
    }, { passive: true });

    btn.addEventListener('pointermove', (e) => {
      if (!pressTimer) return;
      const dx = Math.abs((e.clientX || 0) - startX);
      const dy = Math.abs((e.clientY || 0) - startY);
      // If user starts scrolling/swiping, cancel long press
      if (dx > 8 || dy > 8) clearTimer();
    }, { passive: true });

    btn.addEventListener('pointerup', clearTimer, { passive: true });
    btn.addEventListener('pointercancel', clearTimer, { passive: true });

    btn.addEventListener('click', (e) => {
      if (didLongPress || Date.now() < ignoreClickUntil) { try { e.preventDefault(); } catch (_) {} return; }
      handleTap();
    });
  });
}

function showSnackbar({ message, actionText, onAction, timeoutMs = 4500 } = {}){
  const text = String(message || '').trim();
  if (!text) return;

  const prev = document.getElementById('snackbar');
  if (prev) prev.remove();

  const el = document.createElement('div');
  el.id = 'snackbar';
  el.className = 'snackbar';
  el.innerHTML = `
    <div class="snackbar-text">${escapeHtml(text)}</div>
    ${actionText ? `<button type="button" class="snackbar-action">${escapeHtml(actionText)}</button>` : ''}
  `;
  document.body.appendChild(el);

  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    el.classList.add('hide');
    setTimeout(() => el.remove(), 220);
  };

  const actionBtn = el.querySelector('.snackbar-action');
  if (actionBtn && typeof onAction === 'function') {
    actionBtn.addEventListener('click', (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      close();
      try { onAction(); } catch (_) {}
    });
  }

  el.addEventListener('click', close);
  if (timeoutMs > 0) setTimeout(close, timeoutMs);
}

function showDraftSavedCartToast({ timeoutMs = 1800 } = {}){
  const cartBtn = document.getElementById('openBookingDraft');
  const host = cartBtn?.parentElement;
  if (!cartBtn || !host) {
    showSnackbar({ message: 'Черновик бронирования сохранён', actionText: 'Продолжить', onAction: () => openBookingDraft(), timeoutMs });
    return;
  }

  // cleanup legacy toast element if it exists (older versions)
  try { document.getElementById('bookingDraftToast')?.remove(); } catch (_) {}

  // Ensure toast text span exists inside the cart button
  let textEl = cartBtn.querySelector('.draft-toast-text');
  if (!textEl) {
    textEl = document.createElement('span');
    textEl.className = 'draft-toast-text';
    textEl.setAttribute('aria-hidden', 'true');
    cartBtn.appendChild(textEl);
  }
  textEl.textContent = 'Черновик сохранён';

  // Store previous handler once
  if (!cartBtn.__draftPrevOnclick) {
    cartBtn.__draftPrevOnclick = cartBtn.onclick;
  }

  const close = () => {
    cartBtn.classList.remove('draft-toast');
    cartBtn.setAttribute('aria-label', 'Корзина бронирования');
    if (typeof cartBtn.__draftPrevOnclick === 'function') cartBtn.onclick = cartBtn.__draftPrevOnclick;
  };

  // When toast is active, click opens cart and closes toast (feels like morph back)
  cartBtn.onclick = (e) => {
    try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
    close();
    try { openBookingDraft({ dontChangeTab: true }); } catch (_) { try { openBookingDraft(); } catch (_) {} }
  };

  cartBtn.setAttribute('aria-label', 'Черновик сохранён. Нажмите, чтобы продолжить.');
  // trigger morph animation on the same element
  requestAnimationFrame(() => cartBtn.classList.add('draft-toast'));

  if (cartBtn.__draftToastTimer) { try { clearTimeout(cartBtn.__draftToastTimer); } catch (_) {} }
  cartBtn.__draftToastTimer = setTimeout(() => {
    close();
  }, Math.max(700, Number(timeoutMs) || 1800));
}

async function openBookingDraft(opts = {}){
  let d = window.__bookingDraft || loadBookingDraft();

  const isReadyFilter = (flt) => {
    if (!flt || typeof flt !== 'object') return false;
    if (!flt.from || !flt.to) return false;
    const from = new Date(flt.from);
    const to = new Date(flt.to);
    if (!Number.isFinite(from.getTime()) || !Number.isFinite(to.getTime())) return false;
    if (to <= from) return false;
    const adults = Math.max(0, Number(flt.adults) || 0);
    const kids = Math.max(0, Number(flt.kids) || 0);
    if (adults + kids <= 0) return false;
    if (kids > 0 && adults < 1) return false;
    return true;
  };

  // Если "черновик" пустой и фильтр не настроен — считаем, что бронирование не начинали:
  // не показываем привязку к базе (campName/campId) и открываем пустую корзину.
  if (d) {
    const rawItems = Array.isArray(d.items) ? d.items : [];
    const hasValidItems = rawItems.some(it => Number.isFinite(Number(it?.room_id)));
    if (!hasValidItems && !isReadyFilter(d.filter)) {
      clearBookingDraft();
      d = window.__bookingDraft || loadBookingDraft();
    }
  }

  if (!d) {
    openEmptyBookingConfirmationModal();
    return;
  }

  const cid = Number(d.campId);
  if (!Number.isFinite(cid)) {
    showSnackbar({ message: 'Не выбрана база для бронирования.', timeoutMs: 1800 });
    return;
  }

  if (!opts || !opts.dontChangeTab) {
    try { setTabById('tab-map'); } catch (_) {}
  }

  let camp = null;
  try { camp = await getCampQuick(cid); } catch (_) {}
  if (!camp) camp = { id: cid, name: d.campName || 'База' };

  let roomsAll = [];
  try {
    const data = await fetch(`/api/rooms?camp_id=${cid}`).then(r => r.ok ? r.json() : []);
    roomsAll = Array.isArray(data) ? data : [];
  } catch (_) {}

  const byId = new Map(roomsAll.map(r => [Number(r?.id), r]).filter(([id]) => Number.isFinite(id)));
  const picked = [];
  const initialItems = [];

  const items = Array.isArray(d.items) ? d.items : [];
  for (const it of items) {
    const rid = Number(it?.room_id);
    if (!Number.isFinite(rid)) continue;
    const room = byId.get(rid);
    if (!room) continue;
    picked.push(room);
    initialItems.push({
      room,
      adults: Math.max(0, Number(it?.adults) || 0),
      kids: Math.max(0, Number(it?.kids) || 0),
    });
  }

  if (!picked.length) {
    // Пустая корзина (или удалённые апартаменты) — открываем корзину всё равно
    const filter = d.filter || window.__bookingFilter || {};
    if (items.length > 0) {
      // если в черновике были позиции, но они не найдены — считаем черновик устаревшим
      clearBookingDraft();
      showSnackbar({ message: 'Некоторые апартаменты из черновика недоступны. Корзина очищена.', timeoutMs: 2200 });
    }
    openBookingConfirmationModal({
      camp,
      campId: cid,
      rooms: [],
      filter,
      initialItems: [],
    });
    return;
  }

  openBookingConfirmationModal({
    camp,
    campId: cid,
    rooms: picked,
    filter: d.filter || window.__bookingFilter || {},
    initialItems,
  });
}

function openEmptyBookingConfirmationModal(opts = {}){
  const passed = (opts && typeof opts === 'object') ? opts.filter : null;
  const f = (passed && typeof passed === 'object') ? passed : (window.__bookingFilter || {});

  const dateText = `${fmtDateRu(f.from)} → ${fmtDateRu(f.to)}`;
  const hintText = isBookingFilterReady(f)
    ? 'Теперь выберите базу отдыха на карте и нажмите «Забронировать».'
    : 'Укажите даты и количество гостей, чтобы продолжить бронирование.';

  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); shell.classList.remove('accom-shell'); shell.classList.remove('room-detail-shell'); }

	  showModal(`
	    <div class="alloc-card">
      <div class="accom-head">
        <div class="accom-title">Лист бронирования</div>
        <div class="accom-sub">
          <button type="button" class="bk-input bk-input-inline" id="confirmEditDates">${dateText}</button>
        </div>
      </div>

      <div class="alloc-hint muted" id="confirmHint" style="text-align:center;">${hintText}</div>

      <div class="alloc-list" id="confirmList"></div>

      <button class="button ghost alloc-autopick" id="confirmAutoPick" style="width:100%;margin-top:12px;">Подбор апартаментов для вас</button>

		      <div class="alloc-actions is-row">
		        <button class="button ghost" id="confirmBack">Закрыть корзину</button>
		        <button class="button is-disabled" style="background:#22c55e;border-color:#22c55e;color:#fff;font-weight:600" id="confirmSubmit" aria-disabled="true">БРОНИРУЮ!</button>
		      </div>
		    </div>
		  `);

	  const hintEl = document.getElementById('confirmHint');
	  const editDatesBtn = document.getElementById('confirmEditDates');
	  const backBtn = document.getElementById('confirmBack');
	  const autoPickBtn = document.getElementById('confirmAutoPick');
	  const submitBtn = document.getElementById('confirmSubmit');

		  if (backBtn) backBtn.onclick = () => {
		    closeAllWindowsAndShowMap();
		  };

	  if (submitBtn) {
	    submitBtn.onclick = () => {
	      const cur = window.__bookingFilter || {};
	      if (!isBookingFilterReady(cur)) {
	        markBookingDatesButtonRequired(editDatesBtn);
	        if (hintEl) {
	          hintEl.textContent = 'Укажите даты и количество гостей, чтобы продолжить бронирование.';
	        }
	        return;
	      }
	      showSnackbar({ message: 'Выберите базу отдыха на карте и добавьте апартаменты в корзину или воспользуйтесь подбором в корзине.', timeoutMs: 6500 });
	    };
	  }

  if (autoPickBtn) {
    autoPickBtn.onclick = () => {
      const prev = window.__bookingFilter || {};
      window.__bookingFilter = {
        from: prev.from || null,
        to: prev.to || null,
        adults: Number.isFinite(Number(prev.adults)) ? Number(prev.adults) : 2,
        kids: Number.isFinite(Number(prev.kids)) ? Number(prev.kids) : 0,
        total: Number.isFinite(Number(prev.total)) ? Number(prev.total) : ((Number(prev.adults) || 2) + (Number(prev.kids) || 0)),
        allowSplitRooms: !!prev.allowSplitRooms,
      };
      // Если фильтр уже настроен — сразу подбор
      if (isBookingFilterReady(window.__bookingFilter)) {
        try { openBookingCompareListModal({ filter: window.__bookingFilter }); } catch (_) {}
        return;
      }
      // Иначе сначала показываем фильтр
      openBookingFilterModal({
        mode: 'booking',
        campId: null,
        title: 'Выберите даты и гостей',
        hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем подходящие базы отдыха.',
        applyText: 'Подбор',
        dontCloseBackground: true,
        onApply: () => {
          try { openBookingCompareListModal({ filter: window.__bookingFilter }); } catch (_) {}
        },
      });
    };
  }

  if (editDatesBtn) {
    editDatesBtn.onclick = () => {
      const prev = window.__bookingFilter || {};
      window.__bookingFilter = {
        from: prev.from || null,
        to: prev.to || null,
        adults: Number.isFinite(Number(prev.adults)) ? Number(prev.adults) : 2,
        kids: Number.isFinite(Number(prev.kids)) ? Number(prev.kids) : 0,
        total: Number.isFinite(Number(prev.total)) ? Number(prev.total) : ((Number(prev.adults) || 2) + (Number(prev.kids) || 0)),
        allowSplitRooms: !!prev.allowSplitRooms,
      };

      openBookingFilterModal({
        mode: 'booking',
        campId: null,
        title: 'Выберите даты и гостей',
        hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.',
        applyText: 'Применить',
        dontCloseBackground: true,
        onApply: () => {
          const nf = window.__bookingFilter || {};
          editDatesBtn.textContent = `${fmtDateRu(nf.from)} → ${fmtDateRu(nf.to)}`;
          if (hintEl) {
            hintEl.textContent = isBookingFilterReady(nf)
              ? 'Теперь выберите базу отдыха на карте и нажмите «Забронировать».'
              : 'Укажите даты и количество гостей, чтобы продолжить бронирование.';
          }
        },
      });
    };
  }
}

function allocationToShortText(rooms){
  const by = new Map();
  for (const r of rooms || []) {
    const name = (r.name || r.room_type || 'Вариант').toString().trim() || 'Вариант';
    by.set(name, (by.get(name) || 0) + 1);
  }
  const parts = [];
  for (const [name, cnt] of by.entries()) {
    parts.push(cnt > 1 ? `${cnt}× ${name}` : name);
  }
  return parts.join(' + ');
}

function calculateAutoPickVariantsForRooms(availableRooms, filter){
  const rooms = Array.isArray(availableRooms) ? availableRooms : [];
  const f = (filter && typeof filter === 'object') ? filter : {};
  const totalGuests = (Number(f.adults) || 0) + (Number(f.kids) || 0);
  if (totalGuests <= 0 || rooms.length === 0) return [];
  const allowSplit = !!f.allowSplitRooms;

  const scoreVariant = (variantRooms) => {
    const cnt = (variantRooms || []).length;
    const sumCap = (variantRooms || []).reduce((s, r) => s + (roomCapacity(r) || 0), 0);
    const overcap = Math.max(0, sumCap - totalGuests);
    const price = (variantRooms || []).reduce((s, r) => s + (roomPriceFrom(r) || 0), 0);
    return { cnt, overcap, price };
  };

  // Если split запрещён — ищем лучший одиночный вариант
  const variantsRooms = [];
  if (!allowSplit) {
    const candidates = rooms
      .map(r => ({ r, cap: roomCapacity(r), price: roomPriceFrom(r) || 0 }))
      .filter(x => Number(x.cap) > 0 && Number(x.cap) >= totalGuests);
    candidates.sort((a, b) => (a.cap - b.cap) || ((a.price || 0) - (b.price || 0)));
    if (!candidates.length) return [];
    variantsRooms.push([candidates[0].r]);
  } else {
    const variantsMap = new Map();
    const queue = [new Set()];
    const seenExcl = new Set();

    while (queue.length && variantsMap.size < 8) {
      const excl = queue.shift();
      const exclKey = Array.from(excl).sort((a,b)=>a-b).join(',');
      if (seenExcl.has(exclKey)) continue;
      seenExcl.add(exclKey);

      const pool = rooms.filter(r => !excl.has(Number(r?.id)));
      const best = findBestAllocation(pool, totalGuests);
      if (!best || !best.length) continue;

      const key = best.map(r => Number(r?.id)).filter(Number.isFinite).sort((a,b)=>a-b).join(',');
      if (!key) continue;
      if (!variantsMap.has(key)) {
        variantsMap.set(key, best);
        for (const r of best) {
          const rid = Number(r?.id);
          if (!Number.isFinite(rid)) continue;
          const next = new Set(excl);
          next.add(rid);
          if (next.size <= 4) queue.push(next);
        }
      }
    }

    const all = Array.from(variantsMap.values());
    all.sort((a, b) => {
      const sa = scoreVariant(a);
      const sb = scoreVariant(b);
      if (sa.cnt !== sb.cnt) return sa.cnt - sb.cnt;
      if (sa.overcap !== sb.overcap) return sa.overcap - sb.overcap;
      return sa.price - sb.price;
    });
    all.forEach(v => variantsRooms.push(v));
  }

  const variants = [];
  for (const vr of variantsRooms) {
    const items = autoDistributeGuests(vr, f);
    const v = validateAllocation(items, f);
    if (!v.ok) continue;
    if (v.totalPrice == null) continue;
    variants.push({
      rooms: vr,
      totalPrice: v.totalPrice,
      text: allocationToShortText(vr),
      roomsCount: vr.length,
    });
  }

  variants.sort((a, b) => (a.totalPrice - b.totalPrice) || (a.roomsCount - b.roomsCount));
  return variants.slice(0, 3);
}

async function openBookingCompareListModal({ filter } = {}){
  const f = (filter && typeof filter === 'object') ? filter : (window.__bookingFilter || {});
  if (!isBookingFilterReady(f)) {
    showSnackbar({ message: 'Сначала выберите даты и гостей.', timeoutMs: 2000 });
    return;
  }

  const dateText = `${fmtDateRu(f.from)} → ${fmtDateRu(f.to)}`;
  const guestsText = `Гостей: ${(Number(f.adults) || 0) + (Number(f.kids) || 0)} (взр: ${Number(f.adults) || 0}, дети: ${Number(f.kids) || 0})`;
  const totalGuests = (Number(f.adults) || 0) + (Number(f.kids) || 0);
  const nights = bookingNightsFromFilter(f);
  const hintText = `Выберите базу для размещения <strong>${totalGuests}</strong> ${pluralRu(totalGuests, 'гостя', 'гостей', 'гостей')} на <strong>${nights}</strong> ${pluralRu(nights, 'сутки', 'суток', 'суток')}.`;

  showModal(`
    <div class="alloc-card">
      <div class="accom-head">
        <div class="accom-title">Подбор вариантов</div>
        <div class="accom-sub">
          <span class="muted">${dateText}</span> • <span class="muted">${guestsText}</span>
        </div>
      </div>

      <div class="alloc-hint muted" style="text-align:center;">${hintText}</div>
      <div class="compare-list" id="compareCampsList">
        <div class="muted" style="text-align:center;padding:18px 0;">Подбираем варианты…</div>
      </div>

      <div class="alloc-actions">
        <button class="button ghost" id="compareBack">Назад</button>
        <button class="button primary" id="compareGoCart" disabled>Перейти в корзину</button>
      </div>
    </div>
  `);

  const backBtn = document.getElementById('compareBack');
  if (backBtn) backBtn.onclick = () => { openEmptyBookingConfirmationModal(); };
  const goCartBtn = document.getElementById('compareGoCart');

  const listEl = document.getElementById('compareCampsList');
  if (!listEl) return;

  const mapLimit = async (arr, limit, fn) => {
    const a = Array.isArray(arr) ? arr : [];
    const n = Math.max(1, Math.min(Number(limit) || 1, a.length || 1));
    let i = 0;
    const out = new Array(a.length);
    const workers = Array.from({ length: n }, async () => {
      while (true) {
        const idx = i;
        i += 1;
        if (idx >= a.length) break;
        try { out[idx] = await fn(a[idx], idx); } catch (_) { out[idx] = null; }
      }
    });
    await Promise.all(workers);
    return out;
  };

  let camps = [];
  try {
    const res = await fetch('/api/camps');
    const all = res.ok ? await res.json() : [];
    camps = Array.isArray(all) ? all : [];
    try {
      window.__campsById = Object.fromEntries((camps || []).map(c => [Number(c.id), c]).filter(([id]) => Number.isFinite(id)));
    } catch (_) {}
  } catch (_) {
    camps = [];
  }

  const activeCamps = camps.filter(c => (c.status || 'active') === 'active');
  if (activeCamps.length === 0) {
    listEl.innerHTML = '<div class="muted" style="text-align:center;padding:18px 0;">Нет доступных баз для подбора.</div>';
    return;
  }

  const q = new URLSearchParams({ from: f.from, to: f.to });
  const results = await mapLimit(activeCamps, 4, async (camp) => {
    const cid = Number(camp?.id);
    if (!Number.isFinite(cid)) return null;
    let rooms = [];
    try {
      const resp = await fetch(`/api/camps/${cid}/available-rooms?${q.toString()}`).then(r => r.ok ? r.json() : null);
      const allRooms = Array.isArray(resp?.rooms) ? resp.rooms : [];
      rooms = allRooms.filter(r => r && r.available);
    } catch (_) {
      rooms = [];
    }
    if (!rooms.length) return null;
    const variants = calculateAutoPickVariantsForRooms(rooms, f);
    if (!variants.length) return null;
    const cheapest = Math.min(...variants.map(v => Number(v.totalPrice) || Infinity));
    return { camp, variants, cheapest };
  });

  const usable = results.filter(Boolean);
  usable.sort((a, b) => (a.cheapest - b.cheapest));

  if (usable.length === 0) {
    listEl.innerHTML = '<div class="muted" style="text-align:center;padding:18px 0;">Не найдено подходящих вариантов размещения.</div>';
    return;
  }

  const variantKey = (rooms) =>
    (rooms || [])
      .map(r => Number(r?.id))
      .filter(Number.isFinite)
      .sort((a, b) => a - b)
      .join(',');

  listEl.innerHTML = usable.map((r) => {
    const camp = r.camp || {};
    const cid = Number(camp.id);
    const name = escapeHtml(camp.name || 'База');
    const lake = String(camp.lake_name || '').trim();
    const lakeText = lake ? ` (озеро ${escapeHtml(lake)})` : '';
    const housing = housingLabelTitle(camp.housing_type);
    const variantsHtml = (r.variants || []).map((v, idx) => {
      const priceText = formatPriceRub(v.totalPrice);
      const text = escapeHtml(v.text || '');
      const key = escapeHtml(String(idx));
      const vKey = escapeHtml(variantKey(v.rooms));
      return `
        <div class="compare-variant" data-variant-idx="${key}">
          <div class="compare-variant-main">
            <div class="compare-variant-text">${text}</div>
            <div class="compare-variant-price">${priceText}</div>
          </div>
          <button type="button" class="button ghost compare-toggle" data-camp-id="${cid}" data-variant-key="${vKey}" data-variant-idx="${key}">В корзину</button>
        </div>
      `;
    }).join('');
    return `
      <div class="card compare-camp" data-camp-id="${cid}">
        <div class="compare-camp-title">${name}${lakeText}</div>
        <div class="compare-variants">${variantsHtml}</div>
      </div>
    `;
  }).join('');

  // Открытие карточки базы по нажатию на карточку (кроме кнопок)
  listEl.querySelectorAll('.compare-camp[data-camp-id]').forEach(card => {
    card.addEventListener('click', async (e) => {
      const t = e.target;
      if (t instanceof HTMLElement) {
        if (t.closest('button')) return; // не мешаем выбору варианта
      }
      const cid = Number(card.getAttribute('data-camp-id'));
      if (!Number.isFinite(cid)) return;
      const row = usable.find(x => Number(x?.camp?.id) === cid);
      if (!row) return;
      closeModal(); // закрываем список подбора
      await openCompareCampDetails({
        campId: cid,
        camp: row.camp,
        variants: Array.isArray(row.variants) ? row.variants : [],
        filter: f,
        onBackToCompare: () => openBookingCompareListModal({ filter: f }),
      });
    });
  });

  // Мультикорзина временно отключена: можно выбрать только один вариант
  if (!MULTI_CART_ENABLED) {
    let selectedKey = '';
    let selected = null; // { campId, camp, variant }

    const getKey = (cid, rooms, vKeyRaw) => {
      const k = String(vKeyRaw || '').trim();
      if (k) return `${cid}:${k}`;
      return `${cid}:${variantKey(rooms)}`;
    };

    const refreshSelectionUiSingle = () => {
      if (goCartBtn) {
        goCartBtn.disabled = !selected;
        goCartBtn.textContent = selected ? 'Перейти в корзину (1)' : 'Перейти в корзину';
      }
      listEl.querySelectorAll('.compare-toggle').forEach(btn => {
        const cid = Number(btn.getAttribute('data-camp-id'));
        const vKey = String(btn.getAttribute('data-variant-key') || '');
        const selKey = getKey(cid, null, vKey);
        const isSelected = !!selected && selKey === selectedKey;
        btn.textContent = isSelected ? 'Убрать из корзины' : 'В корзину';
        btn.classList.toggle('compare-remove', isSelected);
      });
    };

    refreshSelectionUiSingle();

    if (goCartBtn) {
      goCartBtn.onclick = async () => {
        if (!selected || !selected.variant) return;
        const cid = Number(selected.campId);
        if (!Number.isFinite(cid)) return;
        let campData = null;
        try { campData = await getCampQuick(cid); } catch (_) {}
        if (!campData) campData = selected.camp || { id: cid, name: 'База' };
        openBookingConfirmationModal({
          camp: campData,
          campId: cid,
          rooms: Array.isArray(selected.variant.rooms) ? selected.variant.rooms : [],
          filter: f,
          onBack: () => openBookingCompareListModal({ filter: f }),
        });
      };
    }

    listEl.querySelectorAll('.compare-toggle').forEach(btn => {
      btn.onclick = () => {
        const cid = Number(btn.getAttribute('data-camp-id'));
        const vidx = Number(btn.getAttribute('data-variant-idx'));
        const vKeyRaw = String(btn.getAttribute('data-variant-key') || '');
        if (!Number.isFinite(cid) || !Number.isFinite(vidx)) return;
        const row = usable.find(x => Number(x?.camp?.id) === cid);
        const variant = row?.variants?.[vidx];
        if (!row || !variant) return;

        const key = getKey(cid, variant.rooms, vKeyRaw);
        if (selected && key === selectedKey) {
          selected = null;
          selectedKey = '';
          refreshSelectionUiSingle();
          return;
        }

        if (selected && key !== selectedKey) {
          showSnackbar({ message: 'Мультикорзина временно отключена — выбранный вариант заменён.', timeoutMs: 1800 });
        }

        selected = { campId: cid, camp: row.camp, variant };
        selectedKey = key;
        refreshSelectionUiSingle();
      };
    });

    return;
  }

  const getMulti = () => loadBookingMultiDraft();
  const getCartKey = (cart) =>
    (Array.isArray(cart?.items) ? cart.items : [])
      .map(it => Number(it?.room_id))
      .filter(Number.isFinite)
      .sort((a, b) => a - b)
      .join(',');

  const refreshSelectionUi = () => {
    const m = getMulti();
    const carts = (m && Array.isArray(m.carts)) ? m.carts : [];
    const selected = carts.filter(c => c && Number.isFinite(Number(c.campId)));
    const count = selected.length;
    if (goCartBtn) {
      goCartBtn.disabled = count === 0;
      goCartBtn.textContent = count > 0 ? `Перейти в корзину (${count})` : 'Перейти в корзину';
    }

    const selectedKeys = new Set(selected.map(c => String(c?.key || '')).filter(Boolean));

    listEl.querySelectorAll('.compare-toggle').forEach(btn => {
      const cid = Number(btn.getAttribute('data-camp-id'));
      const vKey = String(btn.getAttribute('data-variant-key') || '');
      const selKey = `${cid}:${vKey}`;
      const isSelected = selectedKeys.has(selKey);
      btn.textContent = isSelected ? 'Убрать из корзины' : 'В корзину';
      btn.classList.toggle('compare-remove', isSelected);
    });
  };

  refreshSelectionUi();

  if (goCartBtn) {
    goCartBtn.onclick = () => {
      const m = getMulti();
      if (!m || !Array.isArray(m.carts) || m.carts.length === 0) return;
      try {
        syncActiveSingleDraftFromMulti();
        window.__suppressDraftToastOnce = true;
        openBookingDraft({ dontChangeTab: true });
      } catch (_) {}
    };
  }

  listEl.querySelectorAll('.compare-toggle').forEach(btn => {
    btn.onclick = () => {
      const cid = Number(btn.getAttribute('data-camp-id'));
      const vidx = Number(btn.getAttribute('data-variant-idx'));
      const vKey = String(btn.getAttribute('data-variant-key') || '');
      if (!Number.isFinite(cid) || !Number.isFinite(vidx)) return;
      const row = usable.find(x => Number(x?.camp?.id) === cid);
      const variant = row?.variants?.[vidx];
      if (!row || !variant) return;

      const selKey = `${cid}:${vKey || getCartKey({ items: variant.rooms.map(r => ({ room_id: r?.id })) })}`;

      const m = getMulti();
      const carts = (m && Array.isArray(m.carts)) ? m.carts : [];
      const existing = carts.find(c => String(c?.key) === selKey) || null;

      // Toggle off if already selected (exact variant)
      if (existing) {
        removeBookingMultiCart(selKey);
        refreshSelectionUi();
        return;
      }

      // Enforce max 6 selections (total carts)
      if (carts.length >= 6) {
        showSnackbar({ message: 'Можно выбрать до 6 вариантов для сравнения.', timeoutMs: 2200 });
        return;
      }

      const distributed = autoDistributeGuests(variant.rooms, f);
      const itemsForDraft = distributed
        .map(it => ({
          room_id: Number(it?.room?.id),
          adults: Number(it?.adults) || 0,
          kids: Number(it?.kids) || 0,
        }))
        .filter(it => Number.isFinite(it.room_id));

      upsertBookingMultiCart({
        campId: cid,
        campName: row.camp?.name || '',
        lakeName: row.camp?.lake_name || '',
        label: variant.text || '',
        key: selKey,
        filter: {
          from: f.from || null,
          to: f.to || null,
          adults: Number(f.adults) || 0,
          kids: Number(f.kids) || 0,
          total: Number(f.total) || ((Number(f.adults) || 0) + (Number(f.kids) || 0)) || undefined,
          allowSplitRooms: !!f.allowSplitRooms,
        },
        items: itemsForDraft,
      });
      setActiveBookingMultiCart(selKey);
      refreshSelectionUi();
    };
  });
}

function uniqueRoomsFromVariants(variants){
  const byId = new Map();
  for (const v of variants || []) {
    const rooms = Array.isArray(v?.rooms) ? v.rooms : [];
    for (const r of rooms) {
      const id = Number(r?.id);
      if (!Number.isFinite(id)) continue;
      if (!byId.has(id)) byId.set(id, r);
    }
  }
  return Array.from(byId.values());
}

async function openCompareCampRoomsModal({ camp, rooms, variants, filter, initialVariantIndex, onClose } = {}){
  const cid = Number(camp?.id);
  const f = (filter && typeof filter === 'object') ? filter : (window.__bookingFilter || {});
  const nights = bookingNightsFromFilter(f);
  const totalGuests = (Number(f.adults) || 0) + (Number(f.kids) || 0);
  const stayText = `${totalGuests} ${pluralRu(totalGuests, 'гостя', 'гостей', 'гостей')} • ${nights} ${pluralRu(nights, 'сутки', 'суток', 'суток')}`;

  let campData = camp || null;
  if (!campData && Number.isFinite(cid)) {
    try { campData = await getCampQuick(cid); } catch (_) {}
  }
  if (!campData) campData = { id: cid, name: 'База', housing_type: 'apartments' };

  const variantsRaw = Array.isArray(variants) ? variants : [];
  const hasVariants = variantsRaw.length > 0;
  const fallbackRooms = Array.isArray(rooms) ? rooms : [];
  const variantsList = hasVariants
    ? variantsRaw
        .filter(v => Array.isArray(v?.rooms) && v.rooms.length)
        .map(v => ({ rooms: v.rooms, totalPrice: v.totalPrice, text: v.text }))
    : [{ rooms: fallbackRooms, totalPrice: null, text: '' }];

  const totalVariants = variantsList.length;
  const initialIdx = Math.max(0, Math.min(totalVariants - 1, Number(initialVariantIndex) || 0));
  let activeIdx = initialIdx;

  showModal(`
    <div class="accom-card">
      <div class="accom-head">
        <div class="accom-title">${escapeHtml(campData.name || 'База')} • Подобранные варианты</div>
        <div class="accom-sub">${stayText}</div>
      </div>
      ${totalVariants > 1 ? `<div class="compare-variant-tabs" id="compareVariantTabs"></div>` : ''}
      <div class="accom-list" id="compareRoomsList"></div>
      <div class="accom-actions">
        <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff;font-weight:600" id="compareRoomsSelect">Выбрать этот вариант</button>
        <button class="button ghost" id="compareRoomsBack">Назад</button>
      </div>
    </div>
  `);

  const listEl = document.getElementById('compareRoomsList');
  const backBtn = document.getElementById('compareRoomsBack');
  const selectBtn = document.getElementById('compareRoomsSelect');
  if (backBtn) {
    backBtn.onclick = () => {
      closeModal();
      if (typeof onClose === 'function') onClose();
    };
  }
  if (selectBtn) {
    selectBtn.onclick = async () => {
      const currentVariant = variantsList[activeIdx] || variantsList[0] || { rooms: [] };
      const roomsNow = Array.isArray(currentVariant.rooms) ? currentVariant.rooms : [];
      if (!roomsNow.length) {
        showSnackbar({ message: 'В этом варианте нет апартаментов.', timeoutMs: 1800 });
        return;
      }
      try {
        await openBookingConfirmationModal({
          camp: campData,
          campId: cid,
          rooms: roomsNow,
          filter: f,
          onBack: () => openCompareCampRoomsModal({
            camp: campData,
            variants: variantsList,
            filter: f,
            initialVariantIndex: activeIdx,
            onClose,
          }),
        });
      } catch (_) {}
    };
  }
  if (!listEl) return;

  const tabsEl = document.getElementById('compareVariantTabs');

  const renderTabs = () => {
    if (!tabsEl) return;
    tabsEl.innerHTML = variantsList.map((v, idx) => {
      const priceText = (v && v.totalPrice != null) ? formatPriceRub(v.totalPrice) : '—';
      const cls = idx === activeIdx ? 'compare-variant-tab active' : 'compare-variant-tab';
      return `
        <button type="button" class="${cls}" data-vidx="${idx}">
          <span>Вариант ${idx + 1}</span>
          <span class="sub">${priceText}</span>
        </button>
      `;
    }).join('');

    tabsEl.querySelectorAll('.compare-variant-tab[data-vidx]').forEach(btn => {
      btn.onclick = () => {
        const idx = Number(btn.getAttribute('data-vidx'));
        if (!Number.isFinite(idx)) return;
        if (idx === activeIdx) return;
        activeIdx = idx;
        renderTabs();
        renderRooms();
      };
    });
  };

  const renderRooms = () => {
    const current = variantsList[activeIdx] || variantsList[0] || { rooms: [] };
    const listRooms = Array.isArray(current.rooms) ? current.rooms : [];
    if (!listRooms.length) {
      listEl.innerHTML = '<div class="muted" style="text-align:center;padding:18px 0;">Нет подходящих апартаментов.</div>';
      return;
    }

    listEl.innerHTML = listRooms.map((room) => {
      const photos = Array.isArray(room?.photos) ? room.photos : [];
      const cover = photos.find(p => p && p.cover) || photos[0];
      const thumbUrl = cover?.url || '/static/uploads/temp/placeholder.jpg';
      const cap = roomCapacity(room);
      const beds = formatBedsInfo(room);
      const price = roomPriceFrom(room) || 0;
      const priceText = price > 0 ? `${formatPriceRub(price)}/сутки` : '—';
      const bedsLine = beds ? `<div class="accom-meta">Спальные места: ${escapeHtml(beds)}</div>` : '';
      return `
        <button class="accom-item" data-room-id="${Number(room.id)}" style="text-align:left">
          <img class="accom-thumb" src="${thumbUrl}" alt="">
          <div class="accom-main">
            <div class="accom-name">${escapeHtml(room.class || room.name || room.room_type || 'Апартамент')}</div>
            <div class="accom-meta">до ${cap || '?'} гостей • ${priceText}</div>
            ${bedsLine}
          </div>
        </button>
      `;
    }).join('');

    listEl.querySelectorAll('.accom-item[data-room-id]').forEach(btn => {
      btn.onclick = () => {
        const rid = Number(btn.getAttribute('data-room-id'));
        const currentVariant = variantsList[activeIdx] || variantsList[0] || { rooms: [] };
        const roomsNow = Array.isArray(currentVariant.rooms) ? currentVariant.rooms : [];
        const room = roomsNow.find(r => Number(r?.id) === rid);
        if (!room) return;
        openRoomDetails(room, campData, {
          viewOnly: true,
          onBack: () => openCompareCampRoomsModal({
            camp: campData,
            variants: variantsList,
            filter: f,
            initialVariantIndex: activeIdx,
            onClose,
          }),
        });
      };
    });
  };

  renderTabs();
  renderRooms();
}

async function openCompareCampDetails({ campId, camp, variants, filter, onBackToCompare } = {}){
  const cid = Number(campId);
  if (!Number.isFinite(cid)) return;
  const v = Array.isArray(variants) ? variants : [];
  const modal = await openDetails(cid, { showBookInGallery: false });
  if (!modal) return;

  const actions = modal.querySelector('.actions');
  if (!actions) return;
  const buttons = Array.from(actions.querySelectorAll('button'));

  // remove "Забронировать"
  for (const b of buttons) {
    if (String(b.textContent || '').toLowerCase().includes('забронировать')) {
      try { b.remove(); } catch (_) {}
      break;
    }
  }

  // find housing button (primary)
  const housingBtn = actions.querySelector('button.primary');
  if (housingBtn) {
    housingBtn.textContent = 'Подбор апартаментов на этой базе';
    housingBtn.onclick = (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      openCompareCampRoomsModal({
        camp: { ...(camp || {}), id: cid },
        variants: v,
        filter,
        onClose: () => {}, // просто закрываем список, база остается открытой
      });
    };
  }

  // replace back button
  const backBtn = Array.from(actions.querySelectorAll('button')).find(b => String(b.textContent || '').toLowerCase().includes('назад'));
  if (backBtn) {
    backBtn.textContent = 'К списку подбора баз';
    backBtn.onclick = (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      try { modal.remove(); } catch (_) {}
      if (typeof onBackToCompare === 'function') onBackToCompare();
    };
  }
}

function closeModal(){
  const modal = document.getElementById('modal');
  const card  = document.getElementById('modalCard');
  const view = card?.dataset?.view || '';
  const shouldDraftToast = view === 'booking-confirmation' && !!(window.__bookingDraft || loadBookingDraft()) && !window.__suppressDraftToastOnce;
	if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('auth-modal');
    modal.classList.remove('show');
    modal.classList.remove('is-tall');
  }
	if (card) {
		  // снимаем ResizeObserver, если он был повешен
		  if (card.__ro && typeof card.__ro.disconnect === 'function') {
		    try { card.__ro.disconnect(); } catch(_) {}
		    card.__ro = null;
		  }
      if (card.__onResize) {
        try { window.removeEventListener('resize', card.__onResize); } catch (_) {}
        card.__onResize = null;
      }
		  try { delete card.dataset.view; } catch(_) {}
		  card.innerHTML = '';
		  card.classList.remove('booking-shell');  // снимаем «узкую» оболочку
		  card.classList.remove('details');       // снимаем «детали», если открывали карточку номера
      card.classList.remove('accom-shell');
      card.classList.remove('room-detail-shell');
		 }
  if (shouldDraftToast) {
    showDraftSavedCartToast({ timeoutMs: 1800 });
  }
  window.__suppressDraftToastOnce = false;
}

// Click on scroll overlay (not card) closes modal
// Use event delegation on modal element for robustness
if (modal) {
  modal.addEventListener('click', (e) => {
    // Check if clicked on modal-scroll (not on modal-card or its children)
    const scroll = modal.querySelector('.modal-scroll');
    if (scroll && e.target === scroll) {
      closeModal();
    }
  });
}

const TEST_VERIFY_CODE = '0000';
function showAuthError(message){
  const el = document.getElementById('authError');
  if (!el) { if (message) alert(message); return; }
  el.textContent = message || '';
  el.style.display = message ? 'block' : 'none';
}

const TERMS_VERSION = '2026-01-04';
const TERMS_TEXT = `
Пользовательское соглашение (версия ${TERMS_VERSION})
Дата вступления в силу: ${TERMS_VERSION}

1. Термины и определения
1.1. «Сервис» — веб‑приложение/сайт «Турист_03» и его функционал.
1.2. «Оператор/Администрация Сервиса» — лицо, обеспечивающее работу Сервиса.
1.3. «Пользователь» — физическое лицо, использующее Сервис.
1.4. «Поставщик» — база отдыха/объект размещения и/или иное третье лицо, оказывающее услуги Пользователю.

2. Предмет и роль Сервиса (агрегатор/посредник)
2.1. Сервис является информационным агрегатором и технологическим посредником: помогает Пользователю найти предложения Поставщиков и оформить заявку/бронирование.
2.2. Сервис не является исполнителем услуг размещения/отдыха/питания/трансфера и иных услуг Поставщиков, не контролирует качество и безопасность таких услуг и не несёт за них ответственности.
2.3. Договор(ы) об оказании услуг заключаются напрямую между Пользователем и соответствующим Поставщиком. Все претензии по услугам (качество, безопасность, возвраты, отмены, штрафы, претензии третьих лиц и т. п.) Пользователь предъявляет Поставщику.
2.4. Сервис не является туроператором/турагентом и не оказывает туристические услуги.

3. Регистрация и использование
3.1. Для доступа к отдельным функциям требуется регистрация и подтверждение телефона и/или e‑mail. В тестовом режиме подтверждение может быть имитационным.
3.2. Пользователь обязуется указывать достоверные данные и поддерживать их актуальность.
3.3. Пользователь отвечает за сохранность устройства и доступа к аккаунту, а также за все действия, совершённые с его аккаунта.

4. Платежи
4.1. Оплата услуг Поставщиков может осуществляться через интерфейс Сервиса с использованием платёжных провайдеров. Денежные средства вносятся Пользователем в счёт оплаты услуг Поставщика; Сервис обеспечивает технологическое взаимодействие (передачу статусов/подтверждений) и не является кредитной/банковской организацией.
4.2. Сервис может отображать статусы оплаты (включая «оплата наличными»), установленные Поставщиком/его администратором. Пользователь понимает, что такие статусы формируются на основании данных, полученных от Поставщиков и/или платёжных провайдеров.
4.3. Условия возвратов, отмен и штрафов определяются Поставщиком и/или правилами платёжного провайдера.

5. Отказ от ответственности и ограничение ответственности
5.1. Сервис предоставляется «как есть». Сервис не гарантирует бесперебойную работу, отсутствие ошибок, соответствие ожиданиям Пользователя, а также актуальность и полноту информации, предоставляемой Поставщиками.
5.2. Сервис не несёт ответственности за:
— качество/безопасность/соответствие услуг Поставщиков описанию;
— действия/бездействие Поставщиков и третьих лиц;
— любые убытки, вред, расходы и иные последствия, возникшие у Пользователя в связи с оказанием/неоказанием услуг Поставщиком.
5.3. В максимально допустимой законом мере Пользователь соглашается, что любые требования (включая судебные) по услугам Поставщиков и последствиям их оказания/неоказания не должны адресоваться Оператору/Администрации Сервиса, а подлежат предъявлению Поставщику.

6. Персональные данные и согласие на обработку/передачу
6.1. Пользователь даёт согласие на обработку персональных данных Оператором Сервиса (сбор, хранение, систематизацию, использование, уточнение, передачу), в том числе с использованием автоматизированных средств, в целях предоставления функционала Сервиса, оформления и сопровождения бронирований, связи с Пользователем и выполнения обязательств по заявкам/бронированиям.
6.2. Пользователь понимает и соглашается, что для оформления/исполнения бронирования Сервис вправе передавать персональные данные Пользователя Поставщикам и иным третьим лицам (включая платёжные сервисы, службы уведомлений, колл‑центры), когда это необходимо для исполнения заявки/бронирования.
6.3. Пользователь подтверждает, что без такой передачи данных исполнение заявки/бронирования может быть невозможно. Пользователь также соглашается с обработкой данных Поставщиками как самостоятельными операторами персональных данных.

7. Ограничения
7.1. Запрещается использовать Сервис для незаконных целей, вмешательства в работу Сервиса, попыток несанкционированного доступа, распространения вредоносного ПО и иных действий, нарушающих права третьих лиц.
7.2. Сервис вправе ограничить доступ Пользователя при нарушении условий настоящего Соглашения.

8. Изменение условий
8.1. Сервис вправе изменять Соглашение. Новая редакция вступает в силу с момента публикации/обновления в Сервисе, если не указано иное.
8.2. Продолжение использования Сервиса после изменения Соглашения означает согласие Пользователя с новой редакцией.

9. Заключительные положения
9.1. Споры по услугам Поставщиков подлежат урегулированию между Пользователем и Поставщиком.
9.2. По вопросам работы Сервиса Пользователь может обратиться в поддержку, указанную в приложении.

Устанавливая галочку «Я согласен(на) с Пользовательским соглашением», Пользователь подтверждает, что прочитал(а), понял(а) и принимает условия настоящего Соглашения.
`.trim();

function normalizePhoneInputValue(raw, opts){
  const o = (opts && typeof opts === 'object') ? opts : {};
  const v = String(raw || '');
  const trimmed = v.trim();
  if (!trimmed) return '';

  const compact = trimmed.replace(/[^\d+]/g, '');
  const hasPlus = compact.startsWith('+');
  const digitsOnly = hasPlus ? compact.slice(1).replace(/\D/g, '') : compact.replace(/\D/g, '');
  if (!digitsOnly) return hasPlus ? '+' : '';

  // default normalization (keep previous behavior)
  let normalized = '';
  if (hasPlus) {
    let d = digitsOnly;
    if (d.startsWith('8')) d = '7' + d.slice(1);
    normalized = '+' + d;
  } else {
    const d = digitsOnly;
    if (d.startsWith('8')) normalized = '+7' + d.slice(1);
    else if (d.startsWith('9')) normalized = '+7' + d;
    else if (d.startsWith('7')) normalized = '+7' + d.slice(1);
    else normalized = d;
  }

  if (o.requireRuMobile9) {
    let d = normalized.replace(/[^\d]/g, '');
    if (!d) return '';
    if (d.startsWith('8')) d = '7' + d.slice(1);
    if (d.startsWith('9')) d = '7' + d;
    if (!d.startsWith('7')) d = '7';
    // После +7 допускаются только мобильные номера: первая цифра должна быть 9
    if (d.length >= 2 && d[1] !== '9') d = '7';
    return '+' + d;
  }

  return normalized;
}

function attachPhoneAutoPrefix(input, opts){
  if (!input || input.__phoneMaskAttached) return;
  input.__phoneMaskAttached = true;
  const handler = () => {
    const next = normalizePhoneInputValue(input.value, opts);
    if (next !== input.value) {
      input.value = next;
      try { input.setSelectionRange(next.length, next.length); } catch(_) {}
    }
  };
  input.addEventListener('input', handler);
  input.addEventListener('blur', handler);
  handler();
}

function isRuMobilePhoneComplete(phone){
  const v = String(phone || '').trim();
  return /^\+79\d{9}$/.test(v);
}

function openTerms(draft){
  const d = draft || {};
  showModal(`
    <div class="auth-card">
      <div class="auth-head">
        <div class="auth-title">Пользовательское соглашение</div>
      </div>
      <div class="auth-subtitle">Прочитайте условия перед регистрацией.</div>
      <div id="terms_text" style="white-space:pre-wrap;max-height:55vh;overflow:auto;border:1px solid var(--border-color);border-radius:14px;padding:12px;background:rgba(255,255,255,0.03);font-size:13px;line-height:1.45;"></div>
      <div class="auth-actions">
        <button class="button ghost" id="terms_back">Назад</button>
        <button class="button primary" id="terms_ok">Согласен</button>
      </div>
    </div>
  `);
  const termsEl = document.getElementById('terms_text');
  if (termsEl) termsEl.textContent = TERMS_TEXT;
  document.getElementById('terms_back').onclick = ()=> openRegister(d);
  document.getElementById('terms_ok').onclick = ()=> openRegister(Object.assign({}, d, { viewed_terms:true, accept_terms:true }));
}

function openRegister(draft){
  const d = draft || {};
  showModal(`
    <div class="auth-card">
      <div class="auth-head">
        <div class="auth-title">Регистрация</div>
        <div class="auth-step">Шаг 1 из 3</div>
      </div>
      <div class="auth-subtitle">Заполните данные для входа в личный кабинет.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Имя и фамилия</span>
          <input id="reg_name" type="text" placeholder="Например: Иван Петров" value="${String(d.name||'').replace(/\"/g,'&quot;')}">
        </label>
        <label class="auth-field">
          <span>Номер телефона</span>
          <input id="reg_phone" type="tel" inputmode="tel" placeholder="+7 9XX XXX-XX-XX" value="${String(d.phone||'').replace(/\"/g,'&quot;')}">
        </label>
        <label class="auth-field">
          <span>Email (необязательно)</span>
          <input id="reg_email" type="email" inputmode="email" placeholder="name@example.com" value="${String(d.email||'').replace(/\"/g,'&quot;')}">
        </label>
        <div class="auth-terms">
          <input id="reg_terms" type="checkbox" ${d.accept_terms ? 'checked' : ''}>
          <div class="auth-terms-text">
            Я согласен(на) с <span class="auth-terms-link" id="reg_terms_link">Пользовательским соглашением</span>
          </div>
        </div>
      </div>
      <div class="auth-error" id="authError" style="display:none;"></div>
      <div class="auth-actions">
        <button class="button ghost" id="reg_cancel">Отмена</button>
        <button class="button primary" id="reg_submit">Продолжить</button>
      </div>
      <div class="auth-note">Email нужен для отправки квитанций об оплате. Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);

  attachPhoneAutoPrefix(document.getElementById('reg_phone'), { requireRuMobile9: true });
  const link = document.getElementById('reg_terms_link');
  if (link) link.onclick = () => {
    const name  = document.getElementById('reg_name').value.trim();
    const phone = document.getElementById('reg_phone').value.trim();
    const email = document.getElementById('reg_email').value.trim();
    const accept_terms = document.getElementById('reg_terms').checked;
    openTerms({ name, phone, email, accept_terms });
  };
  document.getElementById('reg_cancel').onclick = closeModal;
  document.getElementById('reg_submit').onclick = async () => {
    showAuthError('');
    const name  = document.getElementById('reg_name').value.trim();
    const phone = document.getElementById('reg_phone').value.trim();
    const email = document.getElementById('reg_email').value.trim();
    const accept_terms = document.getElementById('reg_terms').checked;
    if (!name || !phone) { showAuthError('Заполните имя и телефон'); return; }
    if (!isRuMobilePhoneComplete(phone)) { showAuthError('Телефон должен начинаться с +79 (мобильный номер РФ)'); return; }
    if (!accept_terms) { showAuthError('Нужно принять пользовательское соглашение'); return; }

    const res = await fetch('/api/auth/register/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name, phone, email: email || null, accept_terms })
    });
    if (!res.ok) {
      const err = await res.json().catch(()=>({}));
      showAuthError(err.detail || 'Ошибка: не удалось отправить код');
      return;
    }
    try { localStorage.setItem('last_cred', JSON.stringify({ name, phone, email })); } catch(_) {}
    showRegisterVerifyPhone(phone, email);
  };
}

function showRegisterVerifyPhone(phone, email){
  const stepText = email ? 'Шаг 2 из 3' : 'Шаг 2 из 2';
  showModal(`
    <div class="auth-card">
      <div class="auth-head">
        <div class="auth-title">Подтверждение телефона</div>
        <div class="auth-step">${stepText}</div>
      </div>
      <div class="auth-subtitle">Мы отправили код на номер ${phone}.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Код из SMS</span>
          <input id="v_phone_code" class="auth-code" inputmode="numeric" autocomplete="one-time-code" placeholder="1234">
        </label>
      </div>
      <div class="auth-error" id="authError" style="display:none;"></div>
      <div class="auth-actions">
        <button class="button ghost" id="v_phone_cancel">Отмена</button>
        <button class="button primary" id="v_phone_ok">Подтвердить</button>
      </div>
      <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);

  document.getElementById('v_phone_cancel').onclick = closeModal;
  document.getElementById('v_phone_ok').onclick = async () => {
    showAuthError('');
    const code = document.getElementById('v_phone_code').value.trim();
    const vres = await fetch('/api/auth/register/verify-phone', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ phone, code })
    });
    if (!vres.ok) {
      const err = await vres.json().catch(()=>({}));
      showAuthError(err.detail || 'Неверный код');
      return;
    }
    const data = await vres.json().catch(()=>({}));
  if (data && data.token && data.user) {
    setAuth({ token: data.token, user: data.user });
    closeModal();
    renderAccount();
    runPostAuthAction();
    return;
  }
    if (!email) {
      showAuthError('Регистрация завершена, но не удалось получить профиль. Попробуйте войти.');
      return;
    }
    showRegisterVerifyEmail(phone, email);
  };
}

function showRegisterVerifyEmail(phone, email){
  showModal(`
    <div class="auth-card">
      <div class="auth-head">
        <div class="auth-title">Подтверждение email</div>
        <div class="auth-step">Шаг 3 из 3</div>
      </div>
      <div class="auth-subtitle">Мы отправили код на адрес ${email}. Email нужен для отправки квитанций об оплате.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Код из письма</span>
          <input id="v_email_code" class="auth-code" inputmode="numeric" autocomplete="one-time-code" placeholder="1234">
        </label>
      </div>
      <div class="auth-error" id="authError" style="display:none;"></div>
      <div class="auth-actions">
        <button class="button ghost" id="v_email_skip">Пропустить</button>
        <button class="button primary" id="v_email_ok">Завершить</button>
      </div>
      <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);

  document.getElementById('v_email_skip').onclick = async () => {
    showAuthError('');
    const res = await fetch('/api/auth/register/skip-email', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ phone })
    });
    if (!res.ok) {
      const err = await res.json().catch(()=>({}));
      showAuthError(err.detail || 'Не удалось пропустить');
      return;
    }
    const data = await res.json().catch(()=>({}));
  if (data && data.token && data.user) {
    setAuth({ token: data.token, user: data.user });
    closeModal();
    renderAccount();
    runPostAuthAction();
    return;
  }
    showAuthError('Не удалось завершить регистрацию. Попробуйте ещё раз.');
  };
  document.getElementById('v_email_ok').onclick = async () => {
    showAuthError('');
    const code = document.getElementById('v_email_code').value.trim();
    const vres = await fetch('/api/auth/register/verify-email', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ email, code })
    });
    if (!vres.ok) {
      const err = await vres.json().catch(()=>({}));
      showAuthError(err.detail || 'Неверный код');
      return;
    }
    const data = await vres.json().catch(()=>({}));
  if (data && data.token && data.user) {
    setAuth({ token: data.token, user: data.user });
    closeModal();
    renderAccount();
    runPostAuthAction();
    return;
  }
    showAuthError('Не удалось завершить регистрацию. Попробуйте ещё раз или нажмите «Пропустить».');
  };
}

// Вход
function openLogin(){
  showModal(`
    <div class="auth-card">
      <div class="auth-head">
        <div class="auth-title">Вход</div>
        <div class="auth-step">Шаг 1 из 2</div>
      </div>
      <div class="auth-subtitle">Введите номер телефона для входа.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Телефон</span>
          <input id="l_phone" type="tel" inputmode="tel" placeholder="+7 9XX XXX-XX-XX" />
        </label>
      </div>
      <div class="auth-error" id="authError" style="display:none;"></div>
      <div class="auth-actions" id="loginNotFoundActions" style="display:none;grid-template-columns:1fr">
        <button class="button primary" id="l_register">Регистрация</button>
      </div>
      <div class="auth-actions">
        <button class="button ghost" id="l_cancel">Отмена</button>
        <button class="button primary" id="l_start">Получить код</button>
      </div>
      <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);

  const phoneInput = document.getElementById('l_phone');
  const notFoundActions = document.getElementById('loginNotFoundActions');
  const regBtn = document.getElementById('l_register');

  attachPhoneAutoPrefix(phoneInput, { requireRuMobile9: true });
  document.getElementById('l_cancel').onclick = closeModal;

  if (phoneInput) {
    phoneInput.addEventListener('input', () => {
      showAuthError('');
      if (notFoundActions) notFoundActions.style.display = 'none';
    });
  }

  if (regBtn) {
    regBtn.onclick = () => {
      const phone = (phoneInput?.value || '').trim();
      openRegister({ phone });
    };
  }

  document.getElementById('l_start').onclick = async () => {
    showAuthError('');
    if (notFoundActions) notFoundActions.style.display = 'none';
    const phone = document.getElementById('l_phone').value.trim();
    if (!phone) { showAuthError('Введите телефон'); return; }
    if (!isRuMobilePhoneComplete(phone)) { showAuthError('Телефон должен начинаться с +79 (мобильный номер РФ)'); return; }
    const res = await fetch('/api/auth/login/start', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ phone })
    });
    if (!res.ok) {
      const err = await res.json().catch(()=>({}));
      const detail = String(err.detail || err.message || '').trim();
      const isNotFound = res.status === 404 || /не\s*найден/i.test(detail);
      if (isNotFound) {
        showAuthError('Пользователь не найден. Проверьте введённый номер или зарегистрируйтесь.');
        if (notFoundActions) notFoundActions.style.display = 'grid';
      } else {
        showAuthError(detail || 'Ошибка: не удалось отправить код');
      }
      return;
    }
    showLoginVerify(phone);
  };
}

function showLoginVerify(phone){
  showModal(`
    <div class="auth-card">
      <div class="auth-head">
        <div class="auth-title">Код из SMS</div>
        <div class="auth-step">Шаг 2 из 2</div>
      </div>
      <div class="auth-subtitle">Введите код, отправленный на ${phone}.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Код</span>
          <input id="lc_code" class="auth-code" inputmode="numeric" autocomplete="one-time-code" placeholder="1234" />
        </label>
      </div>
      <div class="auth-error" id="authError" style="display:none;"></div>
      <div class="auth-actions">
        <button class="button ghost" id="lc_cancel">Отмена</button>
        <button class="button primary" id="lc_ok">Войти</button>
      </div>
      <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);

  document.getElementById('lc_cancel').onclick = closeModal;
  document.getElementById('lc_ok').onclick = async () => {
    showAuthError('');
    const code = document.getElementById('lc_code').value.trim();
    const vres = await fetch('/api/auth/login/verify', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ phone, code })
    });
    if (!vres.ok) {
      const err = await vres.json().catch(()=>({}));
      showAuthError(err.detail || 'Неверный код');
      return;
    }
    const data = await vres.json();
    setAuth({ token: data.token, user: data.user });
    closeModal();
    renderAccount();
    runPostAuthAction();
  };
}

function getAuthToken(){
  const a = getAuth();
  return a && a.token ? String(a.token) : '';
}

async function authFetchJson(url, options = {}){
  const token = getAuthToken();
  const headers = Object.assign({}, options.headers || {});
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, Object.assign({}, options, { headers }));
  let data = null;
  try { data = await res.json(); } catch(_) {}
  if (res.status === 401) {
    clearAuth();
    renderAccount();
  }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) ? (data.detail || data.message) : `Ошибка (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

function requireAuth(){
  const a = getAuth();
  if (!a || !a.token) {
    openLogin();
    return false;
  }
  return true;
}

function bookingStatusLabel(status){
  const s = String(status || '').toLowerCase();
  if (s === 'pending' || s === 'new') return 'В обработке';
  if (s === 'confirmed') return 'Подтверждено';
  if (s === 'awaiting_payment') return 'Ожидает оплаты';
  if (s === 'cancelled_by_user') return 'Отменена вами';
  if (s === 'rejected') return 'Отклонена администратором';
  if (s === 'completed') return 'Закончена';
  if (s === 'cancelled') return 'Отменена';
  return status || '—';
}

function paymentStatusLabel(status){
  const s = String(status || '').toLowerCase();
  if (s === 'paid') return 'Оплачено';
  if (s === 'cash') return 'Оплата наличными';
  return 'Не оплачено';
}

function fmtDateRu(d){
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('ru-RU'); } catch(_) { return String(d); }
}

async function openAccountBookings(mode){
  if (!requireAuth()) return;
  const title = mode === 'history' ? 'История бронирований' : 'Активные бронирования';
  let items = [];
  try {
    const data = await authFetchJson(`/api/auth/orders?mode=${encodeURIComponent(mode)}`);
    items = Array.isArray(data.items) ? data.items : [];
  } catch (e) {
    showModal(`
      <div class="auth-card">
        <div class="auth-head"><div class="auth-title">${title}</div></div>
        <div class="auth-error" style="display:block;">${e.message}</div>
        <div class="auth-actions">
          <button class="button primary" id="bk_list_close">Закрыть</button>
        </div>
      </div>
    `);
    document.getElementById('bk_list_close').onclick = closeModal;
    return;
  }

  const rows = items.length ? items.map(b=>{
    const st = bookingStatusLabel(b.status);
    const pay = paymentStatusLabel(b.payment_status);
    const canPay = String(b.status||'').toLowerCase() === 'confirmed' && !!b.payment_required && String(b.payment_status||'').toLowerCase() === 'unpaid';
    const roomsCount = Array.isArray(b.items) ? b.items.length : 0;
    return `
      <div class="booking-item" data-oid="${String(b.order_id || '')}">
        <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
          <div style="font-weight:800">${b.camp_name || `База #${b.camp_id}`}</div>
          <div class="muted" style="white-space:nowrap">${fmtDateRu(b.check_in)} → ${fmtDateRu(b.check_out)}</div>
        </div>
        <div class="muted" style="margin-top:6px;display:flex;gap:10px;flex-wrap:wrap">
          ${roomsCount ? `<span>Апартаментов: <b style="color:#e6eaf0">${roomsCount}</b></span>` : ''}
          <span>Статус: <b style="color:#e6eaf0">${st}</b></span>
          <span>Оплата: <b style="color:#e6eaf0">${pay}</b></span>
          ${canPay ? '<span style="color:#22c55e;font-weight:700">доступна оплата</span>' : ''}
        </div>
      </div>
    `;
  }).join('') : `<div class="muted">Пока ничего нет.</div>`;

  showModal(`
    <div class="auth-card">
      <div class="auth-head"><div class="auth-title">${title}</div></div>
      <div class="auth-subtitle">Нажмите на бронь, чтобы открыть детали.</div>
      <div class="auth-fields" style="gap:12px">
        ${rows}
      </div>
      <div class="auth-actions">
        <button class="button primary" id="bk_list_close">Закрыть</button>
      </div>
    </div>
  `);
  document.getElementById('bk_list_close').onclick = closeModal;
  document.querySelectorAll('.booking-item').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const id = el.getAttribute('data-oid');
      if (!id) return;
      await openBookingDetail(id, mode);
    });
  });
}

async function openBookingDetail(orderId, mode){
  let item = null;
  try {
    const oid = encodeURIComponent(String(orderId || ''));
    const data = await authFetchJson(`/api/auth/orders/${oid}`);
    item = data.item;
  } catch (e) {
    showModal(`
      <div class="auth-card">
        <div class="auth-head"><div class="auth-title">Бронь</div></div>
        <div class="auth-error" style="display:block;">${e.message}</div>
        <div class="auth-actions">
          <button class="button primary" id="bk_det_close">Закрыть</button>
        </div>
      </div>
    `);
    document.getElementById('bk_det_close').onclick = closeModal;
    return;
  }

  const stRaw = String(item.status || '').toLowerCase();
  const payRaw = String(item.payment_status || '').toLowerCase();
  const st = bookingStatusLabel(item.status);
  const pay = paymentStatusLabel(item.payment_status);

  const canCancel = ['pending','confirmed','awaiting_payment',''].includes(stRaw);
  const canPay = stRaw === 'confirmed' && !!item.payment_required && payRaw === 'unpaid';
  const canEdit = canCancel && payRaw !== 'paid';

  const roomLines = Array.isArray(item.items) && item.items.length
    ? item.items.map((r)=>{
      const rn = r.room_name || (r.room_id ? `#${r.room_id}` : '—');
      const gc = (r.guests_count ?? '—');
      return `<div class="kv-k">${rn}</div><div>${gc}</div>`;
    }).join('')
    : `<div class="kv-k">—</div><div></div>`;

  showModal(`
    <div class="auth-card">
      <div class="auth-head"><div class="auth-title">Бронь</div></div>
      <div class="auth-fields" style="gap:10px">
        <div class="kv">
          <div class="kv-k">База</div><div>${item.camp_name || `База #${item.camp_id}`}</div>
          <div class="kv-k">Даты</div><div>${fmtDateRu(item.check_in)} → ${fmtDateRu(item.check_out)}</div>
          <div class="kv-k">Гостей</div><div>${item.guests_count ?? '—'}</div>
          <div class="kv-k">Статус</div><div>${st}</div>
          <div class="kv-k">Оплата</div><div>${pay}${item.payment_required && payRaw==='unpaid' ? ' (ожидается)' : ''}</div>
          <div class="kv-k" style="margin-top:10px">Апартаменты</div><div></div>
          ${roomLines}
        </div>
      </div>
      <div class="auth-actions" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        <button class="button ghost" id="bk_det_back">Назад</button>
        <button class="button primary" id="bk_det_close">Закрыть</button>
      </div>
      ${(canEdit || canCancel) ? `
        <div class="auth-actions" style="grid-template-columns:repeat(2,minmax(0,1fr))">
          ${canEdit ? `<button class="button ghost" id="bk_det_edit">Редактировать</button>` : `<div></div>`}
          ${canCancel ? `<button class="button ghost" id="bk_det_cancel">Отменить</button>` : `<div></div>`}
        </div>
      ` : ''}
      ${canPay ? `
        <div class="auth-actions" style="grid-template-columns:1fr">
          <button class="button primary" id="bk_det_pay">Оплатить</button>
        </div>
      ` : ''}
    </div>
  `);

  document.getElementById('bk_det_close').onclick = closeModal;
  document.getElementById('bk_det_back').onclick = ()=> openAccountBookings(mode);
  const btnCancel = document.getElementById('bk_det_cancel');
  const btnPay = document.getElementById('bk_det_pay');
  const btnEdit = document.getElementById('bk_det_edit');
  if (btnEdit) btnEdit.onclick = ()=> openOrderEdit(item, mode);
  if (btnCancel) btnCancel.onclick = async ()=>{
    if (!safeConfirm('Отменить бронь?')) return;
    try {
      const oid = encodeURIComponent(String(item.order_id || orderId || ''));
      await authFetchJson(`/api/auth/orders/${oid}/cancel`, { method:'POST' });
      await openAccountBookings(mode);
    } catch (e) { alert(e.message); }
  };
  if (btnPay) btnPay.onclick = async ()=>{
    try {
      const oid = encodeURIComponent(String(item.order_id || orderId || ''));
      await authFetchJson(`/api/auth/orders/${oid}/pay`, { method:'POST' });
      alert('Запрос на оплату создан. Интеграция оплаты будет добавлена позже.');
    } catch (e) { alert(e.message); }
  };
}

function openOrderEdit(order, mode){
  const oidRaw = String(order.order_id || '');
  showModal(`
    <div class="auth-card">
      <div class="auth-head"><div class="auth-title">Редактирование брони</div></div>
      <div class="auth-subtitle">Изменения применятся ко всем апартаментам в этой брони.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Заезд</span>
          <input id="oe_from" type="date" value="${order.check_in || ''}">
        </label>
        <label class="auth-field">
          <span>Выезд</span>
          <input id="oe_to" type="date" value="${order.check_out || ''}">
        </label>
        <label class="auth-field">
          <span>Комментарий</span>
          <input id="oe_comment" value="${String(order.comment||'').replace(/\"/g,'&quot;')}" placeholder="Например: поздний заезд">
        </label>
      </div>
      <div class="auth-actions" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        <button class="button ghost" id="oe_cancel">Отмена</button>
        <button class="button primary" id="oe_save">Сохранить</button>
      </div>
    </div>
  `);

  document.getElementById('oe_cancel').onclick = ()=> openBookingDetail(oidRaw, mode);
  document.getElementById('oe_save').onclick = async ()=>{
    const payload = {
      check_in: document.getElementById('oe_from').value || null,
      check_out: document.getElementById('oe_to').value || null,
      comment: document.getElementById('oe_comment').value || null,
    };
    try {
      const oid = encodeURIComponent(String(oidRaw || ''));
      await authFetchJson(`/api/auth/orders/${oid}`, {
        method:'PUT',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload),
      });
      await openBookingDetail(oidRaw, mode);
    } catch (e) { alert(e.message); }
  };
}

function openBookingEdit(item, mode){
  showModal(`
    <div class="auth-card">
      <div class="auth-head"><div class="auth-title">Редактирование брони</div></div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Заезд</span>
          <input id="be_from" type="date" value="${item.check_in || ''}">
        </label>
        <label class="auth-field">
          <span>Выезд</span>
          <input id="be_to" type="date" value="${item.check_out || ''}">
        </label>
        <label class="auth-field">
          <span>Гостей</span>
          <input id="be_guests" inputmode="numeric" value="${item.guests_count ?? ''}" placeholder="2">
        </label>
        <label class="auth-field">
          <span>Комментарий</span>
          <input id="be_comment" value="${String(item.comment||'').replace(/\"/g,'&quot;')}" placeholder="Например: поздний заезд">
        </label>
      </div>
      <div class="auth-actions">
        <button class="button ghost" id="be_cancel">Отмена</button>
        <button class="button primary" id="be_save">Сохранить</button>
      </div>
    </div>
  `);
  document.getElementById('be_cancel').onclick = ()=> openBookingDetail(item.id, mode);
  document.getElementById('be_save').onclick = async ()=>{
    const payload = {
      check_in: document.getElementById('be_from').value || null,
      check_out: document.getElementById('be_to').value || null,
      guests_count: Number(document.getElementById('be_guests').value || 0) || null,
      comment: document.getElementById('be_comment').value || null,
    };
    try {
      await authFetchJson(`/api/auth/bookings/${item.id}`, {
        method:'PUT',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload),
      });
      await openBookingDetail(item.id, mode);
    } catch (e) { alert(e.message); }
  };
}

async function openAccountProfile(){
  if (!requireAuth()) return;
  let me = null;
  try {
    const data = await authFetchJson('/api/auth/me');
    me = data.user;
  } catch (e) {
    alert(e.message);
    return;
  }
  showModal(`
    <div class="auth-card">
      <div class="auth-head"><div class="auth-title">Личные данные</div></div>
      <div class="auth-subtitle">Изменения телефона и email требуют подтверждения.</div>
      <div class="auth-fields">
        <label class="auth-field">
          <span>Имя и фамилия</span>
          <input id="pf_name" value="${String(me.name||'').replace(/\"/g,'&quot;')}" placeholder="Иван Петров">
        </label>
        <label class="auth-field">
          <span>Телефон</span>
          <input id="pf_phone" type="tel" inputmode="tel" value="${me.phone||''}" placeholder="+7 9XX XXX-XX-XX">
        </label>
        <label class="auth-field">
          <span>Email (необязательно)</span>
          <input id="pf_email" type="email" inputmode="email" value="${me.email||''}" placeholder="name@example.com">
        </label>
      </div>
      <div class="auth-actions">
        <button class="button ghost" id="pf_back">Назад</button>
        <button class="button primary" id="pf_save" disabled>Сохранить</button>
      </div>
      <button class="button" id="pf_logout_btn" style="width:100%;margin-top:12px;background:transparent;border:2px solid #ef4444;color:#ef4444;font-weight:700;">Выйти из аккаунта</button>
      <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);
  attachPhoneAutoPrefix(document.getElementById('pf_phone'));

  const origName = me.name || '';
  const origPhone = me.phone || '';
  const origEmail = me.email || '';
  const nameInput = document.getElementById('pf_name');
  const phoneInput = document.getElementById('pf_phone');
  const emailInput = document.getElementById('pf_email');
  const saveBtn = document.getElementById('pf_save');

  const checkChanges = () => {
    const hasChanges = nameInput.value !== origName || phoneInput.value !== origPhone || emailInput.value !== origEmail;
    saveBtn.disabled = !hasChanges;
  };

  nameInput.addEventListener('input', checkChanges);
  phoneInput.addEventListener('input', checkChanges);
  emailInput.addEventListener('input', checkChanges);

  document.getElementById('pf_back').onclick = () => closeModal();

  document.getElementById('pf_logout_btn').onclick = async ()=>{
    if (!safeConfirm('Вы уверены, что хотите выйти из аккаунта?')) return;
    try { await authFetchJson('/api/auth/logout', { method:'POST' }); } catch(_) {}
    clearAuth(); closeModal(); renderAccount();
  };

  document.getElementById('pf_save').onclick = async ()=>{
    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const email = emailInput.value.trim();
    try {
      const resp = await authFetchJson('/api/auth/profile', {
        method:'PUT',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ name, phone, email: email || null }),
      });
      const auth = getAuth() || {};
      setAuth({ token: auth.token, user: resp.user });
      renderAccount();

      if (resp.need_phone_verify) {
        await showProfileVerifyPhone(phone);
      }
      if (resp.need_email_verify && email) {
        await showProfileVerifyEmail(email);
      }
      closeModal();
      alert('Данные сохранены.');
    } catch (e) {
      alert(e.message);
    }
  };
}

function showProfileVerifyPhone(phone){
  return new Promise((resolve)=>{
    showModal(`
      <div class="auth-card">
        <div class="auth-head"><div class="auth-title">Подтверждение телефона</div></div>
        <div class="auth-subtitle">Введите код, отправленный на ${phone}.</div>
        <div class="auth-fields">
          <label class="auth-field"><span>Код из SMS</span><input id="pv_code" class="auth-code" inputmode="numeric" autocomplete="one-time-code" placeholder="1234"></label>
        </div>
        <div class="auth-actions">
          <button class="button ghost" id="pv_cancel">Отмена</button>
          <button class="button primary" id="pv_ok">Подтвердить</button>
        </div>
        <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
      </div>
    `);
    document.getElementById('pv_cancel').onclick = ()=>{ closeModal(); resolve(); };
    document.getElementById('pv_ok').onclick = async ()=>{
      const code = document.getElementById('pv_code').value.trim();
      try {
        const resp = await authFetchJson('/api/auth/profile/verify-phone', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ phone, code })
        });
        const auth = getAuth() || {};
        setAuth({ token: auth.token, user: resp.user });
        renderAccount();
        closeModal();
      } catch (e) { alert(e.message); return; }
      resolve();
    };
  });
}

function showProfileVerifyEmail(email){
  return new Promise((resolve)=>{
    showModal(`
      <div class="auth-card">
        <div class="auth-head"><div class="auth-title">Подтверждение email</div></div>
        <div class="auth-subtitle">Введите код, отправленный на ${email}.</div>
        <div class="auth-fields">
          <label class="auth-field"><span>Код из письма</span><input id="pe_code" class="auth-code" inputmode="numeric" autocomplete="one-time-code" placeholder="1234"></label>
        </div>
        <div class="auth-actions">
          <button class="button ghost" id="pe_skip">Пропустить</button>
          <button class="button primary" id="pe_ok">Подтвердить</button>
        </div>
        <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
      </div>
    `);
    document.getElementById('pe_skip').onclick = async ()=>{
      try {
        const auth = getAuth();
        if (auth && auth.user) {
          await authFetchJson('/api/auth/profile', {
            method:'PUT',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ email: null })
          });
        }
      } catch(_) {}
      closeModal();
      resolve();
    };
    document.getElementById('pe_ok').onclick = async ()=>{
      const code = document.getElementById('pe_code').value.trim();
      try {
        const resp = await authFetchJson('/api/auth/profile/verify-email', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ email, code })
        });
        const auth = getAuth() || {};
        setAuth({ token: auth.token, user: resp.user });
        renderAccount();
        closeModal();
      } catch (e) { alert(e.message); return; }
      resolve();
    };
  });
}

// Пример: сохранение e-mail (оставляю как было, код не менял)
// const btnSaveEmail = document.getElementById('btnSaveEmail');
// if (btnSaveEmail) btnSaveEmail.addEventListener('click', saveEmail);


async function loadCamps() {
  try {
    // 1) Базы
    const res = await fetch('/api/camps');
    if (!res.ok) throw new Error('Ошибка загрузки баз');
    const camps = await res.json();
    try {
      window.__campsById = Object.fromEntries((camps || []).map(c => [Number(c.id), c]).filter(([id]) => Number.isFinite(id)));
    } catch(_) {}
    const itemsActive = camps.filter(c => (c.status || 'active') === 'active');

    // 2) Комнаты (одним запросом для всех баз)
    let roomsByCamp = {};
    const roomsResp = await fetch('/api/rooms/all');
    if (roomsResp.ok) {
      const allRooms = await roomsResp.json();
      roomsByCamp = allRooms.reduce((acc, r) => {
        (acc[r.camp_id] ||= []).push(r);
        return acc;
      }, {});
    }

    // Вспомогательные функции для проверки доступности по датам
    const parseD = (s)=> s ? new Date(s) : null;
    const overlap = (aStart, aEnd, bStart, bEnd) => {
      if (!aStart || !aEnd || !bStart || !bEnd) return true; // если нет дат — считаем пересечением по «неизвестности»
      return (aStart <= bEnd) && (bStart <= aEnd);
    };
    // Норма людей в комнате (взрослые + дети, если явно указано; иначе capacity/ beds/ max/2)
    const roomCapacity = (r) => {
      if (Number.isFinite(r.adults) || Number.isFinite(r.kids)) {
        return (Number(r.adults)||0) + (Number(r.kids)||0);
      }
      return Number(r.capacity || r.beds || r.max || 2);
    };
    // Сколько юнитов у комнаты (сколько одинаковых номеров), по умолчанию 1
    const roomUnits = (r) => Number(r.count || 1);

    // Считаем, сколько юнитов комнаты занято в заданный период
    function countBookedUnits(r, fFrom, fTo) {
      // Пытаемся «угадать» формат данных о бронях
      const ranges =
        r.bookings || r.reservations || r.busy_ranges || r.busy || r.orders || [];

      if (!Array.isArray(ranges) || ranges.length === 0) return 0;

      let used = 0;
      for (const b of ranges) {
        // поддержка разных вариантов полей
        const bFrom = parseD(b.from || b.start || b.date_from || b.checkin);
        const bTo   = parseD(b.to   || b.end   || b.date_to   || b.checkout);
        if (!bFrom || !bTo) continue;

        if (overlap(fFrom, fTo, bFrom, bTo)) {
          // сколько юнитов съедает бронь
          const u = Number(b.units || b.count || 1);
          used += u;
        }
      }
      return used;
    }

    // Проверка: хватает ли свободных мест в лагере на диапазон и людей
    function campHasAvailability(camp, f) {
      const rooms = roomsByCamp[camp.id] || [];
      if (!rooms.length) return false;

      // если нет дат — фильтруем только по общей вместимости
      const fFrom = parseD(f.from);
      const fTo   = parseD(f.to);

      let totalCapacity = 0;
      for (const r of rooms) {
        const units = roomUnits(r);
        const capPerUnit = roomCapacity(r);

        let freeUnits = units;
        // если есть даты и есть информация о бронях — считаем свободные юниты
        if (fFrom && fTo && (r.bookings || r.reservations || r.busy_ranges || r.busy || r.orders)) {
          const booked = countBookedUnits(r, fFrom, fTo);
          freeUnits = Math.max(0, units - booked);
        }
        // если нет данных о бронях — считаем все юниты свободными
        totalCapacity += freeUnits * capPerUnit;
        if (totalCapacity >= f.total) return true; // ранний выход
      }
      return totalCapacity >= f.total;
    }

    // 3) Применяем фильтр (если задан)
    const f = window.__bookingFilter;
    let filtered = itemsActive;
    if (f && Number.isFinite(f.total) && f.total > 0) {
      filtered = itemsActive.filter(c => campHasAvailability(c, f));
    }

    // 4) Отрисовка
    closeCampPopupOverlay({ immediate: true });
    if (typeof cluster?.clearLayers === 'function') cluster.clearLayers();
    filtered.forEach(c => {
      if (c.lat == null || c.lng == null) return;

      const marker = L.marker(
        [c.lat, c.lng],
        { icon: campPinIcon(c) }
      );
      marker.__campData = c;
      if (window.TouristMapPopupWidget && typeof window.TouristMapPopupWidget.mount === 'function') {
        const popupHost = document.createElement('div');
        popupHost.className = 'camp-popup-react-host';
        marker.__popupHost = popupHost;
        marker.bindPopup(popupHost, {
          maxWidth: 440,
          className: 'camp-popup',
          autoPan: false,
          closeButton: false,
        });
      } else {
        marker.bindPopup(popupHtmlForCamp(c), {
          maxWidth: 440,
          className: 'camp-popup',
          autoPan: false,
        });
      }
      cluster.addLayer(marker);
    });
  } catch (e) {
    console.error('loadCamps error:', e);
  }
}

function formatCampDetailCount(value){
  const num = Number(value);
  if (!Number.isFinite(num) || num < 0) return '—';
  return `${num} шт.`;
}

function titleCaseLabel(value){
  const text = String(value || '').trim();
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function campDetailIconSvg(kind, meta){
  switch (kind) {
    case 'units':
      return meta?.icon || `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="6" y="5" width="12" height="14"></rect>
          <path d="M9 8h2M13 8h2M9 11h2M13 11h2M9 14h2M13 14h2"></path>
          <rect x="10" y="16" width="4" height="3"></rect>
        </svg>
      `;
    case 'water':
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3c2.9 3.42 4.5 5.82 4.5 8.2A4.5 4.5 0 0 1 12 15.7a4.5 4.5 0 0 1-4.5-4.5C7.5 8.82 9.1 6.42 12 3Z"></path>
          <path d="M5 18c1.5 1.2 3.25 1.8 5.25 1.8S14 19.2 16 18"></path>
          <path d="M3 21c2.1-1.4 4.45-2.1 7.05-2.1 2.62 0 4.97.7 7.05 2.1"></path>
        </svg>
      `;
    case 'bbq':
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M13 3c1.2 1.15 1.56 2.58 1.06 4.3"></path>
          <path d="M9.5 4.25c.96.94 1.23 2.08.8 3.4"></path>
          <path d="M15.5 7.2c2.57 1 3.85 2.67 3.85 5 0 2.87-2.32 5.2-5.18 5.2H10.2C7.34 17.4 5 15.07 5 12.2c0-2.22 1.2-3.84 3.6-4.86"></path>
          <path d="M10 17.4 8.8 21"></path>
          <path d="M14.2 17.4 15.4 21"></path>
        </svg>
      `;
    case 'bath':
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 6.5c0-1.38 1.12-2.5 2.5-2.5 1 0 1.9.6 2.3 1.5"></path>
          <path d="M4.5 12h15"></path>
          <path d="M6 12v2.4c0 2.1 1.7 3.8 3.8 3.8h4.4c2.1 0 3.8-1.7 3.8-3.8V12"></path>
          <path d="M8 18.3 7.2 20"></path>
          <path d="M16 18.3 16.8 20"></path>
          <path d="M9 8.5v3.5"></path>
        </svg>
      `;
    case 'sauna':
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M8 4c.9 1 .9 2.15 0 3.2-.9 1.06-.9 2.2 0 3.3"></path>
          <path d="M12 4c.9 1 .9 2.15 0 3.2-.9 1.06-.9 2.2 0 3.3"></path>
          <path d="M16 4c.9 1 .9 2.15 0 3.2-.9 1.06-.9 2.2 0 3.3"></path>
          <path d="M5.5 14.5h13"></path>
          <path d="M7 14.5v2.2c0 1.82 1.48 3.3 3.3 3.3h3.4c1.82 0 3.3-1.48 3.3-3.3v-2.2"></path>
        </svg>
      `;
    case 'pool':
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 9.5v7"></path>
          <path d="M5 9.5c0-1.7 1.34-3 3-3h1.5c1.66 0 3 1.3 3 3v7"></path>
          <path d="M12.5 16.5c1.12.9 2.37 1.35 3.75 1.35S18.87 17.4 20 16.5"></path>
          <path d="M4 19c1.15.9 2.42 1.35 3.8 1.35S10.45 19.9 11.6 19c1.13-.9 2.4-1.35 3.8-1.35S18.07 18.1 19.2 19"></path>
        </svg>
      `;
    default:
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="7"></circle>
        </svg>
      `;
  }
}

function campDetailFacts(camp){
  return [
    { label: 'Озеро', value: camp?.lake_name || '—', icon: 'water' },
    { label: 'Баня', value: formatCampDetailCount(camp?.bath_count), icon: 'bath' },
    { label: 'Апартаментов', value: camp?.rooms_count ?? '—', icon: 'units' },
    { label: 'Сауна', value: formatCampDetailCount(camp?.sauna_count), icon: 'sauna' },
    { label: 'BBQ общая', value: formatCampDetailCount(camp?.bbq_shared_count), icon: 'bbq' },
    { label: 'Бассейн общий', value: formatCampDetailCount(camp?.pools_shared_count), icon: 'pool' },
    { label: 'BBQ личная', value: formatCampDetailCount(camp?.bbq_count), icon: 'bbq' },
    { label: 'Бассейн личный', value: formatCampDetailCount(camp?.pools_private_count), icon: 'pool' },
  ].map((item) => ({ label: item.label, value: item.value }));
}

// === Детали базы (модалка «Подробнее») — layout и анимации по Figma, данные из реального backend ===
async function openDetails(campId, opts = {}){
  showMiniLoader();
  try {
    window.__currentCampId = campId;
    const [camp, photos] = await Promise.all([
      fetch(`/api/camps/${campId}`).then(r => r.json()),
      fetch(`/api/camps/${campId}/photos`).then(r => r.json()).catch(()=>[])
    ]);
    // cache for fast booking/housing buttons
    try {
      window.__campsById ||= {};
      window.__campsById[Number(campId)] = camp;
    } catch(_) {}
    const meta = campMarkerMeta(camp);
    const pics = ((photos && photos.length) ? photos.map((p) => p?.url) : (camp.photo_main ? [camp.photo_main] : []))
      .filter(Boolean);
    const safeName = escapeHtml(camp.name || 'База');
    const facts = campDetailFacts(camp);
    const showBookInGallery = !(opts && opts.showBookInGallery === false);
    const onBack = opts && typeof opts.onBack === 'function' ? opts.onBack : null;

    let modal = takeoverMiniLoaderAsModal();
    if (!modal) {
      modal = document.createElement('div');
      modal.className = 'modal show camp-detail-overlay';
      modal.style.opacity = '0';
      modal.style.transition = 'opacity .12s ease-out';
      document.body.appendChild(modal);
    } else {
      modal.className = 'modal show camp-detail-overlay';
    }

    modal.innerHTML = `
      <div class="camp-detail-shell ${meta.isVip ? 'is-vip' : ''}" style="--detail-accent:${meta.color}; --detail-rgb:${meta.rgb};">
        <div class="modal-card camp-detail-modal">
          <div class="camp-detail__scroll">
            <div class="camp-detail__header">
              <h2 class="camp-detail__title">${safeName}</h2>
            </div>

            <div class="camp-detail__gallery">
              <div class="camp-detail__gallery-frame ${pics.length ? 'is-interactive' : ''}">
                ${
                  pics.length
                    ? `
                      <div class="camp-detail__gallery-viewport">
                        <div class="camp-detail__gallery-track">${
                          pics.map((u, index) => `
                            <div class="camp-detail__gallery-slide" data-gallery-index="${index}">
                              <img src="${escapeHtml(String(u))}"
                                   alt="${safeName} — фото ${index + 1}"
                                   draggable="false"
                                   loading="eager"
                                   decoding="sync"
                                   fetchpriority="high"
                                   referrerpolicy="no-referrer">
                              ${meta.isVip ? '<div class="camp-detail__gallery-shine" aria-hidden="true"></div>' : ''}
                            </div>
                          `).join('')
                        }</div>
                      </div>
                    `
                    : `
                      <div class="camp-detail__gallery-empty">
                        <span>Фото скоро появятся</span>
                      </div>
                    `
                }

                ${
                  pics.length > 1
                    ? `
                      <button type="button" class="camp-detail__arrow camp-detail__arrow--prev" aria-label="Предыдущее фото">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
                      </button>
                      <button type="button" class="camp-detail__arrow camp-detail__arrow--next" aria-label="Следующее фото">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
                      </button>
                    `
                    : ''
                }

                ${
                  pics.length > 1
                    ? `
                      <div class="camp-detail__dots" role="tablist" aria-label="Переключение фото">
                        ${pics.map((_, index) => `
                          <button type="button" class="camp-detail__dot ${index === 0 ? 'is-active' : ''}" data-gal-index="${index}" aria-label="Фото ${index + 1}"></button>
                        `).join('')}
                      </div>
                    `
                    : ''
                }
              </div>
            </div>

            <div class="camp-detail__facts">
              ${facts.map((fact, index) => `
                <div class="camp-detail__fact" style="--detail-delay:${320 + index * 55}ms;">
                  <div class="camp-detail__fact-row">
                    <span class="camp-detail__fact-label">${escapeHtml(fact.label)}</span>
                    <span class="camp-detail__fact-value">${escapeHtml(String(fact.value))}</span>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="camp-detail__actions">
            <button type="button" class="camp-detail__action camp-detail__action--housing">Апартаменты</button>
            <button type="button" class="camp-detail__action camp-detail__action--book">Забронировать</button>
            <button type="button" class="camp-detail__action camp-detail__action--back">Назад</button>
          </div>
        </div>
      </div>
    `;

    let isClosed = false;
    let onKeyDown = null;
    let onResize = null;
    const closeDetails = () => {
      if (isClosed) return;
      isClosed = true;
      try { if (onKeyDown) window.removeEventListener('keydown', onKeyDown); } catch (_) {}
      try { if (onResize) window.removeEventListener('resize', onResize); } catch (_) {}
      if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
    };

    const bookBtn = modal.querySelector('.camp-detail__action--book');
    const housingBtnEl = modal.querySelector('.camp-detail__action--housing');
    const backBtn = modal.querySelector('.camp-detail__action--back');

    if (bookBtn) bookBtn.onclick = () => { hapticPulse('soft', 14); openBookingFilterWithAuth(campId); };
    if (housingBtnEl) housingBtnEl.onclick = () => { hapticPulse('light', 12); closeDetails(); openCampHousing(campId); };
    if (backBtn) backBtn.onclick = () => {
      hapticPulse('selection', 12);
      closeDetails();
      if (onBack) {
        try { onBack(); } catch(_) {}
      }
    };

    modal.addEventListener('click', (event) => {
      if (event.target === modal) closeDetails();
    });

    onKeyDown = (event) => {
      if (event.key === 'Escape') closeDetails();
    };
    window.addEventListener('keydown', onKeyDown);

    const galleryFrame = modal.querySelector('.camp-detail__gallery-frame');
    const galleryViewport = modal.querySelector('.camp-detail__gallery-viewport');
    const vp = modal.querySelector('.camp-detail__gallery-track');
    const slides = vp ? Array.from(vp.querySelectorAll('.camp-detail__gallery-slide')) : [];
    const imgs = slides.map((slide) => slide.querySelector('img')).filter(Boolean);
    const btnPrev = modal.querySelector('.camp-detail__arrow--prev');
    const btnNext = modal.querySelector('.camp-detail__arrow--next');
    const counter = modal.querySelector('.camp-detail__counter');
    const dots = Array.from(modal.querySelectorAll('.camp-detail__dot'));
    const N = slides.length;

    if (vp && N) {
      vp.style.width = '100%';
      slides.forEach((slide) => {
        slide.style.width = '100%';
        slide.style.minWidth = '100%';
        slide.style.flex = '0 0 100%';
      });
    }

    let i = 0;
    let locked = false;
    const applyActiveGalleryRatio = (index) => {
      if (!galleryViewport) return;
      const img = imgs[index];
      if (!img) return;
      const updateRatio = () => {
        const naturalWidth = Number(img.naturalWidth || img.width || 0);
        const naturalHeight = Number(img.naturalHeight || img.height || 0);
        if (!naturalWidth || !naturalHeight) return;
        galleryViewport.style.aspectRatio = `${naturalWidth} / ${naturalHeight}`;
      };
      if (img.complete) {
        updateRatio();
      } else {
        img.addEventListener('load', updateRatio, { once: true });
      }
    };
    const syncGalleryOffset = () => {
      if (!vp || !galleryViewport || !N) return;
      const viewportWidth = Math.round(galleryViewport.clientWidth || 0);
      if (!viewportWidth) return;
      vp.style.transform = `translate3d(${-i * viewportWidth}px, 0, 0)`;
    };
    const updateUI = () => {
      if (counter) counter.textContent = `${i + 1} / ${N}`;
      if (btnPrev) btnPrev.disabled = i === 0;
      if (btnNext) btnNext.disabled = i === N - 1;
      dots.forEach((dot, index) => {
        dot.classList.toggle('is-active', index === i);
      });
    };

    const go = (to) => {
      if (!vp || !N || locked) return;
      const clamped = Math.max(0, Math.min(N - 1, to));
      if (clamped === i) {
        updateUI();
        return;
      }
      locked = true;
      i = clamped;
      applyActiveGalleryRatio(i);
      syncGalleryOffset();

      const unlock = () => {
        locked = false;
        vp.removeEventListener('transitionend', unlock);
        updateUI();
      };
      vp.addEventListener('transitionend', unlock);
      setTimeout(unlock, 360);
    };

    const throttledPrev = throttle(() => go(i - 1), 260);
    const throttledNext = throttle(() => go(i + 1), 260);
    if (btnPrev) btnPrev.onclick = (event) => {
      if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
      hapticPulse('light', 12);
      throttledPrev();
    };
    if (btnNext) btnNext.onclick = (event) => {
      if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
      hapticPulse('light', 12);
      throttledNext();
    };
    dots.forEach((dot) => {
      dot.addEventListener('click', (event) => {
        if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
        const nextIndex = Number(dot.dataset.galIndex);
        if (!Number.isFinite(nextIndex)) return;
        hapticPulse('selection', 10);
        go(nextIndex);
      });
    });

    if (vp && N) {
      let sx = 0;
      let dx = 0;
      let moving = false;
      const THRESH = 40;

      vp.addEventListener('touchstart', (event) => {
        if (!event.touches[0]) return;
        sx = event.touches[0].clientX;
        dx = 0;
        moving = true;
      }, { passive: true });

      vp.addEventListener('touchmove', (event) => {
        if (!moving || !event.touches[0]) return;
        dx = event.touches[0].clientX - sx;
      }, { passive: true });

      vp.addEventListener('touchend', () => {
        if (!moving) return;
        moving = false;
        if (Math.abs(dx) > THRESH) {
          if (dx < 0) throttledNext();
          else throttledPrev();
        }
      }, { passive: true });

      if (galleryFrame) {
        galleryFrame.addEventListener('click', (event) => {
          if (event.target && event.target.closest && event.target.closest('.camp-detail__arrow, .camp-detail__dot')) return;
          hapticPulse('light', 10);
          openFullscreenGallery(pics, i, { showBook: showBookInGallery });
        });
      }

      applyActiveGalleryRatio(i);
      syncGalleryOffset();
      onResize = () => syncGalleryOffset();
      window.addEventListener('resize', onResize);
      updateUI();
    }

    requestAnimationFrame(() => { modal.style.opacity = '1'; });
    return modal;

  } catch (e) {
    hideMiniLoader();

    console.error(e);
    showModal(`
      <div class="card">
        <p class="muted">Не удалось загрузить карточку базы.</p>
        <div class="actions"><button class="button primary" onclick="closeModal()">OK</button></div>
      </div>`);
    return null;
  }
}

// === Масштабирование «двухколоночной» сетки БЕЗ утечек обработчиков ===
function applyTwoColScale(root){
  const card = root.querySelector('.modal-card.details');
  if (!card) return;

  const run = () => {
    const w = card.clientWidth || 360;
    const k = Math.max(0.85, Math.min(1.05, w / 420)); // 0.85…1.05

    card.style.setProperty('--param-font', `${Math.round(13 * k)}px`);
    card.style.setProperty('--param-gap',  `${Math.round(8  * k)}px`);
    card.style.setProperty('--param-px',   `${Math.round(11 * k)}px`);
    card.style.setProperty('--param-py',   `${Math.round(5  * k)}px`);
  };

  // первый запуск
  run();

  // ВАЖНО: один ResizeObserver на карточку
  if (!card.__ro){
    card.__ro = new ResizeObserver(run);
    card.__ro.observe(card);
  }
}

// ЕДИНЫЙ глобальный resize: дергаем масштабирование только если открыта карточка «Подробнее»
(function attachGlobalScaleOnResize(){
  let raf = 0;
  window.addEventListener('resize', () => {
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const modal = document.querySelector('.modal.show');
      if (!modal) return;
      const details = modal.querySelector('.modal-card.details');
      if (details) applyTwoColScale(modal);
    });
  }, { passive: true });
})();


// === Полноэкранная галерея (свайп + стрелки + зум + пан + кнопки) ===
function openFullscreenGallery(pics, startIndex=0, opts = {}){
  if (!Array.isArray(pics) || pics.length === 0) return;
  const showBook = opts && opts.showBook === false ? false : true;
  const safePics = pics.map((u) => escapeHtml(String(u)));

  const wrap = document.createElement('div');
  wrap.className = 'fs-modal';
  wrap.innerHTML = `
    <div class="fs-stage">
      <div class="fs-viewport">
        <div class="fs-track">
          ${safePics.map((u, index) => `
            <div class="fs-slide" data-fs-index="${index}">
              <img src="${u}"
                   alt="Фото ${index + 1}"
                   draggable="false"
                   loading="eager"
                   decoding="sync"
                   fetchpriority="high"
                   referrerpolicy="no-referrer">
            </div>
          `).join('')}
        </div>
      </div>

      ${pics.length > 1 ? `
        <button type="button" class="fs-arrow fs-arrow--prev" id="fsPrev" aria-label="Предыдущее фото">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
        </button>
        <button type="button" class="fs-arrow fs-arrow--next" id="fsNext" aria-label="Следующее фото">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
        </button>
      ` : ''}

      <div class="fs-footer">
        <div class="fs-counter" id="fsCounter">${Math.min(startIndex + 1, pics.length)} / ${pics.length}</div>
        <div class="fs-actions">
          ${showBook ? '<button type="button" class="fs-action fs-action--book" id="fsBook">Забронировать</button>' : ''}
          <button type="button" class="fs-action fs-action--back" id="fsBack">Назад</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);
  requestAnimationFrame(() => wrap.classList.add('is-open'));

  const viewport = wrap.querySelector('.fs-viewport');
  const track = wrap.querySelector('.fs-track');
  const slides = Array.from(wrap.querySelectorAll('.fs-slide'));
  const counter = wrap.querySelector('#fsCounter');
  const prevBtn = wrap.querySelector('#fsPrev');
  const nextBtn = wrap.querySelector('#fsNext');
  const bookBtn = wrap.querySelector('#fsBook');
  const backBtn = wrap.querySelector('#fsBack');

  let i = Math.max(0, Math.min(pics.length - 1, startIndex));
  let isClosing = false;
  let onResize = null;
  let onKeyDown = null;

  const updateCounter = () => {
    if (counter) counter.textContent = `${i + 1} / ${pics.length}`;
  };

  const syncSlideWidths = () => {
    if (!track || !viewport || !slides.length) return 0;
    const viewportWidth = Math.round(viewport.getBoundingClientRect().width || viewport.clientWidth || window.innerWidth || 0);
    if (!viewportWidth) return 0;
    track.style.gridAutoColumns = `${viewportWidth}px`;
    slides.forEach((slide) => {
      slide.style.width = `${viewportWidth}px`;
    });
    return viewportWidth;
  };

  const syncTrack = (instant = false) => {
    if (!track || !slides.length) return;
    const viewportWidth = syncSlideWidths();
    if (!viewportWidth) return;
    const prevTransition = track.style.transition;
    if (instant) track.style.transition = 'none';
    track.style.transform = `translate3d(${-i * viewportWidth}px, 0, 0)`;
    if (instant) {
      void track.offsetHeight;
      track.style.transition = prevTransition || '';
    }
  };

  const go = (nextIndex) => {
    const total = pics.length;
    i = ((nextIndex % total) + total) % total;
    syncTrack();
    updateCounter();
  };

  const throttledPrev = throttle(() => go(i - 1), 260);
  const throttledNext = throttle(() => go(i + 1), 260);

  const closeFullscreen = () => {
    if (isClosing) return;
    isClosing = true;
    try { if (onResize) window.removeEventListener('resize', onResize); } catch (_) {}
    try { if (onKeyDown) document.removeEventListener('keydown', onKeyDown); } catch (_) {}
    wrap.classList.remove('is-open');
    setTimeout(() => {
      if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
    }, 240);
  };

  if (prevBtn) prevBtn.onclick = (event) => {
    if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
    hapticPulse('light', 12);
    throttledPrev();
  };
  if (nextBtn) nextBtn.onclick = (event) => {
    if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
    hapticPulse('light', 12);
    throttledNext();
  };
  if (bookBtn) bookBtn.onclick = (event) => {
    if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
    hapticPulse('soft', 14);
    closeFullscreen();
    openBookingFilterWithAuth(window.__currentCampId);
  };
  if (backBtn) backBtn.onclick = (event) => {
    if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
    hapticPulse('selection', 10);
    closeFullscreen();
  };

  onKeyDown = (event) => {
    if (event.key === 'Escape') closeFullscreen();
    if (event.key === 'ArrowLeft') throttledPrev();
    if (event.key === 'ArrowRight') throttledNext();
  };
  document.addEventListener('keydown', onKeyDown);

  let sx = 0;
  let dx = 0;
  let swiping = false;
  const THRESH = 50;
  if (viewport) {
    viewport.addEventListener('touchstart', (event) => {
      if (!event.touches[0]) return;
      swiping = true;
      sx = event.touches[0].clientX;
      dx = 0;
    }, { passive: true });

    viewport.addEventListener('touchmove', (event) => {
      if (!swiping || !event.touches[0]) return;
      dx = event.touches[0].clientX - sx;
    }, { passive: true });

    viewport.addEventListener('touchend', () => {
      if (!swiping) return;
      swiping = false;
      if (Math.abs(dx) > THRESH) {
        if (dx < 0) throttledNext();
        else throttledPrev();
      }
    }, { passive: true });
  }

  onResize = () => syncTrack(true);
  window.addEventListener('resize', onResize);
  syncTrack(true);
  updateCounter();
}



// Глобальные обработчики, на которые ссылается HTML в балуне
window.__showCampBrief = function(campId) {
  // закрываем балун, если открыт
  try { document.querySelectorAll('.leaflet-popup-close-button').forEach(b=>b.click()); } catch(_){}
  openDetails(campId);
};

window.__openCampBooking = function(campId) {
  // закрываем «Подробнее», если открыто
  closeTransientOverlays();
  openBookingFilterWithAuth(campId);
};


// Универсальная «простая шторка»
function showSheet(html){
  const wrap = document.createElement('div');
  wrap.id = 't03-sheet';
  wrap.style = 'position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:flex-end;justify-content:center;z-index:9999';
  wrap.innerHTML = `<div style="width:92%;max-width:520px;background:rgba(17,19,23,.9);backdrop-filter:blur(6px);border-radius:18px;padding:16px;margin:14px;box-shadow:0 20px 40px rgba(0,0,0,.4)">${html}</div>`;
  document.body.appendChild(wrap);
  wrap.addEventListener('click', (e)=>{ if(e.target===wrap) closeSheet(); });
}
function closeSheet(){ const n = document.getElementById('t03-sheet'); if(n) n.remove(); }

// Фильтр
function openBooking(campId){
  // одна форма — два ряда (Заезд/Выезд) и (Взрослые/Дети)
  showSheet(`
    <div style="display:grid;gap:10px">
      <div style="font-weight:700;font-size:18px;text-align:center">Выберите даты и гостей</div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div>
          <div style="color:#9aa3af;font-size:12px;margin:2px 0 4px">Заезд</div>
          <input id="bk_checkin" type="date" style="width:100%;height:44px;border-radius:12px;border:1px solid #2a2f3a;background:#0f1216;color:#f2f4f7;padding:0 10px">
        </div>
        <div>
          <div style="color:#9aa3af;font-size:12px;margin:2px 0 4px">Выезд</div>
          <input id="bk_checkout" type="date" style="width:100%;height:44px;border-radius:12px;border:1px solid #2a2f3a;background:#0f1216;color:#f2f4f7;padding:0 10px">
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div>
          <div style="color:#9aa3af;font-size:12px;margin:2px 0 4px">Взрослые</div>
          <select id="bk_adults" style="width:100%;height:44px;border-radius:12px;border:1px solid #2a2f3a;background:#0f1216;color:#f2f4f7;padding:0 10px">
            ${Array.from({length:6},(_,i)=>`<option value="${i+1}">${i+1}</option>`).join('')}
          </select>
        </div>
        <div>
          <div style="color:#9aa3af;font-size:12px;margin:2px 0 4px">Дети</div>
          <select id="bk_children" style="width:100%;height:44px;border-radius:12px;border:1px solid #2a2f3a;background:#0f1216;color:#f2f4f7;padding:0 10px">
            ${Array.from({length:6},(_,i)=>`<option value="${i}">${i}</option>`).join('')}
          </select>
        </div>
      </div>

      <div style="display:flex;gap:10px;justify-content:space-between;margin-top:6px">
        <button class="btn btn-light"   onclick="closeSheet()">Закрыть</button>
        <button class="btn"             onclick="document.getElementById('bk_checkin').value='';document.getElementById('bk_checkout').value='';document.getElementById('bk_adults').selectedIndex=0;document.getElementById('bk_children').selectedIndex=0;">Сбросить</button>
        <button class="btn btn-primary" onclick="applyBooking(${campId||'null'})">Показать</button>
      </div>
    </div>
  `);
}

// обработчик отправки фильтра
function applyBooking(campId){
  // здесь пока просто закрываем — дальше подключим поиск свободных номеров
  closeSheet();
  // … твоя логика фильтрации/запроса
}


// --- Инициализация кликов по таббару (единая версия)
function initTabs(){
  document.querySelectorAll('.tabbar .tab').forEach(tab => {
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();

      // тактильный «тычок» на выборе вкладки
      hapticPulse('selection', 12);

      const targetId = tab.getAttribute('data-target');

      // активная кнопка
      document.querySelectorAll('.tabbar .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      // показ нужной вкладки
      document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
      const tgt = document.getElementById(targetId);
      if (tgt) tgt.style.display = '';

      // если вернулись на карту — подправим размеры
      if (targetId === 'tab-map' && typeof fixMapSize === 'function') {
        fixMapSize();
        if (typeof restoreMapView === 'function') restoreMapView();
      }
    });
  });
}



// === Booking Filter (2×2): кликабельные даты, запоминание значений, применение на карту / бронирование ===
function buildBookingFilterMarkup({ titleText, hintText, applyText, closeText }) {
  const chevrons = `
    <svg class="bk-picker-chevron" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M6 8l4-4 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>
      <path d="M6 12l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>
    </svg>
  `;
  return `
    <div class="booking-card">
      <div class="booking-header">
        <div class="booking-title">${titleText}</div>
        <div class="booking-hint">${hintText}</div>
      </div>

      <div class="booking-grid">
        <label class="bk-field">
          <span>Заезд</span>
          <div class="bk-date">
            <button type="button" class="bk-input is-empty" id="bkShowFrom">—</button>
            <input type="hidden" id="bkFrom" class="bk-native">
          </div>
        </label>

        <label class="bk-field">
          <span>Выезд</span>
          <div class="bk-date">
            <button type="button" class="bk-input is-empty" id="bkShowTo">—</button>
            <input type="hidden" id="bkTo" class="bk-native">
          </div>
        </label>

        <label class="bk-field">
          <span>Взрослые</span>
          <div class="bk-picker-field">
            <button type="button" class="bk-picker-trigger" id="bkAdultsBtn" aria-haspopup="listbox" aria-expanded="false">
              <span class="bk-picker-value" id="bkAdultsValue">2</span>
              ${chevrons}
            </button>
            <input type="hidden" id="bkAdults" class="bk-hidden-value" value="2">
          </div>
        </label>

        <label class="bk-field">
          <span>Дети</span>
          <div class="bk-picker-field">
            <button type="button" class="bk-picker-trigger" id="bkKidsBtn" aria-haspopup="listbox" aria-expanded="false">
              <span class="bk-picker-value" id="bkKidsValue">0</span>
              ${chevrons}
            </button>
            <input type="hidden" id="bkKids" class="bk-hidden-value" value="0">
          </div>
        </label>
      </div>

      <label class="bk-checkbox-wrapper">
        <input type="checkbox" id="bkAllowSplit" class="bk-checkbox">
        <span class="bk-checkbox-box" aria-hidden="true">
          <svg class="bk-checkbox-icon" viewBox="0 0 16 16">
            <path d="M3.5 8.5 6.5 11.5 12.5 4.5"></path>
          </svg>
        </span>
        <span class="bk-checkbox-text">Показать варианты заселения в разные номера или дома</span>
      </label>

      <div class="booking-actions">
        <button type="button" class="bk-action" id="bkClose">${closeText}</button>
        <button type="button" class="bk-action" id="bkReset">Сбросить</button>
        <button type="button" class="bk-action bk-action--primary" id="bkApply">${applyText}</button>
      </div>
    </div>
  `;
}

function formatBookingFieldDate(value) {
  if (!value) return '—';
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return '—';
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12, 0, 0);
  try {
    const currentYear = new Date().getFullYear();
    const options = date.getFullYear() === currentYear
      ? { day: 'numeric', month: 'long' }
      : { day: 'numeric', month: 'long', year: 'numeric' };
    return new Intl.DateTimeFormat('ru-RU', options).format(date).replace(/\s?г\.$/, '');
  } catch (_) {
    return value;
  }
}

function openBookingFilterModal(opts = {}) {
  const dontCloseBackground = opts.dontCloseBackground || false;
  const restoreFilterOnClose = opts.restoreFilterOnClose || false;
  
  const mode = String(opts.mode || 'map');
  const isBooking = mode === 'booking';
  // На этапе выбора дат ещё ничего не подтверждаем
  const titleText = String(opts.title || 'Выберите даты и гостей');
	  const hintText = String(
	    opts.hint != null
	      ? opts.hint
	      : (isBooking
	          ? 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.'
	          : 'При сохранении фильтра на карте будут показаны только базы отдыха, подходящие под Ваш выбор')
	  );
  const applyText = String(opts.applyText || (isBooking ? 'К выбору вариантов' : 'Сохранить'));
  const closeText = String(opts.closeText || (isBooking ? 'Назад' : 'Закрыть'));
  const filterMarkup = buildBookingFilterMarkup({ titleText, hintText, applyText, closeText });

  // Если нужно сохранить фоновое окно, создаём отдельное окно для фильтра
  if (dontCloseBackground) {
    const filterModal = document.createElement('div');
    filterModal.className = 'modal show';
    filterModal.id = 'filterModal';
    // Должен быть поверх основного #modal (корзина/подбор), но ниже полноэкранной галереи
    filterModal.style.zIndex = '6600';
    filterModal.innerHTML = `<div class="modal-card booking-shell">${filterMarkup}</div>`;
    document.body.appendChild(filterModal);

    filterModal.addEventListener('click', (e) => {
      if (e.target === filterModal) {
        const closeBtn = filterModal.querySelector('#bkClose');
        if (closeBtn && typeof closeBtn.click === 'function') closeBtn.click();
        else {
          filterModal.remove();
          if (opts.onClose) opts.onClose();
        }
      }
    });

    // Настраиваем элементы фильтра
    setupBookingFilterElements(filterModal, opts, isBooking, titleText);
    return;
  }

  // Обычная логика - используем основное окно
  closeTransientOverlays({ keepMainModal: true });

  showModal(filterMarkup);

  // сужаем внешнюю «прозрачную» оболочку только для окна фильтра
  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.add('booking-shell'); shell.classList.remove('details'); shell.classList.remove('accom-shell'); shell.classList.remove('room-detail-shell'); }

  // Инициализируем обработчики фильтра
  setupBookingFilterElements(shell || document.body, opts, isBooking, titleText);
}

// === Вспомогательная функция для инициализации обработчиков фильтра ===
function setupBookingFilterElements(container, opts, isBooking, titleText) {
  const card  = container.querySelector('.booking-card') || container;
  const fromI = card.querySelector('#bkFrom');
  const toI   = card.querySelector('#bkTo');
  const fromB = card.querySelector('#bkShowFrom');
  const toB   = card.querySelector('#bkShowTo');
  const adSel = card.querySelector('#bkAdults');
  const kdSel = card.querySelector('#bkKids');
  const adBtn = card.querySelector('#bkAdultsBtn');
  const kdBtn = card.querySelector('#bkKidsBtn');
  const adValue = card.querySelector('#bkAdultsValue');
  const kdValue = card.querySelector('#bkKidsValue');
  const splitChk = card.querySelector('#bkAllowSplit');
  const applyBtn = card.querySelector('#bkApply');

  // Сохраняем исходный фильтр если нужна защита от сброса
  const restoreFilterOnClose = opts.restoreFilterOnClose || false;
  const originalFilter = restoreFilterOnClose ? JSON.parse(JSON.stringify(window.__bookingFilter || {})) : null;
  let shouldRestoreOnClose = restoreFilterOnClose; // Флаг для отмены восстановления если нажали "Применить"

  // заполнение из предыдущего фильтра (если уже выбирали)
  const F = window.__bookingFilter || {};
  if (F.from) fromI.value = F.from;
  if (F.to)   toI.value   = F.to;
  adSel.value = String(F.adults ?? 2);
  kdSel.value = String(F.kids   ?? 0);
  if (F.allowSplitRooms !== undefined) splitChk.checked = F.allowSplitRooms;

  // читаемо показываем выбранные даты
  const sync = () => {
    const fromLabel = formatBookingFieldDate(fromI.value);
    const toLabel = formatBookingFieldDate(toI.value);
    fromB.textContent = fromLabel;
    toB.textContent = toLabel;
    fromB.classList.toggle('is-empty', !fromI.value);
    toB.classList.toggle('is-empty', !toI.value);
  };
  fromI.addEventListener('change', sync);
  toI.addEventListener('change',   sync);
  sync();

  const defaultAdultsMax = 30;
  const defaultKidsMax = 30;
  const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
  const readNum = (input, fallback) => {
    const num = Number(input?.value);
    return Number.isFinite(num) ? num : fallback;
  };
  const setHiddenValue = (input, nextValue, emitChange = false) => {
    if (!input) return;
    input.value = String(nextValue);
    if (emitChange) {
      try { input.dispatchEvent(new Event('change')); } catch (_) {}
    }
  };
  const updateGuestValues = () => {
    if (adValue) adValue.textContent = String(clamp(readNum(adSel, 2), 1, 999));
    if (kdValue) kdValue.textContent = String(clamp(readNum(kdSel, 0), 0, 999));
  };

  // Ограничение по вместимости (для фильтра внутри конкретного апартамента)
  const maxGuests = Number(opts.maxGuests);
  const baseApplyText = String(opts.applyText || (applyBtn ? applyBtn.textContent : 'Применить'));

  function applyCapacityConstraints() {
    const adultsMax = Number.isFinite(maxGuests) && maxGuests > 0 ? maxGuests : defaultAdultsMax;
    const adults = clamp(readNum(adSel, 2), 1, adultsMax);
    const kidsMax = Number.isFinite(maxGuests) && maxGuests > 0 ? Math.max(0, maxGuests - adults) : defaultKidsMax;
    const kids = clamp(readNum(kdSel, 0), 0, kidsMax);
    setHiddenValue(adSel, adults, false);
    setHiddenValue(kdSel, kids, false);
    if (adBtn) {
      adBtn.dataset.min = '1';
      adBtn.dataset.max = String(adultsMax);
    }
    if (kdBtn) {
      kdBtn.dataset.min = '0';
      kdBtn.dataset.max = String(kidsMax);
    }
    updateGuestValues();
  }
  applyCapacityConstraints();

  const busyRanges = Array.isArray(opts.busyRanges) ? opts.busyRanges : [];
  const campRoomsBusyRaw = Array.isArray(opts.campRoomsBusy) ? opts.campRoomsBusy : null;
  const campHousingType = normalizeHousingType(opts.campHousingType || (opts.camp && opts.camp.housing_type));
  const campRoomsBusy = (() => {
    if (!campRoomsBusyRaw) return null;
    const ht = normalizeHousingType(campHousingType);
    let allow = null;
    if (ht === 'apartments') allow = (rt) => rt === 'Апартамент';
    else if (ht === 'houses') allow = (rt) => rt === 'Дом' || rt === 'Коттедж';
    else if (ht === 'rooms') allow = (rt) => rt === 'Номер' || rt === 'Комната';
    if (!allow) return campRoomsBusyRaw;
    const filtered = campRoomsBusyRaw.filter(r => {
      const rt = String(r?.room_type || '').trim();
      if (!rt) return true;
      return allow(rt);
    });
    return filtered.length ? filtered : campRoomsBusyRaw;
  })();
  const hasCampRoomsBusy = !!(campRoomsBusy && campRoomsBusy.length);
  const isoToday = (() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12, 0, 0).toISOString().slice(0, 10);
  })();
  const toMidday = (iso) => {
    if (!iso) return null;
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12, 0, 0);
  };
  const isoOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12, 0, 0).toISOString().slice(0, 10);
  const addDays = (iso, delta) => {
    const d = toMidday(iso);
    if (!d) return null;
    d.setDate(d.getDate() + delta);
    return isoOf(d);
  };
  const overlapRanges = (fromIso, toIso) => {
    const aFrom = toMidday(fromIso);
    const aTo = toMidday(toIso);
    if (!aFrom || !aTo) return false;
    for (const r of busyRanges) {
      const bFrom = toMidday(r?.from);
      const bTo = toMidday(r?.to);
      if (!bFrom || !bTo) continue;
      if (aFrom < bTo && bFrom < aTo) return true;
    }
    return false;
  };
  const isBusyDay = (dayIso) => {
    const day = toMidday(dayIso);
    if (!day) return false;
    for (const r of busyRanges) {
      const bFrom = toMidday(r?.from);
      const bTo = toMidday(r?.to);
      if (!bFrom || !bTo) continue;
      if (day >= bFrom && day < bTo) return true; // занятая ночь
    }
    return false;
  };
  const roomIsFreeForRange = (room, fromIso, toIso) => {
    if (!fromIso || !toIso) return false;
    const aFrom = toMidday(fromIso);
    const aTo = toMidday(toIso);
    if (!aFrom || !aTo) return false;
    const ranges = room?.busy || room?.bookings || room?.reservations || [];
    if (!Array.isArray(ranges) || ranges.length === 0) return true;
    for (const r of ranges) {
      const bFrom = toMidday(r?.from || r?.check_in || r?.start || r?.date_from);
      const bTo = toMidday(r?.to || r?.check_out || r?.end || r?.date_to);
      if (!bFrom || !bTo) continue;
      if (aFrom < bTo && bFrom < aTo) return false;
    }
    return true;
  };
  const campCanStay = (fromIso, toIso) => {
    if (!hasCampRoomsBusy) return true;
    if (!fromIso || !toIso) return false;
    const adults = Number(adSel.value) || 0;
    const kids = Number(kdSel.value) || 0;
    if (kids > 0 && adults <= 0) return false;
    const total = adults + kids;
    if (total <= 0) return false;
    const freeRooms = (campRoomsBusy || []).filter(r => roomIsFreeForRange(r, fromIso, toIso));
    if (!freeRooms.length) return false;
    if (splitChk.checked) {
      const best = findBestAllocation(freeRooms, total);
      return !!(best && best.length);
    }
    return freeRooms.some(r => roomCapacity(r) >= total);
  };
  const validateCampDatesOrReset = () => {
    if (!hasCampRoomsBusy) return;
    const from = fromI.value || '';
    const to = toI.value || '';
    if (!from || !to) return;
    if (!campCanStay(from, to)) {
      fromI.value = '';
      toI.value = '';
      sync();
      try { fromI.dispatchEvent(new Event('change')); } catch(_) {}
      try { toI.dispatchEvent(new Event('change')); } catch(_) {}
      appAlert('Для выбранного количества гостей нет свободных вариантов на эти даты. Выберите даты заново.');
    }
  };

  function canDirectBookNow() {
    const room = opts.targetRoom || null;
    if (!room) return false;
    const from = fromI.value || '';
    const to = toI.value || '';
    if (!from || !to) return false;
    const adults = Number(adSel.value) || 0;
    const kids = Number(kdSel.value) || 0;
    const total = adults + kids;
    if (total <= 0) return false;
    if (kids > 0 && adults <= 0) return false;
    const cap = Number.isFinite(maxGuests) && maxGuests > 0 ? maxGuests : roomCapacity(room);
    if (total > cap) return false;
    if (busyRanges.length && overlapRanges(from, to)) return false;
    try {
      const a = toMidday(from);
      const b = toMidday(to);
      if (!a || !b || b <= a) return false;
    } catch (_) { return false; }
    return true;
  }
  function updateApplyUi() {
    if (!applyBtn) return;
    const v = computeBlocking();
    const blocked = isBooking ? !v.ok : false;
    // не используем disabled-атрибут, чтобы по клику можно было подсветить ошибки
    try { applyBtn.disabled = false; } catch(_) {}
    applyBtn.classList.toggle('is-disabled', blocked);
    applyBtn.setAttribute('aria-disabled', blocked ? 'true' : 'false');
    applyBtn.dataset.disabled = blocked ? '1' : '0';
    applyBtn.textContent = canDirectBookNow() ? 'БРОНИРУЮ!' : baseApplyText;
  }

  function clearBkErrors() {
    try { fromB?.classList?.remove('bk-error'); } catch(_) {}
    try { toB?.classList?.remove('bk-error'); } catch(_) {}
    try { adBtn?.classList?.remove('bk-error'); } catch(_) {}
    try { kdBtn?.classList?.remove('bk-error'); } catch(_) {}
    try { splitChk?.classList?.remove('bk-error'); } catch(_) {}
  }
  function markBkError(el) {
    if (!el) return;
    try { el.classList.add('bk-error'); } catch(_) {}
  }
  function computeBlocking() {
    const from = fromI.value || '';
    const to = toI.value || '';
    const adults = Number(adSel.value) || 0;
    const kids = Number(kdSel.value) || 0;
    const total = adults + kids;
    const cap = Number.isFinite(maxGuests) && maxGuests > 0 ? maxGuests : null;
    const blocked = {
      from: false,
      to: false,
      guests: false,
      capacity: false,
      range: false,
      busy: false,
      campAvail: false,
    };

    if (isBooking) {
      if (!from) blocked.from = true;
      if (!to) blocked.to = true;
      if (from && to) {
        const a = toMidday(from);
        const b = toMidday(to);
        if (!a || !b || b <= a) { blocked.range = true; blocked.from = true; blocked.to = true; }
      }
      if (kids > 0 && adults <= 0) blocked.guests = true;
      if (cap != null && total > cap) blocked.capacity = true;
      if (from && to) {
        if (busyRanges.length && overlapRanges(from, to)) blocked.busy = true;
        if (hasCampRoomsBusy && !campCanStay(from, to)) blocked.campAvail = true;
      }
    } else {
      if (kids > 0 && adults <= 0) blocked.guests = true;
    }
    const ok = !Object.values(blocked).some(Boolean);
    return { ok, blocked, from, to, adults, kids, total, cap };
  }

  function markErrors() {
    clearBkErrors();
    const v = computeBlocking();
    if (v.blocked.from || v.blocked.to || v.blocked.range || v.blocked.busy || v.blocked.campAvail) {
      markBkError(fromB);
      markBkError(toB);
    }
    if (v.blocked.guests || v.blocked.capacity) {
      markBkError(adBtn);
      markBkError(kdBtn);
    }
  }
  updateApplyUi();

  // Запоминаем последний просматриваемый месяц календаря, чтобы "Выезд" открывался на том же месяце
  let lastPickerViewY = null;
  let lastPickerViewM = null;
  let closeWheelPicker = null;

  function destroyWheelPicker() {
    if (typeof closeWheelPicker === 'function') closeWheelPicker();
    closeWheelPicker = null;
    try { adBtn?.setAttribute('aria-expanded', 'false'); } catch (_) {}
    try { kdBtn?.setAttribute('aria-expanded', 'false'); } catch (_) {}
  }

  function openWheelPicker(kind) {
    const trigger = kind === 'adults' ? adBtn : kdBtn;
    const input = kind === 'adults' ? adSel : kdSel;
    if (!trigger || !input) return;

    const currentKind = trigger.getAttribute('aria-expanded') === 'true' ? kind : null;
    if (currentKind === kind) {
      destroyWheelPicker();
      return;
    }
    destroyWheelPicker();

    const min = Number(trigger.dataset.min ?? (kind === 'adults' ? 1 : 0));
    const max = Number(trigger.dataset.max ?? defaultKidsMax);
    if (!Number.isFinite(min) || !Number.isFinite(max) || max < min) return;

    const currentValue = clamp(readNum(input, kind === 'adults' ? 2 : 0), min, max);
    const itemsMarkup = Array.from({ length: max - min + 1 }, (_, index) => {
      const value = min + index;
      return `<div class="bk-wheel-item${value === currentValue ? ' is-active' : ''}" data-value="${value}">${value}</div>`;
    }).join('');

    const overlay = document.createElement('div');
    overlay.className = 'bk-wheel-overlay';
    overlay.innerHTML = `
      <div class="bk-wheel-dismiss" aria-hidden="true"></div>
      <div class="bk-wheel" role="listbox" aria-label="${kind === 'adults' ? 'Взрослые' : 'Дети'}">
        <div class="bk-wheel-fade bk-wheel-fade--top"></div>
        <div class="bk-wheel-fade bk-wheel-fade--bottom"></div>
        <div class="bk-wheel-indicator"></div>
        <div class="bk-wheel-scroll">${itemsMarkup}</div>
      </div>
    `;
    document.body.appendChild(overlay);
    trigger.setAttribute('aria-expanded', 'true');

    const wheel = overlay.querySelector('.bk-wheel');
    const dismiss = overlay.querySelector('.bk-wheel-dismiss');
    const scroll = overlay.querySelector('.bk-wheel-scroll');
    const items = Array.from(overlay.querySelectorAll('.bk-wheel-item'));
    const itemHeight = 48;
    const gap = 10;

    const placeWheel = () => {
      const rect = trigger.getBoundingClientRect();
      const viewportWidth = window.innerWidth || document.documentElement?.clientWidth || 0;
      const viewportHeight = window.innerHeight || document.documentElement?.clientHeight || 0;
      const wheelWidth = Math.min(Math.max(Math.round(rect.width * 1.15), 220), viewportWidth - 24);
      let left = rect.left + (rect.width / 2) - (wheelWidth / 2);
      left = Math.max(12, Math.min(left, viewportWidth - wheelWidth - 12));
      let top = rect.bottom + gap;
      if ((top + 144) > (viewportHeight - 12)) {
        top = Math.max(12, rect.top - 144 - gap);
      }
      wheel.style.width = `${Math.round(wheelWidth)}px`;
      wheel.style.left = `${Math.round(left)}px`;
      wheel.style.top = `${Math.round(top)}px`;
    };

    const updateWheelState = (emitChange = true) => {
      const maxIndex = items.length - 1;
      const index = clamp(Math.round((scroll.scrollTop || 0) / itemHeight), 0, maxIndex);
      const nextValue = min + index;
      items.forEach((item, itemIndex) => item.classList.toggle('is-active', itemIndex === index));
      if (String(nextValue) !== String(input.value)) {
        input.value = String(nextValue);
        updateGuestValues();
        if (emitChange) {
          try { input.dispatchEvent(new Event('change')); } catch (_) {}
        }
      }
    };

    let snapTimer = null;
    const onScroll = () => {
      updateWheelState(true);
      clearTimeout(snapTimer);
      snapTimer = setTimeout(() => {
        const index = clamp(Math.round((scroll.scrollTop || 0) / itemHeight), 0, items.length - 1);
        try {
          scroll.scrollTo({ top: index * itemHeight, behavior: 'smooth' });
        } catch (_) {
          scroll.scrollTop = index * itemHeight;
        }
      }, 70);
    };

    const onKeyDown = (event) => {
      if (event.key === 'Escape') destroyWheelPicker();
    };
    const onResize = () => destroyWheelPicker();

    dismiss?.addEventListener('click', destroyWheelPicker);
    scroll?.addEventListener('scroll', onScroll, { passive: true });
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('resize', onResize, { passive: true });

    requestAnimationFrame(() => {
      placeWheel();
      scroll.scrollTop = (currentValue - min) * itemHeight;
      updateWheelState(false);
    });

    closeWheelPicker = () => {
      clearTimeout(snapTimer);
      try { dismiss?.removeEventListener('click', destroyWheelPicker); } catch (_) {}
      try { scroll?.removeEventListener('scroll', onScroll); } catch (_) {}
      try { document.removeEventListener('keydown', onKeyDown); } catch (_) {}
      try { window.removeEventListener('resize', onResize); } catch (_) {}
      try { overlay.remove(); } catch (_) {}
    };
  }

  function openCustomDatePicker({ targetInput, kind }) {
    destroyWheelPicker();
    try {
      document.querySelectorAll('.dp-overlay').forEach(node => { try { node.remove(); } catch (_) {} });
    } catch (_) {}

    const seedFromInput = targetInput.value ? toMidday(targetInput.value) : null;
    const seedFromCheckin = (fromI?.value) ? toMidday(fromI.value) : null;
    const seedFromLast = (lastPickerViewY != null && lastPickerViewM != null) ? new Date(lastPickerViewY, lastPickerViewM, 1, 12, 0, 0) : null;
    const currentValue = seedFromInput || seedFromCheckin || seedFromLast || toMidday(isoToday);
    let viewY = (currentValue || new Date()).getFullYear();
    let viewM = (currentValue || new Date()).getMonth();
    lastPickerViewY = viewY;
    lastPickerViewM = viewM;

    const originalFrom = (fromI?.value || '').trim();
    const originalTo = (toI?.value || '').trim();

    let tempFrom = originalFrom;
    let tempTo = originalTo;

    // Range mode: choose check-in then check-out in one calendar
    // When opened from "Выезд", start by choosing checkout (if check-in exists)
    let step = (tempFrom && tempTo)
      ? 'done'
      : ((kind === 'from') ? 'from' : (tempFrom ? 'to' : 'from'));

    const overlay = document.createElement('div');
    overlay.className = 'dp-overlay';
    overlay.innerHTML = `
      <div class="dp-card" role="dialog" aria-modal="true">
        <div class="dp-title" id="dpKind"></div>
        <div class="dp-top">
          <button type="button" class="dp-nav" id="dpPrev" aria-label="Предыдущий месяц">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M12.5 4.5 7 10l5.5 5.5"></path></svg>
          </button>
          <div class="dp-selects">
            <div class="dp-chip">
              <select class="dp-select" id="dpMonth"></select>
              <svg class="dp-chip-icon" viewBox="0 0 20 20" aria-hidden="true">
                <path d="M6 8l4-4 4 4"></path>
                <path d="M6 12l4 4 4-4"></path>
              </svg>
            </div>
            <div class="dp-chip">
              <select class="dp-select" id="dpYear"></select>
              <svg class="dp-chip-icon" viewBox="0 0 20 20" aria-hidden="true">
                <path d="M6 8l4-4 4 4"></path>
                <path d="M6 12l4 4 4-4"></path>
              </svg>
            </div>
          </div>
          <button type="button" class="dp-nav" id="dpNext" aria-label="Следующий месяц">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 4.5 13 10l-5.5 5.5"></path></svg>
          </button>
        </div>
        <div class="dp-grid" id="dpGrid"></div>
        <div class="dp-actions">
          <button type="button" class="dp-action" id="dpCancel">Отмена</button>
          <button type="button" class="dp-action" id="dpReset">Сброс</button>
          <button type="button" class="dp-action dp-action--primary" id="dpSave" disabled>Сохранить</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const monthSel = overlay.querySelector('#dpMonth');
    const yearSel = overlay.querySelector('#dpYear');
    const gridEl = overlay.querySelector('#dpGrid');
    const prevBtn = overlay.querySelector('#dpPrev');
    const nextBtn = overlay.querySelector('#dpNext');
    const kindEl = overlay.querySelector('#dpKind');
    const cancelBtn = overlay.querySelector('#dpCancel');
    const resetBtn = overlay.querySelector('#dpReset');
    const saveBtn = overlay.querySelector('#dpSave');
    let titleAnimTimer = null;
    let lastTitle = '';

    const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
    monthSel.innerHTML = monthNames.map((n, i) => `<option value="${i}">${n}</option>`).join('');

    const nowY = new Date().getFullYear();
    const years = [];
    for (let y = nowY - 2; y <= nowY + 6; y++) years.push(y);
    yearSel.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');

    const close = () => {
      clearTimeout(titleAnimTimer);
      try { overlay.remove(); } catch(_) {}
    };

    const setTitle = (nextTitle) => {
      if (!kindEl) return;
      const text = String(nextTitle || '');
      if (!text || text === lastTitle) return;
      const shouldAnimate = !!lastTitle;
      lastTitle = text;

      clearTimeout(titleAnimTimer);
      kindEl.classList.remove('is-animating');
      kindEl.innerHTML = '';

      if (!shouldAnimate) {
        const currentSpan = document.createElement('span');
        currentSpan.className = 'dp-title__text dp-title__text--current';
        currentSpan.textContent = text;
        kindEl.appendChild(currentSpan);
        kindEl.dataset.currentText = text;
        return;
      }

      const oldSpan = document.createElement('span');
      oldSpan.className = 'dp-title__text dp-title__text--old';
      oldSpan.textContent = kindEl.dataset.currentText || '';

      const newSpan = document.createElement('span');
      newSpan.className = 'dp-title__text dp-title__text--new';
      newSpan.textContent = text;

      kindEl.appendChild(oldSpan);
      kindEl.appendChild(newSpan);
      kindEl.dataset.currentText = text;

      requestAnimationFrame(() => {
        kindEl.classList.add('is-animating');
      });

      titleAnimTimer = setTimeout(() => {
        kindEl.classList.remove('is-animating');
        kindEl.innerHTML = '';
        const current = document.createElement('span');
        current.className = 'dp-title__text dp-title__text--current';
        current.textContent = text;
        kindEl.appendChild(current);
      }, 260);
    };

    const canSave = () => {
      if (!tempFrom || !tempTo) return false;
      const a = toMidday(tempFrom);
      const b = toMidday(tempTo);
      return !!(a && b && b > a);
    };

    const updateActions = () => {
      if (!saveBtn) return;
      saveBtn.disabled = !canSave();
    };

    const isDisabledAsFrom = (dayIso) => {
      if (!dayIso) return true;
      if (isBooking && dayIso < isoToday) return true;
      if (!hasCampRoomsBusy && isBusyDay(dayIso)) return true;
      if (hasCampRoomsBusy) {
        const next = addDays(dayIso, 1);
        if (!next || !campCanStay(dayIso, next)) return true;
      }
      return false;
    };

    function isDisabled(dayIso) {
      if (!dayIso) return true;
      const effStep = (step === 'done') ? 'from' : step;
      if (effStep === 'from') {
        return isDisabledAsFrom(dayIso);
      }

      const fromIso = (tempFrom || '').trim();
      if (!fromIso) return false;
      const dDay = toMidday(dayIso);
      const dFrom = toMidday(fromIso);
      if (!dDay || !dFrom) return true;
      // While choosing checkout: allow clicking earlier/equal dates — treat as new check-in
      if (dDay <= dFrom) return isDisabledAsFrom(dayIso);
      if (hasCampRoomsBusy) {
        if (!campCanStay(fromIso, dayIso)) return true;
      } else {
        if (overlapRanges(fromIso, dayIso)) return true;
      }
      return false;
    }

    function render() {
      monthSel.value = String(viewM);
      yearSel.value = String(viewY);
      if (!gridEl) return;

      if (kindEl) {
        setTitle(step === 'from'
          ? 'Выберите дату заезда'
          : (step === 'to' ? 'Выберите дату выезда' : 'Выбранный период проживания'));
      }
      updateActions();

      const firstDay = new Date(viewY, viewM, 1).getDay(); // 0=Sun
      const adjustedFirstDay = firstDay === 0 ? 6 : firstDay - 1; // 0=Mon
      const daysInMonth = new Date(viewY, viewM + 1, 0).getDate();

      const selFrom = (tempFrom || '').trim();
      const selTo = (tempTo || '').trim();
      const dFrom = selFrom ? toMidday(selFrom) : null;
      const dTo = selTo ? toMidday(selTo) : null;

      let html = '';
      const dow = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
      for (const d of dow) html += `<div class="dp-dow">${d}</div>`;
      for (let i = 0; i < adjustedFirstDay; i++) html += `<div class="dp-empty"></div>`;

      for (let d = 1; d <= daysInMonth; d++) {
        const dateIso = `${viewY}-${String(viewM + 1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const isStart = selFrom === dateIso;
        const isEnd = selTo === dateIso;
        const isTod = isoToday === dateIso;

        const inRange = (dFrom && dTo) ? (() => {
          const dd = toMidday(dateIso);
          if (!dd) return false;
          return dd > dFrom && dd < dTo;
        })() : false;

        let busy = false;
        if (step === 'from' || step === 'done') {
          if (hasCampRoomsBusy) {
            if (dateIso >= isoToday) {
              const next = addDays(dateIso, 1);
              busy = !!(next && !campCanStay(dateIso, next));
            }
          } else {
            busy = isBusyDay(dateIso);
          }
        } else {
          const fromIso = selFrom;
          if (fromIso && dateIso > fromIso) {
            if (hasCampRoomsBusy) busy = !campCanStay(fromIso, dateIso);
            else busy = overlapRanges(fromIso, dateIso);
          } else {
            // For dates <= selected check-in, treat them as potential new check-in and show busy days
            if (hasCampRoomsBusy) {
              if (dateIso >= isoToday) {
                const next = addDays(dateIso, 1);
                busy = !!(next && !campCanStay(dateIso, next));
              }
            } else {
              busy = isBusyDay(dateIso);
            }
          }
        }

        const dis = isDisabled(dateIso);
        const cls = [
          'dp-day',
          (isStart || isEnd) ? 'selected' : '',
          isStart ? 'range-start' : '',
          isEnd ? 'range-end' : '',
          inRange ? 'in-range' : '',
          isTod ? 'today' : '',
          dis ? 'disabled' : '',
          busy ? 'busy' : '',
        ].filter(Boolean).join(' ');
        html += `<button type="button" class="${cls}" data-iso="${dateIso}" ${dis ? 'disabled' : ''}>${d}</button>`;
      }

      gridEl.innerHTML = html;

      gridEl.querySelectorAll('[data-iso]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          const iso = btn.getAttribute('data-iso');
          if (!iso || isDisabled(iso)) return;
          try {
            const d = toMidday(iso);
            if (d) { lastPickerViewY = d.getFullYear(); lastPickerViewM = d.getMonth(); }
          } catch (_) {}

          if (step === 'from' || step === 'done') {
            tempFrom = iso;
            tempTo = '';
            step = 'to';
            render();
            return;
          }

          const fromIso = (tempFrom || '').trim();
          if (!fromIso) { step = 'from'; render(); return; }
          const dFrom2 = toMidday(fromIso);
          const dTo2 = toMidday(iso);
          if (!dFrom2 || !dTo2) return;
          if (dTo2 <= dFrom2) {
            tempFrom = iso;
            tempTo = '';
            step = 'to';
            render();
            return;
          }

          tempTo = iso;
          step = 'done';
          render();
        });
      });
    }

    prevBtn.onclick = (e) => {
      e.preventDefault();
      viewM -= 1;
      if (viewM < 0) { viewM = 11; viewY -= 1; }
      lastPickerViewY = viewY; lastPickerViewM = viewM;
      render();
    };
    nextBtn.onclick = (e) => {
      e.preventDefault();
      viewM += 1;
      if (viewM > 11) { viewM = 0; viewY += 1; }
      lastPickerViewY = viewY; lastPickerViewM = viewM;
      render();
    };
    monthSel.onchange = () => { viewM = Number(monthSel.value) || 0; lastPickerViewY = viewY; lastPickerViewM = viewM; render(); };
    yearSel.onchange = () => { viewY = Number(yearSel.value) || viewY; lastPickerViewY = viewY; lastPickerViewM = viewM; render(); };

    if (cancelBtn) cancelBtn.onclick = () => close();
    if (resetBtn) {
      resetBtn.onclick = () => {
        tempFrom = '';
        tempTo = '';
        step = 'from';
        render();
      };
    }
    if (saveBtn) {
      saveBtn.onclick = () => {
        if (!canSave()) return;
        if (fromI) fromI.value = tempFrom || '';
        if (toI) toI.value = tempTo || '';
        sync();
        try { if (fromI) fromI.dispatchEvent(new Event('change')); } catch(_) {}
        try { if (toI) toI.dispatchEvent(new Event('change')); } catch(_) {}
        updateApplyUi();
        validateCampDatesOrReset();
        close();
      };
    }

    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    if (kindEl) {
      kindEl.dataset.currentText = '';
    }
    render();
  }

  // клики по видимым «кнопкам» — открывают наш календарь (без системного)
  fromB.addEventListener('click', (e) => { try { e.preventDefault(); e.stopPropagation(); } catch(_) {} openCustomDatePicker({ targetInput: fromI, kind: 'from' }); });
  toB.addEventListener('click',   (e) => { try { e.preventDefault(); e.stopPropagation(); } catch(_) {} openCustomDatePicker({ targetInput: toI,   kind: 'to'   }); });
  adBtn.addEventListener('click', (e) => { try { e.preventDefault(); e.stopPropagation(); } catch (_) {} openWheelPicker('adults'); });
  kdBtn.addEventListener('click', (e) => { try { e.preventDefault(); e.stopPropagation(); } catch (_) {} openWheelPicker('children'); });

  adSel.addEventListener('change', () => { updateGuestValues(); clearBkErrors(); applyCapacityConstraints(); updateApplyUi(); validateCampDatesOrReset(); });
  kdSel.addEventListener('change', () => { updateGuestValues(); clearBkErrors(); applyCapacityConstraints(); updateApplyUi(); validateCampDatesOrReset(); });
  splitChk.addEventListener('change', () => { clearBkErrors(); updateApplyUi(); validateCampDatesOrReset(); });
  fromI.addEventListener('change', () => { clearBkErrors(); applyCapacityConstraints(); updateApplyUi(); validateCampDatesOrReset(); });
  toI.addEventListener('change', () => { clearBkErrors(); applyCapacityConstraints(); updateApplyUi(); validateCampDatesOrReset(); });

  // кнопки
  card.querySelector('#bkClose').onclick = () => {
    destroyWheelPicker();
    // Если нужно восстановить фильтр при закрытии (например, если сброшен в корзине)
    // но только если не нажимали "Применить"
    if (shouldRestoreOnClose && originalFilter !== null) {
      if (Object.keys(originalFilter).length > 0) {
        window.__bookingFilter = JSON.parse(JSON.stringify(originalFilter));
      } else {
        window.__bookingFilter = null;
      }
      setFilterButtonActive(!!window.__bookingFilter);
      if (window.__bookingFilter) saveBookingFilter(window.__bookingFilter);
      else clearBookingFilter();
    }
    
    const filterModal = document.getElementById('filterModal');
    if (filterModal) {
      // If the booking filter is shown as a separate overlay, remove only it
      filterModal.remove();
      if (!isBooking) {
        try { loadCamps(); if (typeof restoreMapView === 'function') restoreMapView(); } catch(_) {}
        setFilterButtonActive(!!window.__bookingFilter);
      }
      if (opts.onClose) opts.onClose();
      return; // keep the underlying modal/card intact
    }
    // Fallback: when filter lives inside the main modal
    if (!isBooking) {
      try { loadCamps(); if (typeof restoreMapView === 'function') restoreMapView(); } catch(_) {}
      setFilterButtonActive(!!window.__bookingFilter);
    }
    if (opts.onClose) { opts.onClose(); return; }
    closeModal();
  };
  card.querySelector('#bkReset').onclick = ()=>{
    destroyWheelPicker();
    fromI.value=''; toI.value=''; adSel.value='2'; kdSel.value='0'; splitChk.checked=false; sync();
    updateGuestValues();
    // сброс — очищаем общий фильтр и перерисовываем всю карту
    window.__bookingFilter = null;
    clearBookingFilter();
    setFilterButtonActive(false);
    applyCapacityConstraints();
    // Активируем кнопку "Применить" при сбросе
    if (applyBtn) {
      applyBtn.disabled = false;
      applyBtn.classList.remove('is-disabled');
      applyBtn.setAttribute('aria-disabled', 'false');
      applyBtn.dataset.disabled = '0';
    }
    validateCampDatesOrReset();
    clearBkErrors();
  };
  card.querySelector('#bkApply').onclick = async ()=>{
    destroyWheelPicker();
    if (applyBtn && applyBtn.dataset.disabled === '1') { markErrors(); return; }
    const from = fromI.value || '';
    const to   = toI.value   || '';
    const adults = Number(adSel.value);
    const kids   = Number(kdSel.value);
    if (isBooking) {
      if (!from || !to) { markErrors(); return; }
      if (kids > 0 && adults <= 0) { markErrors(); return; }
      if (Number.isFinite(maxGuests) && maxGuests > 0 && (adults + kids) > maxGuests) { markErrors(); return; }
      try {
        const a = toMidday(from);
        const b = toMidday(to);
        if (!a || !b || b <= a) {
          markErrors();
          return;
        }
      } catch(_) {}
      if (busyRanges.length && overlapRanges(from, to)) { markErrors(); return; }
      if (hasCampRoomsBusy && !campCanStay(from, to)) { markErrors(); return; }
    } else {
      if (kids > 0 && adults <= 0) { markErrors(); return; }
    }
    window.__bookingFilter = {
      from,
      to,
      adults,
      kids,
      total: adults + kids,
      allowSplitRooms: splitChk.checked
    };
    saveBookingFilter(window.__bookingFilter);
    setFilterButtonActive(true);
    // Отменяем восстановление исходного фильтра, так как применили новый фильтр
    shouldRestoreOnClose = false;
    // Закрываем фильтр (если он отдельной модалкой поверх)
    const filterModal = document.getElementById('filterModal');
    if (filterModal) filterModal.remove();
    else closeModal();
    if (isBooking) {
      const cid = (opts.campId != null) ? Number(opts.campId) : Number(window.__currentCampId);
      if (typeof opts.onApply === 'function') { await opts.onApply(window.__bookingFilter); return; }
      if (!Number.isFinite(cid)) { appAlert('Не выбрана база отдыха'); return; }
      await openCampAccommodations(cid);
      return;
    }
    // Если работаем в режиме карты — сразу обновим список баз
    if (!isBooking) {
      try { loadCamps(); if (typeof restoreMapView === 'function') restoreMapView(); } catch(_) {}
    }
  };
}

function roomCapacity(r){
  const cap = Number(r.capacity);
  if (Number.isFinite(cap) && cap > 0) return cap;
  const b1 = Number(r.beds_single) || 0;
  const b2 = Number(r.beds_double) || 0;
  const guess = b1 + b2 * 2;
  return guess > 0 ? guess : 2;
}
function roomPriceFrom(r){
  const house = Number(r.price);
  const adult = Number(r.price_adult);
  if (Number.isFinite(house) && house > 0) return house;
  if (Number.isFinite(adult) && adult > 0) return adult;
  return 0;
}
function formatPriceRub(v){
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return '—';
  try { return n.toLocaleString('ru-RU') + ' ₽'; } catch(_) { return String(n) + ' ₽'; }
}

function renderRoomPriceBlock(room, variant = 'default'){
  const priceAdult = Number(room?.price_adult) || 0;
  const priceChild = Number(room?.price_child) || 0;
  const priceFixed = Number(room?.price) || 0;
  if (variant === 'room-detail') {
    const rows = [];
    if (priceAdult > 0) rows.push(`<div class="price-item"><span class="price-k">Взрослый</span><span class="price-v">${formatPriceRub(priceAdult)}</span></div>`);
    if (priceChild > 0) rows.push(`<div class="price-item"><span class="price-k">Ребёнок</span><span class="price-v">${formatPriceRub(priceChild)}</span></div>`);
    if (!rows.length && priceFixed > 0) rows.push(`<div class="price-item total"><span class="price-k">Стоимость</span><span class="price-v">${formatPriceRub(priceFixed)}</span></div>`);
    if (!rows.length) return '';
    return `
      <div class="alloc-price-card alloc-price-card--room-detail${rows.length === 1 ? ' is-single' : ''}">
        ${rows.join('')}
      </div>
    `;
  }
  const rows = [];
  if (priceAdult > 0) rows.push(`<div class="price-item"><span class="price-k">Взрослый</span><span class="price-v">${formatPriceRub(priceAdult)}</span></div>`);
  if (priceChild > 0) rows.push(`<div class="price-item"><span class="price-k">Ребёнок</span><span class="price-v">${formatPriceRub(priceChild)}</span></div>`);
  if (priceFixed > 0) rows.push(`<div class="price-item total"><span class="price-k">Итого</span><span class="price-v">${formatPriceRub(priceFixed)}</span></div>`);
  if (!rows.length) return '';
  return `
    <div class="alloc-price-card">
      ${rows.join('')}
    </div>
  `;
}

function calcRoomSubtotal(room, adults, kids){
  const a = Number(adults) || 0;
  const k = Number(kids) || 0;
  if ((a + k) <= 0) return 0;
  const fixed = Number(room?.price) || 0;
  if (fixed > 0) return fixed;
  const pa = Number(room?.price_adult) || 0;
  const pk = Number(room?.price_child) || 0;
  if (pa <= 0 && pk <= 0) return null;
  return a * pa + k * pk;
}

function autoDistributeGuests(selectedRooms, filter){
  const rooms = Array.isArray(selectedRooms) ? selectedRooms : [];
  const adultsTotal = Number(filter?.adults) || 0;
  const kidsTotal = Number(filter?.kids) || 0;
  const items = rooms.map(r => ({ room: r, adults: 0, kids: 0 }));
  if (!items.length) return items;

  let aLeft = adultsTotal;
  let kLeft = kidsTotal;

  // Никогда не превышаем вместимость комнаты: оставшиеся гости остаются «не размещены» (пользователь добавит вариант).
  // Евристика: стараемся сразу разместить часть детей (≈ половину вместимости), чтобы не загонять всех детей в один номер.
  for (let i = 0; i < items.length && (aLeft > 0 || kLeft > 0); i++) {
    const cap = roomCapacity(items[i].room);
    if (!Number.isFinite(cap) || cap <= 0) continue;

    const kidsTarget = kLeft > 0 ? Math.min(kLeft, Math.floor(cap / 2)) : 0;
    let adultsHere = 0;
    let kidsHere = 0;

    if (kidsTarget > 0 && aLeft > 0) {
      kidsHere = kidsTarget;
      adultsHere = Math.min(aLeft, cap - kidsHere);
      if (adultsHere <= 0) {
        // детям нужен взрослый
        kidsHere = 0;
      }
    }

    // если детей не ставили — заселяем взрослых
    if (adultsHere <= 0 && aLeft > 0) {
      adultsHere = Math.min(aLeft, cap);
    }

    // если есть взрослые и осталась вместимость — добавляем детей
    const usedAfterAdults = adultsHere;
    if (usedAfterAdults > 0 && kLeft > kidsHere) {
      const remCap = Math.max(0, cap - (usedAfterAdults + kidsHere));
      const addKids = Math.min(remCap, (kLeft - kidsHere));
      kidsHere += addKids;
    }

    // финальный кап
    if (adultsHere + kidsHere > cap) {
      const over = adultsHere + kidsHere - cap;
      // режем детей в первую очередь
      kidsHere = Math.max(0, kidsHere - over);
    }
    // дети только со взрослым
    if (kidsHere > 0 && adultsHere <= 0) {
      kidsHere = 0;
    }

    items[i].adults = adultsHere;
    items[i].kids = kidsHere;
    aLeft -= adultsHere;
    kLeft -= kidsHere;
  }
  return items;
}

function validateAllocation(items, filter){
  const errors = [];
  const perItem = [];
  let sumAdults = 0;
  let sumKids = 0;
  let totalPrice = 0;
  let priceUnknown = false;
  const nights = bookingNightsFromFilter(filter);

  (items || []).forEach((it) => {
    const a = Number(it.adults) || 0;
    const k = Number(it.kids) || 0;
    sumAdults += a;
    sumKids += k;

    const cap = roomCapacity(it.room);
    const itemErrors = [];
    if (k > 0 && a <= 0) itemErrors.push('Дети возможны только вместе со взрослым');
    if ((a + k) > cap) itemErrors.push(`Превышена вместимость (${cap})`);
    const sub = calcRoomSubtotal(it.room, a, k);
    if (sub == null) priceUnknown = true;
    else totalPrice += sub * nights;
    perItem.push(itemErrors);
  });

  const needAdults = Number(filter?.adults);
  const needKids = Number(filter?.kids);
  if (Number.isFinite(needAdults) && Number.isFinite(needKids)) {
    if (sumAdults !== needAdults || sumKids !== needKids) {
      errors.push(`Распределите гостей: взрослые ${sumAdults}/${needAdults}, дети ${sumKids}/${needKids}`);
    }
  }
  return {
    ok: errors.length === 0 && perItem.every(a => a.length === 0),
    errors,
    perItem,
    sumAdults,
    sumKids,
    totalPrice: priceUnknown ? null : totalPrice,
  };
}

async function createBookingsFromAllocation(campId, filter, items, comment){
  const cid = Number(campId);
  const from = filter?.from;
  const to = filter?.to;
  const userComment = String(comment || '').trim();
  const payloadItems = (items || [])
    .map(it => ({
      room_id: Number(it.room?.id),
      adults: Number(it.adults) || 0,
      kids: Number(it.kids) || 0,
    }))
    .filter(x => Number.isFinite(x.room_id) && (x.adults + x.kids) > 0);

  // Future-ready payload
  window.__lastBookingRoomsPayload = payloadItems;

  const resp = await authFetchJson('/api/auth/orders', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      camp_id: cid,
      check_in: from,
      check_out: to,
      items: payloadItems.map(it => ({
        room_id: it.room_id,
        adults: it.adults,
        kids: it.kids,
      })),
      comment: userComment || undefined,
    })
  });
  return resp;
}

// Показываем развёрнутое уведомление после успешного бронирования
function showBookingSuccessNotification(result, opts = {}) {
  let orderId = null;
  let bookingIds = null;
  if (result && typeof result === 'object' && !Array.isArray(result)) {
    orderId = result.order_id || result.orderId || null;
    bookingIds = result.booking_ids || result.bookingIds || null;
  } else if (Array.isArray(result)) {
    bookingIds = result;
  } else if (result != null) {
    orderId = String(result);
  }

  const idsText = orderId
    ? `№${orderId}`
    : (Array.isArray(bookingIds) && bookingIds.length > 1
      ? `№${bookingIds.join(', №')}`
      : `№${(bookingIds && bookingIds[0]) || '—'}`);
  
  const modal = document.createElement('div');
  modal.className = 'modal show';
  modal.style.zIndex = '9999';
  
  modal.innerHTML = `
    <div class="modal-card" style="max-width:400px;text-align:center;padding:24px">
      <div style="font-size:48px;margin-bottom:16px">✅</div>
      <div style="font-size:20px;font-weight:600;margin-bottom:12px;color:#22c55e">Заявка отправлена!</div>
      <div style="font-size:14px;line-height:1.5;color:#e5e7eb;margin-bottom:16px">
        Ваша заявка на бронирование ${idsText} успешно создана.
      </div>
      <div style="font-size:13px;line-height:1.6;color:#9ca3af;margin-bottom:20px">
        Администратор проверит данные и подтвердит бронь. Вы получите уведомление о статусе заявки.
        <br><br>
        Вы также можете следить за статусом брони в личном кабинете.
        <br><br>
        <strong style="color:#22c55e">Приятного отдыха! 🏖️</strong>
      </div>
      <button class="button primary" id="successOkBtn" style="width:100%">Понятно</button>
    </div>
  `;
  
  document.body.appendChild(modal);
  const onDone = (opts && typeof opts.onDone === 'function') ? opts.onDone : null;
  
  const okBtn = modal.querySelector('#successOkBtn');
  if (okBtn) {
    okBtn.onclick = () => {
      try { modal.remove(); } catch (_) {}
      if (onDone) { try { onDone(); } catch (_) {} }
    };
  }
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      try { modal.remove(); } catch (_) {}
      if (onDone) { try { onDone(); } catch (_) {} }
    }
  });
}

function openBookingCommentModal({ initialValue = '', onBack, onSubmit } = {}){
  showModal(`
    <div class="alloc-card">
      <div class="accom-head">
        <div class="accom-title">Комментарий к заказу</div>
        <div class="accom-sub muted">Необязательно</div>
      </div>

      <textarea id="orderComment"
        style="width:100%;min-height:120px;resize:none;border-radius:14px;border:1px solid var(--border-color);background:rgba(255,255,255,0.03);color:var(--tg-text);padding:12px;box-sizing:border-box;outline:none;"
        placeholder="Например:\n— Приедем поздно вечером\n— Нужны раздельные кровати\n— Будем с ребёнком\n— Нужны отчётные документы"></textarea>

      <div class="alloc-actions is-row">
        <button class="button ghost" id="orderCommentBack">Назад</button>
        <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff;font-weight:600" id="orderCommentSubmit">БРОНИРУЮ!</button>
      </div>
    </div>
  `);
  try { document.getElementById('modalCard').dataset.view = 'booking-comment'; } catch (_) {}

  const ta = document.getElementById('orderComment');
  if (ta) {
    ta.value = String(initialValue || '');
    try { ta.focus(); } catch (_) {}
  }
  const backBtn = document.getElementById('orderCommentBack');
  const submitBtn = document.getElementById('orderCommentSubmit');

  if (backBtn) {
    backBtn.onclick = () => {
      if (typeof onBack === 'function') { try { onBack(); } catch (_) {} return; }
      closeModal();
    };
  }
  if (submitBtn) {
    submitBtn.onclick = async () => {
      const text = ta ? ta.value : '';
      submitBtn.disabled = true;
      submitBtn.textContent = 'Отправляем...';
      try {
        if (typeof onSubmit === 'function') await onSubmit(text);
      } catch (e) {
        showSnackbar({ message: e?.message || 'Не удалось отправить заявку', timeoutMs: 2200 });
        submitBtn.disabled = false;
        submitBtn.textContent = 'БРОНИРУЮ!';
      }
    };
  }
}

// Функция форматирования кроватей для отображения
function formatBedsInfo(room) {
  const bedsSingle = Number(room.beds_single) || 0;
  const bedsDouble = Number(room.beds_double) || 0;
  const beds = [];
  if (bedsSingle > 0) beds.push(`${bedsSingle}× одноместная`);
  if (bedsDouble > 0) beds.push(`${bedsDouble}× двухместная`);
  return beds.length > 0 ? beds.join(', ') : '';
}

// Открытие полноэкранной галереи фото апартамента
function openPhotoGallery(photos, roomName) {
  if (!Array.isArray(photos) || photos.length === 0) return;
  
  const photoUrls = photos.map(p => p?.url || p).filter(Boolean);
  if (photoUrls.length === 0) return;

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.style.display = 'flex';
  // keep above tabbar/modals
  modal.style.zIndex = '7000';

  const card = document.createElement('div');
  card.style.cssText = `
    width: 100vw;
    height: 100vh;
    background: #000;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 0;
    border-radius: 0;
    max-height: none;
    box-shadow: none;
    animation: none;
  `;

  let currentIdx = 0;

  const imgEl = document.createElement('img');
  imgEl.style.cssText = `
    max-width: 100%;
    max-height: calc(100vh - 60px);
    object-fit: contain;
    border-radius: 0;
  `;
  imgEl.src = photoUrls[currentIdx];

  const controlsEl = document.createElement('div');
  controlsEl.style.cssText = `
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 12px;
    background: rgba(0,0,0,0.8);
    box-sizing: border-box;
    gap: 12px;
    position: absolute;
    bottom: 0;
    left: 0;
  `;

  const prevBtn = document.createElement('button');
  prevBtn.textContent = '← Назад';
  prevBtn.style.cssText = `
    flex: 1;
    padding: 10px;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px;
    color: #fff;
    cursor: pointer;
  `;
  prevBtn.onclick = () => {
    currentIdx = (currentIdx - 1 + photoUrls.length) % photoUrls.length;
    imgEl.src = photoUrls[currentIdx];
    counterEl.textContent = `${currentIdx + 1} / ${photoUrls.length}`;
  };

  const counterEl = document.createElement('div');
  counterEl.style.cssText = `
    color: #fff;
    font-size: 14px;
    min-width: 50px;
    text-align: center;
  `;
  counterEl.textContent = `${currentIdx + 1} / ${photoUrls.length}`;

  const nextBtn = document.createElement('button');
  nextBtn.textContent = 'Вперёд →';
  nextBtn.style.cssText = `
    flex: 1;
    padding: 10px;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px;
    color: #fff;
    cursor: pointer;
  `;
  nextBtn.onclick = () => {
    currentIdx = (currentIdx + 1) % photoUrls.length;
    imgEl.src = photoUrls[currentIdx];
    counterEl.textContent = `${currentIdx + 1} / ${photoUrls.length}`;
  };

  const closeBtn = document.createElement('button');
  closeBtn.textContent = 'Закрыть ✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 10px 16px;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px;
    color: #fff;
    cursor: pointer;
    z-index: 101;
  `;
  closeBtn.onclick = () => modal.remove();

  controlsEl.appendChild(prevBtn);
  controlsEl.appendChild(counterEl);
  controlsEl.appendChild(nextBtn);

  card.appendChild(imgEl);
  card.appendChild(controlsEl);
  card.appendChild(closeBtn);
  modal.appendChild(card);
  document.body.appendChild(modal);

  modal.onclick = (e) => {
    if (e.target === modal) modal.remove();
  };
}

// Открытие детальной карточки апартамента без кнопки выбрать
function openRoomDetailsViewOnly(room, camp) {
  const photos = Array.isArray(room.photos) ? room.photos : [];
  const pics = photos.map(p => p.url);
  const cap = roomCapacity(room);
  const priceAdult = Number(room.price_adult) || 0;
  const priceChild = Number(room.price_child) || 0;
  const priceHouse = Number(room.price) || 0;
  const descHtml = room.description ? room.description.replace(/\n/g, '<br>') : '';

  const floors = Number(room.floors) || 0;
  const floor = Number(room.floor) || 0;
  const bedsSingle = Number(room.beds_single) || 0;
  const bedsDouble = Number(room.beds_double) || 0;

  const bathShort = (() => {
    const s = String(room?.bath_type || '').trim();
    if (!s) return 'Нет';
    return roomParamLabel(s, 'bath');
  })();
  const wcShort = (() => {
    const s = String(room?.wc_type || '').trim();
    if (!s) return 'Нет';
    return roomParamLabel(s, 'wc');
  })();
  const shareVal = (v) => {
    const s = String(v || '').trim();
    if (s === 'private') return 'Индивидуальная';
    if (s === 'shared') return 'Общая';
    return 'Нет';
  };
  const shareValOptional = (v) => {
    const s = String(v || '').trim();
    if (s === 'private') return 'Индивидуальная';
    if (s === 'shared') return 'Общая';
    return null;
  };

  const compactParams = [];
  compactParams.push(['Вместимость', `до ${cap || '?'} гостей`]);
  compactParams.push(['Тип', room.room_type || '—']);
  if (bedsSingle > 0) compactParams.push(['Одноместная 🛏️', String(bedsSingle)]);
  if (bedsDouble > 0) compactParams.push(['Двухместная 🛏️', String(bedsDouble)]);
  compactParams.push(['Кухня', shareVal(room.kitchen_type)]);
  compactParams.push(['Туалет', wcShort]);

  const allParams = [];
  allParams.push(['Вместимость', `до ${cap || '?'} гостей`]);
  allParams.push(['Тип', room.room_type || '—']);
  if (bedsSingle > 0) allParams.push(['Одноместная 🛏️', String(bedsSingle)]);
  if (bedsDouble > 0) allParams.push(['Двухместная 🛏️', String(bedsDouble)]);
  allParams.push(['Душ/Ванна', bathShort]);
  allParams.push(['Туалет', wcShort]);
  allParams.push(['Зона барбекю', shareVal(room.bbq_type)]);
  allParams.push(['Кухня', shareVal(room.kitchen_type)]);
  const gazebo = shareValOptional(room.gazebo_type);
  if (gazebo) allParams.push(['Беседка', gazebo]);
  const terrace = shareValOptional(room.terrace_type);
  if (terrace) allParams.push(['Терраса', terrace]);
  const pool = shareValOptional(room.pool_type);
  if (pool) allParams.push(['Бассейн', pool]);

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.style.display = 'flex';

  const card = document.createElement('div');
  card.className = 'modal-card';

  let html = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px">
      <div>
        <h3 style="margin:0 0 4px 0">${room.name || '—'}</h3>
        <p style="margin:0;color:var(--tg-hint);font-size:13px">${camp?.name || ''}</p>
      </div>
      <button id="closeRoomDetailsBtn" type="button" title="Назад" style="background:none;border:none;color:var(--tg-text);font-size:20px;cursor:pointer">✕</button>
    </div>
  `;

  if (descHtml) {
    html += `<p style="font-size:13px;line-height:1.4;color:var(--tg-hint);margin:0 0 12px 0">${descHtml}</p>`;
  }

  html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">';
  compactParams.forEach(([k, v]) => {
    html += `<div style="display:flex;flex-direction:column;gap:4px;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px">
      <div style="font-size:11px;color:var(--tg-hint)">${k}</div>
      <div style="font-weight:600">${v}</div>
    </div>`;
  });
  html += '</div>';

  if (pics.length > 0) {
    html += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:8px;margin-bottom:16px">`;
    pics.forEach((url, i) => {
      html += `<img src="${url}" alt="Фото ${i+1}" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px;cursor:pointer" data-pic-idx="${i}">`;
    });
    html += '</div>';
  }

  html += '<div style="display:grid;gap:8px;margin-bottom:16px">';
  allParams.forEach(([k, v]) => {
    html += `<div style="display:flex;justify-content:space-between;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px">
      <span style="color:var(--tg-hint)">${k}</span>
      <span style="font-weight:600">${v}</span>
    </div>`;
  });
  html += '</div>';

  card.innerHTML = html;

  const closeBtn = card.querySelector('#closeRoomDetailsBtn');
  if (closeBtn) {
    closeBtn.onclick = () => modal.remove();
  }

  const picImgs = card.querySelectorAll('img[data-pic-idx]');
  picImgs.forEach(img => {
    img.onclick = () => {
      const idx = Number(img.getAttribute('data-pic-idx'));
      if (Number.isFinite(idx)) {
        openPhotoGallery(photos, room.name);
      }
    };
  });

  modal.appendChild(card);
  document.body.appendChild(modal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.remove();
  });
}

// Окно подтверждения бронирования с распределением гостей и итоговой суммой
async function openBookingConfirmationModal({ camp, campId, rooms, filter, onBack, initialItems }) {
  const cid = Number(campId);
  const selectedRooms = Array.isArray(rooms) ? rooms : [];
  const okToProceed = await confirmReplaceBookingDraftIfDifferentCamp({
    nextCampId: cid,
    nextCampName: camp?.name || '',
    willAddRooms: selectedRooms.length > 0,
  });
  if (!okToProceed) return;

  const f = filter || window.__bookingFilter || {};
  const addWord = housingLabelAddWord(camp?.housing_type);
  const choiceWord = housingLabelGenPluralWord(camp?.housing_type);
  const isReadyFilter = (flt) => {
    if (!flt || typeof flt !== 'object') return false;
    if (!flt.from || !flt.to) return false;
    const from = new Date(flt.from);
    const to = new Date(flt.to);
    if (!Number.isFinite(from.getTime()) || !Number.isFinite(to.getTime())) return false;
    if (to <= from) return false;
    const adults = Math.max(0, Number(flt.adults) || 0);
    const kids = Math.max(0, Number(flt.kids) || 0);
    if (adults + kids <= 0) return false;
    if (kids > 0 && adults < 1) return false;
    return true;
  };
  
  // Автоматически распределяем гостей по выбранным апартаментам
  const items = (() => {
    const src = Array.isArray(initialItems) ? initialItems : null;
    if (!src || src.length === 0) return autoDistributeGuests(selectedRooms, f);
    const normalized = [];
    for (const it of src) {
      const room = it?.room;
      const rid = Number(room?.id);
      if (!Number.isFinite(rid)) continue;
      const cap = roomCapacity(room);
      let adults = Math.max(0, Number(it?.adults) || 0);
      let kids = Math.max(0, Number(it?.kids) || 0);
      if (kids > 0 && adults < 1) adults = 1;
      if (Number.isFinite(cap) && cap > 0) {
        const sum = adults + kids;
        if (sum > cap) {
          const over = sum - cap;
          const reduceKids = Math.min(kids, over);
          kids -= reduceKids;
          adults = Math.max(0, adults - Math.max(0, over - reduceKids));
          if (kids > 0 && adults < 1) {
            kids = 0;
            adults = Math.min(adults || 0, cap);
          }
        }
      }
      normalized.push({ room, adults, kids });
    }
    return normalized.length ? normalized : autoDistributeGuests(selectedRooms, f);
  })();
  
  // Загружаем все доступные апартаменты для добавления
  let availableRooms = [];
  
	  // Состояние подбора вариантов размещения
	  let autoPickVariants = [];
	  let autoPickIndex = 0;
	  let autoPickActive = false;
	  let autoPickSnapshot = null; // снимок корзины ДО подбора (для отмены при 1 варианте)
	  let autoPickSnapshotIsSingle = false;

  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); shell.classList.remove('accom-shell'); shell.classList.remove('room-detail-shell'); }

  showModal(`
	      <div class="alloc-card">
	      <div class="accom-head">
	        <div class="accom-title">Лист бронирования</div>
	        <div class="accom-sub">
	          ${camp?.name ? `${camp.name} • ` : ''}
	          <button type="button" class="bk-input bk-input-inline" id="confirmEditDates">${fmtDateRu(f.from)} → ${fmtDateRu(f.to)}</button>
	        </div>
	      </div>

      <div class="alloc-hint muted" id="confirmHint">Проверьте данные бронирования и распределите гостей.</div>

      <div class="alloc-list" id="confirmList"></div>
      
      <button class="button ghost" id="confirmAddRoom" style="width:100%">+ Добавить ${addWord}</button>

		      <div class="alloc-summary" id="confirmSummary" style="display:none"></div>
	      
		      <div class="alloc-pick-actions is-full" id="confirmPickActions">
		        <div class="pick-col pick-main">
		          <button class="button ghost alloc-autopick" id="confirmAutoPick">Подбор в этой базе</button>
		        </div>
		        <div class="pick-col pick-cancel">
		          <button class="button ghost" id="confirmCancelPick" style="border-color:#ef4444;color:#ef4444">Отменить подбор</button>
		        </div>
		      </div>

		      <div class="alloc-actions is-row">
		        <button class="button ghost" id="confirmBack">Закрыть корзину</button>
		        <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff;font-weight:600" id="confirmSubmit">БРОНИРУЮ!</button>
		      </div>
		    </div>
		  `);
  try { document.getElementById('modalCard').dataset.view = 'booking-confirmation'; } catch (_) {}

  const listEl = document.getElementById('confirmList');
  const hintEl = document.getElementById('confirmHint');
  const summaryEl = document.getElementById('confirmSummary');
	  const submitBtn = document.getElementById('confirmSubmit');
	  const addRoomBtn = document.getElementById('confirmAddRoom');
	  const autoPickBtn = document.getElementById('confirmAutoPick');
	  const cancelPickBtn = document.getElementById('confirmCancelPick');
	  const pickActionsEl = document.getElementById('confirmPickActions');
	  const editDatesBtn = document.getElementById('confirmEditDates');

  // Multi-cart отключён

  if (summaryEl) {
    summaryEl.innerHTML = '';
    summaryEl.style.display = 'none';
  }

  function reopenCartWithItems(nextItems) {
    const normalized = (Array.isArray(nextItems) ? nextItems : items)
      .map(it => ({
        room: it?.room,
        adults: Math.max(0, Number(it?.adults) || 0),
        kids: Math.max(0, Number(it?.kids) || 0),
      }))
      .filter(it => Number.isFinite(Number(it?.room?.id)));
    openBookingConfirmationModal({
      camp,
      campId: cid,
      rooms: normalized.map(it => it.room),
      filter: f,
      onBack,
      initialItems: normalized,
    });
  }

  let isAllocationComplete = false;

  if (editDatesBtn) {
    editDatesBtn.onclick = async () => {
      try {
        const cur = window.__bookingFilter || {};
        window.__bookingFilter = {
          from: f.from || cur.from || null,
          to: f.to || cur.to || null,
          adults: Number.isFinite(Number(f.adults)) ? Number(f.adults) : (Number(cur.adults) || 2),
          kids: Number.isFinite(Number(f.kids)) ? Number(f.kids) : (Number(cur.kids) || 0),
          total: Number.isFinite(Number(f.total)) ? Number(f.total) : (Number(cur.total) || undefined),
          allowSplitRooms: (f.allowSplitRooms != null) ? !!f.allowSplitRooms : !!cur.allowSplitRooms,
        };
      } catch (_) {}

      const ht = normalizeHousingType(camp?.housing_type);
      openBookingFilterModal({
        mode: 'booking',
        campId: cid,
        title: 'Выберите даты и гостей',
        hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.',
        applyText: `Применить`,
        dontCloseBackground: true,
        restoreFilterOnClose: true,
        campHousingType: ht,
        onApply: async (newFilter) => {
          if (!newFilter || typeof newFilter !== 'object') return;
          f.from = newFilter.from || null;
          f.to = newFilter.to || null;
          f.adults = Number(newFilter.adults) || 0;
          f.kids = Number(newFilter.kids) || 0;
          f.total = Number(newFilter.total) || ((Number(newFilter.adults) || 0) + (Number(newFilter.kids) || 0)) || undefined;
          f.allowSplitRooms = !!newFilter.allowSplitRooms;

          reopenCartWithItems(items);
        },
      });
    };
  }

  function persistDraft(){
    const payload = {
      v: 1,
      campId: cid,
      campName: camp?.name || '',
      filter: {
        from: f.from || null,
        to: f.to || null,
        adults: Number(f.adults) || 0,
        kids: Number(f.kids) || 0,
        allowSplitRooms: !!f.allowSplitRooms,
        total: Number(f.total) || undefined,
      },
      items: items
        .map(it => ({
          room_id: Number(it?.room?.id),
          adults: Number(it?.adults) || 0,
          kids: Number(it?.kids) || 0,
        }))
        .filter(it => Number.isFinite(it.room_id)),
      updatedAt: Date.now(),
    };
    const hasItems = Array.isArray(payload.items) && payload.items.length > 0;
    // Если нет items — не сохраняем, но и не очищаем всю корзину (clearBookingDraft удаляет из мульти-корзины)
    if (!hasItems) {
      return;
    }
    saveBookingDraft(payload);
  }

  // Автодозаполнение: после добавления апартамента размещаем оставшихся гостей,
  // не меняя уже выставленные значения в существующих карточках.
  function autoFillRemainingGuests(){
    const needAdults = Math.max(0, Number(f.adults) || 0);
    const needKids = Math.max(0, Number(f.kids) || 0);
    let remAdults = Math.max(0, needAdults - items.reduce((s, it) => s + (Number(it?.adults) || 0), 0));
    let remKids = Math.max(0, needKids - items.reduce((s, it) => s + (Number(it?.kids) || 0), 0));
    if (remAdults === 0 && remKids === 0) return;

    for (let idx = items.length - 1; idx >= 0; idx--) {
      const it = items[idx];
      const room = it?.room;
      const cap = roomCapacity(room);
      if (!Number.isFinite(cap) || cap <= 0) continue;

      const curA = Math.max(0, Number(it.adults) || 0);
      const curK = Math.max(0, Number(it.kids) || 0);
      it.adults = curA;
      it.kids = curK;

      let free = cap - (curA + curK);
      if (free <= 0) continue;

      // Если хотим добавить детей в пустой апартамент — сначала добавляем 1 взрослого
      if (remKids > 0 && it.adults === 0 && it.kids === 0) {
        if (remAdults > 0 && free > 0) {
          it.adults += 1;
          remAdults -= 1;
          free -= 1;
        }
      }

      // Добавляем детей (только если уже есть взрослый в этом апартаменте)
      if (remKids > 0 && it.adults > 0 && free > 0) {
        const addKids = Math.min(remKids, free);
        it.kids += addKids;
        remKids -= addKids;
        free -= addKids;
      }

      // Добавляем взрослых
      if (remAdults > 0 && free > 0) {
        const addAdults = Math.min(remAdults, free);
        it.adults += addAdults;
        remAdults -= addAdults;
        free -= addAdults;
      }

      if (remAdults === 0 && remKids === 0) break;
    }
  }

  window.__bookingConfirmationModalContext = {
    camp,
    campId: cid,
    filter: f,
    onBack,
    items,
    addRoom: (room) => {
      if (isAllocationComplete) {
        showSnackbar({ message: 'Выбрано достаточное количество апартаментов для размещения всех гостей.', timeoutMs: 2200 });
        return false;
      }
      const rid = Number(room?.id);
      if (!Number.isFinite(rid)) return false;
      if (items.some(it => Number(it?.room?.id) === rid)) return false;
      items.push({ room, adults: 0, kids: 0 });
      autoFillRemainingGuests();
      return true;
    },
    reopen: () => reopenCartWithItems(items),
  };

  // Функция открытия выбора гостей (центр, стилистика фильтра + ограничения)
	  function openGuestPicker(idx) {
	    const it = items[idx];
	    const room = it.room || {};
	    const cap = roomCapacity(room);
	    const bedsInfo = formatBedsInfo(room);
	    const priceAdult = Number(room.price_adult) || 0;
	    const priceChild = Number(room.price_child) || 0;
	    const priceFixed = Number(room.price) || 0;
	    const adultRateText = priceAdult > 0 ? `${formatPriceRub(priceAdult)}/сутки` : '';
	    const childRateText = priceChild > 0 ? `${formatPriceRub(priceChild)}/сутки` : '';
	    const fixedRateText = (!adultRateText && !childRateText && priceFixed > 0) ? `${formatPriceRub(priceFixed)}/сутки (за дом)` : '';

	    const sheet = document.createElement('div');
	    sheet.className = 'modal show';
	    // Должно быть поверх #modal (корзина), но ниже auth/fullscreen
	    sheet.style.zIndex = '6800';

	    sheet.innerHTML = `
	      <div class="modal-card" style="width:92vw;max-width:380px;margin:0 auto;border-radius:18px">
	        <div style="font-size:18px;font-weight:700;margin-bottom:12px;text-align:center">Распределение гостей</div>
	        <div style="font-size:13px;color:#9ca3af;margin-bottom:${bedsInfo ? '8px' : '16px'};text-align:center">
	          ${room.name || room.room_type || 'Апартамент'} (до ${cap} гостей)
	        </div>
	        ${bedsInfo ? `<div style="font-size:12px;color:#9ca3af;margin-bottom:16px;text-align:center">Спальные места: ${bedsInfo}</div>` : ''}

	        <div style="display:grid;gap:12px;margin-bottom:18px">
	          <div class="bk-field" style="display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:12px">
	            <span style="color:#9aa3af;font-size:13px">Взрослые</span>
	            <span class="muted" style="margin:0;font-size:12px;justify-self:end">${adultRateText || fixedRateText || '&nbsp;'}</span>
	            <select id="guestAdults" class="bk-select" style="width:100px"></select>
	          </div>
	          <div class="bk-field" style="display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:12px">
	            <span style="color:#9aa3af;font-size:13px">Дети</span>
	            <span class="muted" style="margin:0;font-size:12px;justify-self:end">${childRateText || '&nbsp;'}</span>
	            <select id="guestKids" class="bk-select" style="width:100px"></select>
	          </div>
	          <div class="muted" style="text-align:center;font-size:12px">Дети размещаются только с минимум одним взрослым</div>
	        </div>

        <div style="display:grid;gap:10px">
          <button class="button primary" id="guestApply" style="width:100%">Применить</button>
          <button class="button ghost" id="guestCancel" style="width:100%">Отмена</button>
        </div>
      </div>
    `;

    document.body.appendChild(sheet);

    const applyBtn = sheet.querySelector('#guestApply');
    const cancelBtn = sheet.querySelector('#guestCancel');
    const adultsSelect = sheet.querySelector('#guestAdults');
    const kidsSelect = sheet.querySelector('#guestKids');

    // Заполняем селекты с учётом текущих значений
    const fillAdults = () => {
      adultsSelect.innerHTML = Array.from({ length: cap + 1 }, (_, i) => `
        <option value="${i}" ${i === it.adults ? 'selected' : ''}>${i}</option>
      `).join('');
    };

    const fillKids = (maxKids) => {
      const currentVal = kidsSelect.value;
      const current = currentVal !== '' ? Math.max(0, parseInt(currentVal, 10) || 0) : (it.kids || 0);
      kidsSelect.innerHTML = Array.from({ length: maxKids + 1 }, (_, i) => `
        <option value="${i}" ${i === current ? 'selected' : ''}>${i}</option>
      `).join('');
    };

    const recalcOptions = () => {
      const adults = Number(adultsSelect.value) || 0;
      // Дети только если есть минимум 1 взрослый
      const maxKids = adults > 0 ? Math.max(0, cap - adults) : 0;
      fillKids(maxKids);
      const kids = Number(kidsSelect.value) || 0;
      // Общая валидация: не превышаем вместимость и дети не без взрослого
      const total = adults + kids;
      const validAdults = kids === 0 || adults > 0;
      const withinCap = total <= cap;
      const ok = validAdults && withinCap;
      applyBtn.disabled = !ok;
      applyBtn.style.opacity = ok ? '1' : '0.55';
    };

    fillAdults();
    fillKids(Math.max(0, cap - (it.adults || 0 || 0)));
    recalcOptions();

    adultsSelect.addEventListener('change', recalcOptions);
    kidsSelect.addEventListener('change', recalcOptions);

    applyBtn.onclick = () => {
      let adults = Number(adultsSelect.value) || 0;
      let kids = Number(kidsSelect.value) || 0;
      // Автоправка: если дети есть, но взрослых 0 — ставим 1 взрослого
      if (kids > 0 && adults === 0) adults = 1;
      // Доп. защита: дети не больше остатка вместимости
      const maxKids = Math.max(0, cap - adults);
      if (kids > maxKids) kids = maxKids;

      items[idx].adults = adults;
      items[idx].kids = kids;
      sheet.remove();
      render();
      updateSummary();
    };

    cancelBtn.onclick = () => sheet.remove();
    sheet.addEventListener('click', (e) => {
      if (e.target === sheet) sheet.remove();
    });
  }

	  function render() {
	    if (!listEl) return;
	    const nights = bookingNightsFromFilter(f);
	    listEl.innerHTML = items.map((it, idx) => {
	      const room = it.room || {};
	      const cap = roomCapacity(room);
      const photos = Array.isArray(room.photos) ? room.photos : [];
	      const cover = photos.find(p => p && p.cover) || photos[0];
	      const thumb = cover?.url ? `<img class="alloc-thumb" src="${cover.url}" alt="" data-idx="${idx}" style="cursor:pointer">` : `<div class="alloc-thumb ph"></div>`;
	      const sub = calcRoomSubtotal(room, it.adults, it.kids);
	      const subText = (sub == null) ? '—' : formatPriceRub(sub * nights);
	      const total = (Number(it.adults) || 0) + (Number(it.kids) || 0);
	      const bedsInfo = formatBedsInfo(room);
	      const bedsLine = bedsInfo ? `<div class="alloc-meta muted">${bedsInfo}</div>` : '';
      
      return `
        <div class="alloc-item-new" data-idx="${idx}">
          ${thumb}
          <div class="alloc-main-new">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <div class="alloc-name" data-idx="${idx}" style="cursor:pointer">${room.name || room.room_type || 'Апартамент'}</div>
              <button class="alloc-remove-btn" data-idx="${idx}" type="button" title="Удалить">🗑️</button>
            </div>
            <div class="alloc-meta muted">до ${cap} гостей • ${subText}</div>
            ${bedsLine}
            <button class="alloc-guest-btn" data-idx="${idx}" type="button">
              Гостей: ${total} (взр: ${it.adults || 0}, дети: ${it.kids || 0})
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Обработчики кнопок выбора гостей
    listEl.querySelectorAll('.alloc-guest-btn').forEach(btn => {
      btn.onclick = () => {
        const idx = Number(btn.getAttribute('data-idx'));
        if (Number.isFinite(idx)) openGuestPicker(idx);
      };
    });

    // Обработчики кликов по фото — открываем точно так же, как в карточке апартамента (полноэкранка)
    listEl.querySelectorAll('.alloc-thumb[data-idx]').forEach(img => {
      img.onclick = (e) => {
        try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
        const idx = Number(img.getAttribute('data-idx'));
        if (!Number.isFinite(idx) || !items[idx]) return;
        const room = items[idx].room || {};
        const photos = Array.isArray(room.photos) ? room.photos : [];
        const pics = photos.map(p => (p && typeof p === 'object') ? p.url : p).filter(Boolean);
        if (pics.length > 0) openFullscreenGallery(pics, 0, { showBook: false });
      };
    });

    // Обработчики кликов по названию (открытие деталей)
    listEl.querySelectorAll('.alloc-name[data-idx]').forEach(nameEl => {
      nameEl.onclick = () => {
        const idx = Number(nameEl.getAttribute('data-idx'));
        if (Number.isFinite(idx) && items[idx]) {
          const room = items[idx].room || {};
          openRoomDetails(room, camp, {
            viewOnly: true,
            onBack: () => {
              try {
                const ctx = window.__bookingConfirmationModalContext;
                if (ctx && typeof ctx.reopen === 'function') { ctx.reopen(); return; }
              } catch (_) {}
              try { window.__suppressDraftToastOnce = true; openBookingDraft({ dontChangeTab: true }); } catch (_) {}
            },
          });
        }
      };
    });
    
	    // Обработчики кнопок удаления
		    listEl.querySelectorAll('.alloc-remove-btn').forEach(btn => {
		      btn.onclick = async (e) => {
		        e.stopPropagation();
		        const idx = Number(btn.getAttribute('data-idx'));
		        if (Number.isFinite(idx)) {
		          const name = (items[idx]?.room?.class || items[idx]?.room?.name || items[idx]?.room?.room_type || 'апартамент').toString();
		          const ok = await showConfirmModal({
		            title: 'Удалить из корзины?',
		            message: `Удалить «${name}» из корзины?`,
		            confirmText: 'Удалить',
		            cancelText: 'Отмена',
		            danger: true,
		          });
		          if (!ok) return;
		          autoPickActive = false;
		          autoPickIndex = 0;
		          items.splice(idx, 1);
	          // Если удалили последний апартамент, показываем пустую корзину (фильтр сохраняем)
			          if (items.length === 0) {
			            // Удаляем корзину этой базы из мульти-корзины
			            removeBookingMultiCart(cid);
			            // Также очищаем одиночный черновик если он от этой базы
			            const d = window.__bookingDraft || loadBookingDraft();
		            if (d && Number(d.campId) === cid) {
		              try { localStorage.removeItem(BOOKING_DRAFT_KEY); } catch (_) {}
		              window.__bookingDraft = null;
		            }
			            updateBookingDraftUi();
			            openEmptyBookingConfirmationModal({ filter: f });
			            return;
			          }
		          render();
		          updateSummary();
		          persistDraft();
		        }
		      };
		    });
		  }

	  function updateSummary() {
		    const v = validateAllocation(items, f);
		    const totalGuests = (Number(f.adults) || 0) + (Number(f.kids) || 0);
		    const allocatedGuests = v.sumAdults + v.sumKids;
		    const isFilterReady = !!(f.from && f.to && totalGuests > 0 && !(Number(f.kids) > 0 && (Number(f.adults) || 0) < 1));
		    
		    if (hintEl) {
		      if (!isFilterReady) {
		        hintEl.classList.remove('ok', 'warn', 'err');
		        hintEl.classList.add('muted');
		        hintEl.textContent = 'Укажите даты и количество гостей, чтобы продолжить бронирование.';
		      } else {
		      const typeName = String((items[0]?.room?.class || items[0]?.room?.name || 'Размещение') || 'Размещение');
		      const needAdults = Number(f.adults) || 0;
		      const needKids = Number(f.kids) || 0;
		      const remainAdults = Math.max(0, needAdults - v.sumAdults);
	      const remainKids = Math.max(0, needKids - v.sumKids);
	      const remainTotal = remainAdults + remainKids;
	      
	      const plural = (n, one, few, many) => {
	        const x = Math.abs(Number(n) || 0) % 100;
	        const y = x % 10;
	        if (x > 10 && x < 20) return many;
	        if (y > 1 && y < 5) return few;
	        if (y === 1) return one;
	        return many;
	      };
	      const adultsTxt = (n) => `${n} ${plural(n, 'взрослый', 'взрослых', 'взрослых')}`;
	      const adultsGenTxt = (n) => `${n} ${plural(n, 'взрослого', 'взрослых', 'взрослых')}`;
	      const kidsTxt = (n) => `${n} ${plural(n, 'ребёнок', 'детей', 'детей')}`;
	      const kidsGenTxt = (n) => `${n} ${plural(n, 'ребёнка', 'детей', 'детей')}`;
	      
	      const suggestionVariants = (() => {
	        if (!availableRooms || !availableRooms.length || remainTotal <= 0) return [];
	        const selectedIds = new Set(items.map(it => Number(it?.room?.id)).filter(Number.isFinite));
	        const pool = availableRooms
	          .filter(r => Number.isFinite(Number(r?.id)) && !selectedIds.has(Number(r.id)))
	          .filter(r => (roomCapacity(r) || 0) > 0);
	        if (!pool.length) return [];

	        const groupName = (r) => String(r?.class || r?.name || r?.room_type || 'Вариант').trim() || 'Вариант';
	        const allocationText = (rooms) => {
	          const by = new Map();
	          for (const r of rooms || []) {
	            const name = groupName(r);
	            by.set(name, (by.get(name) || 0) + 1);
	          }
	          return Array.from(by.entries())
	            .map(([name, cnt]) => `${cnt}× «${name}»`)
	            .join(' + ');
	        };
	        const score = (rooms) => {
	          const cnt = (rooms || []).length;
	          const cap = (rooms || []).reduce((s, r) => s + (roomCapacity(r) || 0), 0);
	          const over = Math.max(0, cap - remainTotal);
	          const price = (rooms || []).reduce((s, r) => s + (roomPriceFrom(r) || 0), 0);
	          return { cnt, over, price };
	        };

	        const best = findBestAllocation(pool, remainTotal);
	        if (!best || !best.length) return [];
	        const bestText = allocationText(best);
	        const bestKey = best.map(r => Number(r?.id)).filter(Number.isFinite).sort((a,b)=>a-b).join(',');

	        let altBest = null;
	        let altKey = '';
	        for (const r of best) {
	          const rid = Number(r?.id);
	          if (!Number.isFinite(rid)) continue;
	          const alt = findBestAllocation(pool.filter(x => Number(x?.id) !== rid), remainTotal);
	          if (!alt || !alt.length) continue;
	          const key = alt.map(x => Number(x?.id)).filter(Number.isFinite).sort((a,b)=>a-b).join(',');
	          if (!key || key === bestKey) continue;
	          if (!altBest) { altBest = alt; altKey = key; continue; }
	          const a = score(alt);
	          const b = score(altBest);
	          if (a.cnt !== b.cnt) { if (a.cnt < b.cnt) { altBest = alt; altKey = key; } continue; }
	          if (a.over !== b.over) { if (a.over < b.over) { altBest = alt; altKey = key; } continue; }
	          if (a.price !== b.price) { if (a.price < b.price) { altBest = alt; altKey = key; } continue; }
	        }

	        const out = [];
	        if (bestText) out.push(bestText);
	        if (altBest && altKey && altKey !== bestKey) {
	          const altText = allocationText(altBest);
	          if (altText && altText !== bestText) out.push(altText);
	        }
	        return out;
	      })();
	      
	      const itemErrors = [];
	      (v.perItem || []).forEach((errs, idx) => {
	        if (!errs || errs.length === 0) return;
	        const name = (items[idx]?.room?.class || items[idx]?.room?.name || items[idx]?.room?.room_type || `#${idx + 1}`).toString();
	        errs.forEach(err => itemErrors.push(`${name}: ${err}`));
	      });

	      hintEl.classList.remove('ok', 'warn', 'err', 'muted');
	      
		      if (allocatedGuests > totalGuests) {
		        hintEl.classList.add('err');
		        hintEl.textContent = `${typeName}: размещено ${adultsTxt(v.sumAdults)}${v.sumKids ? `, ${kidsTxt(v.sumKids)}` : ''}. Указано в фильтре: ${adultsTxt(needAdults)}${needKids ? ` и ${kidsTxt(needKids)}` : ''}.`;
		      } else if (itemErrors.length) {
		        hintEl.classList.add('err');
		        hintEl.innerHTML = itemErrors.join('<br>');
			      } else if (allocatedGuests < totalGuests) {
		        hintEl.classList.add('warn');
		        const placedParts = [];
		        if (v.sumAdults > 0) placedParts.push(adultsTxt(v.sumAdults));
		        if (v.sumKids > 0) placedParts.push(kidsTxt(v.sumKids));
	        const remainParts = [];
	        if (remainAdults > 0) remainParts.push(adultsGenTxt(remainAdults));
	        if (remainKids > 0) remainParts.push(kidsGenTxt(remainKids));
		        let text = `${typeName}: размещено ${placedParts.length ? placedParts.join(', ') : '0 гостей'}. `;
		        text += `Для размещения ещё ${remainParts.length ? remainParts.join(' и ') : '0 гостей'} вам нужно добавить ${choiceWord}`;
		        if (suggestionVariants.length) {
		          text += `: ${suggestionVariants[0]}`;
		          if (suggestionVariants[1]) text += ` или ${suggestionVariants[1]}`;
		          text += '.';
		          text += ` Нажмите «Подбор ${choiceWord} для вас».`;
		        } else {
		          text += '.';
		        }
		        hintEl.textContent = text;
			      } else {
			        hintEl.classList.add('ok');
			        hintEl.textContent = 'Всё готово к бронированию!';
			      }

		      const canApplyGuestChanges = items.length > 0 && allocatedGuests > totalGuests;
		      if (canApplyGuestChanges && typeof hintEl.textContent === 'string' && hintEl.innerHTML === hintEl.textContent) {
		        hintEl.appendChild(document.createTextNode(' '));
		        const btn = document.createElement('button');
		        btn.type = 'button';
		        btn.className = 'hint-link';
		        btn.textContent = 'Применить изменения';
		        btn.onclick = () => {
		          f.adults = v.sumAdults;
		          f.kids = v.sumKids;
		          f.total = (v.sumAdults + v.sumKids) || undefined;
			          try {
			            window.__bookingFilter = Object.assign({}, window.__bookingFilter || {}, {
			              from: f.from || null,
			              to: f.to || null,
			              adults: Number(f.adults) || 0,
			              kids: Number(f.kids) || 0,
			              total: Number(f.total) || undefined,
			              allowSplitRooms: !!f.allowSplitRooms,
			            });
			          } catch (_) {}
			          try { if (window.__bookingFilter) saveBookingFilter(window.__bookingFilter); } catch (_) {}
			          updateSummary();
			        };
		        hintEl.appendChild(btn);
		      }
		      }
		    }
		    
			    if (summaryEl) {
			      const canShowSummary = items.length > 0 && v.ok && allocatedGuests === totalGuests && v.totalPrice != null;
			      if (canShowSummary) {
	        const needKids = Math.max(0, Number(f.kids) || 0);
	        const nights = bookingNightsFromFilter(f);
	        let adultsCost = 0;
	        let kidsCost = 0;
	        for (const it of items) {
	          const a = Math.max(0, Number(it?.adults) || 0);
	          const k = Math.max(0, Number(it?.kids) || 0);
	          if ((a + k) <= 0) continue;
	          const fixed = Number(it?.room?.price) || 0;
	          if (fixed > 0) {
	            const total = a + k;
	            const perStay = fixed * nights;
	            const adultPart = Math.round(perStay * (a / total));
	            adultsCost += adultPart;
	            kidsCost += (perStay - adultPart);
	            continue;
	          }
	          const pa = Number(it?.room?.price_adult) || 0;
	          const pk = Number(it?.room?.price_child) || 0;
	          if (pa > 0) adultsCost += a * pa * nights;
	          if (pk > 0) kidsCost += k * pk * nights;
	        }

	        const priceText = formatPriceRub(v.totalPrice);
	        const stayText = formatBookingStayText(f);
	        const totalLabel = stayText ? `Итого за ${stayText}` : 'Итого';
	        const rows = [];
	        rows.push(`<div class="alloc-row"><div class="muted">Взрослые (${v.sumAdults})</div><div class="alloc-val">${formatPriceRub(adultsCost)}</div></div>`);
	        if (needKids > 0) {
	          rows.push(`<div class="alloc-row"><div class="muted">Дети (${v.sumKids})</div><div class="alloc-val">${formatPriceRub(kidsCost)}</div></div>`);
	        }
	        rows.push(`<div class="alloc-row" style="font-weight:600;font-size:16px"><div>${totalLabel}</div><div class="alloc-val">${priceText}</div></div>`);
	        summaryEl.innerHTML = rows.join('');
	        summaryEl.style.display = '';
	      } else {
	        summaryEl.innerHTML = '';
			        summaryEl.style.display = 'none';
			      }
			    }
	    if (editDatesBtn && isFilterReady) editDatesBtn.classList.remove('bk-error');
	    if (submitBtn && !submitBtn.disabled) {
	      const blocked = !isFilterReady || !v.ok || allocatedGuests !== totalGuests;
	      submitBtn.classList.toggle('is-disabled', blocked);
	      submitBtn.setAttribute('aria-disabled', blocked ? 'true' : 'false');
	    }
	    updateAutoPickButton();
	    if (addRoomBtn) {
	      isAllocationComplete = items.length > 0 && v.ok && allocatedGuests === totalGuests;
	      addRoomBtn.style.display = isAllocationComplete ? 'none' : '';
	    }
	    persistDraft();
	  }
  
	  // Загружаем доступные апартаменты базы для выбранных дат (чтобы подсказки/добавление были корректны)
	  (async () => {
	    try {
	      let rooms = [];
	      if (f.from && f.to) {
	        const q = new URLSearchParams({ from: f.from, to: f.to });
	        const resp = await fetch(`/api/camps/${cid}/available-rooms?${q.toString()}`).then(r => r.ok ? r.json() : null);
	        const all = Array.isArray(resp?.rooms) ? resp.rooms : [];
	        rooms = all.filter(r => r && r.available);
	      } else {
	        const data = await fetch(`/api/rooms?camp_id=${cid}`).then(r => r.ok ? r.json() : []);
	        rooms = Array.isArray(data) ? data : [];
	      }
	      availableRooms = rooms;
	      updateSummary();
	    } catch (e) {
	      console.error('Не удалось загрузить апартаменты:', e);
	    }
	  })();
  
  // Кнопка добавления апартамента
	  if (addRoomBtn) {
	    addRoomBtn.onclick = async () => {
	      if (isAllocationComplete) {
	        showSnackbar({ message: 'Выбрано достаточное количество апартаментов для размещения всех гостей.', timeoutMs: 2200 });
	        return;
	      }
	      if (!availableRooms.length) {
	        alert('Апартаменты не загружены. Попробуйте еще раз.');
	        return;
	      }

      // Используем стандартное окно выбора апартаментов, как при нажатии "Апартаменты" в меню Подробнее
      // Но при выборе апартамента добавляем его в корзину вместо открытия деталей
      
      const campData = camp || await getCampQuick(cid);
      if (!campData) return;

      // Показываем окно со списком апартаментов (как в openCampAccommodations)
      const ht = normalizeHousingType(campData.housing_type);
      
      showModal(`
        <div class="accom-card">
          <div class="accom-head">
            <div class="accom-title">${campData.name || 'База'} • Добавить ${addWord}</div>
            <div class="accom-sub">Выберите вариант для добавления в бронирование</div>
          </div>
          <div class="accom-list" id="addRoomListStd"></div>
          <div class="accom-actions">
            <button class="button ghost" id="addRoomBackStd">Отмена</button>
          </div>
        </div>
      `);

      const listEl = document.getElementById('addRoomListStd');
      const backBtn = document.getElementById('addRoomBackStd');
      
      if (backBtn) {
        backBtn.onclick = closeModal;
      }

      if (!listEl) return;

      const selectedIds = new Set(items.map(it => Number(it?.room?.id)).filter(Number.isFinite));
      const unusedRooms = availableRooms.filter(r => !selectedIds.has(Number(r?.id)));

      if (unusedRooms.length === 0) {
        listEl.innerHTML = '<div class="muted">Все варианты уже добавлены</div>';
        return;
      }

      // Группируем по типам как в стандартном окне
      const groups = new Map();
      for (const r of unusedRooms) {
        const key = `${r.room_type || 'Дом'}::${r.class || r.name || 'Стандарт'}`;
        if (!groups.has(key)) {
          groups.set(key, { ...r, count: 1, minPrice: r.price || r.price_adult || 0, rooms: [r] });
        } else {
          const g = groups.get(key);
          g.count++;
          g.rooms.push(r);
          const rPrice = r.price || r.price_adult || 0;
          if (rPrice && (!g.minPrice || rPrice < g.minPrice)) g.minPrice = rPrice;
        }
      }

      listEl.innerHTML = '';
      for (const [key, g] of groups) {
        const cap = roomCapacity(g);
        const photos = Array.isArray(g.photos) ? g.photos : [];
        const coverPhoto = photos.find(p => p.cover) || photos[0];
        const thumbUrl = coverPhoto?.url || '/static/uploads/temp/placeholder.jpg';

        const item = document.createElement('button');
        item.className = 'accom-item';
        item.dataset.key = key;
        
        item.innerHTML = `
          <img class="accom-thumb" src="${thumbUrl}" alt="">
          <div class="accom-main">
            <div class="accom-name">${g.class || g.name || 'Без названия'}</div>
            <div class="accom-meta">до ${cap || '?'} гостей • доступно: ${g.count}</div>
          </div>
          <div class="accom-price">от ${(g.minPrice && g.minPrice > 0) ? g.minPrice.toLocaleString('ru-RU') : '—'}&nbsp;₽</div>
        `;
        
        item.onclick = () => {
          // Если только один вариант - открываем карточку
          if (g.rooms.length === 1) {
            const room = g.rooms[0];
            openRoomDetailsFromCart(room, campData, { rooms: g.rooms });
          } else {
            // Если несколько вариантов - показываем их список
            const shell = document.getElementById('modalCard');
            if (shell) {
              shell.classList.remove('booking-shell');
              shell.classList.remove('details');
              shell.classList.add('accom-shell');
            }
            showModal(`
              <div class="accom-card">
                <div class="accom-head">
                  <div class="accom-title">${campData.name || 'База'} • ${g.class || g.name || 'Апартаменты'}</div>
                  <div class="accom-sub">Выберите конкретный вариант для подробностей</div>
                </div>
                <div class="accom-body">
                  <div class="accom-list" id="addRoomVariants"></div>
                </div>
                <div class="accom-actions">
                  <button class="button ghost" id="addRoomBackVariants">Назад</button>
                </div>
              </div>
            `);

            const variantsEl = document.getElementById('addRoomVariants');
            const backVariantsBtn = document.getElementById('addRoomBackVariants');

            if (backVariantsBtn) {
              backVariantsBtn.onclick = () => {
                closeModal();
                // Восстанавливаем предыдущее окно
                addRoomBtn.onclick();
              };
            }

            if (variantsEl) {
              variantsEl.innerHTML = g.rooms.map(room => {
                const photos = Array.isArray(room.photos) ? room.photos : [];
                const cover = photos.find(p => p.cover) || photos[0];
                const thumbUrl = cover?.url || '/static/uploads/temp/placeholder.jpg';
                const price = room.price || room.price_adult || 0;
                const priceText = price > 0 ? `${price.toLocaleString('ru-RU')} ₽` : '—';
                
                return `
                  <button class="accom-item" data-room-id="${room.id}">
                    <img class="accom-thumb" src="${thumbUrl}" alt="">
                    <div class="accom-main">
                      <div class="accom-name">${room.name || 'Апартамент'}</div>
                      <div class="accom-meta">до ${roomCapacity(room)} гостей</div>
                    </div>
                    <div class="accom-price">${priceText}</div>
                  </button>
                `;
              }).join('');

              variantsEl.querySelectorAll('.accom-item').forEach(btn => {
                btn.onclick = () => {
                  const roomId = Number(btn.getAttribute('data-room-id'));
                  const room = g.rooms.find(r => Number(r.id) === roomId);
                  if (!room) return;
                  openRoomDetailsFromCart(room, campData, { rooms: g.rooms });
                };
              });
            }
          }
        };
        
        listEl.appendChild(item);
      }
    };
  }
  
  // Логика кнопки автоподбора апартаментов
	  function calculateAutoPickVariants() {
	    const totalGuests = (Number(f.adults) || 0) + (Number(f.kids) || 0);
	    if (totalGuests <= 0 || !availableRooms.length) return [];
	    const allowSplit = !!f.allowSplitRooms;

	    const scoreVariant = (rooms) => {
	      const cnt = (rooms || []).length;
	      const sumCap = (rooms || []).reduce((s, r) => s + (roomCapacity(r) || 0), 0);
	      const overcap = Math.max(0, sumCap - totalGuests);
	      const price = (rooms || []).reduce((s, r) => s + (roomPriceFrom(r) || 0), 0);
	      return { cnt, overcap, price };
	    };

	    // Если split запрещён — ищем лучший одиночный вариант
	    if (!allowSplit) {
	      const candidates = availableRooms
	        .map(r => ({ r, cap: roomCapacity(r), price: roomPriceFrom(r) || 0 }))
	        .filter(x => Number(x.cap) > 0 && Number(x.cap) >= totalGuests);
	      candidates.sort((a, b) => (a.cap - b.cap) || ((a.price || 0) - (b.price || 0)));
	      if (!candidates.length) return [];
	      const room = candidates[0].r;
	      return [{ key: String(room.id), rooms: [room] }];
	    }

	    // Генерируем несколько лучших комбинаций через перебор исключений (ограниченно)
	    const variantsMap = new Map();
	    const queue = [new Set()];
	    const seenExcl = new Set();

	    while (queue.length && variantsMap.size < 8) {
	      const excl = queue.shift();
	      const exclKey = Array.from(excl).sort((a,b)=>a-b).join(',');
	      if (seenExcl.has(exclKey)) continue;
	      seenExcl.add(exclKey);

	      const pool = availableRooms.filter(r => !excl.has(Number(r?.id)));
	      const best = findBestAllocation(pool, totalGuests);
	      if (!best || !best.length) continue;

	      const key = best.map(r => Number(r?.id)).filter(Number.isFinite).sort((a,b)=>a-b).join(',');
	      if (!key) continue;
	      if (!variantsMap.has(key)) {
	        variantsMap.set(key, { key, rooms: best });
	        // создаём альтернативы, исключая по одному элементу найденного решения
	        for (const r of best) {
	          const rid = Number(r?.id);
	          if (!Number.isFinite(rid)) continue;
	          const next = new Set(excl);
	          next.add(rid);
	          if (next.size <= 4) queue.push(next);
	        }
	      }
	    }

	    const variants = Array.from(variantsMap.values());
	    variants.sort((a, b) => {
	      const sa = scoreVariant(a.rooms);
	      const sb = scoreVariant(b.rooms);
	      if (sa.cnt !== sb.cnt) return sa.cnt - sb.cnt;
	      if (sa.overcap !== sb.overcap) return sa.overcap - sb.overcap;
	      return sa.price - sb.price;
	    });
	    return variants;
	  }
  
				  function updateAutoPickButton() {
				    if (!autoPickBtn) return;
				    if (pickActionsEl) {
				      pickActionsEl.classList.toggle('is-split', !!autoPickActive);
				      pickActionsEl.classList.toggle('is-full', !autoPickActive);
				    }
				    if (cancelPickBtn) {
				      cancelPickBtn.disabled = !autoPickActive;
				      cancelPickBtn.tabIndex = autoPickActive ? 0 : -1;
				      cancelPickBtn.setAttribute('aria-hidden', autoPickActive ? 'false' : 'true');
				    }
				    
				    const totalGuests = (Number(f.adults) || 0) + (Number(f.kids) || 0);
				    const allocatedGuests = items.reduce((sum, it) => sum + (it.adults || 0) + (it.kids || 0), 0);
		        const hasRooms = Array.isArray(availableRooms) && availableRooms.length > 0;
		        const totalGuestsPositive = totalGuests > 0;
		        const isFilterReady = !!(f.from && f.to && totalGuestsPositive);
		        
		        // Кнопка подбора всегда видима в корзине
		        autoPickBtn.style.display = '';
		        if (!hasRooms || !isFilterReady) {
		          autoPickBtn.textContent = !isFilterReady
		            ? 'Подбор доступен после выбора дат и гостей'
		            : 'Подбор в этой базе';
		          autoPickBtn.disabled = true;
		          autoPickBtn.style.opacity = '0.5';
		          return;
		        }
			    
			    // Кнопка подбора показывается всегда когда есть апартаменты и фильтр готов
		        const shouldShow = true;
	        if (shouldShow) {
	          autoPickBtn.style.display = '';
		      
	          // Пересчитываем варианты только если подбор не активен или нет сохранённых вариантов
	          if (!autoPickActive || items.length === 0 || !autoPickVariants.length) {
	            autoPickVariants = calculateAutoPickVariants();
	            autoPickIndex = 0;
	            autoPickActive = false;
	            autoPickSnapshot = null;
	            autoPickSnapshotIsSingle = false;
	          }
		      
			      if (autoPickVariants.length === 0) {
			        autoPickBtn.textContent = 'Подбор в этой базе';
			        autoPickBtn.disabled = true;
			        autoPickBtn.style.opacity = '0.5';
			      } else if (autoPickVariants.length === 1) {
			        autoPickBtn.textContent = autoPickActive ? 'Подбор применён' : 'Подбор в этой базе';
			        autoPickBtn.disabled = false;
			        autoPickBtn.style.opacity = '1';
			      } else {
			        autoPickBtn.textContent = autoPickActive ? 'Следующий подбор' : 'Подбор в этой базе';
			        autoPickBtn.disabled = false;
			        autoPickBtn.style.opacity = '1';
			      }
			    } else {
			      autoPickBtn.style.display = 'none';
			    }
			  }
  
		  const scrollCartToTop = () => {
		    try { modal.scrollTo({ top: 0, behavior: 'smooth' }); return; } catch (_) {}
		    try { modal.scrollTop = 0; } catch (_) {}
		  };

		  const cloneCartItems = (src) => (Array.isArray(src) ? src : []).map(it => ({
		    room: it?.room,
		    adults: Math.max(0, Number(it?.adults) || 0),
		    kids: Math.max(0, Number(it?.kids) || 0),
		  })).filter(it => Number.isFinite(Number(it?.room?.id)));

		  const ensureAutoPickSnapshot = async () => {
		    if (autoPickSnapshot) return true;
		    if (items.length > 0) {
		      const ok = await showConfirmModal({
		        title: 'Подбор апартаментов',
		        message: 'В случае подбора выбранные вами апартаменты будут удалены из корзины. Продолжить?',
		        confirmText: 'Продолжить',
		        cancelText: 'Отмена',
		        danger: true,
		      });
		      if (!ok) return false;
		    }
		    autoPickSnapshot = cloneCartItems(items);
		    return true;
		  };

		  const applyAutoPickVariant = (variant) => {
		    if (!variant || !Array.isArray(variant.rooms) || variant.rooms.length === 0) return;
		    items.length = 0;
		    for (const room of variant.rooms) {
		      items.push({ room, adults: 0, kids: 0 });
		    }
		    const distributed = autoDistributeGuests(variant.rooms, f);
		    distributed.forEach((d, i) => {
		      if (items[i]) {
		        items[i].adults = d.adults;
		        items[i].kids = d.kids;
		      }
		    });
		    autoPickActive = true;
		    render();
		    updateSummary();
		    updateAutoPickButton();
		    scrollCartToTop();
		  };

		  if (autoPickBtn) {
		    autoPickBtn.onclick = async () => {
		      if (!autoPickVariants.length) return;
		      const ok = await ensureAutoPickSnapshot();
		      if (!ok) return;
		      // Если только один вариант — применяем его
		      if (autoPickVariants.length === 1) {
		        autoPickIndex = 0;
		        applyAutoPickVariant(autoPickVariants[0]);
		        return;
		      }
		      const variant = autoPickVariants[autoPickIndex];
		      autoPickIndex = (autoPickIndex + 1) % autoPickVariants.length;
		      applyAutoPickVariant(variant);
		    };
		  }

	  if (cancelPickBtn) {
	    cancelPickBtn.onclick = () => {
	      if (!autoPickSnapshot) return;
	      const restored = cloneCartItems(autoPickSnapshot);
	      items.length = 0;
	      for (const it of restored) items.push(it);
	      autoPickIndex = 0;
	      autoPickActive = false;
	      autoPickSnapshot = null;
	      autoPickSnapshotIsSingle = false;
	      render();
	      updateSummary();
	      updateAutoPickButton();
	      scrollCartToTop();
	    };
	  }

		  document.getElementById('confirmBack').onclick = () => {
		    closeAllWindowsAndShowMap();
		  };

		  document.getElementById('confirmSubmit').onclick = async () => {
		    if (!isBookingFilterReady(f)) {
		      markBookingDatesButtonRequired(editDatesBtn);
		      updateSummary();
		      return;
		    }
		    const v = validateAllocation(items, f);
		    if (!v.ok) { updateSummary(); return; }
		    if (!getAuth() || !getAuth().token) {
		      window.__postAuthAction = () => { try { openBookingDraft(); } catch (_) {} };
		      showAuthChoiceModal({
	        subtitle: 'Для отправки заявки на бронирование необходимо авторизоваться.',
	        onCancel: () => {},
	        onLogin: () => { openLogin(); },
	        onRegister: () => { openRegister(); },
	      });
	      return;
	    }
	    openBookingCommentModal({
	      onBack: () => reopenCartWithItems(items),
	      onSubmit: async (commentText) => {
	        const res = await createBookingsFromAllocation(cid, f, items, commentText);
	        window.__suppressDraftToastOnce = true;
	        clearBookingDraft();
	        closeModal();

	        showBookingSuccessNotification(res, {
	          onDone: () => {
	            closeAllWindows();
	            setTabById('tab-account');
	            openAccountBookings('active');
	          }
	        });
	      }
	    });
	  };

  render();
  updateSummary();
}

function openAllocationModal({ camp, campId, roomsAvailable, selectedRooms, filter, onBack, initialItems }){
  const cid = Number(campId);
  const f = filter || window.__bookingFilter || {};
  const available = Array.isArray(roomsAvailable) ? roomsAvailable : [];
  const selected = Array.isArray(selectedRooms) ? selectedRooms : [];

  const items = (() => {
    const src = Array.isArray(initialItems) ? initialItems : null;
    if (src && src.length) {
      const normalized = [];
      for (const it of src) {
        const room = it?.room;
        const rid = Number(room?.id);
        if (!Number.isFinite(rid)) continue;
        let adults = Math.max(0, Number(it?.adults) || 0);
        let kids = Math.max(0, Number(it?.kids) || 0);
        if (kids > 0 && adults < 1) adults = 1;
        normalized.push({ room, adults, kids });
      }
      if (normalized.length) return normalized;
    }
    return autoDistributeGuests(selected, f);
  })();

  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); shell.classList.remove('accom-shell'); }

  showModal(`
    <div class="alloc-card">
      <div class="accom-head">
        <div class="accom-title">Распределение гостей</div>
        <div class="accom-sub">${camp?.name ? `${camp.name} • ` : ''}${fmtDateRu(f.from)} → ${fmtDateRu(f.to)}</div>
      </div>

      <div class="alloc-hint muted" id="allocHint"></div>

      <div class="alloc-list" id="allocList"></div>

      <div class="alloc-add">
        <select class="alloc-select" id="allocAddSelect">
          <option value="">Добавить апартамент…</option>
          ${available
            .filter(r => r && r.id && !items.some(it => Number(it.room?.id) === Number(r.id)))
            .map(r => `<option value="${r.id}">${(r.name || r.room_type || 'Апартамент')} (до ${roomCapacity(r)})</option>`)
            .join('')}
        </select>
        <button class="button ghost" id="allocAddBtn">Добавить</button>
      </div>

	      <div class="alloc-summary" id="allocSummary" style="display:none"></div>

      <div class="alloc-actions">
        <button class="button ghost" id="allocBack">Назад</button>
        <button class="button primary" id="allocSubmit">Отправить заявку</button>
      </div>
    </div>
  `);

	  const listEl = document.getElementById('allocList');
	  const hintEl = document.getElementById('allocHint');
	  const summaryEl = document.getElementById('allocSummary');
	  const submitBtn = document.getElementById('allocSubmit');

	  if (summaryEl) {
	    summaryEl.innerHTML = '';
	    summaryEl.style.display = 'none';
	  }

  // Сохраняем контекст в глобальную переменную для доступа из openRoomDetailsFromCart
  window.__allocationModalContext = {
    items,
    camp,
    campId: cid,
    availableRooms: available,
    filter: f,
    onBack,
  };

	  function render(){
	    if (!listEl) return;
	    const nights = bookingNightsFromFilter(f);
	    listEl.innerHTML = items.map((it, idx) => {
	      const room = it.room || {};
	      const cap = roomCapacity(room);
      const photos = Array.isArray(room.photos) ? room.photos : [];
	      const cover = photos.find(p => p && p.cover) || photos[0];
	      const thumb = cover?.url ? `<img class="alloc-thumb" src="${cover.url}" alt="">` : `<div class="alloc-thumb ph"></div>`;
	      const sub = calcRoomSubtotal(room, it.adults, it.kids);
	      const subText = (sub == null) ? '—' : formatPriceRub(sub * nights);
	      return `
	        <div class="alloc-item" data-idx="${idx}">
	          ${thumb}
          <div class="alloc-main">
            <div class="alloc-name">${room.name || room.room_type || 'Апартамент'}</div>
            <div class="alloc-meta muted">до ${cap} гостей • ${subText}</div>
            <div class="alloc-controls">
              <div class="alloc-control">
                <div class="muted">Взрослые</div>
                <div class="alloc-step">
                  <button class="alloc-btn" data-act="a-" type="button">−</button>
                  <input class="alloc-input" data-act="a" inputmode="numeric" type="number" min="0" value="${Number(it.adults) || 0}">
                  <button class="alloc-btn" data-act="a+" type="button">+</button>
                </div>
              </div>
              <div class="alloc-control">
                <div class="muted">Дети</div>
                <div class="alloc-step">
                  <button class="alloc-btn" data-act="k-" type="button">−</button>
                  <input class="alloc-input" data-act="k" inputmode="numeric" type="number" min="0" value="${Number(it.kids) || 0}">
                  <button class="alloc-btn" data-act="k+" type="button">+</button>
                </div>
              </div>
            </div>
          </div>
          <button class="alloc-remove" title="Убрать" data-act="rm" type="button">✕</button>
        </div>
      `;
    }).join('');

    listEl.querySelectorAll('.alloc-item').forEach(row => {
      const idx = Number(row.getAttribute('data-idx'));
      if (!Number.isFinite(idx)) return;
      row.addEventListener('click', async (e) => {
        const t = e.target;
        if (!(t instanceof HTMLElement)) return;
        const act = t.getAttribute('data-act');
        if (!act) return;
        e.preventDefault();
        e.stopPropagation();
        const it = items[idx];
        if (!it) return;
        if (act === 'rm') {
          const name = (items[idx]?.room?.name || items[idx]?.room?.class || items[idx]?.room?.room_type || 'апартамент').toString();
          const ok = await showConfirmModal({
            title: 'Удалить из корзины?',
            message: `Удалить «${name}» из корзины?`,
            confirmText: 'Удалить',
            cancelText: 'Отмена',
            danger: true,
          });
          if (!ok) return;
          items.splice(idx, 1);
          // Если удалили последний апартамент, показываем пустую корзину
          if (items.length === 0) {
            // Удаляем корзину этой базы из мульти-корзины
            removeBookingMultiCart(cid);
            // Также очищаем одиночный черновик если он от этой базы
            const d = window.__bookingDraft || loadBookingDraft();
            if (d && Number(d.campId) === cid) {
              try { localStorage.removeItem(BOOKING_DRAFT_KEY); } catch (_) {}
              window.__bookingDraft = null;
            }
            updateBookingDraftUi();
            openEmptyBookingConfirmationModal();
            return;
          }
          render();
          updateSummary();
          persistDraft();
          return;
        }
        const step = (act === 'a+' || act === 'k+') ? 1 : (act === 'a-' || act === 'k-') ? -1 : 0;
        if (step) {
          if (act.startsWith('a')) it.adults = Math.max(0, (Number(it.adults) || 0) + step);
          if (act.startsWith('k')) it.kids = Math.max(0, (Number(it.kids) || 0) + step);
          render();
          updateSummary();
        }
      });

      row.querySelectorAll('input.alloc-input').forEach(inp => {
        inp.addEventListener('input', () => {
          const act = inp.getAttribute('data-act');
          const v = Math.max(0, parseInt(inp.value || '0', 10) || 0);
          if (act === 'a') items[idx].adults = v;
          if (act === 'k') items[idx].kids = v;
          updateSummary();
        });
      });
    });
  }

	  function updateSummary(){
	    const v = validateAllocation(items, f);
    if (hintEl) {
      const extra = [];
      (v.perItem || []).forEach((errs, idx) => {
        if (!errs || errs.length === 0) return;
        const name = (items[idx]?.room?.name || items[idx]?.room?.room_type || `#${idx+1}`).toString();
        extra.push(`${name}: ${errs.join(', ')}`);
      });
      hintEl.textContent = [...v.errors, ...extra].filter(Boolean).join('. ');
    }
		    if (summaryEl) {
		      const canShowSummary = items.length > 0 && v.totalPrice != null;
		      if (canShowSummary) {
		        const priceText = formatPriceRub(v.totalPrice);
		        const stayText = formatBookingStayText(f);
		        const totalLabel = stayText ? `Итого за ${stayText}` : 'Итого';
		        summaryEl.innerHTML = `
		          <div class="alloc-row"><div class="muted">Взрослые</div><div class="alloc-val">${v.sumAdults}</div></div>
		          <div class="alloc-row"><div class="muted">Дети</div><div class="alloc-val">${v.sumKids}</div></div>
		          <div class="alloc-row"><div class="muted">${totalLabel}</div><div class="alloc-val">${priceText}</div></div>
		        `;
		        summaryEl.style.display = '';
		      } else {
	        summaryEl.innerHTML = '';
	        summaryEl.style.display = 'none';
	      }
	    }
    if (submitBtn) submitBtn.disabled = !v.ok;
  }

  // Обновляем глобальный контекст с функциями
  window.__allocationModalContext.render = render;
  window.__allocationModalContext.updateSummary = updateSummary;

  const addSel = document.getElementById('allocAddSelect');
  const addBtn = document.getElementById('allocAddBtn');
  if (addBtn) {
    addBtn.onclick = () => {
      const id = Number(addSel?.value);
      if (!Number.isFinite(id)) return;
      const r = available.find(x => Number(x?.id) === id);
      if (!r) return;
      items.push({ room: r, adults: 0, kids: 0 });
      if (addSel) addSel.value = '';
      render();
      updateSummary();
    };
  }

  document.getElementById('allocBack').onclick = () => {
    if (typeof onBack === 'function') { onBack(); return; }
    closeModal();
  };

  document.getElementById('allocSubmit').onclick = async () => {
    const v = validateAllocation(items, f);
    if (!v.ok) { updateSummary(); return; }
    if (!getAuth() || !getAuth().token) {
      showAuthChoiceModal({
        subtitle: 'Для отправки заявки на бронирование необходимо авторизоваться.',
        onCancel: () => {},
        onLogin: () => { openLogin(); },
        onRegister: () => { openRegister(); },
      });
      return;
    }
    try {
      document.getElementById('allocSubmit').disabled = true;
      const res = await createBookingsFromAllocation(cid, f, items);
      closeModal();
      showBookingSuccessNotification(res, {
        onDone: async () => {
          setTabById('tab-account');
          await openAccountBookings('active');
        }
      });
    } catch (e) {
      alert(e.message || 'Не удалось создать бронь');
      document.getElementById('allocSubmit').disabled = false;
    }
  };

  render();
  updateSummary();
}
function fmtDateShortRu(v){
  if (!v) return '—';
  try { return new Date(v).toLocaleDateString('ru-RU', { day:'2-digit', month:'2-digit' }); } catch(_) { return String(v); }
}

function allocationToText(rooms){
  const by = new Map();
  for (const r of rooms || []) {
    const name = (r.name || r.room_type || 'Вариант').toString().trim() || 'Вариант';
    by.set(name, (by.get(name) || 0) + 1);
  }
  const parts = [];
  for (const [name, cnt] of by.entries()) {
    parts.push(`${cnt}× «${name}»`);
  }
  return parts.join(' + ');
}

function findBestAllocation(rooms, total){
  const need = Number(total) || 0;
  if (need <= 0) return [];
  const items = (rooms || []).filter(r => roomCapacity(r) > 0);
  if (!items.length) return null;

  // 0-1 DP by sum, minimizing room count then overcap then price
  // Важно: храним prev как ссылку на объект состояния (а не индекс суммы),
  // иначе при 1D DP backtracking может "прыгать" на перезаписанные состояния
  // и ошибочно дублировать один и тот же номер.
  const maxCap = Math.max(...items.map(roomCapacity));
  const maxSum = Math.min(need + maxCap * 2, 200); // cap to keep dp small
  const dp = Array(maxSum + 1).fill(null);
  dp[0] = { cnt: 0, price: 0, prev: null, idx: -1 };

  for (let i = 0; i < items.length; i++) {
    const cap = roomCapacity(items[i]);
    const price = roomPriceFrom(items[i]) || 0;
    for (let s = maxSum; s >= 0; s--) {
      const cur = dp[s];
      if (!cur) continue;
      const ns = Math.min(maxSum, s + cap);
      const cand = { cnt: cur.cnt + 1, price: cur.price + price, prev: cur, idx: i };
      const best = dp[ns];
      if (!best) {
        dp[ns] = cand;
        continue;
      }
      if (cand.cnt < best.cnt) { dp[ns] = cand; continue; }
      if (cand.cnt === best.cnt && cand.price < best.price) { dp[ns] = cand; continue; }
    }
  }

  let bestSum = -1;
  let best = null;
  for (let s = need; s <= maxSum; s++) {
    const st = dp[s];
    if (!st) continue;
    if (!best || st.cnt < best.cnt || (st.cnt === best.cnt && (s < bestSum || (s === bestSum && st.price < best.price)))) {
      best = st;
      bestSum = s;
    }
  }
  if (!best) return null;

  const picked = [];
  let st = best;
  while (st && st.idx >= 0) {
    picked.push(items[st.idx]);
    st = st.prev;
  }
  // На всякий случай: защита от дубликатов в сборке текста/вариантов.
  const seen = new Set();
  const out = [];
  for (const r of picked.reverse()) {
    const id = Number(r?.id);
    const key = Number.isFinite(id) ? `id:${id}` : `ref:${String(r?.name||'')}:${String(r?.room_type||'')}:${String(r?.capacity||'')}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  return out;
}

// === Глобальный стек для навигации (для правильного возврата из фильтра) ===
window.__navigationStack = [];

function pushNavStack(state) {
  window.__navigationStack.push(state);
}

function popNavStack() {
  if (window.__navigationStack.length > 0) {
    const state = window.__navigationStack.pop();
    if (state.type === 'roomsList') {
      openRoomsList(state.campId, state.typeName, state.rooms, state.camp);
    } else if (state.type === 'roomDetails') {
      openRoomDetails(state.room, state.camp, state.context || null);
    } else if (state.type === 'campHousing') {
      openCampHousing(state.campId);
    }
    return true;
  }
  return false;
}

// === Показ списка конкретных апартаментов одного типа ===
function openRoomsList(campId, typeName, rooms, camp) {
  const cid = Number(campId);
  const ht = normalizeHousingType(camp?.housing_type || 'apartments');
  const shell = document.getElementById('modalCard');
  if (shell) {
    shell.classList.remove('booking-shell');
    shell.classList.remove('details');
    shell.classList.add('accom-shell');
  }
  
  showModal(`
    <div class="accom-card">
      <div class="accom-head">
        <div class="accom-title">${camp?.name || 'База'} • ${typeName}</div>
        <div class="accom-sub">Выберите конкретный вариант для подробностей</div>
      </div>
      <div class="accom-body">
        <div class="accom-list" id="roomsDetailList"></div>
      </div>
      <div class="accom-actions">
        <button class="button ghost" id="roomsListBack">Назад</button>
        ${(Array.isArray(rooms) && rooms.length > 1) ? '' : `<button class="button primary" id="roomsListBook">Забронировать</button>`}
      </div>
    </div>
  `);

  const listEl = document.getElementById('roomsDetailList');
  if (!listEl) return;

  // Обработчик кнопки "Назад" — после showModal элемент уже существует
  const backBtn = document.getElementById('roomsListBack');
  if (backBtn) {
    backBtn.onclick = (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      closeModal();
      openCampHousing(cid);
    };
  }

  const bookBtn = document.getElementById('roomsListBook');
      if (bookBtn) {
        bookBtn.onclick = async (e) => {
          try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
          
          const openAlloc = () => {
            const f = window.__bookingFilter || {};
            const total = Number(f.total) || (Number(f.adults)||0) + (Number(f.kids)||0);
            let selectedRooms = [];
        if (rooms.length === 0) return;
        if (total > 0) {
          if (f.allowSplitRooms) {
            const best = findBestAllocation(rooms, total);
            selectedRooms = best && best.length ? best : [rooms[0]];
          } else {
            selectedRooms = [rooms.find(r => roomCapacity(r) >= total) || rooms[0]];
          }
        } else {
          selectedRooms = [rooms[0]];
        }
        openAllocationModal({
          camp,
          campId: cid,
          roomsAvailable: rooms,
          selectedRooms,
          filter: window.__bookingFilter,
          onBack: () => openRoomsList(cid, typeName, rooms, camp),
        });
      };

      const f = window.__bookingFilter || {};
      if (!f.from || !f.to) {
        const campData = camp || await getCampQuick(cid);
        const h = normalizeHousingType(campData?.housing_type);
	        openBookingFilterModal({
	          mode: 'booking',
	          campId: cid,
	          title: 'Выберите даты и гостей',
	          hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.',
	          applyText: `К выбору ${housingLabelChoiceWord(h)}`,
	          onApply: () => openAlloc(),
	        });
        return;
      }
      openAlloc();
    };
  }
  
  // Сохраняем в стек для возврата из фильтра
  pushNavStack({ type: 'roomsList', campId: cid, typeName, rooms, camp });

  if (rooms.length === 0) {
    listEl.innerHTML = '<div class="muted">Нет доступных апартаментов</div>';
    return;
  }

  listEl.innerHTML = '';
  for (const room of rooms) {
    const cap = roomCapacity(room);
    const photos = Array.isArray(room.photos) ? room.photos : [];
    const coverPhoto = photos.find(p => p.cover) || photos[0];
    const thumbUrl = coverPhoto?.url || '/static/uploads/temp/placeholder.jpg';
    const roomPrice = room.price || room.price_adult || 0;

    const item = document.createElement('button');
    item.className = 'accom-item';
    
    item.innerHTML = `
      <img class="accom-thumb" src="${thumbUrl}" alt="">
      <div class="accom-main">
        <div class="accom-name">${room.name || 'Без названия'}</div>
        <div class="accom-meta">до ${cap || '?'} гостей</div>
      </div>
      <div class="accom-price">${roomPrice > 0 ? roomPrice.toLocaleString('ru-RU') : '—'}&nbsp;₽</div>
    `;
    
    // Клик по апартаменту показывает детальную карточку
    item.onclick = () => {
      openRoomDetails(room, camp, { campId: cid, typeName, rooms });
    };
    
    listEl.appendChild(item);
  }
}

// === Показ детальной карточки апартамента (как карточка базы) ===
function openRoomDetailsFromCart(room, camp, context) {
  // Открывает карточку апартамента и при нажатии "Добавить в корзину" добавляет его в корзину
  
  openRoomDetails(room, camp, context);
  
  // Переопределяем обработчик кнопки "Выбрать" для добавления в корзину
  setTimeout(() => {
    const selectBtn = document.getElementById('roomDetailBookBtn');
    if (selectBtn) {
      selectBtn.textContent = 'Добавить в корзину';
      selectBtn.onclick = () => {
        // 1) Если сейчас открыта «корзина бронирования» (подтверждение) — добавляем туда и возвращаемся в неё
        const confirmCtx = window.__bookingConfirmationModalContext;
        if (confirmCtx && typeof confirmCtx.addRoom === 'function') {
          const added = confirmCtx.addRoom(room);
          if (!added) return;
          if (typeof confirmCtx.reopen === 'function') confirmCtx.reopen();
          return;
        }

        // 2) Если это контекст распределения гостей — добавляем и возвращаемся в него
        const allocCtx = window.__allocationModalContext;
        if (allocCtx && Array.isArray(allocCtx.items)) {
          const rid = Number(room?.id);
          const exists = Number.isFinite(rid) && allocCtx.items.some(it => Number(it?.room?.id) === rid);
          if (!exists) allocCtx.items.push({ room, adults: 0, kids: 0 });

          openAllocationModal({
            camp: allocCtx.camp,
            campId: allocCtx.campId,
            roomsAvailable: allocCtx.availableRooms,
            selectedRooms: allocCtx.items.map(it => it.room).filter(Boolean),
            filter: allocCtx.filter,
            onBack: allocCtx.onBack,
            initialItems: allocCtx.items,
          });
          return;
        }
      };
    }
  }, 0);
}

function openRoomDetails(room, camp, context) {
  const viewOnly = !!(context && context.viewOnly);
  const photos = Array.isArray(room.photos) ? room.photos : [];
  const pics = photos.map(p => p.url);
  const cap = roomCapacity(room);

  const floors = Number(room.floors) || 0;
  const floor = Number(room.floor) || 0;
  const bedsSingle = Number(room.beds_single) || 0;
  const bedsDouble = Number(room.beds_double) || 0;

  const hasOtherUnitsInBuilding = (() => {
    if (context && Array.isArray(context.rooms)) return context.rooms.length > 1;
    // best-effort fallback: same camp + same room_type + same floors
    const all = Array.isArray(window.__roomsCache) ? window.__roomsCache : [];
    const same = all.filter(r =>
      Number(r?.camp_id) === Number(room?.camp_id) &&
      String(r?.room_type || '') === String(room?.room_type || '') &&
      Number(r?.floors || 0) === floors
    );
    return same.length > 1;
  })();

  const showFloor = floors > 1 && hasOtherUnitsInBuilding && floor > 0;
  const bathValue = (() => {
    const s = String(room?.bath_type || '').trim();
    if (!s) return 'Нет';
    if (s === 'shower' || s === 'bath' || s === 'both') return 'В номере';
    if (s === 'shower-shared') return 'Общий';
    return roomParamLabel(s, 'bath');
  })();
  const wcValue = (() => {
    const s = String(room?.wc_type || '').trim();
    if (!s) return 'Нет';
    if (s === 'indiv-split' || s === 'indiv-combined') return 'В номере';
    if (s === 'shared') return 'Общий';
    return roomParamLabel(s, 'wc');
  })();
  const shareVal = (v, opts = {}) => {
    const s = String(v || '').trim();
    const privateText = opts.privateText || 'Своя';
    const sharedText = opts.sharedText || 'Общая';
    const noneText = opts.noneText || 'Нет';
    if (s === 'private') return privateText;
    if (s === 'shared') return sharedText;
    return noneText;
  };

  const compactParams = [
    { label: 'Вместимость', value: `до ${cap || '?'} гостей`, icon: 'users' },
    { label: 'Тип', value: room.room_type || '—', icon: 'home' },
    { label: 'Одноместная', value: String(bedsSingle), icon: 'bed' },
    { label: 'Двухместная', value: String(bedsDouble), icon: 'bed' },
    { label: 'Кухня', value: shareVal(room.kitchen_type, { privateText: 'В номере', sharedText: 'Общая' }), icon: 'utensils' },
    { label: 'Туалет', value: wcValue, icon: 'bath' },
  ];

  const allParams = [
    { label: 'Вместимость', value: `до ${cap || '?'} гостей`, icon: 'users' },
    { label: 'Тип', value: room.room_type || '—', icon: 'home' },
    { label: 'Одноместная', value: String(bedsSingle), icon: 'bed' },
    { label: 'Двухместная', value: String(bedsDouble), icon: 'bed' },
    { label: 'Кухня', value: shareVal(room.kitchen_type, { privateText: 'В номере', sharedText: 'Общая' }), icon: 'utensils' },
    { label: 'Туалет', value: wcValue, icon: 'bath' },
    { label: 'Душ/Ванна', value: bathValue, icon: 'droplets' },
    { label: 'Зона барбекю', value: shareVal(room.bbq_type, { privateText: 'Своя', sharedText: 'Общая' }), icon: 'flame' },
    { label: 'Беседка', value: shareVal(room.gazebo_type, { privateText: 'Своя', sharedText: 'Общая' }), icon: 'tent' },
    { label: 'Терраса', value: shareVal(room.terrace_type, { privateText: 'Своя', sharedText: 'Общая' }), icon: 'door' },
    { label: 'Бассейн', value: shareVal(room.pool_type, { privateText: 'Свой', sharedText: 'Общий' }), icon: 'waves' },
    { label: 'Балкон', value: shareVal(room.balcony_type, { privateText: 'Свой', sharedText: 'Общий' }), icon: 'door' },
    { label: 'Кондиционер', value: (Number(room.has_ac) || 0) ? 'Есть' : 'Нет', icon: 'wind' },
  ];
  if (showFloor) {
    allParams.splice(2, 0, { label: 'Этаж', value: floors ? `${floor} / ${floors}` : String(floor), icon: 'door' });
  }

  // Определяем слово для кнопки на основе типа апартамента (родительный падеж)
  const roomType = String(room.room_type || '').trim().toLowerCase();
  let objWord = 'апартамента';
  if (roomType === 'дом') objWord = 'дома';
  else if (roomType === 'номер') objWord = 'номера';
  else if (roomType === 'апартамент') objWord = 'апартамента';

  const shell = document.getElementById('modalCard');
  if (shell) {
    shell.classList.remove('booking-shell');
    shell.classList.remove('accom-shell');
    shell.classList.add('details');
    shell.classList.add('room-detail-shell');
  }

  showModal(`
    <div class="room-detail-title">${room.name || 'Апартамент'}</div>

    <div class="details-body room-detail-body">
      <div class="camp-gal room-gal room-detail-gallery">
        <div class="viewport">${
          pics.length > 0
            ? pics.map(u => `
              <img src="${u}"
                   alt=""
                   draggable="false"
                   loading="eager"
                   decoding="sync"
                   fetchpriority="high"
                   referrerpolicy="no-referrer">
            `).join('')
            : '<div class="muted" style="padding:60px 20px;text-align:center">Фото отсутствуют</div>'
        }</div>

        ${pics.length > 1 ? `
          <button type="button" class="room-gal-arrow room-gal-arrow--prev" id="galPrev" aria-label="Предыдущее фото">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg>
          </button>
          <button type="button" class="room-gal-arrow room-gal-arrow--next" id="galNext" aria-label="Следующее фото">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>
          </button>
          <div class="room-gal-counter" id="galCounter">1 / ${pics.length}</div>
        ` : ''}
      </div>

      <div class="room-feature-grid">
        ${renderRoomFeatureCards(compactParams)}
      </div>

      <button class="button ghost room-toggle-all" id="roomToggleAllParams">Открыть все параметры ${objWord}</button>

      ${renderRoomPriceBlock(room, 'room-detail')}
    </div>

    <div class="room-detail-actions">
      <button class="button primary room-detail-choose" id="roomDetailBookBtn">Выбрать</button>
      <button class="button ghost room-detail-back" id="roomDetailsBack">Назад</button>
    </div>
  `);

  const root = document.getElementById('modalCard');

  // Сохраняем в стек для возврата из фильтра
  pushNavStack({ type: 'roomDetails', room, camp, context: context || null });

  // В корзине/режиме просмотра (viewOnly) не показываем кнопки "Выбрать/Забронировать"
  const bookBtn = document.getElementById('roomDetailBookBtn');
  const actionsWrap = document.querySelector('.room-detail-actions');
  if (viewOnly) {
    if (bookBtn) bookBtn.style.display = 'none';
    if (actionsWrap) actionsWrap.classList.add('is-view-only');
  } else if (bookBtn) {
    // Обработчик кнопки "Выбрать" — проверяем авторизацию и показываем выбор Вход/Регистрация
    bookBtn.onclick = async () => {
      const campData = camp || await getCampQuick(camp.id);
      
      // Используем текущий фильтр или создаём базовый с 2 взрослыми
      const filter = window.__bookingFilter || {
        from: null,
        to: null,
        adults: 2,
        kids: 0,
        total: 2,
        allowSplitRooms: false
      };
      
      // Открываем окно подтверждения бронирования напрямую
      openBookingConfirmationModal({
        camp: campData || camp,
        campId: camp.id,
        rooms: [room],
        filter: filter,
        onBack: () => openRoomDetails(room, camp, context),
      });
    };
  }

  // Обработчик кнопки "Назад"
  const backBtn = document.getElementById('roomDetailsBack');
  if (backBtn) {
    backBtn.onclick = (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      const ctx = context || null;
      if (ctx && typeof ctx.onBack === 'function') {
        try { ctx.onBack(); } catch (_) {}
        return;
      }
      if (ctx && Array.isArray(ctx.rooms)) {
        const onlyOne = ctx.rooms.length === 1;
        const destTypeName = ctx.typeName || (room.class || room.name || 'Апартаменты');
        if (onlyOne) {
          // Если в типе доступен ровно один апартамент — возвращаемся к списку типов
          openCampHousing(ctx.campId || camp.id);
        } else {
          openRoomsList(ctx.campId || camp.id, destTypeName, ctx.rooms, camp);
        }
        return;
      }
      const typeName = room.class || room.name || 'Апартаменты';
      const roomsAll = window.__roomsCache || [];
      const key = `${room.room_type || 'Дом'}::${room.class || room.name || 'Стандарт'}`;
      const roomsOfType = roomsAll.filter(r => `${r.room_type || 'Дом'}::${r.class || r.name || 'Стандарт'}` === key);
      if (roomsOfType.length === 1) {
        openCampHousing(camp.id);
      } else {
        openRoomsList(camp.id, typeName, roomsOfType, camp);
      }
    };
  }

  // Окно со всеми параметрами (отдельная модалка поверх карточки)
  const toggleBtn = document.getElementById('roomToggleAllParams');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      openAllParamsModal({
        title: `Параметры ${objWord}`,
        subtitle: room?.name ? String(room.name) : '',
        params: allParams,
      });
    });
  }

  // Галерея (если есть фото)
  if (pics.length > 1) {
    const vp = root ? root.querySelector('.camp-gal .viewport') : null;
    const imgs = vp ? vp.querySelectorAll('img') : [];
    const btnPrev = root ? root.querySelector('#galPrev') : null;
    const btnNext = root ? root.querySelector('#galNext') : null;
    const counter = root ? root.querySelector('#galCounter') : null;

    const N = imgs.length;
    if (vp) {
      vp.style.width = `${N * 100}%`;
      imgs.forEach(img => { img.style.width = `${100 / N}%`; });
    }

    let i = 0;
    let locked = false;
    
    function updateUI(){
      if (counter) counter.textContent = `${i + 1} / ${N}`;
      if (btnPrev) btnPrev.disabled = i === 0;
      if (btnNext) btnNext.disabled = i === N - 1;
    }
    
    function go(to){
      if (!vp || locked) return;
      const clamped = Math.max(0, Math.min(N-1, to));
      if (clamped === i) { updateUI(); return; }
      locked = true;
      i = clamped;

      const step = 100 / N;
      vp.style.transform = `translateX(${-i * step}%)`;

      const unlock = ()=>{ locked = false; vp.removeEventListener('transitionend', unlock); updateUI(); };
      vp.addEventListener('transitionend', unlock);
      setTimeout(unlock, 350);
    }

    const throttledPrev = throttle(()=> go(i-1), 260);
    const throttledNext = throttle(()=> go(i+1), 260);
    if (btnPrev) btnPrev.onclick = () => { hapticPulse('light', 12); throttledPrev(); };
    if (btnNext) btnNext.onclick = () => { hapticPulse('light', 12); throttledNext(); };

    // Свайпы
    if (vp) {
      let sx = 0, dx = 0, moving = false;
      const THRESH = 40;
      vp.addEventListener('touchstart', (e)=>{ if(!e.touches[0])return; sx = e.touches[0].clientX; dx=0; moving=true; }, {passive:true});
      vp.addEventListener('touchmove',  (e)=>{ if(!moving||!e.touches[0])return; dx = e.touches[0].clientX - sx; }, {passive:true});
      vp.addEventListener('touchend',   ()=>{
        if (!moving) return; moving=false;
        if (Math.abs(dx) > THRESH){
          if (dx < 0) throttledNext(); else throttledPrev();
        }
      }, {passive:true});

      // Клик по изображению — полноэкранная галерея
      imgs.forEach((img, idx) => {
        img.addEventListener('click', ()=> openFullscreenGallery(pics, idx, { showBook: !viewOnly }));
      });
    }

    updateUI();
  } else if (pics.length === 1) {
    // Одно фото - клик открывает полноэкранную галерею
    const img = root ? root.querySelector('.camp-gal img') : null;
      if (img) {
        img.style.cursor = 'pointer';
      img.addEventListener('click', ()=> openFullscreenGallery(pics, 0, { showBook: !viewOnly }));
      }
    }

  // Масштабирование
  const modalRoot = document.getElementById('modal');
  applyTwoColScale(modalRoot || document);
}

async function openCampHousing(campId){
  const cid = Number(campId);
  if (!Number.isFinite(cid)) return;
  const f = window.__bookingFilter || {};
  
  // Если фильтр не настроен, показываем все апартаменты для ознакомления (БЕЗ авторизации)
  if (!f.from || !f.to) {
    window.__currentCampId = cid;
    closeTransientOverlays({ keepMainModal: true });
    const shell = document.getElementById('modalCard');
    if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); shell.classList.add('accom-shell'); }

    showModal(`
      <div class="accom-card">
        <div class="accom-head">
          <div class="accom-title">Загрузка…</div>
          <div class="accom-sub">Все доступные варианты размещения</div>
        </div>
        <div class="accom-body">
          <div class="accom-hint" id="accomHint" style="min-height:22px">Для бронирования укажите даты и количество гостей.</div>
          <div class="accom-list" id="accomList">
            <div class="muted">Загружаем информацию о размещении…</div>
          </div>
        </div>
        <div class="accom-actions">
          <button class="button ghost" id="accomBack">Назад</button>
          <button class="button primary" id="accomBooking">Даты и гости</button>
        </div>
      </div>
    `);

    document.getElementById('accomBack').onclick = ()=> { closeModal(); openDetails(cid); };
    document.getElementById('accomBooking').onclick = async ()=> {
      // Фильтр дат и гостей доступен без авторизации (для просмотра доступности).
      const camp = await getCampQuick(cid);
      const ht = normalizeHousingType(camp?.housing_type);
	      openBookingFilterModal({
	        mode: 'booking',
	        campId: cid,
	        title: 'Выберите даты и гостей',
	        hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.',
	        applyText: `К выбору ${housingLabelChoiceWord(ht)}`,
	        onClose: () => {
	          closeModal();
	          openCampHousing(cid);
        }
      });
    };

    let camp = await getCampQuick(cid);
    if (!camp) camp = { id: cid, name: `База #${cid}`, housing_type: 'apartments' };
    const ht = normalizeHousingType(camp.housing_type);

    try {
      // Загружаем все апартаменты без фильтрации по датам
      const data = await fetch(`/api/rooms?camp_id=${cid}`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
        return r.json();
      });
      const roomsAll = Array.isArray(data) ? data : [];

      console.log('Загружено апартаментов:', roomsAll.length);

      // Сохраняем в кеш для навигации назад
      window.__roomsCache = roomsAll;

      const titleEl = document.querySelector('.accom-title');
      if (titleEl) titleEl.textContent = `${camp.name || 'База'} • ${housingLabelTitle(ht)}`;

      const hintEl = document.getElementById('accomHint');
      if (hintEl && roomsAll.length === 0) {
        hintEl.textContent = 'Информация о вариантах размещения отсутствует.';
      }

      const groups = new Map();
      for (const r of roomsAll) {
        const key = `${r.room_type || 'Дом'}::${r.class || r.name || 'Стандарт'}`;
        if (!groups.has(key)) {
          groups.set(key, { ...r, count: 1, minPrice: r.price || r.price_adult || 0 });
        } else {
          const g = groups.get(key);
          g.count++;
          const rPrice = r.price || r.price_adult || 0;
          if (rPrice && (!g.minPrice || rPrice < g.minPrice)) g.minPrice = rPrice;
        }
      }

      const listEl = document.getElementById('accomList');
      if (!listEl) return;

      if (groups.size === 0) {
        listEl.innerHTML = '<div class="muted">Нет информации о вариантах размещения</div>';
        return;
      }

      listEl.innerHTML = '';
      for (const [key, g] of groups) {
        const cap = roomCapacity(g);
        const photos = Array.isArray(g.photos) ? g.photos : [];
        const coverPhoto = photos.find(p => p.cover) || photos[0];
        const thumbUrl = coverPhoto?.url || '/static/uploads/temp/placeholder.jpg';

        const item = document.createElement('button');
        item.className = 'accom-item';
        item.dataset.key = key;
        
        item.innerHTML = `
          <img class="accom-thumb" src="${thumbUrl}" alt="">
          <div class="accom-main">
            <div class="accom-name">${g.class || g.name || 'Без названия'}</div>
            <div class="accom-meta">до ${cap || '?'} гостей • всего: ${g.count}</div>
          </div>
          <div class="accom-price">от ${(g.minPrice && g.minPrice > 0) ? g.minPrice.toLocaleString('ru-RU') : '—'}&nbsp;₽</div>
        `;
        
        // Клик по типу апартаментов: если доступен ровно один вариант — открываем его карточку сразу
        item.onclick = () => {
          const roomsOfType = roomsAll.filter(r => {
            const rKey = `${r.room_type || 'Дом'}::${r.class || r.name || 'Стандарт'}`;
            return rKey === key;
          });
          if (roomsOfType.length === 1) {
            openRoomDetails(roomsOfType[0], camp);
          } else {
            openRoomsList(cid, g.class || g.name || 'Апартаменты', roomsOfType, camp);
          }
        };
        
        listEl.appendChild(item);
      }
    } catch (err) {
      console.error('Ошибка загрузки апартаментов:', err);
      console.error('Stack trace:', err.stack);
      console.error('Error name:', err.name);
      console.error('Error message:', err.message);
      const listEl = document.getElementById('accomList');
      if (listEl) listEl.innerHTML = `<div class="muted">Ошибка загрузки данных: ${err.message}</div>`;
    }
    return;
  }
  
  // Если фильтр настроен, показываем доступные варианты
  await openCampAccommodations(cid);
}

async function openCampAccommodations(campId){
  const cid = Number(campId);
  if (!Number.isFinite(cid)) return;
  window.__currentCampId = cid;
  closeTransientOverlays({ keepMainModal: true });
  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); shell.classList.add('accom-shell'); shell.classList.remove('room-detail-shell'); }

  const f = window.__bookingFilter || {};
  if (!f.from || !f.to) { await openCampHousing(cid); return; }
  const total = Number(f.total) || (Number(f.adults)||0) + (Number(f.kids)||0);

  showModal(`
    <div class="accom-card">
      <div class="accom-head">
        <div class="accom-title">Загрузка…</div>
        <div class="accom-sub">${fmtDateShortRu(f.from)} → ${fmtDateShortRu(f.to)} • гостей: ${total || '—'}</div>
      </div>
      <div class="accom-body">
        <div class="accom-hint" id="accomHint" style="min-height:22px"></div>
        <div class="accom-list" id="accomList">
          <div class="muted">Ищем доступные варианты…</div>
        </div>
      </div>
      <div class="accom-actions">
        <button class="button ghost" id="accomBack">Назад</button>
        <button class="button" id="accomEdit">Изменить фильтр</button>
      </div>
    </div>
  `);

  document.getElementById('accomBack').onclick = ()=> { closeModal(); openDetails(cid); };
  document.getElementById('accomEdit').onclick = async ()=> {
    const camp = await getCampQuick(cid);
    const ht = normalizeHousingType(camp?.housing_type);
	    openBookingFilterModal({
	      mode: 'booking',
	      campId: cid,
	      title: 'Выберите даты и гостей',
	      hint: 'Выберите даты заезда и выезда и укажите количество гостей — мы покажем доступные варианты размещения.',
	      applyText: `К выбору ${housingLabelChoiceWord(ht)}`,
	      dontCloseBackground: true,
	      onClose: () => {
	        // leaving background in place; no action needed
      }
    });
  };

  let camp = await getCampQuick(cid);
  if (!camp) camp = { id: cid, name: `База #${cid}`, housing_type: 'apartments' };
  const ht = normalizeHousingType(camp.housing_type);

  try {
    const q = new URLSearchParams({ from: f.from, to: f.to });
    const data = await fetch(`/api/camps/${cid}/available-rooms?${q.toString()}`).then(r => r.ok ? r.json() : Promise.reject(new Error('Ошибка загрузки номеров')));
    const roomsAll = Array.isArray(data.rooms) ? data.rooms : [];
    const availableRooms = roomsAll.filter(r => r && r.available);
    const eligibleRooms = availableRooms.filter(r => {
      const cap = roomCapacity(r);
      if (!cap) return false;
      if (!total) return true;
      return f.allowSplitRooms ? (cap > 0) : (cap >= total);
    });

    const titleEl = document.querySelector('.accom-title');
    if (titleEl) titleEl.textContent = `${camp.name || 'База'} • ${housingLabelTitle(ht)}`;

    const hintEl = document.getElementById('accomHint');
    if (hintEl) {
      if (total && !f.allowSplitRooms) {
        const one = eligibleRooms.length ? findBestAllocation(eligibleRooms, total) : null;
        if (!one) {
          hintEl.textContent = 'Нет вариантов разместить всех гостей в одном варианте. Включите «заселение в разные номера или дома».';
        } else {
          hintEl.textContent = `Для размещения всех ваших гостей подходит: ${allocationToText(one)}.`;
        }
      } else if (total) {
        const best = findBestAllocation(eligibleRooms, total);
        const alt = best && best.length ? findBestAllocation(eligibleRooms.filter(r => r.id !== best[0].id), total) : null;
        if (best && best.length) {
          // Проверяем, не совпадает ли альтернативный вариант с основным
          const bestText = allocationToText(best);
          const altText = alt && alt.length ? allocationToText(alt) : '';
          const showAlt = altText && altText !== bestText;
          hintEl.textContent = `Для размещения ваших гостей вам подойдет: ${bestText}${showAlt ? `, или: ${altText}` : ''}.`;
        } else {
          hintEl.textContent = 'Подходящих вариантов по выбранным датам нет.';
        }
      } else {
        hintEl.textContent = '';
      }
    }

    const groups = new Map();
    for (const r of eligibleRooms) {
      const k = `${(r.room_type||'').toString()}::${(r.name||'').toString()}`;
      const g = groups.get(k) || { key: k, room_type: r.room_type || '', name: r.name || '', rooms: [], minPrice: 0, maxCap: 0, thumb: '' };
      g.rooms.push(r);
      const p = roomPriceFrom(r);
      if (p > 0) g.minPrice = g.minPrice ? Math.min(g.minPrice, p) : p;
      g.maxCap = Math.max(g.maxCap, roomCapacity(r));
      if (!g.thumb) {
        const ph = Array.isArray(r.photos) ? r.photos : [];
        const cover = ph.find(x => x && x.cover) || ph[0];
        if (cover && cover.url) g.thumb = cover.url;
      }
      groups.set(k, g);
    }

    const sorted = [...groups.values()].sort((a,b)=>{
      const pa = a.minPrice || 999999999;
      const pb = b.minPrice || 999999999;
      if (pa !== pb) return pa - pb;
      return (b.maxCap||0) - (a.maxCap||0);
    });

    const listEl = document.getElementById('accomList');
    if (!listEl) return;
    if (!sorted.length) {
      listEl.innerHTML = `<div class="muted">Подходящих вариантов нет. Попробуйте изменить даты или количество гостей.</div>`;
      return;
    }

    listEl.innerHTML = sorted.map(g=>{
      const title = (g.name || g.room_type || 'Вариант').toString().trim() || 'Вариант';
      const meta = `${g.maxCap ? `до ${g.maxCap} гостей` : 'вместимость уточняйте'} • доступно: ${g.rooms.length}`;
      const price = g.minPrice ? `от ${formatPriceRub(g.minPrice)}` : 'цена уточняется';
      const thumb = g.thumb ? `<img class="accom-thumb" src="${g.thumb}" alt="">` : `<div class="accom-thumb ph"></div>`;
      return `
        <button class="accom-item" data-key="${g.key}">
          ${thumb}
          <div class="accom-main">
            <div class="accom-name">${title}</div>
            <div class="accom-meta">${meta}</div>
          </div>
          <div class="accom-price">${price}</div>
        </button>
      `;
    }).join('');

    listEl.querySelectorAll('.accom-item').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const k = btn.getAttribute('data-key');
        const g = groups.get(k);
        if (!g) return;
        const rooms = Array.isArray(g.rooms) ? g.rooms : [];
        const typeName = (g.name || g.room_type || 'Апартаменты').toString();
        // Если доступен ровно один вариант — открываем его карточку сразу; иначе список конкретных апартаментов
        if (rooms.length === 1) {
          openRoomDetails(rooms[0], camp, { campId: cid, typeName, rooms });
        } else {
          openRoomsList(cid, typeName, rooms, camp);
        }
      });
    });
  } catch (e) {
    const listEl = document.getElementById('accomList');
    if (listEl) listEl.innerHTML = `<div class="muted">${String(e.message || 'Ошибка загрузки')}</div>`;
  }
}

function roomParamLabel(v, kind){
  const s = String(v || '').trim();
  if (!s) return '—';
  if (kind === 'bath') {
    if (s === 'shower') return 'Душ';
    if (s === 'bath') return 'Ванна';
    if (s === 'both') return 'Душ и ванна';
    if (s === 'shower-shared') return 'Душ общий';
  }
  if (kind === 'wc') {
    if (s === 'indiv-split') return 'Индив./раздельный';
    if (s === 'indiv-combined') return 'Индив./совмещённый';
    if (s === 'shared') return 'Общий';
  }
  if (kind === 'share') {
    if (s === 'private') return 'Индивидуальная';
    if (s === 'shared') return 'Общая';
  }
  if (kind === 'share_m') {
    if (s === 'private') return 'Индивидуальный';
    if (s === 'shared') return 'Общий';
  }
  return s;
}

function openRoomCategory(camp, group, filter){
  const rooms = (group.rooms || []).slice().sort((a,b)=> (roomPriceFrom(a)||999999999) - (roomPriceFrom(b)||999999999));
  const r = rooms[0];
  if (!r) return;

  const pics = (Array.isArray(r.photos) ? r.photos : []).map(p => p.url).filter(Boolean);
  const title = (group.name || group.room_type || 'Вариант').toString().trim() || 'Вариант';
  const cap = roomCapacity(r);
  const beds = (Number(r.beds_single)||0) + (Number(r.beds_double)||0) * 2;
  const priceHouse = Number(r.price) || 0;
  const priceAdult = Number(r.price_adult) || 0;
  const priceChild = Number(r.price_child) || 0;

  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('accom-shell'); shell.classList.add('details'); }

  showModal(`
    <div class="details-title">${title}</div>
    <div class="details-desc">${camp?.name ? `${camp.name}. ` : ''}Доступно: ${rooms.length} • ${fmtDateRu(filter.from)} → ${fmtDateRu(filter.to)}</div>
    <div class="details-body">
      <div class="camp-gal room-gal">
        <div class="viewport">${pics.map(u=>`<img src="${u}" alt="" draggable="false" loading="eager" decoding="sync" fetchpriority="high" referrerpolicy="no-referrer">`).join('')}</div>
        <div class="gal-arrow left"  id="rgPrev">‹</div>
        <div class="gal-arrow right" id="rgNext">›</div>
        <div class="gal-counter" id="rgCounter">1/${Math.max(pics.length,1)} →</div>
      </div>

      <div class="param-list grid2">
        ${[
          ['Тип', r.room_type || '—'],
          ['Вместимость', cap ? `${cap} чел.` : '—'],
          ['Кровати', beds ? `${beds} мест` : '—'],
          ['Душ/ванна', roomParamLabel(r.bath_type, 'bath')],
          ['Туалет', roomParamLabel(r.wc_type, 'wc')],
          ['BBQ', roomParamLabel(r.bbq_type, 'share')],
          ['Кухня', roomParamLabel(r.kitchen_type, 'share')],
          ['Беседка', roomParamLabel(r.gazebo_type, 'share')],
          ['Терраса', roomParamLabel(r.terrace_type, 'share')],
          ['Бассейн', roomParamLabel(r.pool_type, 'share_m')],
          ['Балкон', roomParamLabel(r.balcony_type, 'share_m')],
          ['Кондиционер', (Number(r.has_ac)||0) ? 'Есть' : 'Нет'],
        ].map(([k,v])=>`
          <div class="param-item">
            <div class="param-row"><div class="k">${k}</div><div class="v">${v}</div></div>
          </div>
        `).join('')}
      </div>

      ${renderRoomPriceBlock(r)}
    </div>
    <div class="actions" style="display:grid;gap:10px;grid-template-columns:1fr 1fr;">
      <button class="button ghost" id="rgBack">Назад</button>
      <button class="button primary" id="rgChoose">Выбрать</button>
    </div>
  `);

  // gallery nav (reuse same logic as details)
  const vp = document.querySelector('.camp-gal .viewport');
  const imgs = vp ? vp.querySelectorAll('img') : [];
  const btnPrev = document.getElementById('rgPrev');
  const btnNext = document.getElementById('rgNext');
  const counter = document.getElementById('rgCounter');
  const N = Math.max(imgs.length, 1);
  if (vp) {
    vp.style.width = `${N * 100}%`;
    imgs.forEach(img => { img.style.width = `${100 / N}%`; });
  }
  let i = 0;
  function update(){
    const left  = (i > 0)     ? '← ' : '';
    const right = (i < N - 1) ? ' →' : '';
    if (counter) counter.textContent = `${left}${i+1}/${N}${right}`;
    if (btnPrev) btnPrev.classList.toggle('disabled', i === 0);
    if (btnNext) btnNext.classList.toggle('disabled', i === N - 1);
  }
  function go(to){
    const clamped = Math.max(0, Math.min(N - 1, to));
    i = clamped;
    const step = 100 / N;
    if (vp) vp.style.transform = `translateX(${-i * step}%)`;
    update();
  }
  if (btnPrev) btnPrev.onclick = () => { hapticPulse('light', 12); go(i-1); };
  if (btnNext) btnNext.onclick = () => { hapticPulse('light', 12); go(i+1); };
  imgs.forEach((img, idx) => img.addEventListener('click', ()=> openFullscreenGallery(pics, idx)));
  go(0);

  document.getElementById('rgBack').onclick = ()=> openCampAccommodations(Number(camp?.id || window.__currentCampId));
  document.getElementById('rgChoose').onclick = async ()=>{
    const cid = Number(camp?.id || window.__currentCampId);
    const f = filter || window.__bookingFilter || {};
    const total = Number(f.total) || (Number(f.adults)||0) + (Number(f.kids)||0);
    let selectedRooms = [r];
    if (f.allowSplitRooms && total > roomCapacity(r)) {
      const best = findBestAllocation(rooms, total);
      if (best && best.length) selectedRooms = best;
    }
    openAllocationModal({
      camp,
      campId: cid,
      roomsAvailable: rooms,
      selectedRooms,
      filter: f,
      onBack: () => openRoomCategory(camp, group, f),
    });
  };
}




// --- геоцентрирование карты ---
function initGeoButton() {
  const btn = document.getElementById('geoBtn');
  if (!btn) return;
btn.addEventListener('click', () => {
  hapticPulse('soft', 14);
  if (!navigator.geolocation) return alert('Геолокация недоступна');
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      if (typeof map !== 'undefined') {
        map.flyTo([latitude, longitude], Math.max(map.getZoom(), 12));
        L.circleMarker([latitude, longitude], { radius: 6 }).addTo(map);
      }
    },
    () => alert('Не удалось получить геолокацию'),
    { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
  );
});

}

// --- кнопка открытия фильтра ---
function initBookingFilterButton() {
  const ids = ['openBookingFilter','toggleFilters']; // поддерживаем оба варианта id
  ids.forEach(id => {
    const btn = document.getElementById(id);
if (btn) btn.addEventListener('click', () => { hapticPulse('selection', 10); openBookingFilterModal(); });
  });
}

function setFilterButtonActive(active){
  const ids = ['openBookingFilter','toggleFilters'];
  ids.forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.classList.toggle('filter-active', !!active);
  });
}

// --- Переключение вкладок по data-target
function setTabById(targetId){
  // прячем всё
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  // показываем цель
  const tgt = document.getElementById(targetId);
  if (tgt) tgt.style.display = '';

  // активная кнопка в таббаре
  document.querySelectorAll('.tabbar .tab').forEach(t => {
    t.classList.toggle('active', t.getAttribute('data-target') === targetId);
  });

  // карта — фикс размеров
  if (targetId === 'tab-map') {
    if (typeof fixMapSize === 'function') fixMapSize();
    if (typeof restoreMapView === 'function') restoreMapView();
  }
}
window.setTabById = setTabById;

// ==== СТАРТ ====
window.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initBookingFilterButton();
  setFilterButtonActive(!!window.__bookingFilter);
  initGeoButton();
  loadBookingDraft();
  updateBookingDraftUi();
    setTabById('tab-map');
    loadCamps().then(()=> restoreMapView());  // <-- после загрузки маркеров сразу fitBounds
  setTimeout(()=> typeof map!=='undefined' && map.invalidateSize(), 80);
  document.getElementById('openBookingFilter').onclick = openBookingFilterModal;
  const refreshBtn = document.getElementById('refreshMap');
  if (refreshBtn) refreshBtn.onclick = () => {
    try { refreshBtn.disabled = true; } catch (_) {}
    try { location.reload(); } catch (_) {}
  };
  const draftBtn = document.getElementById('openBookingDraft');
  if (draftBtn) {
    draftBtn.onclick = openBookingDraft;

    // Android WebView sometimes "jumps" centered absolute buttons on tap.
    // Force a stable pressed state on pointer/touch down.
    const setPressed = () => { try { draftBtn.classList.add('is-pressed'); } catch (_) {} };
    const clearPressed = () => { try { draftBtn.classList.remove('is-pressed'); } catch (_) {} };
    try { draftBtn.addEventListener('pointerdown', setPressed, { passive: true }); } catch (_) {}
    try { draftBtn.addEventListener('pointerup', clearPressed, { passive: true }); } catch (_) {}
    try { draftBtn.addEventListener('pointercancel', clearPressed, { passive: true }); } catch (_) {}
    try { draftBtn.addEventListener('touchstart', setPressed, { passive: true }); } catch (_) {}
    try { draftBtn.addEventListener('touchend', clearPressed, { passive: true }); } catch (_) {}
    try { draftBtn.addEventListener('touchcancel', clearPressed, { passive: true }); } catch (_) {}
    try { draftBtn.addEventListener('blur', clearPressed, { passive: true }); } catch (_) {}
  }
  try { renderAccount(); } catch(_) {}
  try {
    (async ()=>{
      let tok = getAuthToken();
      if (!tok) {
        tok = await cloudGetToken();
        if (tok) setAuth({ token: tok, user: (getAuth() || {}).user || null });
      }
      if (tok) {
        authFetchJson('/api/auth/me').then((d)=>{
          if (d && d.user) {
            setAuth({ token: tok, user: d.user });
            renderAccount();
          }
        }).catch(()=>{});
      }
    })();
  } catch(_) {}

});

// Гарантированная фиксация размеров таб-иконок (п.4)
(function fixTabbarLayout(){
  const items = document.querySelectorAll('.tabbar .item');
  items.forEach(it => {
    it.style.minWidth = '0';
    it.style.flex = '1 1 0';
  });
})();


// Привязка кнопок ЛК в новой верстке (если присутствуют)
(function(){
  const btnLogin  = document.getElementById('btnLoginOpen');
  const btnReg    = document.getElementById('btnRegisterOpen');
  if (btnLogin && typeof openLogin === 'function')   btnLogin.addEventListener('click', openLogin);
  if (btnReg   && typeof openRegister === 'function') btnReg.addEventListener('click', openRegister);

  const btnActive = document.getElementById('btnAccountActive');
  const btnHist   = document.getElementById('btnAccountHistory');
  const btnProf   = document.getElementById('btnAccountProfile');
  if (btnActive) btnActive.addEventListener('click', ()=> openAccountBookings('active'));
  if (btnHist)   btnHist.addEventListener('click', ()=> openAccountBookings('history'));
  if (btnProf)   btnProf.addEventListener('click', openAccountProfile);
})();
