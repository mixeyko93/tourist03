# Deployment runbook: systemd path

Канонический production path — systemd-сценарий `./deploy.sh` на `/opt/tourist03`. Docker Compose остаётся локальным/альтернативным способом запуска. Этот документ не запускает deploy.

## До утверждённого окна

1. На рабочей ветке выполнить `./scripts/deploy-preflight.sh`.
2. Проверить production `.env`: `ENVIRONMENT=production`, уникальные `SESSION_SECRET_KEY`/`PG_PASSWORD`, `SESSION_COOKIE_SECURE=true`, явный `CORS_ORIGINS`, `ALLOW_SIMULATED_AUTH=false`, пустой `SIM_VERIFY_CODE`.
3. Зафиксировать SHA предыдущей версии и подготовить rollback owner.
4. На сервере создать и проверить backup через `PYTHON_BIN=./.venv/bin/python BACKUP_ROOT=/var/backups/tourist03 ./scripts/backup.sh`.
5. В отдельной test БД выполнить `scripts/restore-check.sh` для актуального backup.

## Release sequence

1. Обновить approved revision штатным `./deploy.sh`.
2. Выполнить явную миграцию `./.venv/bin/python -m tourist03.migrations upgrade`; web import сам миграции не выполняет.
3. Собрать frontend до передачи revision: `cd frontend && npm ci && npm run build`.
4. Перезапустить units только после успешной миграции/build.
5. Проверить `GET /health` и `GET /ready`; второй endpoint обязан вернуть `200` и `migrations=current`.
6. Проверить публичный `/api/version`, CRM login и superadmin login без записи реальных данных.

## Rollback

Feature flags — первый rollback: закрыть public feature без удаления schema. Для application rollback вернуть заранее записанную revision, восстановить совместимые dependencies/static build, перезапустить units и проверить `/health`/`/ready`.

Schema rollback не выполняется автоматически: миграции additive. Полный restore допускается только после решения владельца системы и после проверки restore в test DB. Не используйте dumps из git как operational backup.

## Scaling note

`RATE_LIMIT_STORAGE=memory` рассчитан на один web process. Перед запуском нескольких workers/instances настройте `RATE_LIMIT_STORAGE=redis` и `REDIS_URL`, затем отдельно проверьте Redis-backed limiter. При недоступном Redis процесс временно использует process-local fallback и пишет error log; это не считается готовым scale-out состоянием.
