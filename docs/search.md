# Туристический поиск

## Контракт

`GET /api/public/search` объединяет опубликованные Catalog Entity,
редакционные подборки и маршруты. URL `/search` хранит состояние в компактных
query params и поддерживает refresh, back/forward и обычный share.

Поиск нормализует Unicode, регистр, `ё/е`, дефисы и пробелы, затем безопасно
расширяет запрос конфигурируемыми синонимами и кириллическо-латинской
транслитерацией. PostgreSQL использует weighted `tsvector` с русским словарём,
GIN и опциональную trigram similarity. Без `pg_trgm` сохраняются FTS,
prefix/contains и детерминированный tie-breaker.

## Ranking

Приоритет: exact name → name prefix → slug → alias → kind/type → location →
tags → amenities → descriptions → ограниченный editorial/freshness/quality
boost. Numeric score не отдаётся; UI показывает только понятные причины
совпадения. Платного продвижения нет.

## Facets и безопасность

Поддерживаются source, kind, type/subtype, region, district, city, tags,
amenities, season, route difficulty/duration и collection audience. Nearby
радиус живёт в отдельном bounded-сценарии. Все параметры ограничены,
slug-списки нормализуются, SQL параметризован, snippets остаются plain text.
Draft/internal/owner/applicant поля не входят в projection.

Autocomplete использует debounce, AbortController и клавиатурную модель
Arrow Up/Down, Enter, Escape с live announcement. Недавние запросы — только
локально, максимум 10. `/search` всегда `noindex,follow`.
