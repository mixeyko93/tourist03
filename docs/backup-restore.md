# Backup и проверка восстановления

Скрипты Этапа 1.1 не меняют production автоматически. Их запускают только в утверждённое окно и с переменными окружения production, загруженными из защищённого источника.

## Backup

```bash
PYTHON_BIN=./.venv/bin/python BACKUP_ROOT=/var/backups/tourist03 ./scripts/backup.sh
```

Скрипт создаёт закрытый timestamp-каталог с:

- `database.dump` в формате `pg_dump -Fc --no-owner --no-acl`;
- `uploads.tar.gz`;
- `migrations.json` с версией runner;
- `row_counts.tsv` по таблицам `auth`, `catalog`, `crm`;
- `sha256sums.txt` и `timestamp.txt`.

Каталог `backups/` игнорируется git. Backup нельзя сохранять в tracked `archive/`, присылать в тикеты или распаковывать рядом с production uploads.

## Restore-check

Восстановление допускается только в заранее созданную БД, чьё имя содержит `test` или `restore`.

```bash
RESTORE_TEST_DB=tourist03_restore_test \
RESTORE_CONFIRM=RESTORE_TEST_DATABASE \
RESTORE_UPLOAD_DIR=/tmp/tourist03-restore-uploads \
./scripts/restore-check.sh /var/backups/tourist03/20260716T120000Z
```

Скрипт откажется работать без фразы подтверждения, с именем не-test БД или с путём live `static/uploads`. Он сверяет row counts и запускает `python -m tourist03.migrations check` против восстановленной БД. Создание test БД и выдача test-only credentials остаются ручной административной процедурой.
