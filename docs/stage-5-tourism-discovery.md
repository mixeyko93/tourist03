# Этап 5: туристический поиск, подборки и маршруты

## Статус и границы

Документ подготовлен до массовых изменений кода в ветке
`feature/tourism-discovery`, созданной от `origin/main`
`38209a79f354bd1e4ba2dc43e469204d2f3dd3be`.

Этап развивает публичный browser-first контур, каталог и Superadmin. Он не
меняет booking/CRM-контракт, Owner Portal, moderation и submission workflow.
Telegram, туристические аккаунты, персональные рекомендации, отзывы,
бронирование, оплата, внешний поисковый SaaS и автоматическая GPS-навигация
не входят в этап.

Все новые возможности по умолчанию выключены:

- `FEATURE_DISCOVERY_SEARCH`;
- `FEATURE_EDITORIAL_COLLECTIONS`;
- `FEATURE_TOURISM_ROUTES`;
- `FEATURE_NEARBY_DISCOVERY`;
- `FEATURE_RELATED_ENTITIES`;
- `FEATURE_LOCAL_RECENT_HISTORY`.

Отключённая возможность отвечает `404` на собственных страницах и API, не
добавляет тяжёлые ресурсы в первый экран и не меняет поведение Этапа 4.

## Результат предварительного аудита

### Каталог и публичный контур

- Универсальная сущность продолжает храниться в `catalog.camps`; тип задают
  `catalog.entity_kinds`, `catalog.place_types`, `schema_key` и
  `schema_version`.
- Публичный `/api/public/entities` уже фильтрует только `published`,
  `active/published`, `public` сущности и поддерживает kinds, subtypes,
  географию, amenities, цены и bbox.
- Текущий текстовый фильтр строит `to_tsvector('simple', ...)` во время
  запроса, использует `websearch_to_tsquery` и несколько `ILIKE`, но не имеет
  русского словаря, централизованной нормализации и relevance sort.
- `idx_camps_public_search` — GIN по `simple`-вектору названия, описаний и
  адресных полей. Его сохраняем для совместимости; новый индекс добавляем
  отдельно.
- Карта — Leaflet с MarkerCluster и chunked loading. API-загрузка маркеров
  пакетная, карта остаётся центральным элементом первого экрана.
- Detail pages рендерятся на сервере через Jinja, имеют canonical, Open Graph,
  JSON-LD и человекочитаемую дату. Sitemap сейчас содержит главную и
  опубликованные сущности.
- Public frontend — независимые ES modules в `static/public`; карта
  lazy-loadится после пересечения viewport или взаимодействия.

### Управление и workflows

- Superadmin — React Router с route-level lazy imports и сессионной защитой.
  Существующие catalog, audit и optimistic-locking паттерны переиспользуются.
- Owner Portal, заявки и change requests используют текущий schema-driven
  каталог. Владельцы могут предлагать изменения сущностей через модерацию, но
  не создают публичные теги, подборки или маршруты.
- Audit хранится в существующем системном журнале; отдельную систему событий
  для редакционного контента создавать не требуется.
- Legacy `/api/camps`, CRM и booking остаются accommodation-only и не должны
  зависеть от discovery-таблиц.

### PostgreSQL, производительность и CI

- Локальный PostgreSQL: 16.11; development host — `localhost`, production не
  подключён.
- Текущая миграция: `0028_entity_workflows_indexes`.
- Русская конфигурация PostgreSQL FTS доступна штатно.
- `pg_trgm` 1.6 и `unaccent` 1.1 доступны на сервере, но не установлены.
  Миграции не должны требовать права `CREATE EXTENSION`.
- PostGIS не доступен и для текущего масштаба не нужен.
- Координатные и публикационные индексы Этапа 4 уже пригодны для предварительного
  bbox-фильтра.
- Одобренный baseline initial public CSS/JS: 68 019 gzip bytes, предельное
  значение +10% — 74 821 bytes. Новый review сохраняет тот же принцип:
  discovery-модули не входят в initial route до взаимодействия.
- Базовые бюджеты: desktop Performance не ниже 95, mobile не ниже 90,
  Accessibility 100, CLS не выше 0,05, mobile LCP не выше 2,8 секунды.
- Общий CI уже выполняет Python unit/compile, frontend unit/build, PostgreSQL
  migrations/integration, secret scan, npm audit и pip-audit. Для Этапа 5
  нужен отдельный visual/performance workflow.

## Архитектура

Новая подсистема изолируется в слоях:

- `tourist03/domain/discovery.py` — нормализация, validation, Haversine,
  GeoJSON и детерминированные веса;
- `tourist03/repositories/discovery.py` — параметризованные SQL-запросы,
  транзакции, optimistic locking и query projections;
- `tourist03/services/discovery.py` — feature gates, DTO orchestration,
  cache policy и публичные use cases;
- `tourist03/routers/discovery.py` — публичный и Superadmin API;
- `tourist03/dto/discovery.py` — строгие request/response models;
- Jinja-шаблоны и отдельные `static/public/discovery-*.js/css` — SSR и
  browser UX;
- lazy React routes — только для редакторов Superadmin.

Публичные запросы не возвращают внутренние notes, created/updated actor ids,
владельцев, контакты заявителей, moderation payload или draft references.

## Поиск

### Нормализация

Backend-сервис создаёт безопасное представление запроса:

1. Unicode normalization и lower case;
2. замена `ё` на `е`;
3. нормализация дефисов, punctuation и повторных пробелов;
4. ограничение длины и числа tokens;
5. распознавание кириллицы и латиницы;
6. двунаправленная предсказуемая transliteration;
7. расширение только по versioned synonym config;
8. дедупликация вариантов и жёсткий лимит расширений.

Конфигурация содержит синонимы и сокращения вроде `SUP/сап`,
`ATV/квадроцикл/квадрик`, `баня/сауна`, `тур/экскурсия`,
`СПб/Питер/Санкт-Петербург`, `Подмосковье/Московская область`.
Frontend не является источником search semantics.

### Индекс

Аддитивная миграция добавляет нормализованное поисковое поле и weighted
`tsvector` для опубликованного контента. Вектор использует русский словарь и
разные веса:

- A: name, slug и aliases;
- B: kind/type, location и tags;
- C: amenities и short description;
- D: full description.

GIN индекс обслуживает основной FTS. Если `pg_trgm` уже установлен или
создание расширения разрешено, условно создаются trigram indexes для name,
slug и normalized text. Без расширения prefix/limited typo fallback работает
на безопасных `ILIKE`/similarity-independent правилах и не ломает запуск.
`unaccent` не является обязательным: русско-латинские варианты формирует
application normalization.

Поисковые документы подборок и маршрутов формируются отдельно, чтобы не
раздувать строку `catalog.camps` и не смешивать статусы.

### Ранжирование

Score вычисляется сервером и имеет стабильный tie-breaker:

1. точное normalized name;
2. name prefix;
3. точный slug;
4. точный alias;
5. kind/type/subtype;
6. region/city;
7. shared tags;
8. amenities;
9. short description;
10. full description;
11. ограниченный editorial boost;
12. `confirmed_at`/`updated_at` freshness;
13. существующий quality/completeness signal;
14. `lower(title/name), source kind, id` как финальный порядок.

Exact match получает независимый верхний класс, поэтому editorial weight не
может вытеснить релевантное точное совпадение. Numeric score не показывается
пользователю. Для каждого результата backend может вернуть безопасные match
reasons и plain-text snippet; HTML/highlight строится DOM API во frontend.

### Suggestions, popular и local history

Suggestions объединяют сущности, географию, теги, подборки и маршруты,
группируют тип результата и возвращают небольшой payload. UI использует
debounce, AbortController, `aria-activedescendant`, Arrow Up/Down, Enter,
Escape и live announcements.

Popular — агрегированный allowlisted результат, а не сырые редкие запросы.
Точная поисковая строка не попадает в публичный список до достижения порога.
Recent searches/views хранятся только в browser storage, максимум 20 записей,
очищаются пользователем и никогда не синхронизируются.

## Теги

Добавляются:

- `catalog.tags`;
- `catalog.entity_tags`.

Slug уникален без учёта регистра; category, icon key, sort order и active
валидируются. Связь имеет уникальную пару `(entity_id, tag_id)` и индексы в
обоих направлениях. Теги участвуют в поиске, facets, rules и рекомендациях.
Owner Portal может предложить только уже существующие теги через change
request; создание нового публичного тега остаётся у редакции.

## Редакционные подборки

Добавляются `content.collections`, `content.collection_items` и
`content.collection_rules`. Типы: `manual`, `rule_based`, `mixed`; статусы:
`draft`, `in_review`, `published`, `disabled`, `archived`.

Rules — строго типизированный JSON DSL с allowlist полей и операторов. Он
компилируется repository-слоем в параметризованный SQL; произвольный SQL,
имена таблиц и raw fragments запрещены. Mixed collection сначала применяет
ручной порядок, затем дедуплицированные rule results.

Публикация требует уникального slug, title, short description, SEO metadata,
обложки или утверждённого placeholder и минимум трёх опубликованных элементов,
если Superadmin явно не указал документированное editorial exception.
Публичный projection повторно проверяет статус каждого элемента.

## Туристические маршруты

Добавляются `content.routes` и `content.route_points`. Маршрут является
редакционной последовательностью, а не GPS-навигацией. Точка ссылается на
published Catalog Entity либо содержит собственный title, description и
координаты.

Для публикации требуется минимум две уникально упорядоченные точки. Draft
preview может показывать draft entity только авторизованному Superadmin;
публичный projection такую связь исключает.

GeoJSON допускает только LineString/MultiLineString в ограниченном payload:
валидные longitude/latitude, лимит координат, depth и properties, без
исполняемых/произвольных полей. Сложная геометрия отклоняется или упрощается
до сохранения. Автоматическая маршрутизация и обещание навигационной точности
отсутствуют.

## Nearby

`/nearby` сначала объясняет запрос геолокации. Координаты передаются только
для текущего API-запроса, не записываются в БД, логи, analytics или local
history.

Repository:

1. валидирует lat/lng и радиус из allowlist 5/10/25/50/100 км;
2. рассчитывает bounding box;
3. применяет существующие numeric coordinate indexes;
4. вычисляет Haversine только для ограниченного набора кандидатов;
5. сортирует по distance и deterministic id tie-breaker.

Fallback: последняя точка карты в текущей browser session, выбранный город,
ручная точка или общая карта. PostGIS не внедряется.

## Рекомендации

Детерминированный service использует конфигурируемые положительные веса:
same type/subtype, shared tags/amenities, same region/city, nearby distance,
shared collection/route, editorial boost и freshness. Текущая сущность и
непубличный контент исключаются до scoring.

Ответ содержит reason (`Рядом`, `Похожий тип`, `В этом регионе`,
`В этой подборке`, `В этом маршруте`), но не numeric score. История туриста
и персональный профиль не используются.

## API

Публичные endpoints:

- `GET /api/public/search`;
- `GET /api/public/search/suggestions`;
- `GET /api/public/search/popular`;
- `GET /api/public/nearby`;
- `GET /api/public/entities/{slug}/related`;
- `GET /api/public/entities/{slug}/nearby`;
- `GET /api/public/collections`;
- `GET /api/public/collections/{slug}`;
- `GET /api/public/routes`;
- `GET /api/public/routes/{slug}`;
- `GET /api/public/discovery/home`.

Все endpoints имеют Pydantic validation, max limits, pagination,
детерминированную сортировку, отдельный read rate limit, payload budget и
published-only repository query. Cache policy:

- search/suggestions/nearby — private или short public cache без координат в
  shared key;
- collection/route/detail — short public cache с Last-Modified/ETag;
- discovery home — short public cache;
- Superadmin — `no-store`.

List responses не содержат галереи и тяжёлые attributes. Related data
загружается пакетно, без N+1.

## Public UI, карта и share

SSR routes:

- `/search` — `noindex,follow`, canonical без произвольной query;
- `/collections/{slug}` — index только для published;
- `/routes/{slug}` — index только для published;
- `/nearby` — `noindex,follow`.

Главная сохраняет map-first: начало карты находится не дальше 650 px от
верхнего края на desktop и 580 px на mobile. Компактный поиск остаётся у
карты; подборки, направления, маршруты, nearby и недавно обновлённые элементы
располагаются после неё либо lazy-loadятся.

Search state хранится в компактных query params с allowlist. Переход к
сущности может открыть marker по slug/id; back/forward восстанавливает query,
filters и viewport без сериализации JSON в URL. Collection и route modes
подсвечивают соответствующие точки, сохраняя chunked loading.

Share использует Web Share API и безопасный fallback копирования ссылки.
Telegram SDK не подключается.

## SSR, SEO и sitemap

Published collection и route получают unique title/description, canonical,
Open Graph, breadcrumbs и JSON-LD (`ItemList`, `TouristTrip` или ближайший
подходящий тип). `lastmod` берётся из фактического `updated_at`.

Sitemap расширяется отдельными published entries; при оправданном объёме
разделяется на entities/collections/routes через sitemap index. Draft,
disabled, archived и бесконечные search/filter combinations не индексируются.

## Superadmin

Добавляются lazy routes «Подборки» и «Маршруты». Редакторы используют
существующие session/CSRF/audit patterns:

- list/search/filter/create/edit;
- preview публичной страницы и rule result;
- attach/sort entities или route points;
- SEO preview;
- publish/disable/archive;
- optimistic locking через `content_version`;
- идемпотентная защита от повторной публикации;
- audit с actor, target, old/new metadata.

Route drag sorting всегда сохраняет явные целочисленные positions.
Конфликт версии возвращает `409` с понятным сообщением, а не перезаписывает
чужие изменения.

## Безопасность и privacy

- Только параметризованный SQL; FTS query строится из нормализованных tokens.
- Regex в request path не применяется к неограниченному пользовательскому
  тексту.
- Snippets — plain text; frontend не вставляет trusted HTML.
- Slug, bbox, radius, pagination, GeoJSON, rules и sort keys имеют allowlist и
  верхние границы.
- Публичные projections повторно проверяют publication/visibility и не
  раскрывают draft entity через collection/route.
- Redirect/share/media URLs проходят существующую http(s) validation.
- Rate-limit распространяется на search, suggestions и nearby.
- Точные координаты туриста не сохраняются и не попадают в analytics.
- Analytics агрегированы; raw query retention ограничен, редкие и
  чувствительные запросы исключаются из popular.
- Cache keys нормализованы; ответы с координатами не допускаются в общий cache.

## Миграции и rollback

Аддитивный порядок после `0028`:

1. tags и entity_tags;
2. search fields/vector/indexes и optional extensions;
3. collections/items/rules;
4. routes/points;
5. discovery-specific composite indexes;
6. analytics aggregate structure только при фактической необходимости.

Проверяются upgrade от main, clean DB, повторный upgrade, migration check и
readiness. Никаких destructive rename/drop и production migration.

Rollback приложения: выключить шесть feature flags и вернуть application
commit. Новые unused таблицы и индексы остаются на месте до отдельного
согласованного удаления после backup/usage check. Optional extensions не
являются условием запуска старого или нового кода.

## Проверки и бюджеты

Backend/unit покрывают normalization, exact/prefix/typo/transliteration/
synonym ranking, tags, filters, snippets, pagination, rules, publication,
GeoJSON, nearby и deterministic recommendations.

PostgreSQL integration покрывает migration from main/clean/repeat, Russian
FTS, extension fallback, EXPLAIN/index use, no draft leak, collections,
routes, nearby и regression универсального каталога, Owner Portal,
moderation, submissions, CRM и legacy API.

Browser desktop/mobile покрывает homepage, autocomplete keyboard/mobile,
search/filters/map transition, empty/loading/error, collection, route,
nearby permission/denial/fallback, related, share, local history,
back/forward, direct refresh, reduced motion и отсутствие Telegram.

Review artifact `tourism-discovery-review` содержит `index.html`,
`review-metrics.json`, `bundle-report.json`, API/SQL metrics,
Lighthouse HTML/JSON и согласованный набор desktop/mobile/Superadmin PNG.

Критические бюджеты:

- initial public gzip growth не более 10% относительно зафиксированного
  baseline;
- desktop Performance не ниже 95;
- mobile Performance не ниже 90;
- Accessibility ровно 100;
- CLS не выше 0,05;
- mobile LCP не выше 2,8 секунды;
- начало карты не дальше 650 px от верха desktop и 580 px от верха mobile;
- search/suggestions/nearby измеряются p50/p95, payload и SQL query count;
- list payload не содержит gallery/media originals.

## Критерии завершения

Этап готов к визуальной приёмке только когда поиск и русский ranking
стабильны, autocomplete доступен, collections/routes/nearby/related работают,
draft content не доступен, геолокация не сохраняется, карта остаётся
map-first, Superadmin управляет редакционным контентом, SEO/sitemap корректны,
регрессии Owner Portal/moderation/CRM/legacy отсутствуют, все проверки и CI
зелёные, artifact опубликован, а PR остаётся draft.

Merge, deploy и production migrations в рамках реализации Этапа 5 не
выполняются.
