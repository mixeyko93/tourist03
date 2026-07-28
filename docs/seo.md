# SEO универсального каталога

## URL и индексация

Канонический URL любой сущности: `${PUBLIC_BASE_URL}/places/{slug}`.
`PUBLIC_BASE_URL` задаётся конфигурацией; домен не вычисляется из
недоверенного `Host`. Slug проходит строгую проверку.

В sitemap включаются только записи, для которых одновременно выполнены:

- `publication_status=published`;
- legacy status разрешает публикацию;
- `visibility=public`;
- тип и схема активны.

`unlisted`, `hidden`, draft, disabled и archived не появляются в sitemap или
карте. Robots и canonical используют тот же `PUBLIC_BASE_URL`.

## Metadata

SSR detail формирует:

- уникальные `<title>` и description;
- canonical;
- Open Graph title/description/image/url;
- `BreadcrumbList`;
- типизированный JSON-LD entity.

Schema.org выбирается из allowlist:

| Вид/схема | Schema.org |
|---|---|
| accommodation | `LodgingBusiness` |
| food / restaurant | `Restaurant` |
| guide | `ProfessionalService` |
| excursion | `TouristTrip` |
| event | `Event` |
| sight | `TouristAttraction` |
| прочие услуги/активности | `LocalBusiness` |

Если точного безопасного типа нет, используется `LocalBusiness`; произвольное
значение из БД в `@type` не проходит. JSON-LD содержит только фактически
имеющиеся публичные поля. Цена соответствует `price_mode`; «по запросу» не
превращается в выдуманное число.

## Защита вывода

- тексты проходят Jinja autoescape;
- JSON-LD создаётся сериализатором и не конкатенируется из raw HTML;
- canonical, social и media URLs проходят нормализацию;
- private contacts и moderation comments не попадают в metadata;
- calendar date сохраняется без timezone-сдвига;
- один detail template предотвращает расходящиеся SEO-реализации по типам.

Regression tests проверяют canonical, breadcrumb, JSON-LD type, sitemap,
escaping и отсутствие внутренних полей для accommodation, service и
excursion.

## Discovery pages

- `/search` и `/nearby` всегда используют `noindex,follow`; произвольные
  query/facet-комбинации не создают индексируемые страницы.
- `/collections/{slug}` и `/routes/{slug}` индексируются только при
  `status=published`.
- Published collection получает canonical, Open Graph, `BreadcrumbList` и
  `ItemList`; published route дополнительно использует `TouristTrip`.
- Sitemap включает только опубликованные collection/route URL и фактический
  `updated_at` как `lastmod`.
- Canonical строится из `PUBLIC_BASE_URL`, а не из входного `Host`.

Архивирование или выключение материала удаляет его из sitemap и публичного
projection без удаления самой записи. Search state остаётся shareable обычной
компактной ссылкой, но не становится SEO-страницей.
