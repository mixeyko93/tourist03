# Этап 3.1 — заявки на размещение и модерация

Статус: реализовано локально в feature-ветке, ожидает review. Базовая версия `main`:
`975c3e2b2dc4f33a98a60e2933ef5214145a191b`, обязательная migration
version: `0017_catalog_amenities`.

Production-БД, production migrations, merge и deploy в этом этапе не
используются.

## Предварительный аудит

### Контуры

- Публичный сайт — Jinja/HTML и модульный JavaScript в `static/public`.
- Superadmin — React + TypeScript + Vite, маршруты `/admin/*`.
- Backend — FastAPI app factory, раздельные router/service/repository слои.
- БД — PostgreSQL со схемами `auth`, `catalog`, `crm`; схемы `moderation` пока
  нет.
- Публичный каталог — `catalog.camps`, `catalog.rooms`,
  `catalog.place_contacts`, `catalog.amenities`, `catalog.camp_amenities`,
  канонические media с legacy fallback.

### Что можно переиспользовать

- `FeatureGateMiddleware` возвращает 404 для выключенных публичных контуров.
- `RateLimitMiddleware` поддерживает memory и Redis storage.
- Session-bound CSRF уже защищает unsafe superadmin endpoints.
- Upload service проверяет размер, extension/MIME и декодирование через Pillow,
  использует случайные имена и атомарное перемещение временного файла.
- `crm.audit_log` — существующий append-only прикладной журнал.
- `crm.notification_events` — общий outbox для in-app/Telegram; staff bot уже
  доставляет Telegram события связанным суперадминам.
- SMTP-настройки существуют, но отправителя и retry-механизма для email пока нет.
- Каталог уже умеет нормализовать безопасные public contacts, MAX и video URL.
- Superadmin editor поддерживает `publication_status=draft`, legacy
  `status=disabled`, rooms, amenities, contacts и media.

### Выводы аудита

- Новая заявка не должна использовать `auth.users`: регистрация и owner portal
  не входят в этап.
- Applicant contacts, public contacts и anti-spam hashes хранятся раздельно.
- Существующий защищённый upload нельзя открывать анонимно; для заявок нужен
  отдельный staged flow с draft token и TTL.
- `crm.notification_events` расширяется как общий outbox вместо второй очереди.
- Создание catalog draft выполняется одной DB-транзакцией и никогда не ставит
  `publication_status=published`.
- Публичная форма загружается только на `/add-place`, поэтому initial bundle
  главной карты не увеличивается.

## Feature flag и конфигурация

Добавляется `FEATURE_PLACEMENT_SUBMISSIONS=false`.

Флаг управляет:

- CTA на главной и в мобильном меню;
- страницами `/add-place` и `/submission-status`;
- всеми `/api/public/submissions*` и preview media routes.

При `false` публичные страницы и API возвращают 404. Superadmin API остаётся
доступным, чтобы выключение публичного приёма не скрывало уже полученные данные.
Каталог, CRM и booking от флага не зависят.

Новые настройки:

```env
FEATURE_PLACEMENT_SUBMISSIONS=false
SUBMISSION_MAX_PLACE_PHOTOS=20
SUBMISSION_MAX_ROOM_PHOTOS=5
SUBMISSION_MAX_IMAGE_BYTES=10485760
SUBMISSION_MAX_IMAGE_PIXELS=40000000
SUBMISSION_DRAFT_TTL_HOURS=168
SUBMISSION_UPLOAD_TTL_HOURS=48
SUBMISSION_MIN_FILL_SECONDS=20
SUBMISSION_MAX_LINKS=12
SUBMISSION_RATE_PER_HOUR=5
SUBMISSION_CAPTCHA_PROVIDER=test
SUBMISSION_CAPTCHA_VERIFY_URL=
SUBMISSION_CAPTCHA_SECRET=
SUBMISSION_CAPTCHA_CLIENT_SCRIPT_URL=
SUBMISSION_CAPTCHA_SITE_KEY=
SUBMISSION_CAPTCHA_TEST_TOKEN=test-pass
SUBMISSION_RETENTION_REJECTED_DAYS=365
SUBMISSION_RETENTION_ABANDONED_DAYS=30
SUBMISSION_RETENTION_TECHNICAL_DAYS=90
```

В production при включённом feature flag запрещены test/disabled CAPTCHA
provider, пустой CAPTCHA secret и process-local rate limiter для multi-worker
deployment. Production также требует HTTPS client adapter, который определяет
`window.touristikaCaptcha.execute()`, и public site key. Реальные credentials в
репозиторий не попадают.

## Миграции

Все изменения additive и разбиваются на пять revisions:

1. `0018_moderation_submissions` — схема, submissions, статусы и draft/tracking
   token hashes.
2. `0019_submission_media` — staged media metadata и limits.
3. `0020_submission_history_notes` — immutable status history и notes.
4. `0021_submission_outbox` — связь submissions с общим
   `crm.notification_events`, retry/dedupe/email destination.
5. `0022_submission_indexes` — FK, partial/cover uniqueness, pagination,
   retention и anti-abuse indexes, validation constraints.

Миграции проверяются:

- с пустой БД;
- с точной текущей версией `0017_catalog_amenities`;
- повторным upgrade;
- `migration check`/`/ready`;
- без изменения существующих catalog/CRM данных.

## Структура БД

### `moderation.placement_submissions`

Основные поля из задания сохраняются. Дополнительно нужны:

- `draft_token_hash`, `tracking_token_hash` — SHA-256 от случайных
  256-битных tokens; raw token в БД не хранится;
- `submit_idempotency_key_hash` — защита повторной отправки;
- `draft_expires_at`;
- `consents JSONB` и `consented_at`;
- `status_public_comment`;
- `content_version INTEGER NOT NULL DEFAULT 1`;
- `created_camp_id` хранится в заданном поле `published_camp_id`; несмотря на
  legacy-имя, ссылка указывает на непубличный draft.

`public_number` — случайный непоследовательный номер формата
`TUR-YYYY-XXXXXXXX`. Sequential DB id никогда не является публичным
идентификатором.

`ip_hash` и `user_agent_hash` создаются keyed SHA-256 от нормализованных
значений и secret приложения. Raw IP/User-Agent не записываются.

### `moderation.submission_media`

Кроме заданных полей:

- `scope` (`place`/`room`);
- `room_client_id` для связи с элементом `rooms_payload`;
- `preview_token` как случайный unguessable URL segment;
- `thumbnail_storage_key`;
- `attached_at` и `expires_at`.

Ограничения:

- только image media;
- максимум одна cover на заявку;
- place ≤ 20, room_client_id ≤ 5 — серверная проверка под row lock;
- storage keys не принимаются от клиента;
- удаление — soft delete через `deleted_at`.

### `moderation.submission_status_history`

История содержит каждую смену статуса, actor type/id, public/internal comments и
timestamp. UPDATE/DELETE запрещаются trigger; добавление выполняется только
вместе со сменой status в одной транзакции.

### `moderation.submission_notes`

Используется для внутренних заметок, public clarification и ответа заявителя.
`is_visible_to_applicant` явно отделяет публичный текст от internal notes.

### Общий outbox

Переиспользуется `crm.notification_events`. Additive columns:

- `submission_id`;
- `dedupe_key`;
- `recipient_address` для email;
- `attempts`, `next_attempt_at`, `last_error`, `sent_at`.

Unique partial index по `dedupe_key` обеспечивает идемпотентность. Telegram и
email failures не откатывают основную операцию. Retry использует bounded
exponential backoff.

## Статусы и переходы

Backend state machine:

| Из | В | Кто/условие |
|---|---|---|
| `draft` | `submitted` | заявитель, валидная форма/CAPTCHA/consents |
| `submitted` | `new` | система в транзакции отправки |
| `new` | `in_review` | суперадмин берёт в работу |
| `in_review` | `needs_clarification` | суперадмин, обязателен public comment |
| `needs_clarification` | `in_review` | ответ заявителя либо суперадмин |
| `in_review` | `approved` | суперадмин |
| `approved` | `object_draft_created` | транзакционное создание объекта |
| `object_draft_created` | `published` | existing catalog editor публикует вручную |
| `new`/`in_review`/`needs_clarification` | `rejected` | обязательна причина |
| `submitted`/`new`/`in_review` | `withdrawn` | tracking-token заявителя или суперадмин |
| `published`/`rejected`/`withdrawn` | `archived` | суперадмин |

Frontend никогда не отправляет произвольный service status. Все transitions
проверяются domain helper и повторно ограничиваются SQL constraint.

## Public API

Обязательные endpoints:

- `GET /api/public/submissions/config`;
- `POST /api/public/submissions/drafts`;
- `PATCH /api/public/submissions/drafts/{draft_token}`;
- `POST /api/public/submissions/drafts/{draft_token}/media`;
- `DELETE /api/public/submissions/drafts/{draft_token}/media/{media_id}`;
- `POST /api/public/submissions`;
- `GET /api/public/submissions/{public_number}/status`.

Дополнительные защищённые действия для заявленного flow:

- `POST /api/public/submissions/{public_number}/responses` — ответ после
  clarification;
- `POST /api/public/submissions/{public_number}/withdraw` — отзыв заявки;
- `GET /api/public/submission-media/{preview_token}` — unguessable staged
  preview без раскрытия storage path.

Draft token передаётся в path согласно контракту и хранится только в браузере.
Tracking token передаётся в `X-Submission-Tracking-Token`; tracking URL хранит
его во fragment (`#token=`), чтобы secret не попадал в HTTP logs/Referer.

Public status DTO содержит только:

- public number;
- публичный status/label;
- public comment;
- updated timestamp;
- созданный public place URL только после фактической публикации.

Applicant contacts, internal notes, hashes, spam score, internal IDs и audit не
выдаются.

## Public форма

Маршрут `/add-place` использует отдельные `submission.css` и `submission.js`,
загружаемые только на этой странице.

Восемь шагов:

1. заявитель;
2. объект и coordinate picker Leaflet;
3. отдельные public contacts;
4. amenities с группировкой по category;
5. rooms для accommodation types;
6. staged images, cover/sort и safe video links;
7. consents;
8. summary preview и submit.

После submit показываются public number, tracking link и нейтральное объяснение
модерации без обещания срока.

### Локальный черновик

- IndexedDB versioned store содержит форму и File/Blob;
- autosave после debounce и при смене шага;
- индикатор `saving/saved/error` через `aria-live`;
- corrupted value сбрасывается безопасно;
- миграция формата выполняется versioned transform;
- `beforeunload` предупреждает только при несохранённых изменениях;
- успешный submit удаляет IndexedDB draft.

Фотографии не попадают в localStorage. localStorage используется только для
короткого server draft token и текущего шага.

## Staged media flow

1. Server draft создаётся до первой загрузки.
2. Draft token авторизует upload/delete.
3. Файл читается с hard byte limit.
4. Проверяются extension, declared MIME, Pillow `verify` и повторное decode.
5. Decompression bomb warning/error и pixel limit отклоняются.
6. Изображение пересобирается в safe raster, EXIF/metadata не копируются.
7. Создаются random storage key и thumbnail; запись атомарная.
8. Metadata сохраняются только после успешной записи файлов.
9. При DB/file error временные файлы удаляются.
10. При submit media привязываются к заявке; orphan cleanup работает по TTL.

SVG, HTML, executable и server video запрещены. Video URLs проходят текущий
host allowlist.

## Антиспам

- `CaptchaProvider` protocol отделяет business logic от provider adapter.
- В test/dev применяется deterministic provider с явным test token.
- Honeypot — hard block как очевидный automation signal.
- Minimum fill time считается от server-side `created_at`.
- Per-IP-hash и per-draft rate limits; global middleware остаётся первым слоем.
- Duplicate fingerprint и число submissions за окно повышают spam score.
- Link count, field lengths и invalid URL контролируются до DB write.
- Высокий score помечает заявку и создаёт warning, но не теряет валидные данные.
- Повторный submit с тем же idempotency key возвращает тот же result.

## Superadmin API и UI

API:

- list/detail с pagination, filters и search;
- optimistic PATCH по `content_version`;
- status, notes, clarification, approve, reject, create-object-draft, archive;
- только `get_superadmin`, session requests дополнительно защищены CSRF;
- все mutations пишут history и audit.

Раздел `/admin/submissions`:

- таблица номера/status/name/type/region/applicant/date/moderator/spam/media;
- фильтры из задания без N+1;
- detail с applicant/public contacts раздельно;
- media, rooms, amenities, video, consents, history, notes и spam signals;
- side-by-side preview будущей карточки;
- действия с confirmation/error/focus management;
- созданный draft открывается в existing `/admin/bases/{id}` editor.

## Создание catalog draft

Операция принимает idempotency key и выполняется под
`SELECT ... FOR UPDATE`:

1. если `published_camp_id` уже заполнен — вернуть существующий camp;
2. разрешить только status `approved`;
3. создать уникальный slug через существующий `catalog.slugify_place_name`;
4. вставить `catalog.camps` с `publication_status=draft`,
   legacy `status=disabled`;
5. перенести public contacts, amenities, rooms, video URLs и media metadata;
6. скопировать staged files в permanent camp/room paths, не удаляя originals до
   commit; при exception удалить новые copies;
7. записать `published_camp_id`, history, audit и outbox;
8. commit;
9. best-effort очистить staged originals.

Ни один шаг не выставляет `published`/`active`. Повторный вызов возвращает тот же
camp id. Existing editor остаётся единственной точкой ручной публикации.

## Telegram и email

### Telegram

- На новую/high-risk/clarification-response/create-error/email-error заявку
  создаются deduplicated `crm.notification_events`;
- recipients — все активные связанные superadmin Telegram accounts;
- action URL ведёт на `/admin/submissions/{id}`;
- существующий staff bot доставляет сообщения;
- ошибка delivery увеличивает attempts и планирует retry, но не ломает request.

### Email

Шаблоны: принято, требуется уточнение, одобрено, создан draft, опубликовано,
отклонено. Внешний текст использует только public number, tracking URL и public
comment.

SMTP adapter доставляет pending email outbox events. При пустом SMTP события
остаются queued с диагностикой, а submission сохраняется. Internal ID/comments
в письма не попадают. Email для owner/representative обязателен, для tourist —
опционален.

## Security и персональные данные

- Separate DTO для public tracking и superadmin detail.
- Raw IP/User-Agent не хранятся.
- Raw tokens не хранятся и сравниваются constant-time.
- Все SQL parameterized; list paginated.
- Jinja autoescape и React text rendering исключают raw HTML.
- URL проходят type-specific allowlist.
- Draft/tracking token не даёт доступа к superadmin data.
- Session-authenticated admin mutations требуют CSRF.
- Media path строится только сервером из random keys.
- Audit не содержит фото, raw form payload, tokens или applicant contacts.
- Logs используют public number и internal submission id, но не PII.

Retention policy:

- abandoned drafts: 30 дней;
- orphan uploads: 48 часов после expiry;
- rejected/withdrawn submissions: 365 дней;
- technical hashes/events: 90 дней;
- published linkage/history: пока существует catalog object.

Сроки конфигурируются. В production автоматическое удаление не включается без
отдельно настроенного и проверенного job; в этапе добавляются только query/helper
и documented dry-run.

## Тесты

### Unit/HTTP

- state machine, role requirements, contacts separation, tokens, idempotency;
- CAPTCHA, spam score, rate limits, URL/MAX validation;
- image spoofing, bombs, path traversal, limits и cleanup;
- tracking IDOR/enumeration и absence of internal fields;
- clarification/reject requirements, optimistic locking, audit/outbox.

### PostgreSQL

- clean/current/repeated migrations;
- create/media/history/notes;
- approve/reject/clarification;
- transactional and idempotent object draft;
- forced failure rollback;
- catalog/CRM/booking regressions.

### Browser

- desktop/mobile steps, map picker, IndexedDB autosave/restore;
- upload/delete/cover/sort, validation, preview, submit success, tracking;
- superadmin list/detail/actions/create draft;
- browser-first operation without Telegram;
- keyboard, focus, aria-live and compact viewports.

### Visual/performance

Workflow artifact `placement-submissions-review` содержит `index.html`,
`review-metrics.json` и все заданные desktop/mobile PNG.

Lighthouse gates:

- landing Performance ≥ 90;
- form Performance ≥ 90;
- Accessibility ≥ 98;
- CLS ≤ 0.05.

Также фиксируются JS/CSS bundle delta, API payload sizes, upload timings и query
count для admin list.

## Rollback

1. Выключить `FEATURE_PLACEMENT_SUBMISSIONS`.
2. Откатить application revision; additive tables/columns не мешают старому коду.
3. Pending outbox events можно остановить по channel/status без удаления заявок.
4. Не удалять production submissions/media автоматически.
5. Drop новых структур допустим только отдельным согласованным изменением после
   backup, application rollback и проверки отсутствия данных/linkage.

## Критерии приёмки

- Feature off даёт 404 и не влияет на существующие данные.
- Form/draft/upload/submit/tracking работают desktop/mobile.
- Anti-spam и tokens выдерживают security regression suite.
- Superadmin moderation и history работают с optimistic locking.
- Reject/clarification требуют публичную причину.
- Telegram/email используют outbox/retry/dedupe.
- Object draft создаётся один раз, остаётся непубличным и открывается в existing
  editor.
- Existing catalog, CRM и booking тесты зелёные.
- Migrations, unit, PostgreSQL, browser, frontend build, screenshots и Lighthouse
  зелёные.
- Итоговый PR остаётся draft; merge/deploy/production migrations отсутствуют.

## Фактическая локальная проверка

Проверено на Python 3.11 и PostgreSQL 16 перед открытием draft PR:

- `pip check` и public-PyPI `pip-audit`: ошибок и известных уязвимостей нет;
- compileall: успешно;
- unit profile: 111 tests, 19 ожидаемо skipped integration/browser tests;
- полный PostgreSQL profile: 111 tests, 2 ожидаемо skipped browser classes;
- existing browser smoke: 5/5;
- submission browser/screenshot regression: 1/1, 25 PNG;
- TypeScript + Vite production build: успешно;
- npm production audit: 0 vulnerabilities;
- Lighthouse landing: Performance 92, Accessibility 100, CLS 0;
- Lighthouse `/add-place`: Performance 93, Accessibility 100, CLS 0.045;
- review upload fixture: 46.9 ms в локальном mocked browser flow.

Форма загружает отдельные 31 463 B JS (8 624 B gzip) и 13 915 B CSS
(3 350 B gzip) только на `/add-place`; landing regression подтверждает отсутствие
этих ресурсов в initial load. Репрезентативные JSON payload fixtures:
config 1 151 B, admin list с одной строкой 649 B, detail 2 830 B. Admin list
пагинирован и получает media count одной SQL-командой без N+1.
