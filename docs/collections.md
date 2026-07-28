# Редакционные подборки

Подборки хранятся в `content.collections`, элементы — в
`content.collection_items`, правила — в `content.collection_rules`. Типы:
`manual`, `rule_based`, `mixed`; статусы: `draft`, `in_review`, `published`,
`disabled`, `archived`.

Rule JSON проходит allowlist-валидацию и компилируется только в
параметризованный SQL. Произвольные SQL/operator/table fragments запрещены.
Public projection повторно проверяет публикацию каждой Catalog Entity и не
раскрывает draft content.

Публикация требует title/slug/cover/short description/SEO и минимум три
опубликованных элемента, кроме явного editorial exception. Сезон и аудитория
управляются редактором, а не вычисляются автоматически по месяцу.

`/collections/{slug}` — SSR page с canonical, Open Graph, breadcrumbs,
`ItemList`, картой и share. Superadmin поддерживает preview, сортировку,
rules preview, SEO, статусы, audit и optimistic locking. Владельцы объектов
не создают подборки напрямую.
