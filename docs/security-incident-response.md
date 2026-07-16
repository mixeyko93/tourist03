# План реагирования на потенциальную компрометацию

## Область инцидента

В git отслеживаются файлы:

- `archive/db/tourist03.sql`;
- `archive/db/tourist03.dump`.

SQL dump содержит строки из таблиц пользователей, bearer-токенов, CRM accounts, объектов, фотографий, апартаментов, бронирований и связей управляющих. Сами секреты и персональные значения в этом документе не приводятся.

Существующие tracked dumps и uploads в рамках Этапа 1.1 не удаляются. Git history не переписывается.

## Потенциально затронутые категории

- имена, телефоны и email туристов;
- открытые bearer-токены `auth.user_tokens`;
- login/password hashes управляющих;
- данные бронирований и комментарии;
- контакты владельцев/управляющих;
- идентификаторы Telegram, если присутствовали в более новых dumps/history;
- DB/session/API/bot/SMTP secrets, если они когда-либо попадали в tracked файлы или commit history.

Наличие каждой категории нужно проверять без вывода значений в терминал, тикеты или отчёты.

## Приоритет ротации

1. Открытые bearer/API/session tokens.
2. Пароли пользователей панелей и bootstrap credentials.
3. Telegram/VK bot tokens и webhook-related credentials.
4. PostgreSQL credentials.
5. SMTP credentials.
6. Остальные интеграционные secrets.

## Обязательная последовательность

1. Снять новый зашифрованный backup production-БД и uploads вне git.
2. Проверить restore backup в отдельной test database.
3. Сменить пароли затронутых учётных записей.
4. Отозвать bearer/API/reset/link tokens и активные sessions.
5. Заменить `SESSION_SECRET_KEY`, DB, bot, SMTP и прочие подтверждённо затронутые secrets.
6. Проверить доступ к CRM, superadmin, bot и БД после ротации.
7. После подтверждения пользователя удалить dumps из рабочего дерева отдельным commit.
8. Отдельно согласовать окно очистки git history и force-push.
9. Проверить clones, forks, CI artifacts, caches и backups remote provider.
10. При необходимости уведомить затронутых лиц в соответствии с применимыми правилами обработки персональных данных.

## Безопасный поиск

Команды ниже показывают имена файлов и тип совпадения. Перед использованием следует исключить вывод самих значений.

```bash
git ls-files '*.env' '*.sql' '*.dump' '*.pem' '*.key'
git log --all --name-only -- '*.env' '*.sql' '*.dump'
git grep -n -I -E 'PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY'
```

Для автоматического сканирования рекомендуется Gitleaks:

```bash
gitleaks detect --source . --redact --no-banner
```

Tracked SQL dumps будут контролируемым исключением только до отдельного удаления. Любые новые dumps запрещены.

## Подготовленные, но запрещённые без подтверждения команды

### git-filter-repo

```bash
git filter-repo \
  --path archive/db/tourist03.sql \
  --path archive/db/tourist03.dump \
  --invert-paths
```

### BFG

```bash
bfg --delete-files 'tourist03.sql' repository.git
bfg --delete-files 'tourist03.dump' repository.git
```

После любого history rewrite потребуются coordinated force-push, повторное клонирование рабочих копий и удаление старых refs/caches. Эти команды на Этапе 1.1 не выполняются.

## Последствия force-push

- меняются commit SHA всей затронутой истории;
- открытые branches/PR и локальные clones расходятся;
- старые commits могут оставаться в forks, mirrors, caches и artifacts;
- требуется заморозка записи в репозиторий и уведомление всех участников;
- очистка истории не заменяет ротацию secrets.

## Checklist проверки

- [ ] Новый production backup создан вне git и проверен восстановлением.
- [ ] Определены фактически затронутые категории данных.
- [ ] Отозваны tourist bearer tokens.
- [ ] Завершены активные sessions после смены session secret.
- [ ] Сменены CRM/superadmin passwords и bootstrap credentials.
- [ ] Ротированы Telegram/VK bot tokens при подтверждённом попадании.
- [ ] Ротированы DB и SMTP credentials при подтверждённом попадании.
- [ ] Проверены GitHub/GitFlic mirrors, CI artifacts и forks.
- [ ] Получено отдельное подтверждение удаления tracked dumps.
- [ ] Получено отдельное подтверждение history rewrite/force-push.
- [ ] Подготовлено уведомление затронутых лиц, если оно требуется.
