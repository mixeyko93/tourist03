# Этап 3.2: Owner Portal и изменения объектов

## Контуры и feature flags

Owner Portal — отдельный продукт по адресу `/owner`. Его учётные записи
находятся в `auth.owner_accounts` и не используют `camp_admin_accounts`.

- `FEATURE_OWNER_PORTAL=false` скрывает страницу, owner auth и owner API через
  одинаковый 404;
- `FEATURE_OWNER_CHANGE_REQUESTS=false` скрывает редактор изменений и очередь
  superadmin;
- второй флаг нельзя включить без первого;
- production-включение Owner Portal требует настроенного SMTP.

Публичный каталог продолжает работать при любых значениях этих флагов.

## Модель Published и Proposed

Владелец никогда не обновляет `catalog.*` через редактор. При создании
изменений backend фиксирует:

1. `published_snapshot` и `base_content_version`;
2. только разрешённый `proposed_payload`;
3. объяснимый `diff_payload`;
4. staged media отдельно от публичной галереи.

После `submitted → in_review → approved` суперадмин выполняет отдельное
идемпотентное apply-действие. В одной PostgreSQL-транзакции проверяется базовая
версия, обновляется Published, применяются contacts/amenities/rooms/media,
пишутся immutable history и общий `crm.audit_log`, закрывается запрос и
создаются события существующего `crm.notification_events`. Ошибка любого шага
откатывает всю транзакцию. Отклонение не меняет Published.

Владелец может немедленно снять объект с публикации. Повторное включение
представлено `request_publication` внутри Proposed и применимо только после
модерации; поле `publication_status` владельцу недоступно.

## Статусы и понятные названия

| Внутренний статус | Owner UI |
|---|---|
| `draft` | Черновик |
| `submitted` | Отправлено |
| `in_review` | На проверке |
| `needs_changes` | Нужны изменения |
| `approved` | Одобрено |
| `applied` | Опубликовано |
| `rejected` | Отклонено |
| `withdrawn` | Отозвано |
| `archived` | В архиве |

Переходы валидирует backend. Для `needs_changes` и `rejected` обязателен
понятный владельцу комментарий.

## API

Аутентификация и профиль:

```text
POST /api/owner/auth/login
POST /api/owner/auth/logout
POST /api/owner/auth/forgot-password
POST /api/owner/auth/reset-password
GET  /api/owner/me
GET  /api/owner/auth/session
PATCH /api/owner/profile
PATCH /api/owner/profile/password
```

Объекты и изменения:

```text
GET  /api/owner/dashboard
GET  /api/owner/camps/{camp_id}
POST /api/owner/camps/{camp_id}/unpublish
POST /api/owner/camps/{camp_id}/changes
GET  /api/owner/changes
GET  /api/owner/changes/{change_id}
PATCH /api/owner/changes/{change_id}
POST /api/owner/changes/{change_id}/submit
POST /api/owner/changes/{change_id}/withdraw
POST /api/owner/changes/{change_id}/media
DELETE /api/owner/changes/{change_id}/media/{media_id}
DELETE /api/owner/changes/{change_id}/published-media/{media_id}
```

Superadmin:

```text
GET  /api/superadmin/owner-changes
GET  /api/superadmin/owner-changes/{change_id}
POST /api/superadmin/owner-changes/{change_id}/decision
POST /api/superadmin/owner-changes/{change_id}/apply
GET|POST /api/superadmin/owners
PATCH /api/superadmin/owners/{owner_id}
POST /api/superadmin/owners/{owner_id}/camps
```

Queue поддерживает фильтры `status`, `camp_id`, `owner_id`, `region`,
`date_from`, `date_to`.

## Безопасность

- пароли владельцев — Argon2id;
- raw reset token не хранится в PostgreSQL или outbox: письмо восстанавливает
  bearer token из ссылки на reset record и серверного session secret;
- forgot-password всегда возвращает одинаковый ответ;
- login, auth и owner writes имеют rate limits;
- успешный login и logout очищают session, предотвращая fixation;
- все unsafe owner API после входа требуют CSRF;
- каждый объект и Change Request проверяется на owner link, что закрывает IDOR;
- slug, publication status, owner links, audit и внутренние поля модерации не
  входят в allowlist Proposed;
- изображения проверяются Pillow, очищаются от metadata и хранятся staged;
- контакты и видео проходят allowlist схем и доверенных hosts.

Telegram и email используют существующий outbox. Ошибка доставки не откатывает
уже завершённое решение модерации.

## Dashboard и индекс качества

Dashboard batch-запросом получает снимки всех связанных объектов и показывает
состояние публикации, последнюю правку/модерацию, количество фото, комнат и
удобств, ожидающие изменения, рекомендации и activity feed. Activity feed
читает существующий `crm.audit_log`, отдельная event-система не создаётся.

Индекс качества рассчитывает backend-сервис. Положительные веса берутся из
`OWNER_CARD_COMPLETENESS_WEIGHTS`; ответ содержит процент, earned/total weight,
checklist, автоматически исчезающие рекомендации и health-индикаторы. Метрики
просмотров намеренно не реализованы.

## Локальная проверка

```bash
python -m unittest tests.test_owner_domain -v
RUN_PG_INTEGRATION=1 python -m unittest tests.test_owner_postgres -v
RUN_UI_SMOKE=1 python -m unittest tests.test_owner_browser -v
cd frontend && npm run build
```

Для визуального review используется отдельное test-приложение и artifact
`owner-portal-review`. В artifact находятся `index.html`,
`review-metrics.json`, desktop login/dashboard/editor/diff/history/profile/
superadmin moderation и mobile login/dashboard/editor/history/diff.

## Производительность и доступность

Owner Portal разделён на отдельные route chunks: login, dashboard, objects,
editor, media uploader, history, profile и diff. CRM, публичная карта и
страницы Superadmin не попадают в начальный owner bundle. Dashboard использует
один агрегированный quality query, limit/offset pagination и summary DTO без
media URL, proposed/published payload и полного diff. Число SQL-запросов не
растёт вместе с количеством объектов.

Контрольный Lighthouse на локальном review-приложении:

- desktop: Performance 100, Accessibility 100, Best Practices 100, SEO 100,
  CLS 0;
- mobile с тем же Lighthouse throttling profile: Performance 97,
  Accessibility 100, Best Practices 100, SEO 100, LCP 2.560 s, TBT 0 ms,
  CLS 0.

Trace, bundle sizes, API contract и команды воспроизведения описаны в
[performance.md](performance.md).

Никакие команды этапа не применяют production migrations и не выполняют
deploy.
