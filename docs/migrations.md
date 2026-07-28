# Миграции каталога и заявок

Текущая обязательная версия: `0028_entity_workflows_indexes`. Приложение не применяет миграции при импорте или startup.

## Цепочка Этапа 2.2

- `0014_place_types` — расширяемый справочник и 12 seed-типов.
- `0015_universal_camp_fields` — slug, type, география, публикация, timestamps, public compatibility fields.
- `0016_public_contacts` — канонические публичные контакты без owner/manager/admin данных.
- `0017_catalog_amenities` — 16 seed-удобств, связи, media metadata, indexes и validation constraints.

Все revisions additive. `catalog.camps`, legacy columns, photo tables, rooms, CRM и booking сохраняются.

## Цепочка Этапа 3.1

- `0018_moderation_submissions` — схема `moderation`, заявки, opaque token hashes, optimistic locking;
- `0019_submission_media` — staged images, preview tokens, TTL и metadata;
- `0020_submission_history_notes` — immutable status history и notes;
- `0021_submission_outbox` — Telegram/email outbox, dedupe, retry и связь с заявкой;
- `0022_submission_indexes` — FK, checks, cover/anti-abuse/retention indexes и immutable `crm.audit_log`.

Migration integration строит точное состояние `0017_catalog_amenities`, сохраняет
существующие catalog/CRM записи, дважды применяет `0018`–`0022` и проверяет
запрет UPDATE/DELETE для status history и audit.

## Цепочка Этапа 3.2

- `0023_owner_identity` — отдельные owner accounts, reset/login events и связи
  владельцев с несколькими объектами;
- `0024_owner_change_requests` — Published/Proposed snapshots, staged media,
  immutable history и notes;
- `0025_owner_integrity_outbox` — внешние ключи, status/role checks, индексы и
  owner references в существующем notification outbox.

Revisions additive и по умолчанию недоступны продукту из-за двух feature flags.
Integration suite применяет всю цепочку на чистом PostgreSQL и проверяет
изоляцию владельцев, неизменность Published до approve, rejection,
идемпотентный apply и отсутствие raw reset token.

## Цепочка Этапа 4

- `0026_entity_taxonomy` — 10 верхнеуровневых видов, новые подтипы и связь
  существующих `place_types` с видом/default schema;
- `0027_entity_schemas` — versioned schema registry, universal fields и
  compatibility view `catalog.entities`;
- `0028_entity_workflows_indexes` — schema snapshot в owner/submission
  workflow, контакт `route`, public search/map/facet и moderation indexes.

Seed схем версии 1 в `0027_entity_schemas` хранится literal-значениями внутри
исторической миграции. Runtime registry не меняет уже выпущенную миграцию:
новые поля и правила получают новую версию схемы и отдельную additive
migration.

Миграции additive: `catalog.camps`, rooms, booking, CRM, owners и история
модерации сохраняются. Upgrade integration строит состояние ровно на `0025`,
добавляет legacy accommodation, owner link, Change Request и placement
submission, применяет новую цепочку дважды и проверяет backfill/schema freeze.

## Команды

```bash
python -m tourist03.migrations status
python -m tourist03.migrations check
python -m tourist03.migrations upgrade
```

Сначала выполнять `status`, затем backup/restore-check, после этого `upgrade`
в утверждённом окне и повторный `check`. В CI upgrade проверяется на пустом
PostgreSQL; integration suite отдельно проверяет каталожную цепочку с `0013`,
заявки с `0017` и universal catalog с `0025`.

## Backfill

- active/published legacy objects → `publication_status=published`;
- archived → `archived`, прочие → `disabled`;
- slug транслитерируется один раз, конфликт получает `-{id}`;
- default type — `recreation-base`;
- short description берётся из existing description;
- phone/site переносятся только из явно публичных legacy fields;
- owner, manager и admin phones никогда не становятся public contacts.

Slug не меняется автоматически при последующем переименовании. `updated_at` и `content_version` обновляет trigger; `published_at` появляется при первой публикации.

## Проверки после upgrade

```sql
SELECT version FROM public.schema_migrations ORDER BY version;
SELECT COUNT(*) FROM catalog.entity_kinds;   -- 10
SELECT COUNT(*) FROM catalog.entity_schemas; -- 5
SELECT COUNT(*) FROM catalog.place_types;    -- 31
SELECT COUNT(*) FROM catalog.amenities;      -- 16
SELECT COUNT(*) FROM catalog.camps WHERE slug IS NULL OR place_type_id IS NULL OR publication_status IS NULL;
SELECT lower(slug), COUNT(*) FROM catalog.camps GROUP BY lower(slug) HAVING COUNT(*) > 1;
SELECT to_regclass('moderation.placement_submissions');
SELECT to_regclass('moderation.submission_media');
SELECT COUNT(*) FROM moderation.submission_media WHERE status='staged' AND expires_at <= NOW();
SELECT to_regclass('auth.owner_accounts');
SELECT to_regclass('moderation.owner_change_requests');
SELECT to_regclass('catalog.entities');
SELECT COUNT(*) FROM catalog.camps WHERE schema_key IS NULL OR schema_version IS NULL;
SELECT COUNT(*) FROM moderation.owner_change_requests WHERE schema_key IS NULL OR schema_version IS NULL;
```

Для фильтров проверить `EXPLAIN (ANALYZE, BUFFERS)` по publication/type/region/city. На локальном acceptance query использовал `idx_camps_region_publication`; list payload 6 объектов — 2690 байт, p95 10,69 мс, detail — 3782 байта.

## Rollback

Автоматического destructive downgrade нет. Для заявок application rollback
начинается с `FEATURE_PLACEMENT_SUBMISSIONS=false` и оставляет additive
`moderation` schema/outbox columns. Удаление новых структур допускается только
отдельным согласованным изменением после backup, отката приложения и проверки
отсутствия нужных заявок/связанных catalog drafts. Production restore
выполняется только по runbook `docs/backup-restore.md`; dumps и uploads не
удаляются.

Для Owner Portal первый rollback — выключить
`FEATURE_OWNER_CHANGE_REQUESTS`, затем `FEATURE_OWNER_PORTAL`. Schema, staged
media, audit и outbox при этом сохраняются. Уже применённые одобренные
изменения не откатываются автоматически: восстановление published snapshot
требует нового проверяемого Change Request либо отдельного согласованного
restore. Destructive downgrade отсутствует.

Для универсального каталога первый rollback — `FEATURE_SERVICES=false`.
Taxonomy, registry, attributes и schema snapshots при этом сохраняются.
Используемые версии схем защищены FK; удалять их или `catalog.entities`
автоматически запрещено.
