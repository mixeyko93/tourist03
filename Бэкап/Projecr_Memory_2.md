# Турист03 — Project Memory (чат-конспект)

Этот файл — сжатая «память проекта» по итогам текущего чата. Его цель — дать быстрый контекст,
зафиксировать принятые решения, конечные файлы и API, чтобы продолжить работу без потерь
в будущих сессиях.

---

## 1) Итоговое состояние ( UX / UI )

- **Главный экран**: карта Leaflet (всегда *светлые* OSM-тайлы), эмодзи-маркеры баз «🏡».
- **Фильтр дат/гостей**: выезжающая верхняя карточка, кнопка FAB «📅» (слева).
- **Геолокация**: FAB «📍» (справа) — ставит маркер пользователя и круг точности.
- **Нижний таббар** (крупные эмодзи + подпись): «Карта / Брони / Услуги / Помощь».
- **Тёмная/Светлая тема**: переключатель в экране «Помощь». Плавная анимация переключения.
  Карта остаётся светлой независимо от темы.
- **Панель доступности**: слайд-секция снизу с вариантами номеров и ценой.

### Важные UX-решения
- FAB-кнопки видны **только** во вкладке «Карта».
- Заголовок фильтра центрирован.
- Кнопки оформления приведены к единому стилю с таббаром.
- Админ-ссылки в пользовательских страницах убраны.

---

## 2) Маршруты фронтенда
- `/` и `/index.html` → главный SPA (из `/web/index.html`).
- **Статика** отдаётся с префикса `/static` (CSS/JS/HTML-админки).
- Админки:
  - `/admin-bot` (`/admin-bot.html`) — админ броней.
  - `/admin-camps` (`/admin-camps.html`) — супер-админ: базы/номера.

> Важно: после изменения схемы статики пути в `index.html` к CSS/JS используют `/static/...`.

---

## 3) Телеграм-бот (вебхук)
Бот — «лоунчер» мини-приложения. Никаких сообщений пользователю писать нельзя — только кнопка входа.

### Поведение
- На `/start` бот **убирает** возможную старую reply-клавиатуру и присылает приветствие
  с **единственной inline-кнопкой** `Турист_03 ⛺️` (web_app → URL мини-приложения).
- Любой текст: повторно присылает то же приветствие с inline-кнопкой.
- Данные из мини-приложения (`web_app_data`) принимаются и прокидываются в REST `/api/bookings`.

### Кнопки
- ТОЛЬКО **InlineKeyboard**: `[{ text: "Турист_03 ⛺️", web_app: { url: WEBAPP_URL } }]`
- Полностью убраны любые Reply-клавиатуры (включая «Открыть карту» и пр.).

---

## 4) REST API (in-memory заглушки)
(Для миграции в БД — заменить хранилища CAMPS/ROOMS/BOOKINGS.)

### Camps
- `GET  /api/camps` → список баз
- `POST /api/camps` → создать базу
- `PUT  /api/camps/{{id}}` → изменить базу
- `DELETE /api/camps/{{id}}` → удалить базу (каскадно удаляются номера)

### Rooms
- `GET  /api/rooms?camp_id={{id}}` → список номеров (фильтр по базе)
- `POST /api/rooms` → создать номер
- `PUT  /api/rooms/{{id}}` → изменить номер
- `DELETE /api/rooms/{{id}}` → удалить номер

### Availability
- `GET /api/availability?camp_id&date_from&date_to&guests&adults&children`
  → список доступных предложений (заглушка).

### Bookings
- `GET    /api/bookings` → последние заявки
- `POST   /api/bookings` → создать заявку
- `POST   /api/bookings/{{id}}/status?status=(pending|confirmed|cancelled)` → сменить статус
- `DELETE /api/bookings/{{id}}` → удалить заявку

---

## 5) Конфиг и деплой

### .env (пример)
```
BOT_TOKEN=***
WEBAPP_URL=https://<ваш-домен-или-туннель>/
```

### Вебхук
`POST /tg/webhook/${BOT_TOKEN}` — тот самый адрес, который настраивается в BotFather
(или через `setWebhook`).

---

## 6) Финальные файлы (снимки из чата)

Ниже зафиксированы «рабочие» версии **app.py** и **index.html**,
которые мы собрали и тестировали.

### A) app.py
Полный файл сохранён как `app_final.py`.

### B) index.html (web/index.html)
```html
<!doctype html>
<html lang="ru" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Tourist03</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
  <link rel="stylesheet" href="/static/styles.css?v=12" />
</head>
<body>
  <div id="topbar">
    <div class="topbar-title span2">Заполните данные для поиска баз по параметрам</div>
    <label>Заезд <input type="date" id="dateFrom"></label>
    <label>Выезд <input type="date" id="dateTo"></label>
    <div class="row span2">
      <div class="stepper"><div class="cap">Взрослые</div><div class="ctrl" data-target="adults">
        <button class="minus">−</button><span class="val" id="adultsVal">1</span><button class="plus">+</button>
      </div></div>
      <div class="stepper"><div class="cap">Дети</div><div class="ctrl" data-target="children">
        <button class="minus">−</button><span class="val" id="childrenVal">0</span><button class="plus">+</button>
      </div></div>
    </div>
    <div class="row span2 actions-row">
      <button id="reset" class="secondary">Сбросить</button>
      <button id="apply" class="primary">Показать</button>
    </div>
  </div>

  <div id="map" class="screen active"></div>

  <button class="fab fab-soft" id="toggleFilters" aria-label="Фильтр по датам" title="Фильтр по датам">📅</button>
  <button class="fab fab-soft" id="geoBtn" aria-label="Моё местоположение" title="Моё местоположение">📍</button>

  <div id="panel">
    <h4>Доступные номера</h4>
    <div id="panelList"></div>
    <div class="actions"><button class="secondary" onclick="hidePanel()">Закрыть</button></div>
  </div>

  <section id="bookingsScreen" class="screen">
    <div class="wrap">
      <h2>Ваши брони</h2>
      <div class="card">
        <p class="muted" id="myBookingsHint">Позже здесь будут ваши заявки.</p>
        <div id="myBookingsList"></div>
      </div>
    </div>
  </section>

  <section id="servicesScreen" class="screen">
    <div class="wrap">
      <h2>Дополнительные услуги</h2>
      <div class="card"><p class="muted">Пример: аренда лодки, баня, питание.</p></div>
    </div>
  </section>

  <section id="helpScreen" class="screen">
    <div class="wrap">
      <h2>Помощь</h2>
      <div class="card card-xl">
        <div class="settings-row">
          <div class="settings-title">Тема интерфейса</div>
          <label class="switch">
            <input type="checkbox" id="themeToggle" />
            <span class="slider"></span>
          </label>
        </div>
      </div>
    </div>
  </section>

  <nav class="tabbar">
    <div class="tab active" data-tab="map">
      <div class="icon">🗺️</div>
      <div class="label">Карта</div>
    </div>
    <div class="tab" data-tab="bookings">
      <div class="icon">📑</div>
      <div class="label">Брони</div>
    </div>
    <div class="tab" data-tab="services">
      <div class="icon">🛎️</div>
      <div class="label">Услуги</div>
    </div>
    <div class="tab" data-tab="help">
      <div class="icon">❓</div>
      <div class="label">Помощь</div>
    </div>
  </nav>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  <script src="/static/app.js?v=12"></script>
</body>
</html>
```

---

## 7) Что ещё можно сделать быстро
- Добавить автоопределение темы по `prefers-color-scheme` (и синхронизацию с переключателем).
- Перевести in-memory данные на SQLite/PostgreSQL + Alembic.
- Ролевая авторизация в админках, JWT для `/api/*`.

