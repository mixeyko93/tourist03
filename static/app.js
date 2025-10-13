// ==== Telegram WebApp — полноэкранный режим ====
const isTG = !!(window.Telegram && window.Telegram.WebApp);
if (isTG) {
  Telegram.WebApp.ready();
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
  ? L.markerClusterGroup()
  : L.featureGroup();               // у featureGroup есть getBounds/getLayers
map.addLayer(cluster);

function fixMapSize(){ setTimeout(()=> map.invalidateSize(true), 50); }
window.addEventListener('load', fixMapSize);
window.addEventListener('resize', fixMapSize);
if (isTG) Telegram.WebApp.onEvent('viewportChanged', fixMapSize);

function emojiHouseIcon(emoji = '🏡') {
  return L.divIcon({
    html: `<div class="emoji-pin" aria-hidden="true">${emoji}</div>`,
    className: 'emoji-marker', iconSize: [36, 44], iconAnchor: [18, 40], popupAnchor: [0, -36]
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
function popupPaddingTop(){ return topbar && topbar.classList.contains('visible') ? 96 : 16; }
map.on('popupopen', (e) => {
  try {
    const px = map.project(e.popup._latlng);
    px.y -= popupPaddingTop();
    map.panTo(map.unproject(px), { animate: true });
  } catch(_) {}
});

// ... тут остаётся вся ваша существующая логика загрузки баз, фильтров, доступности,
// обработчиков геолокации, и т.п. (ничего не менял)

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
function closeModal(){ modal.style.display = 'none'; modalCard.innerHTML = ''; }
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
    const res = await fetch('/api/camps');
    if (!res.ok) throw new Error('Ошибка загрузки баз');

    const items = await res.json(); // массив [{id,name,lat,lng,min_price,emoji}, ...]
    if (typeof cluster !== 'undefined') cluster.clearLayers();

    items.forEach(c => {
      if (c.lat == null || c.lng == null) return;
      const marker = L.marker([c.lat, c.lng], {
        icon: emojiHouseIcon(c.emoji || '🏕️')
      }).bindPopup(`<b>${c.name}</b>${c.min_price ? `<br>от ${c.min_price} ₽` : ''}`);
      if (typeof cluster !== 'undefined') cluster.addLayer(marker); else marker.addTo(map);
    });
  } catch (e) {
    console.error(e);
  }
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

// --- фильтр-бронирование: простая модалка с датами и гостями ---
function openBookingFilterModal() {
  showModal(`
    <div class="auth">
      <div class="title">Бронирование</div>
      <div class="field">
        <label>Заезд</label>
        <input id="bf_from" type="date">
      </div>
      <div class="field">
        <label>Выезд</label>
        <input id="bf_to" type="date">
      </div>
      <div class="field">
        <label>Взрослые</label>
        <input id="bf_adults" type="number" min="1" value="2">
      </div>
      <div class="field">
        <label>Дети</label>
        <input id="bf_kids" type="number" min="0" value="0">
      </div>
      <div class="actions">
        <button class="button ghost"   id="bf_close">Закрыть</button>
        <button class="button ghost"   id="bf_reset">Сбросить</button>
        <button class="button primary" id="bf_apply">Показать</button>
      </div>
    </div>
  `);

  const $ = (id)=>document.getElementById(id);
  $('bf_close').onclick = closeModal;
  $('bf_reset').onclick = () => {
    $('bf_from').value = '';
    $('bf_to').value = '';
    $('bf_adults').value = 2;
    $('bf_kids').value = 0;
    window.__bookingFilter = null;
  };
  $('bf_apply').onclick = () => {
    const from   = $('bf_from').value;
    const to     = $('bf_to').value;
    const adults = $('bf_adults').valueAsNumber || 1;
    const kids   = $('bf_kids').valueAsNumber || 0;
    window.__bookingFilter = { from, to, adults, kids };
    closeModal();
    if (typeof loadCamps === 'function') loadCamps();
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
  const btn = document.getElementById('openBookingFilter');
  if (!btn) return;
  btn.addEventListener('click', openBookingFilterModal);
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
  loadCamps();
  setTimeout(()=> typeof map!=='undefined' && map.invalidateSize(), 80);
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
