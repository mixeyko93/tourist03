# Архитектура Туристики

## Контуры

| Контур | UI | Backend | Данные |
|---|---|---|---|
| Публичный каталог | SSR + browser-first JavaScript, Leaflet | FastAPI public API | `catalog.*` через public allowlist |
| Owner Portal | React, route-level chunks | `/api/owner/*` | owner links, proposed changes, audit/outbox |
| Superadmin | React | `/api/superadmin/*` | moderation, catalog editor, audit |
| CRM | React | защищённые internal routes | camps, rooms, booking |
| Telegram bot | aiogram | те же сервисные границы | без обязательности для browser UI |

## Универсальный каталог

```text
entity kind
  └── subtype
        └── schema key + immutable version
              └── catalog entity (compatibility storage: catalog.camps)
                    ├── contacts
                    ├── amenities
                    ├── media / videos
                    ├── accommodation rooms
                    └── schema-validated attributes
```

`catalog.entities` — read model, а не новая конкурирующая master table.
Физическое хранение в `catalog.camps` сохраняет CRM, booking и старые
интеграции. Taxonomy и schema registry добавляют универсальность без
data migration с высоким риском.

## Границы доверия

- Repository использует параметризованный SQL и возвращает внутренние rows.
- Service применяет visibility/publication rules, schema validation и
  формирует allowlisted DTO.
- Public API никогда не сериализует внутреннюю ORM/SQL-запись напрямую.
- Jinja использует autoescape; JSON-LD сериализуется как данные, а не HTML.
- Owner пишет только Proposed; Superadmin decision/apply отделены.
- Audit/history append-only, уведомления проходят существующий outbox.

## Версионирование схем

Сущность и модерационная запись хранят `schema_key` и `schema_version`.
Registry version не редактируется задним числом: новая форма создаётся новой
версией, а старые карточки продолжают рендериться по прежнему контракту.
Allowlist компонентов защищает schema-driven rendering от произвольного кода.

## Feature flags

- `FEATURE_SERVICES` — universal service/activity catalog;
- `FEATURE_OWNER_PORTAL` — owner UI/API;
- `FEATURE_OWNER_CHANGE_REQUESTS` — Proposed/moderation workflow;
- `FEATURE_PLACEMENT_SUBMISSIONS` — публичная форма заявки.

Флаги не применяют миграции. Миграции запускаются только явной командой.
Deployment и production upgrade выполняются отдельным утверждённым процессом.

Подробности: [Этап 4](stage-4-universal-tourism-catalog.md),
[API](api.md), [Entity Schemas](entity-schemas.md), [SEO](seo.md).
