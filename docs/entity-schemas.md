# Entity Schemas

## Назначение

Entity Schema — versioned декларативный контракт type-specific полей. Он
управляет backend validation, public DTO, секциями detail-карточки и
Schema.org mapping. Схема не содержит исполняемый код, HTML или имена
произвольных React-компонентов.

Встроенные версии:

- `accommodation@1`;
- `service@1`;
- `restaurant@1`;
- `guide@1`;
- `excursion@1`.

## Формат registry

```json
{
  "schema_key": "service",
  "version": 1,
  "title": "Услуга или активность",
  "applicable_kinds": ["service", "activity", "transport", "rental"],
  "fields": [
    {
      "key": "duration_minutes",
      "label": "Продолжительность",
      "type": "integer",
      "section": "service",
      "public": true,
      "required": false,
      "min": 1,
      "max": 100800,
      "unit": "мин"
    }
  ],
  "sections": [
    {
      "key": "service",
      "title": "Об услуге",
      "component": "facts",
      "fields": ["duration_minutes"]
    }
  ],
  "validation": {"additional_properties": false},
  "display": {"detail_layout": "service", "marker_style": "brand"},
  "schema_org_type": "LocalBusiness",
  "quality_keys": ["name", "description", "photos"]
}
```

Разрешённые field types: `string`, `integer`, `number`, `boolean`, `enum`,
`string_list`. Разрешённые display components: `summary`, `facts`, `pricing`,
`rooms`, `amenities`, `contacts`, `gallery`, `schedule`, `map`.

## Правила

- `schema_key` и field keys имеют ограниченный ASCII-формат;
- version — положительное целое;
- каждый field key уникален;
- section ссылается только на зарегистрированные fields;
- unknown descriptor keys и components отклоняются;
- numeric ranges, length и list limits проверяются backend;
- boolean не принимает строки `"true"`/`"false"`;
- unknown entity attributes отклоняются, а не молча публикуются;
- `public=false` исключает поле из `display_sections`;
- пустая секция не рендерится;
- quality weights применяются только к ключам активной схемы.

## Изменение схем

Опубликованную версию не правят несовместимо. Для нового контракта:

1. добавить новую версию registry;
2. добавить additive migration seed;
3. научить backend читать обе версии;
4. добавить unit/API/browser regression;
5. переводить сущности явным модерируемым изменением.

Change Request хранит schema snapshot (`schema_key`, `schema_version`).
Удалять используемую версию запрещено FK. Новая schema не разрешает владельцу
обойти Proposed → moderation → Published.

## Добавление нового подтипа

Подтип связывается с существующими `entity_kind` и default schema. Если
набор полей уже подходит, код detail page не меняется. Новая схема нужна
только при действительно новом наборе валидируемых данных, а новая UI
компонента — только после отдельного allowlist и accessibility review.
