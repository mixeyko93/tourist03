# Туристика: план публичного запуска

## Статус документа

- Проект: `tourist03` / «Туристика».
- Зафиксированный baseline: commit `331e67b3d5de259aa57944e633802da9062b5d12`.
- Первый приоритет: обычный мобильный браузер, затем desktop, позднее Telegram Mini App.
- Публичный продукт первого запуска: информационный каталог туристических объектов и услуг без публичного бронирования.
- Существующие бронирования, CRM, учётные записи, bot API и Telegram WebApp сохраняются в кодовой базе.

## Текущее состояние

### Backend

FastAPI-приложение уже разделено на routers, services, repositories, DTO и domain-слои. При этом крупные модули CRM всё ещё монолитны, а текущий `app.py` выполняет миграции при импорте, использует открытый CORS и допускает случайный session secret.

Существующие API охватывают:

- каталог баз и апартаментов;
- туристическую регистрацию и bearer-аутентификацию;
- бронирования и группы бронирований;
- CRM управляющих;
- superadmin;
- загрузку файлов;
- Telegram-привязку и уведомления.

### Frontend

Публичный `/` работает на Jinja/HTML и крупных `static/app.js`, `static/styles.css`. Интерфейс ориентирован на бронирование и Telegram WebApp. React + TypeScript + Vite обслуживает CRM, superadmin и отдельный legacy map route.

Leaflet, marker clustering, геолокация по кнопке, галереи и фирменные маркеры уже существуют. Нет публичного поиска по России, универсальных услуг, slug-страниц, полноценного SEO и устойчивого browser-first режима.

### PostgreSQL

Используются схемы `auth`, `catalog`, `crm` и собственный migration runner. Текущая обязательная версия — `0013_admin_profile_pins`.

Основные существующие сущности:

- `catalog.camps`, `catalog.rooms`;
- legacy и новые media-таблицы;
- `auth.users`, tourist tokens, CRM и superadmin accounts;
- `crm.bookings`, services, shifts, change requests, notifications и audit log.

Таблицы бронирования и `catalog.camps` нельзя удалять, очищать или несовместимо переименовывать.

### Operations

В репозитории одновременно описаны systemd-based `deploy.sh` и Docker Compose. Production deploy выполняется через `deploy.sh`, но текущий сценарий не содержит обязательного backup/readiness gate и автоматизированного безопасного rollback.

## Риски

### Критические

1. Публичный `/api/camps` возвращает внутренние `owner`, `manager`, `admin_phones` и полагается на frontend-фильтрацию статуса.
2. В git tracked DB dumps содержат строки из auth, catalog и booking-таблиц. Их нельзя удалять до ротации и отдельного согласования очистки истории.
3. Миграции выполняются при импорте приложения.
4. При отсутствии `SESSION_SECRET_KEY` возможен новый случайный ключ на каждом рестарте.
5. Production CORS открыт на wildcard.
6. Туристическая auth simulation использует общий verification code; токены не имеют срока жизни и хранятся в открытом виде.
7. Cookie/session write API не имеют системной CSRF-защиты и общего rate limiting.
8. Upload validation доверяет расширению и заявленному MIME; разрешена серверная загрузка видео.

### Высокие

- в legacy-схеме нет внешних ключей;
- отсутствуют `/health` и migration-aware `/ready`;
- публичный `/api/version` раскрывает operational metadata;
- uploads могут случайно попадать в git;
- unit test dependencies и тестовые ожидания рассинхронизированы;
- нет CI;
- production backup/restore не автоматизирован и не проверяется восстановлением.

## Архитектурные решения

1. Сохранить технический пакет `tourist03` и compatibility entrypoint `app:app`.
2. Ввести `create_app(settings=None)` без DB side effects при импорте.
3. Централизовать ENV в типизированном settings module с production validation.
4. Выполнять миграции только явной командой; `/ready` проверяет DB и обязательную версию.
5. Использовать additive migrations. Текущий runner сохраняется до отдельного Alembic baseline этапа.
6. Разделить публичные и внутренние DTO/queries. Публичные endpoints используют allowlist полей.
7. Feature flags блокируют и UI, и backend. CRM `/api/admin/**` остаётся независимой.
8. Сохранить текущий tourist booking app как закрываемый legacy route.
9. CSRF применить к session-cookie write endpoints; bearer tourist API не смешивать с cookie CSRF.
10. In-memory limiter допустим для одного процесса/dev. Production multi-worker/scale-out требует Redis-backed implementation.
11. Каноническим production path считать systemd deploy через `deploy.sh`; Docker Compose оставить для локального/альтернативного запуска до отдельной миграции инфраструктуры.

## Feature flags

Безопасные defaults до приёмки последующих этапов:

```env
FEATURE_PUBLIC_BOOKING=false
FEATURE_PUBLIC_USER_AUTH=false
FEATURE_OWNER_PORTAL=false
FEATURE_SERVICES=false
FEATURE_TELEGRAM_WEBAPP=false
FEATURE_PAID_PLACEMENT=false
FEATURE_LEGACY_TOURIST_APP=false
```

## Модель данных будущих этапов

Этап 1.1 не меняет product schema. Планируются только additive изменения:

- `catalog.place_types` и связь с `catalog.camps`;
- slug, публикационный статус, регион/город и version fields в `catalog.camps`;
- нормализованные публичные контакты и amenities;
- отдельные catalog services, при необходимости связанные с `crm.services`;
- отдельные owner accounts и ownership links;
- moderation submissions/change requests/feedback;
- analytics events и daily aggregates;
- plans/subscriptions с `free` для существующих объектов.

Поля добавляются nullable или с безопасными defaults, затем backfill, проверка и только после этого ограничения. PostGIS не вводится без замера production-объёма и профиля геозапросов.

## API

### Этап 1.1

- сохранить `/api/camps` как безопасный публичный compatibility endpoint;
- сохранить защищённые CRM/superadmin API для внутренних данных;
- безопасный `/api/version`;
- `/health` и `/ready`;
- feature flags endpoint для frontend без секретных настроек;
- CSRF token endpoint для cookie/session clients.

### Будущие публичные API

```text
GET  /api/public/places
GET  /api/public/places/{slug}
GET  /api/public/services
GET  /api/public/services/{slug}
GET  /api/public/search
GET  /api/public/filters
POST /api/public/submissions
POST /api/public/feedback
```

Существующие booking и CRM API остаются compatibility layer.

## Миграции

1. Текущий baseline: `0013_admin_profile_pins`.
2. Web worker не применяет миграции.
3. Явные команды runner: `status`, `check`, `upgrade`.
4. `check` и `/ready` не создают таблицы и не применяют SQL.
5. Перед product migrations: `pg_dump -Fc --no-owner --no-acl`, uploads archive, row counts, migration list и SHA256.
6. Восстановление проверяется только в отдельной test database.
7. Alembic baseline вводится отдельным согласованным этапом после проверки production schema.

## Этапы

1.1. Security, configuration and foundation.

2. Browser-first public map, search, filters, cards, contacts and hidden booking UI.

3. Universal place/service model and additive migrations.

4. Placement submissions, drafts, media, anti-spam and notifications.

5. Superadmin moderation, feedback, owners, analytics and plans.

6. Owner portal and moderated changes.

7. Performance, SEO, security review, tests, deployment and final documentation.

## Rollback

- Главный rollback механизм — выключение feature flags и возврат предыдущего application commit/image.
- Additive schema должна оставаться совместимой с предыдущим приложением.
- Не выполнять destructive down migrations с пользовательскими данными.
- При migration failure транзакция runner откатывается до записи версии.
- Перед deploy фиксировать previous commit и проверенный backup.
- Rollback deploy: вернуть previous commit, установить совместимые зависимости/build, перезапустить сервисы, проверить `/health` и `/ready`.
- Полный restore БД выполняется только при подтверждённой порче данных и после отдельного решения владельца системы.

## Критерии приёмки

### Этап 1.1

- импорт приложения не меняет БД;
- production settings требуют стабильный session secret и DB settings;
- CORS не использует wildcard в production;
- session cookies имеют HttpOnly, SameSite и Secure в production;
- CSRF защищает критические session write endpoints;
- rate limiting защищает auth, login и upload;
- публичный catalog DTO не содержит внутренних полей;
- inactive/archived/hidden объекты не возвращаются публично;
- `/api/version`, `/health`, `/ready` безопасны;
- public auth и legacy tourist app выключены flags;
- upload validation проверяет реальное изображение;
- unit tests, typecheck и production build зелёные;
- backup/restore-check, deployment guide и CI существуют;
- production DB, deploy, push, merge и history rewrite не выполнялись.

### Публичный запуск

- обычный браузер работает без Telegram API;
- карта mobile-first, с кластеризацией, поиском, фильтрами и geolocation fallback;
- нет публичного booking/date filter/tourist account;
- CRM и booking code сохранены;
- услуги и размещение находятся на общей карте;
- owner changes проходят moderation;
- миграции воспроизводимы, backup и rollback проверены.
