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
function housingLabelObjectWord(housingType){
  const ht = normalizeHousingType(housingType);
  if (ht === 'houses') return 'дома';
  if (ht === 'rooms') return 'номера';
  return 'апартамента';
}

function openAllParamsModal({ title, subtitle, params }) {
  const rows = Array.isArray(params) ? params : [];
  const overlay = document.createElement('div');
  overlay.className = 'modal show';
  overlay.style.zIndex = '9999';
  overlay.innerHTML = `
    <div class="modal-card details">
      <div class="details-title">${title || 'Параметры'}</div>
      ${subtitle ? `<div class="details-desc">${subtitle}</div>` : ''}
      <div class="details-body">
        <div class="allparams-list">
          ${rows.map(([k, v]) => `
            <div class="allparams-row">
              <div class="allparams-k">${k}</div>
              <div class="allparams-v">${v}</div>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="actions" style="display:flex;justify-content:center;">
        <button class="button ghost" id="allParamsBack">Назад</button>
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


// === СБОРКА БАЛУНА ДЛЯ БАЗЫ (с загрузочным эмоджи вместо фото до onload) ===
function buildCampPopup(camp){
  const hasPhoto = !!camp.photo_main;
  const priceText = (camp.min_price && Number(camp.min_price) > 0)
      ? `Стоимость от ${camp.min_price}₽ за человека`
      : 'Стоимость уточняйте';

  return `
    <div style="min-width:260px;max-width:320px">
      <div style="font-weight:800;font-size:22px;text-align:center;margin:0 0 8px">
        ${camp.name||''}
      </div>

      <!-- Крышка с эмоджи-плейсхолдером; фото проявится, когда загрузится -->
      <div class="popup-cover">
        <div class="popup-emoji">🏖️</div>
        ${hasPhoto
          ? `<img class="popup-photo"
     src="${camp.photo_main}"
     alt=""
     loading="eager"
     decoding="sync"
     fetchpriority="high"
     referrerpolicy="no-referrer"
     onload="window.__popupCoverLoaded(this)"
     onerror="window.__popupCoverError(this)">`
          : ``}
      </div>

      <div class="price" style="text-align:center;margin:10px 0 12px;color:#6b7280">
        ${priceText}
      </div>

      <div style="display:flex;gap:10px;justify-content:center">
        <button class="btn btn-primary" onclick="openDetails(${camp.id})">Подробнее</button>
        <button class="btn btn-success" onclick="openBookingFilterWithAuth(${camp.id})">Забронировать</button>
      </div>
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
  // Проверка авторизации
  if (!getAuth() || !getAuth().token) {
    // Закрываем все открытые модальные окна перед показом сообщения об авторизации
    const openModals = document.querySelectorAll('.modal.show');
    openModals.forEach(m => m.remove());
    
    showModal(`
      <div class="auth-card" style="text-align:center">
        <div class="auth-head" style="justify-content:center">
          <div class="auth-title">Необходима авторизация</div>
        </div>
        <div class="auth-subtitle" style="color:#fff;margin:12px 0 16px;line-height:1.5;font-size:15px">Для бронирования базы отдыха необходимо авторизоваться в приложении.</div>
        <div class="auth-actions" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
          <button class="button primary" id="authLogin" style="background:#2a9df4;border-color:#2a9df4">Вход</button>
          <button class="button primary" id="authRegister" style="background:#22c55e;border-color:#22c55e">Регистрация</button>
        </div>
        <button class="button ghost" id="authCancel" style="width:100%">Отмена</button>
      </div>
    `);
    document.getElementById('authCancel').onclick = closeModal;
    document.getElementById('authRegister').onclick = ()=> { closeModal(); openRegister(); };
    document.getElementById('authLogin').onclick = ()=> { closeModal(); openLogin(); };
    return;
  }
  
  // Если авторизован — открываем фильтр в режиме бронирования
  const camp = Number.isFinite(resolvedCampId) ? await getCampQuick(resolvedCampId) : null;
  const ht = normalizeHousingType(camp?.housing_type);
  const applyText = `К выбору ${housingLabelChoiceWord(ht)}`;
  openBookingFilterModal({
    mode: 'booking',
    campId: Number.isFinite(resolvedCampId) ? resolvedCampId : null,
    title: 'Подтвердите данные для бронирования',
    hint: 'Укажите даты и количество гостей. После подтверждения вы сможете выбрать подходящий вариант размещения.',
    applyText
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
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
  maxZoom: 19
}).addTo(map);

const cluster = (typeof L.markerClusterGroup === 'function')
  ? L.markerClusterGroup({
      maxClusterRadius: 60,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      iconCreateFunction: function (grp) {
        const count = grp.getChildCount();
        const size =
          count < 10 ? 'small' : count < 30 ? 'medium' : 'large';
        return L.divIcon({
          html: `<div class="cl-inner">${count}</div>`,
          className: `cl-marker cl-${size}`,
          iconSize: L.point(44, 44)
        });
      }
    })
  : L.featureGroup();
map.addLayer(cluster);

function fixMapSize(){ setTimeout(()=> map.invalidateSize(true), 50); }
window.addEventListener('load', fixMapSize);
window.addEventListener('resize', fixMapSize);
if (isTG) Telegram.WebApp.onEvent('viewportChanged', fixMapSize);

function emojiHouseIcon(emoji = '🏡', size = 'standard') {
  // standard ≈ 36x44, vip ≈ 72x88
  const isVip = (String(size).toLowerCase() === 'vip');
  const iconSize   = isVip ? [72, 88] : [36, 44];
  const iconAnchor = isVip ? [36, 80] : [18, 40];
  const popupAnchor= isVip ? [0, -72] : [0, -36];

  return L.divIcon({
    html: `<div class="emoji-pin" aria-hidden="true">${emoji}</div>`,
    className: `emoji-marker ${isVip ? 'vip' : 'std'}`,
    iconSize, iconAnchor, popupAnchor
  });
}


let lastMapView = null;
map.on('moveend', () => { lastMapView = { center: map.getCenter(), zoom: map.getZoom() }; });

function restoreMapView() {
  setTimeout(() => {
    map.invalidateSize();
    if (lastMapView) {
      map.setView(lastMapView.center, lastMapView.zoom, { animate: false });
    } else if (typeof cluster !== 'undefined' && cluster.getLayers && cluster.getLayers().length) {
      map.fitBounds(cluster.getBounds(), { padding: [20,20] });
    }
  }, 60);
}

const topbar = document.getElementById('topbar');
// Центруем карту так, чтобы балун был в видимой середине
map.on('popupopen', (e) => {
  try {
    const cont = e && e.popup && e.popup._container ? e.popup._container : null;

    // 1) центрирование с учётом высоты балуна
    const h = cont ? cont.offsetHeight : 260;
    const latlng = e.popup.getLatLng();
    const px = map.project(latlng);
px.y -= (h / 2);
map.panTo(map.unproject(px), { animate: true, duration: 0.25 }); // короче анимация = меньше «дёргания»

    // 2) запускаем перебор эмоджи для только что открытого балуна
    if (cont) __startPopupEmojiLoop(cont);
  } catch(_) {}
});

// Чистим таймер, когда балун закрыли
map.on('popupclose', (e) => {
  try {
    const cont = e && e.popup && e.popup._container ? e.popup._container : null;
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
function clearAuth(){
  localStorage.removeItem(AUTH_KEY);
  cloudRemoveToken();
}

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
  if (profile) {
    const name = profile.user?.name?.split(' ')[0] || 'гость';
    const hr = new Date().getHours();
    const phrase = hr < 6 ? 'Доброй ночи' : hr < 12 ? 'Доброе утро' : hr < 18 ? 'Добрый день' : 'Добрый вечер';
    const emoji  = hr < 6 ? '🌙' : hr < 12 ? '☀️' : hr < 18 ? '🌤️' : '🌙';
    if (title) title.textContent = `${phrase}, ${name}! ${emoji}`;
  } else {
    const hr = new Date().getHours();
    const phrase = hr < 6 ? 'Доброй ночи' : hr < 12 ? 'Доброе утро' : hr < 18 ? 'Добрый день' : 'Добрый вечер';
    const emoji  = hr < 6 ? '🌙' : hr < 12 ? '☀️' : hr < 18 ? '🌤️' : '🌙';
    if (title) title.textContent = `${phrase}! ${emoji}`;
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
function showModal(html){ modalCard.innerHTML = html; modal.style.display = 'grid'; }
function closeModal(){
  const modal = document.getElementById('modal');
  const card  = document.getElementById('modalCard');
	if (modal) modal.style.display = 'none';
	if (card) {
	  // снимаем ResizeObserver, если он был повешен
	  if (card.__ro && typeof card.__ro.disconnect === 'function') {
	    try { card.__ro.disconnect(); } catch(_) {}
	    card.__ro = null;
	  }
	  card.innerHTML = '';
	  card.classList.remove('booking-shell');  // снимаем «узкую» оболочку
	  card.classList.remove('details');       // снимаем «детали», если открывали карточку номера
	 }
}

modal.addEventListener('click', (e)=>{ if (e.target === modal) closeModal(); });

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

function normalizePhoneInputValue(raw){
  const v = String(raw || '');
  const trimmed = v.trim();
  if (!trimmed) return '';

  const compact = trimmed.replace(/[^\d+]/g, '');
  if (compact.startsWith('+')) {
    const digits = compact.slice(1).replace(/\D/g, '');
    if (!digits) return '+';
    // if user typed +8..., normalize to +7...
    if (digits.startsWith('8')) return '+7' + digits.slice(1);
    return '+' + digits;
  }

  const digits = compact.replace(/\D/g, '');
  if (!digits) return '';
  if (digits.startsWith('8')) return '+7' + digits.slice(1);
  if (digits.startsWith('9')) return '+7' + digits;
  if (digits.startsWith('7')) return '+7' + digits.slice(1);
  return digits;
}

function attachPhoneAutoPrefix(input){
  if (!input || input.__phoneMaskAttached) return;
  input.__phoneMaskAttached = true;
  const handler = () => {
    const next = normalizePhoneInputValue(input.value);
    if (next !== input.value) {
      input.value = next;
      try { input.setSelectionRange(next.length, next.length); } catch(_) {}
    }
  };
  input.addEventListener('input', handler);
  input.addEventListener('blur', handler);
  handler();
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
        <button class="button primary" id="terms_ok">Понятно</button>
      </div>
    </div>
  `);
  const termsEl = document.getElementById('terms_text');
  if (termsEl) termsEl.textContent = TERMS_TEXT;
  document.getElementById('terms_back').onclick = ()=> openRegister(d);
  document.getElementById('terms_ok').onclick = ()=> openRegister(Object.assign({}, d, { viewed_terms:true }));
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

  attachPhoneAutoPrefix(document.getElementById('reg_phone'));
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
          <input id="v_phone_code" inputmode="numeric" placeholder="${TEST_VERIFY_CODE}">
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
          <input id="v_email_code" inputmode="numeric" placeholder="${TEST_VERIFY_CODE}">
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
      <div class="auth-actions">
        <button class="button ghost" id="l_cancel">Отмена</button>
        <button class="button primary" id="l_start">Получить код</button>
      </div>
      <div class="auth-note">Для тестов код подтверждения: ${TEST_VERIFY_CODE}</div>
    </div>
  `);

  attachPhoneAutoPrefix(document.getElementById('l_phone'));
  document.getElementById('l_cancel').onclick = closeModal;
  document.getElementById('l_start').onclick = async () => {
    showAuthError('');
    const phone = document.getElementById('l_phone').value.trim();
    if (!phone) { showAuthError('Введите телефон'); return; }
    const res = await fetch('/api/auth/login/start', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ phone })
    });
    if (!res.ok) {
      const err = await res.json().catch(()=>({}));
      showAuthError(err.detail || 'Ошибка: не удалось отправить код');
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
          <input id="lc_code" inputmode="numeric" placeholder="${TEST_VERIFY_CODE}" />
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
    const data = await authFetchJson(`/api/auth/bookings?mode=${encodeURIComponent(mode)}`);
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
    return `
      <div class="booking-item" data-bid="${b.id}">
        <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
          <div style="font-weight:800">${b.camp_name || `База #${b.camp_id}`}</div>
          <div class="muted" style="white-space:nowrap">${fmtDateRu(b.check_in)} → ${fmtDateRu(b.check_out)}</div>
        </div>
        <div class="muted" style="margin-top:6px;display:flex;gap:10px;flex-wrap:wrap">
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
      const id = el.getAttribute('data-bid');
      if (!id) return;
      await openBookingDetail(Number(id), mode);
    });
  });
}

async function openBookingDetail(bookingId, mode){
  let item = null;
  try {
    const data = await authFetchJson(`/api/auth/bookings/${bookingId}`);
    item = data.item;
  } catch (e) {
    showModal(`
      <div class="auth-card">
        <div class="auth-head"><div class="auth-title">Бронь #${bookingId}</div></div>
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

  const canEdit = ['pending','confirmed','awaiting_payment',''].includes(stRaw) && payRaw !== 'paid' && stRaw !== 'completed';
  const canCancel = ['pending','confirmed','awaiting_payment',''].includes(stRaw);
  const canPay = stRaw === 'confirmed' && !!item.payment_required && payRaw === 'unpaid';

  showModal(`
    <div class="auth-card">
      <div class="auth-head"><div class="auth-title">Бронь #${item.id}</div></div>
      <div class="auth-fields" style="gap:10px">
        <div class="kv">
          <div class="kv-k">База</div><div>${item.camp_name || `База #${item.camp_id}`}</div>
          <div class="kv-k">Номер</div><div>${item.room_name || (item.room_id ? `#${item.room_id}` : '—')}</div>
          <div class="kv-k">Даты</div><div>${fmtDateRu(item.check_in)} → ${fmtDateRu(item.check_out)}</div>
          <div class="kv-k">Гостей</div><div>${item.guests_count ?? '—'}</div>
          <div class="kv-k">Статус</div><div>${st}</div>
          <div class="kv-k">Оплата</div><div>${pay}${item.payment_required && payRaw==='unpaid' ? ' (ожидается)' : ''}</div>
        </div>
      </div>
      <div class="auth-actions" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        <button class="button ghost" id="bk_det_back">Назад</button>
        <button class="button primary" id="bk_det_close">Закрыть</button>
      </div>
      ${(canEdit || canCancel) ? `
        <div class="auth-actions" style="grid-template-columns:repeat(2,minmax(0,1fr))">
          ${canEdit ? '<button class="button ghost" id="bk_det_edit">Редактировать</button>' : '<div></div>'}
          ${canCancel ? '<button class="button ghost" id="bk_det_cancel">Отменить</button>' : '<div></div>'}
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
  const btnEdit = document.getElementById('bk_det_edit');
  const btnCancel = document.getElementById('bk_det_cancel');
  const btnPay = document.getElementById('bk_det_pay');
  if (btnEdit) btnEdit.onclick = ()=> openBookingEdit(item, mode);
  if (btnCancel) btnCancel.onclick = async ()=>{
    if (!confirm('Отменить бронь?')) return;
    try {
      await authFetchJson(`/api/auth/bookings/${item.id}/cancel`, { method:'POST' });
      await openAccountBookings(mode);
    } catch (e) { alert(e.message); }
  };
  if (btnPay) btnPay.onclick = async ()=>{
    try {
      await authFetchJson(`/api/auth/bookings/${item.id}/pay`, { method:'POST' });
      alert('Запрос на оплату создан. Интеграция оплаты будет добавлена позже.');
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
    if (!confirm('Вы уверены, что хотите выйти из аккаунта?')) return;
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
          <label class="auth-field"><span>Код из SMS</span><input id="pv_code" inputmode="numeric" placeholder="${TEST_VERIFY_CODE}"></label>
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
          <label class="auth-field"><span>Код из письма</span><input id="pe_code" inputmode="numeric" placeholder="${TEST_VERIFY_CODE}"></label>
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
    if (typeof cluster?.clearLayers === 'function') cluster.clearLayers();
    filtered.forEach(c => {
      if (c.lat == null || c.lng == null) return;

      const marker = L.marker(
        [c.lat, c.lng],
        { icon: emojiHouseIcon(c.emoji || '🏕️', c.emoji_size || 'standard') }
      );
      marker.bindPopup(popupHtmlForCamp(c), { maxWidth: 260, className: 'camp-popup' });
      cluster.addLayer(marker);
    });
  } catch (e) {
    console.error('loadCamps error:', e);
  }
}

// === Детали базы (модалка «Подробнее») — стабильные параметры, галерея со стрелками/свайпом ===
async function openDetails(campId){
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
    const pics = (photos && photos.length) ? photos.map(p=>p.url) : (camp.photo_main ? [camp.photo_main] : []);
    const descHtml = (camp.description || 'Описание пока отсутствует').replace(/\n/g,'<br>');
    const ht = normalizeHousingType(camp.housing_type);
    const housingBtn = housingLabelTitle(ht);

    let modal = takeoverMiniLoaderAsModal();
    if (!modal) {
      modal = document.createElement('div');
      modal.className = 'modal show';
      modal.style.opacity = '0';
      modal.style.transition = 'opacity .12s ease-out';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="modal-card details">
        <div class="details-title">${camp.name || 'База'}</div>
        <div class="details-desc">${descHtml}</div>

        <div class="details-body">
          <div class="camp-gal">
            <div class="viewport">${
              pics.map(u => `
                <img src="${u}"
                     alt=""
                     draggable="false"
                     loading="eager"
                     decoding="sync"
                     fetchpriority="high"
                     referrerpolicy="no-referrer">
              `).join('')
            }</div>

            <div class="gal-arrow left"  id="galPrev">‹</div>
            <div class="gal-arrow right" id="galNext">›</div>
            <div class="gal-counter" id="galCounter">1/${Math.max(pics.length,1)} →</div>
          </div>

          <!-- Сетка 2×4: параметр + значение РЯДОМ, ячейки в два столбца -->
          <div class="param-list grid2">
            ${[
              ['Озеро',                   camp.lake_name || '—'],
              ['Апартаментов',            camp.rooms_count ?? '—'],
              ['BBQ общая',              `${camp.bbq_shared_count ?? 0} шт.`],
              ['BBQ личная',             `${camp.bbq_count ?? 0} шт.`],                // было «индивидуальная»
              ['Баня',                   `${camp.bath_count ?? 0} шт.`],
              ['Сауна',                  `${camp.sauna_count ?? 0} шт.`],
              ['Бассейн общий',          `${camp.pools_shared_count ?? 0} шт.`],
              ['Бассейн личный',         `${camp.pools_private_count ?? 0} шт.`]      // было «индивидуальный»
            ].map(([k,v]) => `
              <div class="param-item">
                <div class="param-row"><div class="k">${k}</div><div class="v">${v}</div></div>
              </div>
            `).join('')}
          </div>

        </div>

        <div class="actions" style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
          <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff" onclick="openBookingFilterWithAuth(${campId})">Забронировать</button>
          <button class="button primary" onclick="openCampHousing(${campId})">${housingBtn}</button>
          <button class="button ghost" onclick="document.body.removeChild(this.closest('.modal'))">Назад</button>
        </div>
      </div>
    `;

    // ---- Мини-галерея (стрелки + свайп, без проскока) ----
    const vp = modal.querySelector('.camp-gal .viewport');
    const imgs = vp ? vp.querySelectorAll('img') : [];
    const btnPrev = modal.querySelector('#galPrev');
    const btnNext = modal.querySelector('#galNext');
    const counter = modal.querySelector('#galCounter');

    // фикс ленты: ширина = N*100%, каждый кадр занимает 100% окна
    const N = Math.max(imgs.length, 1);
    if (vp) {
      vp.style.width = `${N * 100}%`;
      imgs.forEach(img => { img.style.width = `${100 / N}%`; });
    }

    let i = 0;
    let locked = false;     // защита от «пролёта»
    function updateUI(){
      const left  = (i > 0)     ? '← ' : '';
      const right = (i < N - 1) ? ' →' : '';
      counter.textContent = `${left}${i+1}/${N}${right}`;
      btnPrev.classList.toggle('disabled', i === 0);
      btnNext.classList.toggle('disabled', i === N-1);
    }
function go(to){
  if (!vp || locked) return;
  const clamped = Math.max(0, Math.min(N-1, to));
  if (clamped === i) { updateUI(); return; }
  locked = true;                      // пока идёт анимация — блокируем дальнейшие переходы
  i = clamped;

  // ВАЖНО: трек шириной N*100%, каждый кадр = 100/N%.
  // Сдвигаем на долю кадра, а не на 100% всего трека.
  const step = 100 / N;
  vp.style.transform = `translateX(${-i * step}%)`;

  // снимем блокировку по окончании CSS-перехода (fallback — таймер)
  const unlock = ()=>{ locked = false; vp.removeEventListener('transitionend', unlock); updateUI(); };
  vp.addEventListener('transitionend', unlock);
  setTimeout(unlock, 350);
}

    const throttledPrev = throttle(()=> go(i-1), 260);
    const throttledNext = throttle(()=> go(i+1), 260);
    if (btnPrev) btnPrev.onclick = () => { hapticPulse('light', 12); throttledPrev(); };
    if (btnNext) btnNext.onclick = () => { hapticPulse('light', 12); throttledNext(); };


    // свайпы
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

      // клик по каждому изображению — открываем полноэкранную галерею с правильным индексом
      imgs.forEach((img, idx) => {
        img.addEventListener('click', ()=> openFullscreenGallery(pics, idx));
      });
    }

        updateUI();

        // Всегда 2 колонки. Подгоняем размеры шрифтов/отступов под ширину карточки.
        applyTwoColScale(modal);

        requestAnimationFrame(()=> { modal.style.opacity = '1'; });

  } catch (e) {
    hideMiniLoader();

    console.error(e);
    showModal(`
      <div class="card">
        <p class="muted">Не удалось загрузить карточку базы.</p>
        <div class="actions"><button class="button primary" onclick="closeModal()">OK</button></div>
      </div>`);
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
function openFullscreenGallery(pics, startIndex=0){
  if (!Array.isArray(pics) || pics.length === 0) return;

  const wrap = document.createElement('div');
  wrap.className = 'fs-modal';
  wrap.innerHTML = `
    <div class="fs-viewport">
      <div class="fs-track">
        ${pics.map(u => `
          <img src="${u}"
               alt=""
               draggable="false"
               loading="eager"
               decoding="sync"
               fetchpriority="high"
               referrerpolicy="no-referrer">
        `).join('')}
      </div>
    </div>

    <!-- Стрелки поверх фото -->
    <div class="fs-arrow left"  id="fsPrev">‹</div>
    <div class="fs-arrow right" id="fsNext">›</div>

    <div class="fs-ui">
      <div class="fs-counter" id="fsCounter">${Math.min(startIndex+1,pics.length)}/${pics.length}</div>
      <div class="fs-actions">
        <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff" id="fsBook">Забронировать</button>
        <button class="button ghost" id="fsBack">Назад</button>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);

  const track = wrap.querySelector('.fs-track');
  const imgs  = [...wrap.querySelectorAll('.fs-track img')];
  const cnt   = wrap.querySelector('#fsCounter');
  const fsPrev = wrap.querySelector('#fsPrev');
  const fsNext = wrap.querySelector('#fsNext');

  // позиции слайдов
  let i = Math.max(0, Math.min(pics.length-1, startIndex));
  let locked = false;

  // ЗУМ/ПАН состояние ПО-СЛАЙДНО
  const Z_MIN = 1;
  const Z_MAX = 3;
  const zoom = imgs.map(()=>1);          // текущий масштаб
  const panX = imgs.map(()=>0);          // смещение по X в px
  const panY = imgs.map(()=>0);          // смещение по Y в px

  function updateCounter(){ cnt.textContent = `${i+1}/${pics.length}`; }

  function slideGo(to, opts = {}){
    if (locked) return;
    const n = pics.length;
    // Circular navigation: wrap around at boundaries
    const dest = ((to % n) + n) % n;
    const instant = !!opts.instant || Math.abs(dest - i) > 1;

    locked = true;
    const applyPos = () => { track.style.transform = `translateX(${-dest*100}vw)`; };
    if (instant) {
      const prevTransition = track.style.transition;
      track.style.transition = 'none';
      applyPos();
      void track.offsetHeight;
      track.style.transition = prevTransition || '';
    } else {
      applyPos();
    }
    const unlock = ()=>{ locked = false; track.removeEventListener('transitionend', unlock); updateCounter(); };
    track.addEventListener('transitionend', unlock);
    setTimeout(unlock, 350);

    i = dest;
  }

  // Начальная ширина и позиция
  track.style.width = `${pics.length * 100}vw`;
  imgs.forEach(el => el.style.width = '100vw');
  slideGo(i, { instant: true });
  updateCounter();

  // Антидребезг для стрелок
  const resetZoomState = (k) => {
    zoom[k] = 1; panX[k] = 0; panY[k] = 0;
    applyZoomPan(k);
  };

  const fsThPrev = throttle(() => {
    if (zoom[i] !== 1) resetZoomState(i); // сбрасываем зум и позволяем листать
    slideGo(i - 1);
  }, 260);
  const fsThNext = throttle(() => {
    if (zoom[i] !== 1) resetZoomState(i);
    slideGo(i + 1);
  }, 260);

if (fsPrev) fsPrev.onclick = () => { hapticPulse('light', 12); fsThPrev(); };
if (fsNext) fsNext.onclick = () => { hapticPulse('light', 12); fsThNext(); };


  // Клавиатура (desktop)
  document.addEventListener('keydown', fsKeyHandler);
  function fsKeyHandler(e){
    if (e.key === 'ArrowLeft')  fsThPrev();
    if (e.key === 'ArrowRight') fsThNext();
  }

  // ====== ЗУМ/ПАН на активном слайде ======
  function applyZoomPan(k){
    const img = imgs[k];
    img.style.transition = 'transform .03s linear'; // чуть сгладим пан
    img.style.transform  = `translate(${panX[k]}px, ${panY[k]}px) scale(${zoom[k]})`;
  }
  function clampPanToBounds(k){
    const z = zoom[k];
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    // при object-fit:contain используем размер вьюпорта
    const maxX = (vw * (z - 1)) / 2;
    const maxY = (vh * (z - 1)) / 2;
    panX[k] = Math.max(-maxX, Math.min(maxX, panX[k]));
    panY[k] = Math.max(-maxY, Math.min(maxY, panY[k]));
  }
  function resetZoomIfSmall(k){
    if (zoom[k] <= 1.01){
      zoom[k] = 1; panX[k] = 0; panY[k] = 0;
    }
  }

  // Обработчики жестов — ВЕШАЕМ НА КАЖДУЮ КАРТИНКУ
  imgs.forEach((img, idx) => {
    let t1x=0, t1y=0, t2x=0, t2y=0;
    let startDist=0, startZoom=1;
    let lastX=0, lastY=0;
    let isPinching=false, isPanning=false;
    let lastTapTime=0;

    // Touch Start
    img.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2){
        // Pinch start
        isPinching = true; isPanning = false;
        const a = e.touches[0], b = e.touches[1];
        t1x=a.clientX; t1y=a.clientY; t2x=b.clientX; t2y=b.clientY;
        startDist = Math.hypot(t2x - t1x, t2y - t1y);
        startZoom = zoom[idx];
      } else if (e.touches.length === 1){
        // Pan start (только если уже увеличено)
        isPinching = false;
        if (zoom[idx] > 1){
          isPanning = true;
          lastX = e.touches[0].clientX;
          lastY = e.touches[0].clientY;
        } else {
          isPanning = false;
        }
      }
    }, { passive: true });

    // Touch Move
    img.addEventListener('touchmove', (e) => {
      if (isPinching && e.touches.length === 2){
        const a = e.touches[0], b = e.touches[1];
        const dist = Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
        let z = startZoom * (dist / (startDist || 1));
        z = Math.max(Z_MIN, Math.min(Z_MAX, z));
        zoom[idx] = z;
        clampPanToBounds(idx);
        applyZoomPan(idx);
      } else if (isPanning && e.touches.length === 1){
        const cx = e.touches[0].clientX;
        const cy = e.touches[0].clientY;
        panX[idx] += (cx - lastX);
        panY[idx] += (cy - lastY);
        lastX = cx; lastY = cy;
        clampPanToBounds(idx);
        applyZoomPan(idx);
      }
    }, { passive: true });

    // Touch End
    img.addEventListener('touchend', (e) => {
      // Сброс флагов
      if (e.touches.length === 0){ isPinching = false; isPanning = false; }
      clampPanToBounds(idx);
      resetZoomIfSmall(idx);
      applyZoomPan(idx);

      // Двойной тап — зум/откат
      const now = Date.now();
      if (now - lastTapTime < 300 && e.changedTouches && e.changedTouches.length === 1){
        if (zoom[idx] === 1){
          zoom[idx] = 2.2; panX[idx]=0; panY[idx]=0;
        } else {
          zoom[idx] = 1; panX[idx]=0; panY[idx]=0;
        }
        applyZoomPan(idx);
      }
      lastTapTime = now;
    }, { passive: true });

    // Колесо мыши — zoom на десктопе
    img.addEventListener('wheel', (e) => {
      e.preventDefault();
      let z = zoom[idx] + (e.deltaY < 0 ? 0.15 : -0.15);
      z = Math.max(Z_MIN, Math.min(Z_MAX, z));
      zoom[idx] = z;
      clampPanToBounds(idx);
      applyZoomPan(idx);
    }, { passive: false });

    // Клик мышью — переход между слайдами только если не увеличено
    img.addEventListener('click', (e) => {
      if (zoom[idx] > 1.01) return;
      const rect = track.getBoundingClientRect();
      const leftHalf = (e.clientX - rect.left) < rect.width/2;
      if (leftHalf) fsThPrev(); else fsThNext();
    });
  });

  // Свайпы по треку (перелистывание) — ТОЛЬКО когда текущий слайд не увеличен
  let sx = 0, dx = 0, swiping = false;
  const THRESH = 50;
  const isZoomed = () => (zoom[i] || 1) > 1.01;
  track.addEventListener('touchstart', (e)=> {
    if (isZoomed()) return;                 // при зуме перелистывание выключено
    if (!e.touches[0]) return;
    swiping = true; sx = e.touches[0].clientX; dx = 0;
  }, {passive:true});
  track.addEventListener('touchmove', (e)=> {
    if (!swiping || !e.touches[0]) return;
    dx = e.touches[0].clientX - sx;
  }, {passive:true});
  track.addEventListener('touchend', ()=> {
    if (!swiping) return; swiping = false;
    if (isZoomed()) return;                 // на всякий случай
    if (Math.abs(dx) > THRESH){
      if (dx < 0) fsThNext(); else fsThPrev();
    }
  }, {passive:true});

  // Кнопки
    wrap.querySelector('#fsBook').onclick = ()=> { hapticPulse('soft', 14); closeFullscreen(); openBookingFilterWithAuth(window.__currentCampId); };
    wrap.querySelector('#fsBack').onclick  = ()=> { hapticPulse('selection', 10); closeFullscreen(); };
    wrap.addEventListener('click', (e)=>{ if (e.target === wrap) closeFullscreen(); });

  function closeFullscreen(){
    document.removeEventListener('keydown', fsKeyHandler);
    if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
  }
}



// Глобальные обработчики, на которые ссылается HTML в балуне
window.__showCampBrief = function(campId) {
  // закрываем балун, если открыт
  try { document.querySelectorAll('.leaflet-popup-close-button').forEach(b=>b.click()); } catch(_){}
  openDetails(campId);
};

window.__openCampBooking = function(campId) {
  // закрываем «Подробнее», если открыто
  const m = document.querySelector('.modal.show');
  if (m) m.remove();
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
function openBookingFilterModal(opts = {}) {
  const dontCloseBackground = opts.dontCloseBackground || false;
  
  const mode = String(opts.mode || 'map');
  const isBooking = mode === 'booking';
  const titleText = String(opts.title || (isBooking ? 'Подтвердите данные для бронирования' : 'Выберите даты и гостей'));
  const hintText = String(
    opts.hint != null
      ? opts.hint
      : (isBooking
          ? 'Укажите даты и количество гостей. После подтверждения вы сможете выбрать подходящий вариант размещения.'
          : 'При сохранении фильтра на карте будут показаны только базы отдыха, подходящие под Ваш выбор')
  );
  const applyText = String(opts.applyText || (isBooking ? 'К выбору вариантов' : 'Сохранить'));
  const closeText = String(opts.closeText || (isBooking ? 'Назад' : 'Закрыть'));

  // Если нужно сохранить фоновое окно, создаём отдельное окно для фильтра
  if (dontCloseBackground) {
    const filterModal = document.createElement('div');
    filterModal.className = 'modal show';
    filterModal.id = 'filterModal';
    filterModal.innerHTML = `
      <div class="modal-card booking-shell">
        <div class="booking-card">
          <div class="booking-title">${titleText}</div>

          <div class="booking-hint">${hintText}</div>

          <div class="booking-grid">
            <label class="bk-field">
              <span>Заезд</span>
              <div class="bk-date">
                <div class="bk-input" id="bkShowFrom">—</div>
                <input type="date" id="bkFrom" class="bk-native">
              </div>
            </label>

            <label class="bk-field">
              <span>Выезд</span>
              <div class="bk-date">
                <div class="bk-input" id="bkShowTo">—</div>
                <input type="date" id="bkTo" class="bk-native">
              </div>
            </label>

            <label class="bk-field">
              <span>Взрослые</span>
              <select id="bkAdults" class="bk-select">
                ${Array.from({length:30},(_,i)=>`<option>${i+1}</option>`).join('')}
              </select>
            </label>

            <label class="bk-field">
              <span>Дети</span>
              <select id="bkKids" class="bk-select">
                ${Array.from({length:31},(_,i)=>`<option>${i}</option>`).join('')}
              </select>
            </label>
          </div>

          <label class="bk-checkbox-wrapper">
            <input type="checkbox" id="bkAllowSplit" class="bk-checkbox">
            <span>Показать варианты заселения в разные номера или дома</span>
          </label>

          <div class="booking-actions">
            <button class="button ghost" id="bkClose">${closeText}</button>
            <button class="button ghost" id="bkReset">Сбросить</button>
            <button class="button primary" id="bkApply">${applyText}</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(filterModal);

    // Клик по фону закрывает фильтр
    filterModal.addEventListener('click', (e) => {
      if (e.target === filterModal) {
        filterModal.remove();
        if (opts.onClose) opts.onClose();
      }
    });

    // Настраиваем элементы фильтра
    setupBookingFilterElements(filterModal, opts, isBooking, titleText);
    return;
  }

  // Обычная логика - используем основное окно
  const prev = document.querySelector('.modal.show');
  if (prev) prev.remove();

  showModal(`
    <div class="booking-card">
      <div class="booking-title">${titleText}</div>

      <div class="booking-hint">${hintText}</div>

      <div class="booking-grid">
        <label class="bk-field">
          <span>Заезд</span>
          <div class="bk-date">
            <div class="bk-input" id="bkShowFrom">—</div>
            <input type="date" id="bkFrom" class="bk-native">
          </div>
        </label>

        <label class="bk-field">
          <span>Выезд</span>
          <div class="bk-date">
            <div class="bk-input" id="bkShowTo">—</div>
            <input type="date" id="bkTo" class="bk-native">
          </div>
        </label>

        <label class="bk-field">
          <span>Взрослые</span>
          <select id="bkAdults" class="bk-select">
            ${Array.from({length:30},(_,i)=>`<option>${i+1}</option>`).join('')}
          </select>
        </label>

        <label class="bk-field">
          <span>Дети</span>
          <select id="bkKids" class="bk-select">
            ${Array.from({length:31},(_,i)=>`<option>${i}</option>`).join('')}
          </select>
        </label>
      </div>

      <label class="bk-checkbox-wrapper">
        <input type="checkbox" id="bkAllowSplit" class="bk-checkbox">
        <span>Показать варианты заселения в разные номера или дома</span>
      </label>

      <div class="booking-actions">
        <button class="button ghost" id="bkClose">${closeText}</button>
        <button class="button ghost" id="bkReset">Сбросить</button>
        <button class="button primary" id="bkApply">${applyText}</button>
      </div>
    </div>
  `);

  // сужаем внешнюю «прозрачную» оболочку только для окна фильтра
  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.add('booking-shell'); shell.classList.remove('details'); }

  // Инициализируем обработчики фильтра
  setupBookingFilterElements(document.body, opts, isBooking, titleText);
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
  const splitChk = card.querySelector('#bkAllowSplit');

  // заполнение из предыдущего фильтра (если уже выбирали)
  const F = window.__bookingFilter || {};
  if (F.from) fromI.value = F.from;
  if (F.to)   toI.value   = F.to;
  adSel.value = String(F.adults ?? 2);
  kdSel.value = String(F.kids   ?? 0);
  if (F.allowSplitRooms !== undefined) splitChk.checked = F.allowSplitRooms;

  // читаемо показываем выбранные даты
  const fmt  = v => v ? new Date(v).toLocaleDateString('ru-RU') : '—';
  const sync = () => { fromB.textContent = fmt(fromI.value); toB.textContent = fmt(toI.value); };
  fromI.addEventListener('change', sync);
  toI.addEventListener('change',   sync);
  sync();

  // Простой JS календарь для браузеров без поддержки date picker
  function showDatePicker(input, label) {
    const currentValue = input.value ? new Date(input.value) : new Date();
    const year = currentValue.getFullYear();
    const month = currentValue.getMonth();
    
    const daysInMonth = (y, m) => new Date(y, m+1, 0).getDate();
    const firstDay = new Date(year, month, 1).getDay();
    const days = daysInMonth(year, month);
    
    let html = `<div style="background:rgba(17,19,23,.95);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:12px;width:280px;max-width:90vw">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;font-weight:600">
        <button type="button" style="background:none;border:none;color:#e5e7eb;cursor:pointer;font-size:16px" id="prevMonth">‹</button>
        <div id="monthYear" style="font-size:14px"></div>
        <button type="button" style="background:none;border:none;color:#e5e7eb;cursor:pointer;font-size:16px" id="nextMonth">›</button>
      </div>
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;font-size:12px;text-align:center">`;
    
    // дни недели
    const dayNames = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
    dayNames.forEach(d => html += `<div style="color:#9aa3ad;font-weight:600;padding:4px">${d}</div>`);
    
    // пустые дни до начала месяца
    const adjustedFirstDay = firstDay === 0 ? 6 : firstDay - 1;
    for (let i = 0; i < adjustedFirstDay; i++) {
      html += `<div style="padding:4px"></div>`;
    }
    
    // дни месяца
    for (let d = 1; d <= days; d++) {
      const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const isSelected = input.value === dateStr;
      const isToday = new Date().toISOString().split('T')[0] === dateStr;
      const bgColor = isSelected ? '#22c55e' : isToday ? 'rgba(34,197,94,0.2)' : 'transparent';
      html += `<button type="button" data-date="${dateStr}" style="background:${bgColor};border:1px solid ${isSelected ? '#22c55e' : 'transparent'};color:#e5e7eb;border-radius:6px;padding:4px;cursor:pointer;font-size:12px">${d}</button>`;
    }
    
    html += `</div></div>`;
    
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:60';
    overlay.innerHTML = html;
    document.body.appendChild(overlay);
    
    const monthYearEl = overlay.querySelector('#monthYear');
    const updateMonth = (y, m) => {
      monthYearEl.textContent = new Date(y, m).toLocaleDateString('ru-RU', {month:'long', year:'numeric'});
    };
    updateMonth(year, month);
    
    let currentY = year, currentM = month;
    overlay.querySelector('#prevMonth').onclick = (e) => {
      e.preventDefault();
      currentM--;
      if (currentM < 0) { currentM = 11; currentY--; }
      overlay.remove();
      showDatePicker(input, label);
    };
    
    overlay.querySelector('#nextMonth').onclick = (e) => {
      e.preventDefault();
      currentM++;
      if (currentM > 11) { currentM = 0; currentY++; }
      overlay.remove();
      showDatePicker(input, label);
    };
    
    overlay.querySelectorAll('[data-date]').forEach(btn => {
      btn.onclick = (e) => {
        e.preventDefault();
        input.value = btn.dataset.date;
        sync();
        overlay.remove();
      };
    });
    
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
  }
  
  // клики по видимым «кнопкам» и input-ам — открывают JS календарь
  const openPicker = (inp) => showDatePicker(inp, 'Выберите дату');
  
  // Добавляем обработчик к самим input-ам и визуальным кнопкам
  fromI.addEventListener('click', (e) => {
    e.stopPropagation();
    openPicker(fromI);
  });
  toI.addEventListener('click', (e) => {
    e.stopPropagation();
    openPicker(toI);
  });
  
  fromB.addEventListener('click', () => openPicker(fromI));
  toB.addEventListener('click',   () => openPicker(toI));

  // кнопки
  card.querySelector('#bkClose').onclick = opts.onClose || closeModal;
  card.querySelector('#bkReset').onclick = ()=>{
    fromI.value=''; toI.value=''; adSel.value='2'; kdSel.value='0'; splitChk.checked=false; sync();
    // сброс — очищаем общий фильтр и перерисовываем всю карту
    window.__bookingFilter = null;
  };
  card.querySelector('#bkApply').onclick = async ()=>{
    const from = fromI.value || '';
    const to   = toI.value   || '';
    const adults = Number(adSel.value);
    const kids   = Number(kdSel.value);
    if (isBooking) {
      if (!from || !to) { appAlert('Выберите даты заезда и выезда'); return; }
      try {
        const a = new Date(from);
        const b = new Date(to);
        if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime()) || b <= a) {
          appAlert('Проверьте даты заезда/выезда');
          return;
        }
      } catch(_) {}
    }
    window.__bookingFilter = {
      from,
      to,
      adults,
      kids,
      total: adults + kids,
      allowSplitRooms: splitChk.checked
    };
    closeModal();
    if (isBooking) {
      const cid = (opts.campId != null) ? Number(opts.campId) : Number(window.__currentCampId);
      if (!Number.isFinite(cid)) { appAlert('Не выбрана база отдыха'); return; }
      if (typeof opts.onApply === 'function') { await opts.onApply(window.__bookingFilter); return; }
      await openCampAccommodations(cid);
      return;
    }
    try { await loadCamps(); if (typeof restoreMapView==='function') restoreMapView(); } catch(_) {}
  };
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
  const splitChk = card.querySelector('#bkAllowSplit');

  // заполнение из предыдущего фильтра (если уже выбирали)
  const F = window.__bookingFilter || {};
  if (F.from) fromI.value = F.from;
  if (F.to)   toI.value   = F.to;
  adSel.value = String(F.adults ?? 2);
  kdSel.value = String(F.kids   ?? 0);
  if (F.allowSplitRooms !== undefined) splitChk.checked = F.allowSplitRooms;

  // читаемо показываем выбранные даты
  const fmt  = v => v ? new Date(v).toLocaleDateString('ru-RU') : '—';
  const sync = () => { fromB.textContent = fmt(fromI.value); toB.textContent = fmt(toI.value); };
  fromI.addEventListener('change', sync);
  toI.addEventListener('change',   sync);
  sync();

  // клики по видимым кнопкам/input — открывают календарь
  const openPicker = (inp) => {
    const currentValue = inp.value ? new Date(inp.value) : new Date();
    const year = currentValue.getFullYear();
    const month = currentValue.getMonth();
    
    const daysInMonth = (y, m) => new Date(y, m+1, 0).getDate();
    const firstDay = new Date(year, month, 1).getDay();
    const days = daysInMonth(year, month);
    
    let html = `<div style="background:rgba(17,19,23,.95);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:12px;width:280px;max-width:90vw">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;font-weight:600">
        <span>${new Date(year, month).toLocaleDateString('ru-RU', {month:'long', year:'numeric'})}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">`;
        const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
        dayNames.forEach(name => { html += `<div style="text-align:center;font-size:11px;color:#999;margin-bottom:4px">${name}</div>`; });
        for (let i = 0; i < firstDay - 1; i++) html += '<div></div>';
        for (let d = 1; d <= days; d++) {
          const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
          const isSelected = inp.value === dateStr;
          html += `<button data-date="${dateStr}" style="background:${isSelected?'#2a9df4':'transparent'};color:#fff;border:1px solid #444;border-radius:4px;padding:4px;cursor:pointer;font-size:12px">${d}</button>`;
        }
      html += '</div></div>';
    
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:grid;align-items:center;justify-content:center;z-index:9998';
    overlay.innerHTML = html;
    document.body.appendChild(overlay);
    
    overlay.addEventListener('click', (e) => {
      if (e.target.dataset.date) {
        inp.value = e.target.dataset.date;
        sync();
        overlay.remove();
      }
    });
    
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
  };
  
  fromI.addEventListener('click', (e) => { e.stopPropagation(); openPicker(fromI); });
  toI.addEventListener('click', (e) => { e.stopPropagation(); openPicker(toI); });
  fromB.addEventListener('click', () => openPicker(fromI));
  toB.addEventListener('click',   () => openPicker(toI));

  // кнопки
  card.querySelector('#bkClose').onclick = () => {
    const filterModal = document.getElementById('filterModal');
    if (filterModal) filterModal.remove();
    if (opts.onClose) opts.onClose();
    else closeModal();
  };
  
  card.querySelector('#bkReset').onclick = ()=>{
    fromI.value=''; toI.value=''; adSel.value='2'; kdSel.value='0'; splitChk.checked=false; sync();
    window.__bookingFilter = null;
  };
  
  card.querySelector('#bkApply').onclick = async ()=>{
    const from = fromI.value || '';
    const to   = toI.value   || '';
    const adults = Number(adSel.value);
    const kids   = Number(kdSel.value);
    if (isBooking) {
      if (!from || !to) { appAlert('Выберите даты заезда и выезда'); return; }
      try {
        const a = new Date(from);
        const b = new Date(to);
        if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime()) || b <= a) {
          appAlert('Проверьте даты заезда/выезда');
          return;
        }
      } catch(_) {}
    }
    window.__bookingFilter = {
      from, to, adults, kids,
      total: adults + kids,
      allowSplitRooms: splitChk.checked
    };
    
    // Закрываем фильтр
    const filterModal = document.getElementById('filterModal');
    if (filterModal) filterModal.remove();
    else closeModal();
    
    if (isBooking) {
      const cid = (opts.campId != null) ? Number(opts.campId) : Number(window.__currentCampId);
      if (!Number.isFinite(cid)) { appAlert('Не выбрана база отдыха'); return; }
      if (typeof opts.onApply === 'function') { await opts.onApply(window.__bookingFilter); return; }
      await openCampAccommodations(cid);
      return;
    }
    try { await loadCamps(); if (typeof restoreMapView==='function') restoreMapView(); } catch(_) {}
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

function renderRoomPriceBlock(room){
  const priceAdult = Number(room?.price_adult) || 0;
  const priceChild = Number(room?.price_child) || 0;
  const priceFixed = Number(room?.price) || 0;
  const rows = [];
  if (priceAdult > 0) rows.push(`<span class="muted">Взрослый: <b>${formatPriceRub(priceAdult)}</b></span>`);
  if (priceChild > 0) rows.push(`<span class="muted">Ребёнок: <b>${formatPriceRub(priceChild)}</b></span>`);
  if (priceFixed > 0) rows.push(`<span class="muted">Итого: <b>${formatPriceRub(priceFixed)}</b></span>`);
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

  // Ensure at least 1 adult in the first room if we have any guests
  if (aLeft > 0) { items[0].adults = 1; aLeft -= 1; }

  // Put kids first, spreading by capacity (requires adult in that room)
  for (let i = 0; i < items.length && kLeft > 0; i++) {
    if (items[i].adults <= 0 && aLeft > 0) { items[i].adults = 1; aLeft -= 1; }
    if (items[i].adults <= 0) continue;
    const cap = roomCapacity(items[i].room);
    const used = items[i].adults + items[i].kids;
    const canAdd = Math.max(0, cap - used);
    const add = Math.min(canAdd, kLeft);
    items[i].kids += add;
    kLeft -= add;
  }

  // Put remaining adults by capacity
  for (let i = 0; i < items.length && aLeft > 0; i++) {
    const cap = roomCapacity(items[i].room);
    const used = items[i].adults + items[i].kids;
    const canAdd = Math.max(0, cap - used);
    const add = Math.min(canAdd, aLeft);
    items[i].adults += add;
    aLeft -= add;
  }

  // If still left, dump into first room (user will fix) but keep non-negative
  if (aLeft > 0) items[0].adults += aLeft;
  if (kLeft > 0) {
    if (items[0].adults <= 0) items[0].adults = 1;
    items[0].kids += kLeft;
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
    else totalPrice += sub;
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

async function createBookingsFromAllocation(campId, filter, items){
  const cid = Number(campId);
  const from = filter?.from;
  const to = filter?.to;
  const payloadItems = (items || [])
    .map(it => ({
      room_id: Number(it.room?.id),
      adults: Number(it.adults) || 0,
      kids: Number(it.kids) || 0,
    }))
    .filter(x => Number.isFinite(x.room_id) && (x.adults + x.kids) > 0);

  // Future-ready payload
  window.__lastBookingRoomsPayload = payloadItems;

  const created = [];
  for (const it of payloadItems) {
    const resp = await authFetchJson('/api/auth/bookings', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        camp_id: cid,
        room_id: it.room_id,
        check_in: from,
        check_out: to,
        adults: it.adults,
        kids: it.kids,
      })
    });
    created.push(resp.booking_id);
  }
  return created;
}

function openAllocationModal({ camp, campId, roomsAvailable, selectedRooms, filter, onBack }){
  const cid = Number(campId);
  const f = filter || window.__bookingFilter || {};
  const available = Array.isArray(roomsAvailable) ? roomsAvailable : [];
  const selected = Array.isArray(selectedRooms) ? selectedRooms : [];

  const items = autoDistributeGuests(selected, f);

  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); }

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

      <div class="alloc-summary" id="allocSummary"></div>

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

  function render(){
    if (!listEl) return;
    listEl.innerHTML = items.map((it, idx) => {
      const room = it.room || {};
      const cap = roomCapacity(room);
      const photos = Array.isArray(room.photos) ? room.photos : [];
      const cover = photos.find(p => p && p.cover) || photos[0];
      const thumb = cover?.url ? `<img class="alloc-thumb" src="${cover.url}" alt="">` : `<div class="alloc-thumb ph"></div>`;
      const sub = calcRoomSubtotal(room, it.adults, it.kids);
      const subText = (sub == null) ? '—' : formatPriceRub(sub);
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
      row.addEventListener('click', (e) => {
        const t = e.target;
        if (!(t instanceof HTMLElement)) return;
        const act = t.getAttribute('data-act');
        if (!act) return;
        e.preventDefault();
        e.stopPropagation();
        const it = items[idx];
        if (!it) return;
        if (act === 'rm') {
          items.splice(idx, 1);
          render();
          updateSummary();
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
      const priceText = (v.totalPrice == null) ? '—' : formatPriceRub(v.totalPrice);
      summaryEl.innerHTML = `
        <div class="alloc-row"><div class="muted">Взрослые</div><div class="alloc-val">${v.sumAdults}</div></div>
        <div class="alloc-row"><div class="muted">Дети</div><div class="alloc-val">${v.sumKids}</div></div>
        <div class="alloc-row"><div class="muted">Итого</div><div class="alloc-val">${priceText}</div></div>
      `;
    }
    if (submitBtn) submitBtn.disabled = !v.ok;
  }

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
    if (!requireAuth()) return;
    const v = validateAllocation(items, f);
    if (!v.ok) { updateSummary(); return; }
    try {
      document.getElementById('allocSubmit').disabled = true;
      const ids = await createBookingsFromAllocation(cid, f, items);
      closeModal();
      setTabById('tab-account');
      await openAccountBookings('active');
      alert(ids.length > 1 ? `Заявки на бронирование созданы: ${ids.join(', ')}` : `Заявка на бронирование создана (№${ids[0]}).`);
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
  const maxCap = Math.max(...items.map(roomCapacity));
  const maxSum = Math.min(need + maxCap * 2, 200); // cap to keep dp small
  const dp = Array(maxSum + 1).fill(null);
  dp[0] = { cnt: 0, price: 0, prev: -1, idx: -1 };

  for (let i = 0; i < items.length; i++) {
    const cap = roomCapacity(items[i]);
    const price = roomPriceFrom(items[i]) || 0;
    for (let s = maxSum; s >= 0; s--) {
      const cur = dp[s];
      if (!cur) continue;
      const ns = Math.min(maxSum, s + cap);
      const cand = { cnt: cur.cnt + 1, price: cur.price + price, prev: s, idx: i };
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
  let s = bestSum;
  while (s > 0) {
    const st = dp[s];
    if (!st || st.idx < 0) break;
    picked.push(items[st.idx]);
    s = st.prev;
  }
  return picked.reverse();
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
  
  showModal(`
    <div class="accom-card">
      <div class="accom-head">
        <div class="accom-title">${camp?.name || 'База'} • ${typeName}</div>
        <div class="accom-sub">Выберите конкретный вариант для подробностей</div>
      </div>
      <div class="accom-list" id="roomsDetailList"></div>
      <div class="accom-actions">
        <button class="button ghost" id="roomsListBack">Назад</button>
        <button class="button primary" id="roomsListBook">Забронировать</button>
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
      if (!requireAuth()) return;

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
          title: 'Подтвердите данные для бронирования',
          hint: 'Укажите даты и количество гостей. После подтверждения вы сможете выбрать подходящий вариант размещения.',
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
function openRoomDetails(room, camp, context) {
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
  if (showFloor) allParams.push(['Этаж', floors ? `${floor} / ${floors}` : String(floor)]);
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
  const balcony = shareValOptional(room.balcony_type);
  if (balcony) allParams.push(['Балкон', balcony]);
  allParams.push(['Кондиционер', (Number(room.has_ac) || 0) ? 'Есть' : 'Нет']);

  const objWord = housingLabelObjectWord(camp?.housing_type || 'apartments');

  const shell = document.getElementById('modalCard');
  if (shell) {
    shell.classList.remove('booking-shell');
    shell.classList.add('details');
  }

  showModal(`
    <div class="details-title">${room.name || 'Апартамент'}</div>
    ${descHtml ? `<div class="details-desc">${descHtml}</div>` : ''}

    <div class="details-body">
      <div class="camp-gal room-gal">
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
          <div class="gal-arrow left"  id="galPrev">‹</div>
          <div class="gal-arrow right" id="galNext">›</div>
          <div class="gal-counter" id="galCounter">1/${pics.length} →</div>
        ` : ''}
      </div>

      <div class="room-params-compact">
        ${compactParams.map(([k,v]) => `
          <div class="room-param-line">
            <span class="room-param-k">${k}</span>
            <span class="room-param-sep">—</span>
            <span class="room-param-v">${v}</span>
          </div>
        `).join('')}
      </div>

      <button class="button ghost room-toggle-all" id="roomToggleAllParams">Открыть все параметры ${objWord}</button>

      ${renderRoomPriceBlock(room)}
    </div>

    <div class="actions" style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
      <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff" id="roomDetailBookBtn">Забронировать</button>
      <button class="button ghost" id="roomDetailsBack">Назад</button>
    </div>
  `);

  const root = document.getElementById('modalCard');

  // Сохраняем в стек для возврата из фильтра
  pushNavStack({ type: 'roomDetails', room, camp, context: context || null });

  // Обработчик кнопки "Забронировать"
  document.getElementById('roomDetailBookBtn').onclick = async () => {
    if (!requireAuth()) return;
    
    const campData = camp || await getCampQuick(camp.id);
    const ht = normalizeHousingType(campData?.housing_type);

    const roomsAll = Array.isArray(window.__roomsCache) ? window.__roomsCache : [];
    const key = `${room.room_type || 'Дом'}::${room.class || room.name || 'Стандарт'}`;
    const roomsOfType = roomsAll.length
      ? roomsAll.filter(r => `${r.room_type || 'Дом'}::${r.class || r.name || 'Стандарт'}` === key)
      : [room];

    const openAlloc = () => {
      openAllocationModal({
        camp: campData || camp,
        campId: camp.id,
        roomsAvailable: roomsOfType,
        selectedRooms: [room],
        filter: window.__bookingFilter,
        onBack: () => openRoomDetails(room, camp, context),
      });
    };

    const f = window.__bookingFilter || {};
    if (!f.from || !f.to) {
      openBookingFilterModal({
        mode: 'booking',
        campId: camp.id,
        title: 'Подтвердите данные для бронирования',
        hint: 'Укажите даты и количество гостей. После подтверждения вы сможете выбрать подходящий вариант размещения.',
        applyText: `К выбору ${housingLabelChoiceWord(ht)}`,
        onApply: () => openAlloc(),
      });
      return;
    }
    openAlloc();
  };

  // Обработчик кнопки "Назад"
  const backBtn = document.getElementById('roomDetailsBack');
  if (backBtn) {
    backBtn.onclick = (e) => {
      try { e.preventDefault(); e.stopPropagation(); } catch (_) {}
      const ctx = context || null;
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
      const left  = (i > 0)     ? '← ' : '';
      const right = (i < N - 1) ? ' →' : '';
      counter.textContent = `${left}${i+1}/${N}${right}`;
      if (btnPrev) btnPrev.classList.toggle('disabled', i === 0);
      if (btnNext) btnNext.classList.toggle('disabled', i === N-1);
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
        img.addEventListener('click', ()=> openFullscreenGallery(pics, idx));
      });
    }

    updateUI();
  } else if (pics.length === 1) {
    // Одно фото - клик открывает полноэкранную галерею
    const img = root ? root.querySelector('.camp-gal img') : null;
    if (img) {
      img.style.cursor = 'pointer';
      img.addEventListener('click', ()=> openFullscreenGallery(pics, 0));
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
    // закрываем любые старые .modal.show
    try { document.querySelectorAll('.modal.show').forEach(m => m.remove()); } catch(_) {}
    const shell = document.getElementById('modalCard');
    if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); }

    showModal(`
      <div class="accom-card">
        <div class="accom-head">
          <div class="accom-title">Загрузка…</div>
          <div class="accom-sub">Все доступные варианты размещения</div>
        </div>
        <div class="accom-hint" id="accomHint" style="min-height:22px">Для бронирования укажите даты и количество гостей.</div>
        <div class="accom-list" id="accomList">
          <div class="muted">Загружаем информацию о размещении…</div>
        </div>
        <div class="accom-actions">
          <button class="button ghost" id="accomBack">Назад</button>
          <button class="button primary" id="accomBooking">Забронировать</button>
        </div>
      </div>
    `);

    document.getElementById('accomBack').onclick = ()=> { closeModal(); openDetails(cid); };
    document.getElementById('accomBooking').onclick = async ()=> {
      // Проверяем авторизацию только при попытке забронировать
      if (!requireAuth()) return;
      
      const camp = await getCampQuick(cid);
      const ht = normalizeHousingType(camp?.housing_type);
      openBookingFilterModal({
        mode: 'booking',
        campId: cid,
        title: 'Подтвердите данные для бронирования',
        hint: 'Укажите даты и количество гостей. После подтверждения вы сможете выбрать подходящий вариант размещения.',
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
  
  // Если фильтр настроен, требуем авторизацию для бронирования
  if (!requireAuth()) return;
  await openCampAccommodations(cid);
}

async function openCampAccommodations(campId){
  const cid = Number(campId);
  if (!Number.isFinite(cid)) return;
  if (!requireAuth()) return;
  window.__currentCampId = cid;
  // закрываем любые старые .modal.show, чтобы не было «слоёв»
  try { document.querySelectorAll('.modal.show').forEach(m => m.remove()); } catch(_) {}
  const shell = document.getElementById('modalCard');
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.remove('details'); }

  const f = window.__bookingFilter || {};
  if (!f.from || !f.to) { await openCampHousing(cid); return; }
  const total = Number(f.total) || (Number(f.adults)||0) + (Number(f.kids)||0);

  showModal(`
    <div class="accom-card">
      <div class="accom-head">
        <div class="accom-title">Загрузка…</div>
        <div class="accom-sub">${fmtDateShortRu(f.from)} → ${fmtDateShortRu(f.to)} • гостей: ${total || '—'}</div>
      </div>
      <div class="accom-hint" id="accomHint" style="min-height:22px"></div>
      <div class="accom-list" id="accomList">
        <div class="muted">Ищем доступные варианты…</div>
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
      title: 'Подтвердите данные для бронирования',
      hint: 'Укажите даты и количество гостей. После подтверждения вы сможете выбрать подходящий вариант размещения.',
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
          hintEl.textContent = `Для размещения всех ваших гостей необходимо выбрать: ${bestText}${showAlt ? `, или: ${altText}` : ''}.`;
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
  if (shell) { shell.classList.remove('booking-shell'); shell.classList.add('details'); }

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
    if (!requireAuth()) return;
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
  initGeoButton();
    setTabById('tab-map');
    loadCamps().then(()=> restoreMapView());  // <-- после загрузки маркеров сразу fitBounds
  setTimeout(()=> typeof map!=='undefined' && map.invalidateSize(), 80);
  document.getElementById('openBookingFilter').onclick = openBookingFilterModal;
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
