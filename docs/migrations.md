# Миграции универсального каталога

Текущая обязательная версия: `0017_catalog_amenities`. Приложение не применяет миграции при импорте или startup.

## Цепочка Этапа 2.2

- `0014_place_types` — расширяемый справочник и 12 seed-типов.
- `0015_universal_camp_fields` — slug, type, география, публикация, timestamps, public compatibility fields.
- `0016_public_contacts` — канонические публичные контакты без owner/manager/admin данных.
- `0017_catalog_amenities` — 16 seed-удобств, связи, media metadata, indexes и validation constraints.

Все revisions additive. `catalog.camps`, legacy columns, photo tables, rooms, CRM и booking сохраняются.

## Команды

```bash
python -m tourist03.migrations status
python -m tourist03.migrations check
python -m tourist03.migrations upgrade
```

Сначала выполнять `status`, затем backup/restore-check, после этого `upgrade` в утверждённом окне и повторный `check`. В CI upgrade проверяется на пустой PostgreSQL; integration suite дополнительно строит состояние ровно `0013_admin_profile_pins`, добавляет legacy данные и применяет `0014`–`0017` дважды.

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
SELECT COUNT(*) FROM catalog.place_types; -- 12
SELECT COUNT(*) FROM catalog.amenities;    -- 16
SELECT COUNT(*) FROM catalog.camps WHERE slug IS NULL OR place_type_id IS NULL OR publication_status IS NULL;
SELECT lower(slug), COUNT(*) FROM catalog.camps GROUP BY lower(slug) HAVING COUNT(*) > 1;
```

Для фильтров проверить `EXPLAIN (ANALYZE, BUFFERS)` по publication/type/region/city. На локальном acceptance query использовал `idx_camps_region_publication`; list payload 6 объектов — 2690 байт, p95 10,69 мс, detail — 3782 байта.

## Rollback

Автоматического destructive downgrade нет. При application rollback оставить additive schema на месте. Удаление новых структур допускается только отдельным согласованным изменением после backup, отката приложения и проверки отсутствия данных/ссылок. Production restore выполняется только по runbook `docs/backup-restore.md`; dumps и uploads не удаляются.
