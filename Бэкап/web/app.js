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

// --- Запрет масштабирования pinch/ctrl+wheel (п.3)
window.addEventListener('wheel', (e) => {
  if (e.ctrlKey) { e.preventDefault(); }
}, { passive: false });
window.addEventListener('gesturestart', (e) => { e.preventDefault(); }, { passive: false });
window.addEventListener('gesturechange', (e) => { e.preventDefault(); }, { passive: false });
window.addEventListener('gestureend', (e) => { e.preventDefault(); }, { passive: false });

function updateBotbar() {
  const vh = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp.viewportHeight : window.innerHeight;
  const ih = window.innerHeight;
  const extra = Math.max(0, Math.round(ih - vh));
  document.documentElement.style.setProperty('--botbar', extra + 'px');
  fixMapSize();
}
updateBotbar();
window.addEventListener('resize', updateBotbar);
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
  document.querySelectorAll('.screen').forEach(el=>el.classList.remove('active'));
  (screens[name]||[]).forEach(el=>el && el.classList.add('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.tab===name));

  const showMapOnly = (name === 'map');
  document.getElementById('toggleFilters').style.display = showMapOnly ? 'flex' : 'none';
  document.getElementById('geoBtn').style.display = showMapOnly ? 'flex' : 'none';

  hideFilters();
  if (name === 'map') { fixMapSize(); restoreMapView(); }
  if (name === 'account') renderAccount();
}
const screens = {
  map: [document.getElementById('map')],
  account: [document.getElementById('accountScreen')],
  services: [document.getElementById('servicesScreen')],
  help: [document.getElementById('helpScreen')],
};

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => setTab(t.dataset.tab)));

// ==== Карта ====
const map = L.map('map', { zoomControl: true }).setView([56.0, 43.5], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);
const cluster = L.markerClusterGroup(); map.addLayer(cluster);
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
function popupPaddingTop(){ return topbar.classList.contains('visible') ? 96 : 16; }
map.on('popupopen', (e) => {
  hideFilters(); e.popup.options.autoPan = true;
  e.popup.options.autoPanPaddingTopLeft = L.point(0, popupPaddingTop());
  e.popup.options.autoPanPadding = L.point(20, 20); e.popup.update();
});

const state = { adults: 1, children: 0 };
const adultsEl = document.getElementById('adultsVal');
const childrenEl = document.getElementById('childrenVal');
function renderSteppers(){ adultsEl.textContent = state.adults; childrenEl.textContent = state.children; }
renderSteppers();
document.querySelectorAll('.stepper .ctrl').forEach(ctrl=>{
  const target = ctrl.dataset.target;
  ctrl.querySelector('.minus').addEventListener('click', ()=>{ state[target] = Math.max( target==='adults' ? 1 : 0, state[target]-1 ); renderSteppers(); });
  ctrl.querySelector('.plus').addEventListener('click', ()=>{ state[target] = Math.min( 10, state[target]+1 ); renderSteppers(); });
});

function getFilters(){
  const dateFrom = document.getElementById('dateFrom').value;
  const dateTo   = document.getElementById('dateTo').value;
  const adults   = state.adults;
  const children = state.children;
  const guests   = adults + children;
  return { dateFrom, dateTo, adults, children, guests };
}
function requireDates(){
  const { dateFrom, dateTo } = getFilters();
  if (!dateFrom || !dateTo) { alert('Выберите даты заезда и выезда.'); return false; }
  if (new Date(dateTo) <= new Date(dateFrom)) { alert('Дата выезда должна быть позже даты заезда.'); return false; }
  return true;
}
function resetFilters(){
  document.getElementById('dateFrom').value = '';
  document.getElementById('dateTo').value = '';
  state.adults = 1; state.children = 0; renderSteppers();
}

async function loadCamps() {
  const res = await fetch('/api/camps');
  const list = await res.json();
  cluster.clearLayers();
  list.forEach(c => {
    const m = L.marker([c.lat, c.lng], { icon: emojiHouseIcon('🏡') });
    const img = (c.photos && c.photos[0]) ? c.photos[0] : 'https://via.placeholder.com/800x500?text=%D0%A4%D0%BE%D1%82%D0%BE';
    const price = (c.min_price != null) ? `${c.min_price} ₽/сутки` : 'Цена по запросу';
    const lake = c.lake_name ? `${c.lake_name}` : '';
    const siteBtn = c.site_url ? `<a class="btn link" href="${c.site_url}" target="_blank" rel="noopener">Подробнее</a>` : '';
    const popup = `
      <div class="popup">
        <img src="${img}" alt="Фото">
        <div class="popup-title">${c.name}</div>
        ${lake ? `<div class="popup-sub">${lake}</div>` : ''}
        <div class="popup-meta"><strong>${price}</strong><span class="muted">${c.phone ?? ''}</span></div>
        <div class="popup-actions">
          ${siteBtn}
          <button class="btn" onclick='showAvailability(${c.id})'>Забронировать</button>
        </div>
      </div>`;
    m.bindPopup(popup, { maxWidth: 300 });
    cluster.addLayer(m);
  });
  if (list.length) {
    const bounds = L.latLngBounds(list.map(c => [c.lat, c.lng]));
    map.fitBounds(bounds.pad(0.2)); fixMapSize();
  }
}

async function showAvailability(campId) {
  if (!requireDates()) return;
  const { dateFrom, dateTo, adults, children, guests } = getFilters();
  const params = new URLSearchParams({
    camp_id: String(campId), date_from: dateFrom, date_to: dateTo,
    guests: String(guests), adults: String(adults), children: String(children)
  });
  const res = await fetch(`/api/availability?${params.toString()}`);
  if (!res.ok) { alert('Ошибка запроса доступности'); return; }
  const items = await res.json();
  const list = document.getElementById('panelList');
  list.innerHTML = '';
  if (!items.length) {
    list.innerHTML = '<div class="item"><div>Нет доступных номеров на выбранные даты.</div></div>';
  } else {
    items.forEach(x => {
      const div = document.createElement('div');
      div.className = 'item';
      div.innerHTML = `
        <div>
          <div class="name">${x.room_name}</div>
          <div class="meta">Вместимость: ${x.capacity} · Ночей: ${x.nights}</div>
        </div>
        <div style="text-align:right">
          <div class="price">${x.total_price} ₽</div>
          <button class="btn" onclick="bookRoom(${x.room_id})">Забронировать</button>
        </div>`;
      list.appendChild(div);
    });
  }
  showPanel();
}

async function bookRoom(roomId) {
  if (!requireDates()) return;
  const { dateFrom, dateTo, adults, children, guests } = getFilters();
  const profile = getAuth();

  // Если не авторизован — отправим в ЛК
  if (!profile) {
    setTab('account');
    alert('Для оформления брони сначала авторизуйтесь.');
    return;
  }
  let name = profile.user?.name || prompt('Ваше имя:'); if (!name) return;
  let phone = profile.user?.phone || prompt('Телефон:');  if (!phone) return;

  const payload = { room_id: roomId, date_from: dateFrom, date_to: dateTo,
                    guests, adults, children, customer_name:name, phone };

  if (isTG) {
    Telegram.WebApp.MainButton.setText('Отправить заявку');
    Telegram.WebApp.MainButton.onClick(() => {
      Telegram.WebApp.sendData(JSON.stringify(payload));
      Telegram.WebApp.MainButton.hide();
      alert('Заявка отправлена боту, проверьте чат.');
    });
    Telegram.WebApp.MainButton.show();
  } else {
    const res = await fetch('/api/bookings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if (res.ok) { const data = await res.json(); alert('Заявка создана! №'+data.id); hidePanel(); }
    else { alert('Не удалось создать бронь: ' + await res.text()); }
  }
}

// ==== Фильтр панель ====
const toggleBtn = document.getElementById('toggleFilters');
function showFilters(){ topbar.classList.add('visible'); fixMapSize(); }
function hideFilters(){ topbar.classList.remove('visible'); fixMapSize(); }
function toggleFilters(){ topbar.classList.toggle('visible'); fixMapSize(); }
toggleBtn.addEventListener('click', toggleFilters);
map.on('click', hideFilters);

// ==== Геолокация ====
let myMarker = null, myCircle = null;
function locateMe(){
  if (!navigator.geolocation) { alert('Геолокация не поддерживается в этом браузере.'); return; }
  navigator.geolocation.getCurrentPosition(
    (pos)=>{
      const { latitude, longitude, accuracy } = pos.coords;
      const latlng = [latitude, longitude];
      if (!myMarker) {
        myMarker = L.marker(latlng, {
          icon: L.divIcon({ html: `<div class=\"emoji-pin\" aria-hidden=\"true\">📍</div>`, className: 'emoji-marker', iconSize: [36,44], iconAnchor: [18,40] })
        }).addTo(map);
      } else { myMarker.setLatLng(latlng); }
      if (!myCircle) {
        myCircle = L.circle(latlng, { radius: accuracy, color: '#0a84ff', fillColor: '#0a84ff', fillOpacity: .1, weight: 1 }).addTo(map);
      } else { myCircle.setLatLng(latlng); myCircle.setRadius(accuracy); }
      map.setView(latlng, 13);
    },
    (err)=> alert(err && err.message ? err.message : 'Не удалось определить местоположение'),
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
  );
}
document.getElementById('geoBtn').addEventListener('click', locateMe);

document.getElementById('apply').addEventListener('click', async () => { await loadCamps(); hideFilters(); });
document.getElementById('reset').addEventListener('click', async () => { resetFilters(); await loadCamps(); hideFilters(); });

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
  guest.style.display = profile ? 'none' : 'block';
  user.style.display  = profile ? 'block' : 'none';
  data.style.display  = 'none';
  if (profile) {
    const name = profile.user?.name?.split(' ')[0] || 'гость';
    const h = document.getElementById('helloLine');
    const hr = new Date().getHours();
    let greet = 'Добрый день';
    if (hr >= 5 && hr < 12) greet = 'Доброе утро';
    else if (hr >= 12 && hr < 18) greet = 'Добрый день';
    else if (hr >= 18 && hr < 23) greet = 'Добрый вечер';
    else greet = 'Доброй ночи';
    h.textContent = `${greet}, ${name}`;
  }
}

// ===== Модалки: конструкторы форм =====
const modal = document.getElementById('modal');
const modalCard = document.getElementById('modalCard');

function showModal(html, cardClass = '') {
  modalCard.className = 'modal-card' + (cardClass ? (' ' + cardClass) : '');
  modalCard.innerHTML = html;
  modal.style.display = 'grid';
}
function closeModal() {
  modal.style.display = 'none';
  modalCard.className = 'modal-card';
  modalCard.innerHTML = '';
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
  `, 'auth');  // <<< добавлен класс карточке

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

    // Плавно меняем содержимое, размер карточки не прыгает
    const step = document.getElementById('authStep');
    step.innerHTML = `
      <div class="field">
        <label>Введите код из SMS</label>
        <input id="v_code" type="text" inputmode="numeric" placeholder="0000" maxlength="6" autofocus>
      </div>
      <div class="actions">
        <div class="button ghost" id="v_cancel">Отмена</div>
        <div class="button primary" id="v_ok">Подтвердить</div>
      </div>
    `;

    // WebOTP (если поддерживается)
    (async ()=>{
      try{
        if ('OTPCredential' in window && window.isSecureContext) {
          const cred = await navigator.credentials.get({ otp:{ transport:['sms'] } });
          if (cred && cred.code) document.getElementById('v_code').value = cred.code.trim();
        }
      }catch(e){}
    })();

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
        <button class="primary" id="v_submit">Подтвердить</button>
      </div>
    </div>`);
      // Попытка авто-считывания кода из SMS (WebOTP API, работает только по HTTPS и не во всех браузерах)
  (async ()=>{
    try{
      if ('OTPCredential' in window && window.isSecureContext) {
        const ac = new AbortController();
        // Закроем запрос, если модалка закрыта вручную
        const stop = ()=>{ try{ ac.abort(); }catch{} };
        modal.addEventListener('click', (e)=>{ if(e.target===modal) stop(); }, { once:true });

        const cred = await navigator.credentials.get({
          otp: { transport: ['sms'] },
          signal: ac.signal
        });
        if (cred && cred.code) {
          const input = document.getElementById('v_code');
          input.value = cred.code.trim();
        }
      }
    }catch(e){ /* тихо игнорируем, просто нет поддержки */ }
  })();

  document.getElementById('v_cancel').onclick = closeModal;
  document.getElementById('v_submit').onclick = async ()=>{
    const code = document.getElementById('v_code').value.trim();
    const res = await fetch(`/api/auth/${mode}/verify`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ phone, code }) });
    if (!res.ok) { alert('Код неверный'); return; }
    const data = await res.json();
    setAuth({ token: data.token, user: data.user });
    closeModal(); renderAccount();
  };
}

// Вход
function openLogin(){
  showModal(`
    <div class="form">
      <h3>Вход</h3>
      <label>Номер телефона<input id="l_phone" placeholder="+7 900 000-00-00" /></label>
      <div class="actions-row">
        <button class="secondary" id="l_cancel">Отмена</button>
        <button class="primary" id="l_submit">Получить код</button>
      </div>
    </div>`);
  document.getElementById('l_cancel').onclick = closeModal;
  document.getElementById('l_submit').onclick = async ()=>{
    const phone = document.getElementById('l_phone').value.trim();
    if (!phone) { alert('Введите телефон'); return; }
    const res = await fetch('/api/auth/login/start', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ phone }) });
    if (!res.ok) { alert(await res.text()); return; }
    const data = await res.json();
    showVerifyPhone(phone, 'login');
    console.log('DEBUG SMS code:', data.debug_code);
  };
}

// Ваши данные
async function openYourData(){
  const profile = getAuth(); if (!profile) return;
  document.getElementById('yourData').style.display = 'block';
  document.getElementById('yd_name').value  = profile.user?.name || '';
  document.getElementById('yd_phone').value = profile.user?.phone || '';
  document.getElementById('yd_email').value = profile.user?.email || '';
}

async function saveEmail(){
  const profile = getAuth(); if (!profile) return;
  const email = document.getElementById('yd_email').value.trim();
  if (!email) { alert('Введите E‑mail'); return; }
  const res = await fetch('/api/auth/email/start', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ token: profile.token, email }) });
  if (!res.ok) { alert(await res.text()); return; }
  const data = await res.json();
  showModal(`
    <div class="form">
      <h3>Подтверждение E‑mail</h3>
      <p class="muted">Мы отправили код на почту. Введите его ниже.</p>
      <label>Код<input id="e_code" placeholder="0000"/></label>
      <div class="actions-row">
        <button class="secondary" id="e_cancel">Отмена</button>
        <button class="primary" id="e_submit">Подтвердить</button>
      </div>
    </div>`);
  document.getElementById('e_cancel').onclick = closeModal;
  document.getElementById('e_submit').onclick = async ()=>{
    const code = document.getElementById('e_code').value.trim();
    const res2 = await fetch('/api/auth/email/verify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ token: profile.token, code }) });
    if (!res2.ok) { alert('Код неверный'); return; }
    const d2 = await res2.json();
    setAuth({ token: profile.token, user: d2.user });
    closeModal(); alert('E‑mail подтверждён и сохранён');
  };
}

// Привязка кнопок ЛК
const btnLogin = document.getElementById('btnLogin');
const btnRegister = document.getElementById('btnRegister');
const btnYourData = document.getElementById('btnYourData');
const btnBack = document.getElementById('btnBack');
const btnSaveEmail = document.getElementById('btnSaveEmail');

if (btnLogin) btnLogin.addEventListener('click', openLogin);
if (btnRegister) btnRegister.addEventListener('click', openRegister);
if (btnYourData) btnYourData.addEventListener('click', openYourData);
if (btnBack) btnBack.addEventListener('click', ()=>{ document.getElementById('yourData').style.display = 'none'; });
if (btnSaveEmail) btnSaveEmail.addEventListener('click', saveEmail);

// ==== Старт ====
loadCamps();
setTab('map');
renderAccount();
setTimeout(()=> map.invalidateSize(), 50);


// Гарантированная фиксация размеров таб-иконок (п.4)
(function fixTabbarLayout(){
  document.querySelectorAll('.tabbar .tab').forEach(it => {
    it.style.minWidth = '0';
    it.style.flex = '1 1 0';
  });
})();
