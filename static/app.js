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

// === СБОРКА БАЛУНА ДЛЯ БАЗЫ (ЗАМЕНА КОНТЕНТА) ===
function buildCampPopup(camp){
  // фото для бaлуна — главная фото базы
  const img = camp.photo_main ? `<img class="popup-photo" src="${camp.photo_main}" alt="">` : '';
  const priceText = (camp.min_price && Number(camp.min_price) > 0)
      ? `Стоимость от ${camp.min_price}₽ за человека`
      : 'Стоимость уточняйте';

  return `
    <div style="min-width:260px;max-width:320px">
      <div style="font-weight:800;font-size:22px;text-align:center;margin:0 0 8px">${camp.name||''}</div>
      ${img}
      <div style="text-align:center;margin:10px 0 12px;color:#6b7280">${priceText}</div>
      <div style="display:flex;gap:10px;justify-content:center">
        <button class="btn btn-primary" onclick="openDetails(${camp.id})">Подробнее</button>
        <button class="btn btn-success" onclick="openBookingFilterModal()">Забронировать</button>
      </div>
    </div>
  `;
}

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
    const h = cont ? cont.offsetHeight : 260;  // приблизительная высота балуна
    const latlng = e.popup.getLatLng();
    const px = map.project(latlng);
    px.y -= (h / 2);                            // сдвиг на половину высоты балуна
    map.panTo(map.unproject(px), { animate: true, duration: 0.35 });
  } catch(_) {}
});


// ==== AUTH: простая модель на токенах ====
const AUTH_KEY = 'auth_profile';
function getAuth(){ try { return JSON.parse(localStorage.getItem(AUTH_KEY) || ''); } catch { return null; } }
function setAuth(p){ localStorage.setItem(AUTH_KEY, JSON.stringify(p)); }
function clearAuth(){ localStorage.removeItem(AUTH_KEY); }

function renderAccount(){
  const profile = getAuth();
  const guest = document.getElementById('accountGuest');
  const user  = document.getElementById('accountUser');
  const data  = document.getElementById('yourData');
  if (!guest || !user || !data) { return; } // защита: новой разметки может не быть
  guest.style.display = profile ? 'none' : 'block';
  user.style.display  = profile ? 'block' : 'none';
  data.style.display  = 'none';
  if (profile) {
    const name = profile.user?.name?.split(' ')[0] || 'гость';
    const h = document.getElementById('helloLine');
    const hr = new Date().getHours();
    if (h) h.textContent = `${hr<6?'Доброй ночи':hr<12?'Доброе утро':hr<18?'Добрый день':'Добрый вечер'}, ${name}!`;
    const p = document.getElementById('profileName');
    if (p) p.textContent = profile.user?.name || '';
    const ph = document.getElementById('profilePhone');
    if (ph) ph.textContent = profile.user?.phone || '';
  }
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
    card.innerHTML = '';
    card.classList.remove('booking-shell');  // снимаем «узкую» оболочку
  }
}

modal.addEventListener('click', (e)=>{ if (e.target === modal) closeModal(); });

function openRegister(){
  showModal(`
    <div class="auth">
      <div class="title">Регистрация</div>
      <div id="authStep">
        <div class="field">
          <label>Имя и фамилия</label>
          <input id="reg_name" type="text" placeholder="Например: Иван Петров">
        </div>
        <div class="field">
          <label>Номер телефона</label>
          <input id="reg_phone" type="tel" inputmode="tel" placeholder="+7 9XX XXX-XX-XX">
        </div>
        <div class="actions">
          <div class="button ghost" id="reg_cancel">Отмена</div>
          <div class="button primary" id="reg_submit">Зарегистрироваться</div>
        </div>
      </div>
    </div>
  `);

  document.getElementById('reg_cancel').onclick = closeModal;
  document.getElementById('reg_submit').onclick = async () => {
    const name  = document.getElementById('reg_name').value.trim();
    const phone = document.getElementById('reg_phone').value.trim();
    if (!name || !phone) { alert('Заполните имя и телефон'); return; }

    const res = await fetch('/api/auth/register/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name, phone })
    });
    if (!res.ok) { alert('Ошибка: не удалось отправить код'); return; }
    try { localStorage.setItem('last_cred', JSON.stringify({ name, phone })); } catch(_) {}
    showVerifyPhone(phone, 'register');
  };
}

function showVerifyPhone(phone, mode){
  showModal(`
    <div class="form">
      <h3>Подтверждение номера</h3>
      <p class="muted">Мы отправили код на номер, введите его ниже.</p>
      <label>Код из SMS<input id="v_code" placeholder="0000" /></label>
      <div class="actions-row">
        <button class="secondary" id="v_cancel">Отмена</button>
        <button class="primary" id="v_ok">Подтвердить</button>
      </div>
    </div>
  `);

  document.getElementById('v_cancel').onclick = closeModal;
  document.getElementById('v_ok').onclick = async () => {
    const code = document.getElementById('v_code').value.trim();
    const vres = await fetch('/api/auth/register/verify', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ phone, code })
    });
    if (!vres.ok) { alert('Неверный код'); return; }
    const data = await vres.json();
    setAuth({ token: data.token, user: data.user });
    closeModal(); renderAccount();
  };
}

// Вход
function openLogin(){
  showModal(`
    <div class="form">
      <h3>Вход</h3>
      <label>Телефон<input id="l_phone" placeholder="+7 9XX XXX-XX-XX" /></label>
      <div class="actions-row">
        <button class="secondary" id="l_cancel">Отмена</button>
        <button class="primary" id="l_start">Получить код</button>
      </div>
    </div>
  `);

  document.getElementById('l_cancel').onclick = closeModal;
  document.getElementById('l_start').onclick = async () => {
    const phone = document.getElementById('l_phone').value.trim();
    if (!phone) { alert('Введите телефон'); return; }
    const res = await fetch('/api/auth/login/start', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ phone }) });
    if (!res.ok) { alert('Ошибка: не удалось отправить код'); return; }
    showModal(`
      <div class="form">
        <h3>Код из SMS</h3>
        <label>Код<input id="lc_code" placeholder="0000" /></label>
        <div class="actions-row">
          <button class="secondary" id="lc_cancel">Отмена</button>
          <button class="primary" id="lc_ok">Войти</button>
        </div>
      </div>
    `);
    document.getElementById('lc_cancel').onclick = closeModal;
    document.getElementById('lc_ok').onclick = async () => {
      const code = document.getElementById('lc_code').value.trim();
      const vres = await fetch('/api/auth/login/verify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ phone, code }) });
      if (!vres.ok) { alert('Неверный код'); return; }
      const data = await vres.json();
      setAuth({ token: data.token, user: data.user });
      closeModal(); renderAccount();
    };
  };
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
    const itemsActive = camps.filter(c => (c.status || 'active') === 'active');

    // 2) Комнаты (одним запросом)
    let roomsByCamp = {};
    const roomsResp = await fetch('/api/rooms');
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
        if (fFrom && fTo) {
          const booked = countBookedUnits(r, fFrom, fTo);
          freeUnits = Math.max(0, units - booked);
        }
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

// === Детали базы (модалка «Подробнее») — жёстко без «мигания» карты ===
async function openDetails(campId){
  // 1) показываем эмодзи-лоадер
  showMiniLoader();

  try {
    // 2) тянем данные параллельно
    const [camp, photos] = await Promise.all([
      fetch(`/api/camps/${campId}`).then(r => r.json()),
      fetch(`/api/camps/${campId}/photos`).then(r => r.json()).catch(()=>[])
    ]);

    const picUrls = (photos && photos.length)
      ? photos.map(p => p.url)
      : (camp.photo_main ? [camp.photo_main] : []);

    const descHtml = (camp.description || 'Описание пока отсутствует').replace(/\n/g,'<br>');

    const paramsHtml = [
      ['Озеро',                    camp.lake_name || '—'],
      ['Апартаментов',             camp.rooms_count ?? '—'],
      ['BBQ общая',               `${camp.bbq_shared_count ?? 0} шт.`],
      ['BBQ индивидуальная',      `${camp.bbq_count ?? 0} шт.`],
      ['Баня',                    `${camp.bath_count ?? 0} шт.`],
      ['Сауна',                   `${camp.sauna_count ?? 0} шт.`],
      ['Бассейн общий',           `${camp.pools_shared_count ?? 0} шт.`],
      ['Бассейн индивидуальный',  `${camp.pools_private_count ?? 0} шт.`],
    ].map(([k,v]) => `
      <div class="param-card"><span>${k}</span><b style="color:#fff">${v}</b></div>
    `).join('');

    // 3) НЕ удаляем лоадер — перехватываем его DOM и превращаем в модалку
    let modal = takeoverMiniLoaderAsModal();
    if (!modal) {
      // на случай, если лоадер уже закрыт — создадим обычную модалку
      modal = document.createElement('div');
      modal.className = 'modal show';
      modal.style.opacity = '0';
      modal.style.transition = 'opacity .12s ease-out';
      document.body.appendChild(modal);
    }

    // наполняем контентом «Подробнее» поверх той же подложки (карта не видна ни на кадр)
    modal.innerHTML = `
      <div class="modal-card auth">
        <div class="title" style="text-align:center">${camp.name || 'База'}</div>
        <div style="margin-top:6px;color:#d1d5db;text-align:center;line-height:1.35">${descHtml}</div>

        <div class="camp-gal" style="margin-top:10px">
          <div class="viewport">${picUrls.map(u=>`<img src="${u}">`).join('')}</div>
          ${picUrls.length>1 ? '<div class="nav prev">‹</div><div class="nav next">›</div>' : ''}
        </div>

        <div style="margin-top:10px">${paramsHtml}</div>

        <div class="actions" style="margin-top:14px;display:flex;gap:10px;justify-content:center;">
          <button class="button ghost" onclick="document.body.removeChild(this.closest('.modal'))">Назад</button>
          <button class="button" style="background:#22c55e;border-color:#22c55e;color:#fff" onclick="openBookingFilterModal()">Забронировать</button>
        </div>
      </div>
    `;

    // 4) инициализация слайдера
    const vp = modal.querySelector('.camp-gal .viewport');
    if (vp) {
      const imgs = vp.querySelectorAll('img');
      let i = 0;
      function go(k){ i=(k+imgs.length)%imgs.length; vp.style.transform = `translateX(${-i*100}%)`; }
      if (imgs.length > 1) {
        const prev = modal.querySelector('.camp-gal .prev');
        const next = modal.querySelector('.camp-gal .next');
        if (prev) prev.onclick = ()=> go(i-1);
        if (next) next.onclick = ()=> go(i+1);
      }
      vp.style.width = `${imgs.length * 100}%`;
      imgs.forEach(img => img.style.width = `${100 / imgs.length}%`);
      go(0);
    }

    // 5) мягко проявляем модалку (она уже перекрывает карту)
    requestAnimationFrame(()=> { modal.style.opacity = '1'; });

  } catch (e) {
    // на ошибке аккуратно закрываем лоадер
    hideMiniLoader();
    console.error(e);
    showModal(`
      <div class="card">
        <p class="muted">Не удалось загрузить карточку базы.</p>
        <div class="actions"><button class="button primary" onclick="closeModal()">OK</button></div>
      </div>`);
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
  openBookingFilterModal();
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


// === Booking Filter (2×2): кликабельные даты, запоминание значений, применение на карту ===
function openBookingFilterModal() {
  const prev = document.querySelector('.modal.show');
  if (prev) prev.remove();

  showModal(`
    <div class="booking-card">
      <div class="booking-title">Выберите даты и гостей</div>

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

      <div class="booking-actions">
        <button class="button ghost" id="bkClose">Закрыть</button>
        <button class="button ghost" id="bkReset">Сбросить</button>
        <button class="button primary" id="bkApply">Сохранить</button>
      </div>
    </div>
  `);

  // сужаем внешнюю «прозрачную» оболочку только для окна фильтра
  const shell = document.getElementById('modalCard');
  if (shell) shell.classList.add('booking-shell');

  // ссылки
  const card  = document.querySelector('.booking-card');
  const fromI = card.querySelector('#bkFrom');
  const toI   = card.querySelector('#bkTo');
  const fromB = card.querySelector('#bkShowFrom');
  const toB   = card.querySelector('#bkShowTo');
  const adSel = card.querySelector('#bkAdults');
  const kdSel = card.querySelector('#bkKids');

  // заполнение из предыдущего фильтра (если уже выбирали)
  const F = window.__bookingFilter || {};
  if (F.from) fromI.value = F.from;
  if (F.to)   toI.value   = F.to;
  adSel.value = String(F.adults ?? 2);
  kdSel.value = String(F.kids   ?? 0);

  // читаемо показываем выбранные даты
  const fmt  = v => v ? new Date(v).toLocaleDateString('ru-RU') : '—';
  const sync = () => { fromB.textContent = fmt(fromI.value); toB.textContent = fmt(toI.value); };
  fromI.addEventListener('change', sync);
  toI.addEventListener('change',   sync);
  sync();

  // клики по видимым «кнопкам» — открывают системный пикер (на всех платформах)
  const openPicker = (inp) => {
    if (typeof inp.showPicker === 'function') { inp.showPicker(); return; }
    inp.focus(); inp.click(); // fallback для старых десктопов
  };
  fromB.addEventListener('click', () => openPicker(fromI));
  toB.addEventListener('click',   () => openPicker(toI));

  // кнопки
  card.querySelector('#bkClose').onclick = closeModal;
  card.querySelector('#bkReset').onclick = ()=>{
    fromI.value=''; toI.value=''; adSel.value='2'; kdSel.value='0'; sync();
    // сброс — очищаем общий фильтр и перерисовываем всю карту
    window.__bookingFilter = null;
  };
  card.querySelector('#bkApply').onclick = async ()=>{
    window.__bookingFilter = {
      from:   fromI.value || '',
      to:     toI.value   || '',
      adults: Number(adSel.value),
      kids:   Number(kdSel.value),
      total:  Number(adSel.value) + Number(kdSel.value)
    };
    closeModal();
    try { await loadCamps(); if (typeof restoreMapView==='function') restoreMapView(); } catch(_) {}
  };
}




// --- геоцентрирование карты ---
function initGeoButton() {
  const btn = document.getElementById('geoBtn');
  if (!btn) return;
  btn.addEventListener('click', () => {
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
    if (btn) btn.addEventListener('click', openBookingFilterModal);
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
})();
