# Этап 2.2 — универсальный публичный каталог

## Исходное состояние

- Базовая ветка: `main` на `5c924b59ae12f61fd5953bacb4eff971fcfb5909`.
- Рабочая ветка: `feature/universal-public-catalog`.
- Текущая migration version: `0013_admin_profile_pins`.
- Физическая основа каталога остаётся `catalog.camps`; `catalog.rooms`, booking,
  CRM и legacy API не переименовываются.
- В локальной development-БД на старте: 6 camps, 12 rooms, 9 camp photos и
  36 room photos. `catalog.camp_media` и `catalog.room_media` существуют, но
  пока пусты, поэтому публичная галерея должна иметь legacy fallback.
- Anonymous `/api/camps` уже использует отдельный allowlist DTO и фильтрует
  legacy status. Superadmin и CRM работают через защищённые internal routes.

Production-БД, production migrations и deploy в этом этапе не используются.

## План изменений

### Миграции

1. `0014_place_types`: расширяемый справочник типов и seed 12 типов.
2. `0015_universal_camp_fields`: nullable universal fields, slug/status backfill,
   ограничения публикационных статусов, timestamps и indexes.
3. `0016_public_contacts`: отдельные публичные контакты и compatibility backfill
   из public/legacy phone/site fields без смешивания owner/manager/admin данных.
4. `0017_catalog_amenities`: справочник удобств, many-to-many связь и индексы.

Все изменения additive. Existing active/published записи получают
`publication_status=published`, archived — `archived`, остальные — `disabled`.
Slug создаётся один раз из транслитерации имени с ID-суффиксом и дальше не
меняется автоматически. `content_version` начинается с 1.

### Модели и DTO

- Отдельные public DTO: place list/detail, type, contact, amenity, room и media.
- Internal DTO и legacy `PublicCampDTO` не переиспользуются как public place DTO.
- Public DTO не включают owner, manager, admin phones, moderation/audit/billing
  или скрытые контакты.

### API

- `GET /api/public/place-types` и `GET /api/public/amenities`.
- `GET /api/public/places` с q/type/location/amenity/bbox/pagination filters.
- `GET /api/public/places/{slug}` с публичными contacts, media, rooms и amenities.
- Legacy `GET /api/camps` и `GET /api/camps/{id}` сохраняют текущий контракт и
  server-side visibility rules; CRM не переводится на public endpoints.
- Limits и bbox валидируются, запросы parameterized, порядок детерминирован.

### Public frontend и SEO

- Map-first frontend загружает облегчённый list endpoint, type metadata и filters.
- Маркеры различаются icon/accent из `place_types`; emoji, VIP и paid priority не
  используются. Popup ведёт на `/places/{slug}` и не загружает detail заранее.
- `/places/{slug}` — SSR/Jinja public page с canonical, Open Graph, JSON-LD,
  breadcrumb, contacts, gallery, rooms, amenities, safe videos и датой актуальности.
- Sitemap формируется динамически из published places и `PUBLIC_BASE_URL`.

### Superadmin

- Existing editor дополняется universal fields, type/status, public contacts,
  amenities, videos, SEO/public preview и publish validation.
- Existing rooms/media и legacy fields остаются редактируемыми.
- Список получает search/type/publication filters и public-page action.

### Совместимость и безопасность

- `catalog.camps`, rooms, booking и legacy columns не удаляются.
- Public publication требует одновременно legacy active/published status и
  `publication_status=published`.
- Contacts нормализуются на backend; URL допускают только контекстные
  `http`, `https`, `tel` и `mailto`. Social URLs проверяются по host.
- Canonical media берутся из approved `camp_media`/`room_media`; при отсутствии
  используется legacy photo fallback. Server-side video upload не добавляется.
- Описания выводятся Jinja autoescape; raw HTML из БД не рендерится.

### Rollback

- До merge: удалить feature branch, не затрагивая `main` и БД.
- После применения только в test/local: откат приложения на предыдущий commit;
  новые nullable columns не мешают старому коду.
- Новые таблицы можно удалить только после orphan/usage check и только если они
  пусты. Автоматический destructive downgrade не добавляется.
- Backfill legacy status/slug не изменяет удаляемые legacy fields и не требует
  обратной миграции для работы старого приложения.

## Критерии приёмки

- Миграции проходят с пустой БД, с `0013` и повторно; orphan/constraint checks зелёные.
- Types seeded, slug уникален, public API видит только published active places.
- Public contacts/amenities/media безопасны; internal поля отсутствуют в JSON/HTML.
- Detail page, SEO и dynamic sitemap работают только для published places.
- Map использует новый list API, filters/types/popup/detail link работают desktop/mobile.
- Superadmin редактирует новые поля, при этом CRM, booking и legacy API не ломаются.
- Unit, PostgreSQL integration, browser smoke, frontend build, Lighthouse и
  screenshot artifact `public-catalog-review` проходят.
- Итог — draft PR в `main`; merge и deploy выполняются только отдельным заданием.
