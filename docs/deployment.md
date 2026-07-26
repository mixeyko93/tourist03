# Deployment runbook: systemd path

Канонический production path — systemd-сценарий `./deploy.sh` на `/opt/tourist03`. Docker Compose остаётся локальным/альтернативным способом запуска. Этот документ не запускает deploy.

## До утверждённого окна

1. На рабочей ветке выполнить `./scripts/deploy-preflight.sh`.
2. Проверить production `.env`: `ENVIRONMENT=production`, уникальные `SESSION_SECRET_KEY`/`PG_PASSWORD`, `SESSION_COOKIE_SECURE=true`, явный `CORS_ORIGINS`, `ALLOW_SIMULATED_AUTH=false`, пустой `SIM_VERIFY_CODE`.
3. Зафиксировать SHA предыдущей версии и подготовить rollback owner.
4. На сервере создать и проверить backup через `PYTHON_BIN=./.venv/bin/python BACKUP_ROOT=/var/backups/tourist03 ./scripts/backup.sh`.
5. В отдельной test БД выполнить `scripts/restore-check.sh` для актуального backup.
6. Проверить `python -m tourist03.migrations status`: до upgrade допустима только ожидаемая цепочка до `0022_submission_indexes`, неизвестных revisions быть не должно.
7. В preview/test окружении открыть карту, фильтры и одну `/places/{slug}`; проверить, что draft/disabled/archived URL возвращают 404.
8. Оставить `FEATURE_PLACEMENT_SUBMISSIONS=false`, пока не настроены и не проверены CAPTCHA client/server pair, SMTP, staff bot/outbox worker, upload volume и privacy owner.

## Release sequence

1. Обновить approved revision штатным `./deploy.sh`.
2. Выполнить явную миграцию `./.venv/bin/python -m tourist03.migrations upgrade`; web import сам миграции не выполняет.
3. Собрать frontend до передачи revision: `cd frontend && npm ci && npm run build`.
4. Перезапустить units только после успешной миграции/build.
5. Проверить `GET /health` и `GET /ready`; второй endpoint обязан вернуть `200` и `migrations=current`.
6. Проверить публичный `/api/version`, CRM login и superadmin login без записи реальных данных.
7. Для каталога проверить `/api/public/place-types`, `/api/public/amenities`, paginated `/api/public/places?limit=1`, detail опубликованного slug и dynamic `/sitemap.xml`.

## Enablement заявок

После миграции, но до включения флага:

1. Настроить `SUBMISSION_CAPTCHA_PROVIDER=http`, HTTPS verify URL, secret,
   доверенный HTTPS client-adapter и public site key. Client adapter обязан
   определить `window.touristikaCaptcha.execute()` и вернуть одноразовый token.
2. Настроить SMTP и тестовую доставку. `SMTP_PASSWORD` и CAPTCHA secret хранятся
   только в private environment.
3. Убедиться, что staff bot process запущен, имеет PostgreSQL/SMTP env и тот же
   `UPLOAD_DIR`; он доставляет Telegram/email outbox и, только при отдельном
   `SUBMISSION_CLEANUP_ENABLED=true`, очищает expired orphan files.
4. При нескольких web workers использовать Redis rate limiter.
5. В test/preview включить флаг и пройти draft → upload → submit → tracking →
   moderation → approved → object draft. Убедиться, что объект остаётся
   `draft/disabled`, не виден на карте и не принимает бронирования.
6. Проверить recipient list Telegram и тестовый mailbox, затем согласованно
   включить `FEATURE_PLACEMENT_SUBMISSIONS=true`.

Test CAPTCHA token запрещён в production и не переносится из `.env.example`.

## Catalog backfill gate

После `0017_catalog_amenities` и до открытия трафика проверки должны вернуть нули:

```sql
SELECT COUNT(*) FROM catalog.camps WHERE slug IS NULL OR place_type_id IS NULL OR publication_status IS NULL;
SELECT lower(slug), COUNT(*) FROM catalog.camps GROUP BY lower(slug) HAVING COUNT(*) > 1;
SELECT COUNT(*) FROM catalog.place_contacts contacts LEFT JOIN catalog.camps camps ON camps.id=contacts.camp_id WHERE camps.id IS NULL;
SELECT COUNT(*) FROM catalog.camp_amenities links LEFT JOIN catalog.camps camps ON camps.id=links.camp_id WHERE camps.id IS NULL;
```

Проверить вручную выборку `publication_status`: legacy active/published должны быть published, archived — archived. Публичные contacts нельзя заполнять из `owner`, `manager` или `admin_phones`.

## Rollback

Feature flags — первый rollback: закрыть public feature без удаления schema. Для application rollback вернуть заранее записанную revision, восстановить совместимые dependencies/static build, перезапустить units и проверить `/health`/`/ready`.

Schema rollback не выполняется автоматически: миграции additive. Полный restore допускается только после решения владельца системы и после проверки restore в test DB. Не используйте dumps из git как operational backup.

Для заявок первый rollback — `FEATURE_PLACEMENT_SUBMISSIONS=false`: public
страницы/API возвращают 404, а superadmin сохраняет доступ к данным. Outbox
worker можно остановить отдельно после фиксации очереди. Schema и uploads не
удалять; cleanup не включать как способ rollback.

## Scaling note

`RATE_LIMIT_STORAGE=memory` рассчитан на один web process. Перед запуском нескольких workers/instances настройте `RATE_LIMIT_STORAGE=redis` и `REDIS_URL`, затем отдельно проверьте Redis-backed limiter. При недоступном Redis процесс временно использует process-local fallback и пишет error log; это не считается готовым scale-out состоянием.
