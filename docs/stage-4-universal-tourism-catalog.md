# Этап 4 — универсальный каталог туристических сущностей

Статус: реализуется в `feature/universal-tourism-catalog`. Изменения остаются
за feature flag, production-БД и deploy этим этапом не затрагиваются.

## Результат

`Catalog Entity` — единый публичный и модерационный контракт для всего, что
может быть показано на карте. Размещение остаётся физически совместимым с
`catalog.camps`, но рядом с ним поддерживаются услуги, активности, питание,
транспорт, прокат, гиды, события, достопримечательности и экскурсии.

Три уровня модели:

1. `entity_kind` — крупная группа, например `accommodation` или `activity`;
2. `subtype` — управляемый справочник, например `boat-rental` или `fishing`;
3. `schema_key` + `schema_version` — версия разрешённых полей и секций карточки.

Новый вид или подтип добавляется записью справочника и подходящей схемой. Для
него не нужен отдельный public endpoint или отдельный HTML-шаблон.

## Additive migrations

- `0026_entity_taxonomy` — десять групп сущностей и расширяемые подтипы;
- `0027_entity_schemas` — versioned schema registry, универсальные поля,
  compatibility view `catalog.entities`;
- `0028_entity_workflows_indexes` — schema snapshot для заявок/изменений,
  route-contact, поисковые, картографические и workflow indexes.

`catalog.camps`, `catalog.rooms`, booking, CRM и legacy API не удаляются и не
переименовываются. Старые типы получают `entity_kind=accommodation` и
`schema_key=accommodation`. Миграции идемпотентны; destructive downgrade
намеренно отсутствует.

## Schema-driven карточки

Registry содержит схемы `accommodation`, `service`, `restaurant`, `guide` и
`excursion`. Backend:

- принимает только известные ключи, типы и display-компоненты;
- нормализует значения по декларативным ограничениям;
- не пропускает неизвестные attributes в public DTO;
- строит непустые `display_sections`;
- фиксирует версию схемы в Change Request.

Frontend использует один detail template `/places/{slug}`. Секция комнат
появляется только у размещения; продолжительность, место встречи, языки,
вместимость и стоимость выводятся согласно активной схеме.

## Public map, search и filters

Единый endpoint `/api/public/entities` обслуживает смешанную карту. Он
поддерживает полнотекстовый поиск, type/subtype, регион, район, город,
удобства, сезонность, режим работы, детей, животных, парковку, Wi-Fi,
ценовой диапазон, bbox и bounded pagination. Facets поступают из
`/api/public/catalog-facets`.

Маркеры используют один набор SVG-пиктограмм и различаются не только цветом.
Карта, popup, search, geolocation, clustering и browser-first режим остаются
общими для всех видов. Telegram SDK не требуется.

## Owner Portal и модерация

Owner Portal показывает единый список сущностей и разрешает владельцу создать
черновик размещения, услуги, активности, экскурсии или проката. Новый объект
создаётся непубличным и проходит тот же workflow:

`Черновик → Отправлено → На проверке → Одобрено → Опубликовано`

Отклонение и запрос доработок не меняют Published. Schema key/version
замораживаются в модерационной записи, поэтому изменение registry не меняет
уже отправленную заявку задним числом. Owner isolation, CSRF, audit log,
staged media и idempotent apply сохраняются.

Superadmin получает единый список, фильтрацию по виду/подтипу/статусу, поиск,
редактор, архив и ограниченные массовые изменения статуса.

## SEO и public safety

Каждая опубликованная сущность получает canonical, Open Graph, breadcrumb,
safe JSON-LD и sitemap URL. Schema.org тип выбирается из allowlist по schema
или виду. `hidden`, `unlisted`, draft, disabled и archived записи не попадают
в карту и sitemap. Public DTO не содержат owner, moderation, audit, billing,
manager или admin contacts.

## Совместимость

- `/api/public/places*` остаётся accommodation-compatible facade;
- `/api/camps*` остаётся deprecated legacy API;
- `/places/{slug}` сохраняется как единый публичный URL;
- существующие accommodation rooms/media/contacts работают без изменения;
- `FEATURE_SERVICES=false` скрывает универсальные service/activity возможности,
  не ломая опубликованные размещения.

Фильтр «Открыто сейчас» разбирает дневные и ночные интервалы из
`working_hours` и использует локальное время каталога `Asia/Irkutsk`
(Республика Бурятия). Выход в несколько часовых поясов потребует отдельного
версионированного поля и новой additive migration, без изменения исторической
схемы.

## Проверки

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv-owner/bin/python -m unittest \
  tests.test_catalog_entities tests.test_public_catalog -v
RUN_PG_INTEGRATION=1 ./.venv-owner/bin/python -m unittest \
  tests.test_catalog_migrations tests.test_universal_catalog_postgres -v
RUN_UI_SMOKE=1 ./.venv-owner/bin/python -m unittest \
  tests.test_universal_catalog_browser -v
cd frontend && npm run build
```

`npm run build` сначала запускает оба TypeScript `tsc --noEmit`, затем
production-сборку Vite.

PR workflow создаёт artifact `universal-tourism-catalog-review` с desktop и
mobile screenshots, `index.html`, browser assertions, bundle report и
Lighthouse HTML/JSON. Порог: mobile Performance ≥ 90, desktop ≥ 95,
Accessibility = 100, CLS ≤ 0,05; public initial gzip bundle не превышает
baseline Этапа 3.2 более чем на 10%.

## Rollback

До применения миграций достаточно выключить `FEATURE_SERVICES` и откатить
application commit. После test/local upgrade новые таблицы и колонки
оставляются на месте: старый код продолжает использовать `catalog.camps`.
Удаление schema registry, taxonomy или columns допускается только отдельным
согласованным изменением после backup и orphan/usage check. Production restore
выполняется только по `docs/backup-restore.md`.
