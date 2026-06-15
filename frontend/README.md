# Туристика Frontend

Frontend-слой пользовательского приложения, Туристика CRM и Туристика Admin на `React + TypeScript + Vite`.

Что уже есть:

- реальный экран карты на Leaflet;
- компонент `CampMarker`;
- состояния `selected`, `vip`, `disabled`;
- загрузка данных из `/api/camps`;
- анимация на `framer-motion`.

Маршрут внутри FastAPI после сборки:

```text
/react-map
```

Сборка складывается прямо в:

```text
static/react-map
```

Локальный запуск:

```bash
cd frontend
npm install
npm run dev
```

Сборка:

```bash
cd frontend
npm run build
```
