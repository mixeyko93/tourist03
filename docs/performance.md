# Производительность Owner Portal

## Воспроизводимый профиль

Mobile измеряется Lighthouse 12.8.2 с его стандартным mobile-профилем:

- viewport 412×823, device scale factor 1.75;
- simulated throttling: RTT 150 ms, throughput 1638.4 Kbit/s;
- CPU slowdown multiplier 4;
- production Vite build;
- test-приложение с теми же assets и dashboard DTO, без подмены UI-данных.

Команды:

```bash
cd frontend && npm run build
cd ..
OWNER_PORTAL_REVIEW_DIR=artifacts/owner-portal-review \
  python scripts/capture_owner_portal_review.py
python scripts/profile_owner_dashboard.py \
  --output artifacts/owner-portal-review/dashboard-api-profile.json
```

## Trace до оптимизации

Контрольный mobile run на commit `b31e835`:

- Performance 79, Accessibility 100, Best Practices 100, SEO 100;
- FCP 3470.6 ms, LCP 4081.6 ms, TBT 0 ms, CLS 0.019;
- LCP: мобильный логотип в `.owner-mobile-header`;
- 2483 ms, или 61% LCP, составляла задержка до начала загрузки LCP;
- 26 initial requests, 492678 transferred bytes;
- общий initial JS: 293944 raw / 94470 gzip;
- монолитный Owner Portal: 33375 raw / 9210 gzip;
- owner CSS: 20217 raw / 4710 gzip, из них Lighthouse считал
  неиспользованными на dashboard 11259 bytes;
- unused JS: около 141 KB в общем entry и 20.7 KB в Owner Portal;
- top long task: 56 ms в общем entry;
- render-blocking resources и third-party requests отсутствовали.

Причина была не в тяжёлом React render: TBT уже равнялся нулю. Задержку
создавали несжатая прямая выдача 294 KB общего JS, один 33 KB owner chunk,
позднее обнаружение логотипа и последовательный API waterfall
`session → dashboard`. Dashboard также загружал полную историю, proposed
payload, published snapshot, diff и 30 событий, хотя первый экран их не
использовал.

## Реализация

- `/static/*` сжимается GZip на уровне приложения, даже если Uvicorn временно
  работает без reverse proxy. Authenticated HTML и JSON намеренно не
  сжимаются этим middleware.
- Критический Manrope ExtraBold и мобильный логотип preloaded только для
  `/owner`; внешних Google Fonts нет.
- Login, dashboard, objects, editor, media uploader, history, profile и diff
  загружаются отдельными dynamic imports. Superadmin moderation остаётся
  отдельным admin route chunk.
- Dashboard выполняет один защищённый запрос вместо `session → dashboard`.
- Dashboard возвращает до 20 объектов, пять summary изменений и семь событий.
  Полные proposed/published/diff/media payloads отсутствуют.
- Список объектов и история имеют limit/offset pagination. Полный diff
  загружается только на `/owner/changes/{id}`, editor и media — после открытия
  объекта и начала редактирования.
- Quality data собираются одним агрегированным PostgreSQL query без media URL,
  caption, EXIF или room photo payload.
- Owner principal кэшируется только в `request.state`; между запросами и
  владельцами cache не разделяется.

## Контрольный результат

Локальный reproducible run после оптимизации:

- mobile: Performance 95, Accessibility 100, Best Practices 100, SEO 100;
- mobile: FCP 1512.8 ms, LCP 2797.8 ms, TBT 0 ms, CLS 0;
- desktop: Performance 100, Accessibility 100, Best Practices 100, SEO 100;
- desktop: FCP 516.4 ms, LCP 633.9 ms, TBT 0 ms, CLS 0;
- 24 initial requests, 234277 transferred bytes;
- LCP после оптимизации: `Здравствуйте, Михаил`;
- long tasks после оптимизации отсутствуют;
- единственный заметный unused JS остаток — около 40.8 KB compressed transfer
  в общем React/React Router entry. Его дальнейшее сокращение потребует
  отдельного разделения исторического CRM entry и не входит в точечную
  оптимизацию Этапа 3.2.

Точные route sizes, waterfall и Lighthouse JSON/HTML находятся в artifact
`owner-portal-review`: `bundle-report.json`, `review-metrics.json`,
`lighthouse-mobile.*`, `lighthouse-desktop.*`.

## PostgreSQL dashboard profile

Тестовый PostgreSQL 16 profile:

- `/api/owner/dashboard`: 16.57 ms;
- 6 SQL queries с учётом проверки owner session;
- response 5083 bytes;
- используется `idx_camp_owner_links_owner`;
- activity limit 7;
- response не содержит full history, proposed payload, full diff, media URL
  или notifications;
- `Cache-Control: no-store`;
- owner isolation проверена.

Значения времени зависят от машины, поэтому CI сохраняет свежий
`dashboard-api-profile.json` в artifact, а контракт и максимальное число
запросов защищены regression test.
