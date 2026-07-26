# Персональные данные и retention заявок

Документ относится к публичным заявкам на размещение Этапа 3.1. Он описывает
технические границы хранения, но не заменяет утверждённую юридическую политику
или назначение ответственного за персональные данные.

## Разделение данных

- Applicant contacts (`applicant_*`) доступны только авторизованному
  superadmin и используются для модерации/уведомлений.
- Public contacts хранятся отдельно, проходят allowlist нормализацию и только
  они переносятся в будущую карточку объекта.
- IP и User-Agent не хранятся в исходном виде: записывается keyed SHA-256 со
  стабильным server secret.
- Raw draft/tracking tokens в PostgreSQL не сохраняются. В БД находятся только
  hashes; tracking token передаётся во fragment URL, чтобы не попадать в
  HTTP logs и Referer.
- Internal notes, spam score, consents metadata и audit не входят в public DTO.
- Audit не содержит полные form payload, фотографии, raw tokens и applicant
  contacts. `crm.audit_log` и status history защищены от UPDATE/DELETE trigger.

## Сроки

| Категория | Default | Настройка |
|---|---:|---|
| Abandoned draft | 30 дней | `SUBMISSION_RETENTION_ABANDONED_DAYS` |
| Staged/orphan upload | 48 часов | `SUBMISSION_UPLOAD_TTL_HOURS` |
| Rejected/withdrawn submission | 365 дней | `SUBMISSION_RETENTION_REJECTED_DAYS` |
| Technical anti-spam data | 90 дней | `SUBMISSION_RETENTION_TECHNICAL_DAYS` |

Связь опубликованной заявки и status history хранится, пока существует
связанный catalog object либо пока не утверждена отдельная policy удаления.

## Очистка

`SUBMISSION_CLEANUP_ENABLED=false` по умолчанию. При выключенной настройке
retention helpers только определяют границы, но ничего не удаляют.

При осознанном включении staff bot worker выбирает только expired
`status=staged` media через `FOR UPDATE SKIP LOCKED`, помечает metadata
удалённой и удаляет original/thumbnail из общего `UPLOAD_DIR`. Web и worker
обязаны видеть один и тот же upload volume. Удаление rejected submissions,
applicant contacts или audit автоматически не реализовано и требует отдельной
задачи, privacy review, backup и dry-run.

## Доступ и инциденты

- Public status требует пару `public_number` + secret tracking token и отдаёт
  только allowlisted status fields.
- Staged preview использует случайный unguessable token и прекращает работать
  после expiry/deletion.
- Superadmin mutations защищены session authentication, CSRF и optimistic
  `content_version`.
- При подозрении на утечку сначала выключить feature flag, сохранить audit и
  outbox evidence, затем действовать по
  `docs/security-incident-response.md`. Не удалять данные и uploads как способ
  сокрытия инцидента.

До production enablement владелец продукта должен утвердить публичный текст
согласия, фактические сроки, privacy contact и процедуру исполнения запросов
субъектов данных.
