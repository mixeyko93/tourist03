## Быстрый деплой Туристики (Docker + Caddy + Postgres)

### 1) Установить Docker на сервере
```bash
apt-get update
apt-get install -y ca-certificates curl
curl -fsSL https://get.docker.com | sh
apt-get install -y docker-compose-plugin
```

### 2) Скопировать проект на сервер
С локальной машины (macOS), из папки проекта:
```bash
rsync -avz --exclude '.git' --exclude '.venv' --exclude '__pycache__' --exclude '.env' ./ root@YOUR_SERVER_IP:/opt/tourist03/
```

### 3) Настроить переменные окружения
```bash
cd /opt/tourist03/deploy
cp .env.example .env
nano .env
```

Сгенерировать `ADMIN_PASS_HASH`:
```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'YOUR_PASSWORD'
```

### 4) Запустить
```bash
cd /opt/tourist03/deploy
docker compose up -d --build
docker compose ps
```

Логи:
```bash
docker compose logs -f caddy
docker compose logs -f app
docker compose logs -f bot
```
