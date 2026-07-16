# Туристика

Туристика — сервис для поиска баз отдыха, домиков и бронирования рядом, а также CRM для владельцев и администраторов баз отдыха.

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

`/api/camps` использует публичный allowlist DTO и server-side filter статуса `active`/`published`; CRM/superadmin остаются на внутренних API. `/health` проверяет процесс, а `/ready` дополнительно проверяет доступ к DB и version `0013_admin_profile_pins`.

## Migrations, backup и deploy

Миграции никогда не выполняются при импорте `app`. Доступные команды:

```bash
./.venv/bin/python -m tourist03.migrations status
./.venv/bin/python -m tourist03.migrations check
./.venv/bin/python -m tourist03.migrations upgrade
```

Операционные инструкции находятся в [backup-restore.md](docs/backup-restore.md) и [deployment.md](docs/deployment.md). Канонический production path — systemd `./deploy.sh`; Docker Compose оставлен для локального/альтернативного использования. Эти инструкции не являются разрешением на deploy.

Tracked legacy dumps и existing uploads в Этапе 1.1 намеренно не удаляются. Порядок ротации, проверки backup/restore и отдельного согласования history cleanup описан в [security-incident-response.md](docs/security-incident-response.md).
