# Туристика

Туристика — browser-first карта и универсальный публичный каталог туристических объектов, а также CRM для управляющих и администраторов объектов.

## Состав системы

- клиентское Telegram WebApp / веб-приложение;
- CRM для баз отдыха;
- суперадминка;
- FastAPI backend;
- PostgreSQL;
- Telegram bot.

## Названия частей продукта

- клиентское приложение: Туристика;
- CRM: Туристика CRM;
- суперадминка: Туристика Admin;
- API: Turistika API.

## Домены

Рабочий домен на время разработки остаётся прежним. Домен turistika365.ru зарезервирован как будущий публичный домен проекта.

## Техническое имя

Техническое имя пакета/репозитория может временно оставаться `tourist03`, чтобы не ломать импорты, миграции и текущую инфраструктуру.

## Локальный запуск и проверки

1. Скопируйте `.env.example` в приватный `.env` и заполните только локальные значения.
2. Установите зависимости: `./.venv/bin/python -m pip install -r requirements-dev.txt`.
3. Примените схему явно: `./.venv/bin/python -m tourist03.migrations upgrade`.
4. Запустите приложение: `./.venv/bin/uvicorn app:app --reload`.

Единая команда unit-профиля:

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest discover -s tests -v
```

PostgreSQL integration tests запускаются только с `RUN_PG_INTEGRATION=1`; browser smoke — только с `RUN_UI_SMOKE=1`. Они не входят в обычный unit-профиль и требуют отдельного окружения.

CRM/superadmin frontend проверяется командой `cd frontend && npm run build`.

## Configuration и безопасность

Переменные приложения типизированы в `tourist03.settings.Settings`. В production обязательно задать стабильный `SESSION_SECRET_KEY` (не короче 32 символов), не-placeholder `PG_PASSWORD`, `SESSION_COOKIE_SECURE=true` и список `CORS_ORIGINS` без `*`. Production не запустится с `SIM_VERIFY_CODE`, `ALLOW_SIMULATED_AUTH=true`, `SUPERADMIN_LOCAL_BYPASS=true` или compatibility CSRF bypass.

Все public feature flags по умолчанию выключены:

```env
FEATURE_PUBLIC_BOOKING=false
FEATURE_PUBLIC_USER_AUTH=false
FEATURE_OWNER_PORTAL=false
FEATURE_SERVICES=false
FEATURE_TELEGRAM_WEBAPP=false
FEATURE_PAID_PLACEMENT=false
FEATURE_LEGACY_TOURIST_APP=false
```

Новый публичный каталог использует отдельные DTO и маршруты:

```text
GET /api/public/place-types
GET /api/public/amenities
GET /api/public/places?q=&place_type=&region=&city=&amenity=&bbox=&limit=&offset=
GET /api/public/places/{slug}
GET /places/{slug}
```

List endpoint отдаёт только лёгкие данные карты и только записи с `publication_status=published` плюс legacy `status=active|published`. Detail содержит публичные contacts/media/rooms. Owner, manager, admin phones, moderation и audit data в public DTO не входят. `/api/camps` сохранён как deprecated compatibility API; CRM/superadmin остаются на защищённых internal routes.

`/health` проверяет процесс, а `/ready` дополнительно проверяет доступ к DB и version `0017_catalog_amenities`. Публичный каталог не зависит от Telegram SDK. Booking, public auth, owner portal, services и paid placement продолжают управляться отдельными feature flags и в Этапе 2.2 не включаются.

Production и CI используют Python 3.11. Dependency audit в CI всегда получает метаданные и пакеты из публичного PyPI (`https://pypi.org/simple`). Если production устанавливает зависимости через внутренний mirror, mirror обязан синхронизировать безопасные версии с PyPI; credentials такого mirror не хранятся в репозитории и не используются security-аудитом.

## Migrations, backup и deploy

Миграции никогда не выполняются при импорте `app`. Доступные команды:

```bash
./.venv/bin/python -m tourist03.migrations status
./.venv/bin/python -m tourist03.migrations check
./.venv/bin/python -m tourist03.migrations upgrade
```

Операционные инструкции находятся в [backup-restore.md](docs/backup-restore.md), [deployment.md](docs/deployment.md) и [migrations.md](docs/migrations.md). Архитектура и acceptance Этапа 2.2 описаны в [stage-2.2-universal-catalog.md](docs/stage-2.2-universal-catalog.md). Канонический production path — systemd `./deploy.sh`; Docker Compose оставлен для локального/альтернативного использования. Эти инструкции не являются разрешением на deploy.

Tracked legacy dumps и existing uploads в Этапе 1.1 намеренно не удаляются. Порядок ротации, проверки backup/restore и отдельного согласования history cleanup описан в [security-incident-response.md](docs/security-incident-response.md).
