# API универсального каталога

## Public

| Метод и путь | Назначение |
|---|---|
| `GET /api/public/entity-kinds` | Активные крупные группы и marker metadata |
| `GET /api/public/entity-types` | Подтипы; поддерживает фильтр по виду |
| `GET /api/public/entity-schemas` | Публичные активные версии схем |
| `GET /api/public/entity-schemas/{schema_key}` | Одна разрешённая схема |
| `GET /api/public/catalog-facets` | Значения и counts для фильтров |
| `GET /api/public/entities` | Универсальный list/map/search endpoint |
| `GET /api/public/entities/{slug}` | Универсальная detail-карточка |
| `GET /places/{slug}` | SSR detail и SEO |

List принимает: `q`, `type`, `subtype`, `region`, `district`, `city`,
`amenity`, `seasonality`, `working_hours`, `children`, `pets`, `parking`,
`wifi`, `price_min`, `price_max`, `bbox`, `map_only`, `limit`, `offset`.
Повторяющиеся значения нормализуются; bbox, ranges и pagination ограничены.

List DTO лёгкий: идентификатор, slug, вид/подтип/schema, название, краткое
описание, география, координаты, cover, публичная цена, краткие contacts и
amenities. Detail дополнительно содержит allowlisted attributes,
`display_sections`, gallery, videos, contacts, working hours и — только для
размещения — rooms.

## Compatibility

```text
GET /api/public/place-types
GET /api/public/amenities
GET /api/public/places
GET /api/public/places/{slug}
GET /api/camps                 # deprecated
GET /api/camps/{id}            # deprecated
```

`places` продолжает обслуживать accommodation clients. Новые клиенты должны
использовать `entities`; отдельные endpoint-деревья для услуг, экскурсий или
проката не создаются.

## Owner

```text
GET  /api/owner/entities
POST /api/owner/entities
GET  /api/owner/entities/{entity_id}
POST /api/owner/entities/{entity_id}/changes
```

Создание принимает вид, подтип, имя, краткое описание, schema-attributes и
модель цены. Backend сверяет подтип с видом и схемой. Результат — непубличный
черновик, связанный с текущим owner; публикации напрямую нет. Дальнейшая
работа использует существующие `/api/owner/changes*`.

## Superadmin

Универсальный список использует `/api/superadmin/entities`, detail/editor —
`/api/superadmin/entities/{entity_id}`, массовая смена разрешённого
publication status — `/api/superadmin/entities/bulk`. Все маршруты защищены
superadmin session и CSRF для unsafe-методов. Архив — состояние, а не
физическое удаление.

## Ошибки и безопасность

- `404` одинаково скрывает отсутствующую и непубличную сущность;
- `422` означает invalid filter/schema payload;
- public ответы исключают owner, applicant, manager, moderation, audit,
  internal media storage keys и private contacts;
- неизвестные schema fields отклоняются;
- URL contacts/video проходят отдельные allowlists;
- response ordering детерминирован, limit не бывает неограниченным.
