
import os
import json
import logging

import sqlite3
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi import BackgroundTasks


# === НАСТРОЙКИ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = BASE_DIR

# --- База данных ---
DB_DIR = Path(BASE_DIR) / "db"
DB_DIR.mkdir(exist_ok=True)

CAMPS_DB = DB_DIR / "camps.db"
USERS_DB = DB_DIR / "users.db"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tourist03.app")

# === ИНИЦИАЛИЗАЦИЯ ===
app = FastAPI(title="Tourist03 WebApp")

def init_camps_db():
    conn = sqlite3.connect(CAMPS_DB)
    cur = conn.cursor()
    # Базы отдыха
    cur.execute("""
    CREATE TABLE IF NOT EXISTS camps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        min_price INTEGER,
        emoji TEXT
    );
    """)
    # Номера
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camp_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        capacity INTEGER,
        price INTEGER,
        FOREIGN KEY(camp_id) REFERENCES camps(id) ON DELETE CASCADE
    );
    """)
    # Администраторы баз
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camp_id INTEGER NOT NULL,
        name TEXT,
        phone TEXT,
        email TEXT,
        FOREIGN KEY(camp_id) REFERENCES camps(id) ON DELETE CASCADE
    );
    """)

    # seed демо-данных
    cur.execute("SELECT COUNT(*) FROM camps")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO camps(name, lat, lng, min_price, emoji) VALUES(?,?,?,?,?)",
            [
                ("Байкал Резиденс", 51.870, 107.600, 4500, "🏕️"),
                ("Уютный берег",    51.780, 107.520, 3200, "🏡"),
                ("Таёжный домик",   51.820, 107.670, 3800, "🌲"),
            ]
        )
        # Пара номеров для примера
        cur.executemany(
            "INSERT INTO rooms(camp_id, name, capacity, price) VALUES(?,?,?,?)",
            [
                (1, "Домик у озера", 4, 6000),
                (1, "Семейный",       6, 8000),
                (2, "Стандарт",       2, 3500),
            ]
        )
        # Привяжем по админу к базам
        cur.executemany(
            "INSERT INTO admins(camp_id, name, phone, email) VALUES(?,?,?,?)",
            [
                (1, "Админ Байкал", "+7 900 000-00-01", "admin1@example.com"),
                (2, "Админ Берег",  "+7 900 000-00-02", "admin2@example.com"),
            ]
        )
    conn.commit()
    conn.close()


def init_users_db():
    conn = sqlite3.connect(USERS_DB)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        email TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


# Разрешаем CORS (для локальной отладки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статику
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Шаблоны (если нужно отдавать index.html динамически)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Отдаёт главный интерфейс мини-приложения (index.html)
    """
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>index.html не найден</h1>", status_code=500)
    return FileResponse(index_path)


# ========== API БАЗОВЫЕ ==========

@app.get("/api/ping")
async def ping():
    return {"status": "ok"}


# ---------- API: РЕГИСТРАЦИЯ ----------
@app.post("/api/auth/register/start")
async def auth_register_start(request: Request):
    """
    Начало регистрации — отправка кода (эмуляция).
    """
    data = await request.json()
    name = data.get("name")
    phone = data.get("phone")
    logger.info(f"Регистрация начата: {name} / {phone}")
    # Эмуляция: отправляем SMS
    return {"sent": True}


@app.post("/api/auth/register/verify")
async def auth_register_verify(request: Request):
    """
    Проверка кода регистрации.
    """
    data = await request.json()
    phone = data.get("phone")
    code = data.get("code")
    logger.info(f"Подтверждение кода для {phone}: {code}")
    # Эмуляция регистрации
    user = {"id": 1, "name": "Иван Петров", "phone": phone}
    token = "demo_token"
    return {"token": token, "user": user}


# ---------- API: ВХОД ----------
@app.post("/api/auth/login/start")
async def auth_login_start(request: Request):
    """
    Начало авторизации — отправка кода (эмуляция).
    """
    data = await request.json()
    phone = data.get("phone")
    logger.info(f"Отправка кода входа на номер: {phone}")
    return {"sent": True}


@app.post("/api/auth/login/verify")
async def auth_login_verify(request: Request):
    """
    Проверка кода входа.
    """
    data = await request.json()
    phone = data.get("phone")
    code = data.get("code")
    logger.info(f"Авторизация {phone} с кодом {code}")
    # Эмуляция входа
    user = {"id": 1, "name": "Иван Петров", "phone": phone}
    token = "demo_token_login"
    return {"token": token, "user": user}


# ---------- API: ПРОФИЛЬ ----------
@app.get("/api/profile")
async def get_profile():
    """
    Возвращает профиль текущего пользователя (эмуляция).
    """
    demo_user = {"id": 1, "name": "Иван Петров", "phone": "+7 900 000 00 00"}
    return {"user": demo_user}

# ======= MOCK-ДАННЫЕ ДЛЯ АДМИНОК (пока без БД) =======

from datetime import datetime, timedelta

# Брони (для /admin)
BOOKINGS = [
    {
        "id": 101,
        "camp_name": "Байкал Резиденс",
        "room_name": "Домик у озера",
        "date_from": (datetime.today()).isoformat(),
        "date_to":   (datetime.today() + timedelta(days=2)).isoformat(),
        "guests": 3,
        "customer_name": "Иван Петров",
        "phone": "+7 900 000-00-00",
        "status": "pending",  # pending | confirmed | cancelled
    },
    {
        "id": 102,
        "camp_name": "Уютный берег",
        "room_name": "Стандарт",
        "date_from": (datetime.today()).isoformat(),
        "date_to":   (datetime.today() + timedelta(days=1)).isoformat(),
        "guests": 2,
        "customer_name": "Анна Смирнова",
        "phone": "+7 901 111-11-11",
        "status": "confirmed",
    },
]

# Базы и номера (для /superadmin)
CAMPS = [
    {
        "id": 1, "name": "Байкал Резиденс", "lake_name": "Байкал",
        "lat": 51.870, "lng": 107.600,
        "address": "Улан-Удэ, ...", "phone": "+7 902 000-00-01",
        "site_url": "https://example.com/baikal", "min_price": 4500,
        "photos": ["https://picsum.photos/seed/baikal/800/400"]
    },
    {
        "id": 2, "name": "Уютный берег", "lake_name": None,
        "lat": 51.780, "lng": 107.520,
        "address": None, "phone": None,
        "site_url": None, "min_price": 3200,
        "photos": []
    },
]
ROOMS = [
    { "id": 11, "camp_id": 1, "name": "Домик у озера", "capacity": 4, "price": 6000, "photos": [] },
    { "id": 12, "camp_id": 1, "name": "Семейный",     "capacity": 6, "price": 8000, "photos": [] },
    { "id": 21, "camp_id": 2, "name": "Стандарт",     "capacity": 2, "price": 3500, "photos": [] },
]
USERS = [
    {
        "id": 1, "name": "Иван Петров", "phone": "+7 900 000-00-00", "email": "ivan@example.com",
        "verified_phone": True, "verified_email": False, "bookings": [101], "created_at": datetime.utcnow().isoformat()
    }
]

# ----- API для admin-base.html -----
@app.get("/api/bookings")
async def api_bookings_list():
    return BOOKINGS

@app.post("/api/bookings/{booking_id}/status")
async def api_bookings_status(booking_id: int, status: str):
    found = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if not found:
        return JSONResponse({"detail": "not found"}, status_code=404)
    found["status"] = status
    return {"ok": True}

@app.delete("/api/bookings/{booking_id}")
async def api_bookings_delete(booking_id: int):
    global BOOKINGS
    before = len(BOOKINGS)
    BOOKINGS = [b for b in BOOKINGS if b["id"] != booking_id]
    return {"deleted": before - len(BOOKINGS)}

def _conn_camps():
    conn = sqlite3.connect(CAMPS_DB)
    conn.row_factory = sqlite3.Row
    # важно для каскадного удаления rooms по camp_id
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@app.get("/api/camps")
async def api_camps_list():
    """Список баз из SQLite для карты/суперадмина."""
    conn = _conn_camps()
    rows = conn.execute("SELECT id, name, lat, lng, min_price, emoji FROM camps").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/camps")
async def api_camps_create(req: Request):
    data = await req.json()
    name = (data.get("name") or "").strip()
    lat  = float(data.get("lat"))
    lng  = float(data.get("lng"))
    min_price = int(data["min_price"]) if data.get("min_price") not in (None, "",) else None
    emoji = (data.get("emoji") or "").strip() or "🏕️"

    if not name:
        return JSONResponse({"detail": "name required"}, status_code=400)

    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO camps(name, lat, lng, min_price, emoji) VALUES(?,?,?,?,?)",
        (name, lat, lng, min_price, emoji)
    )
    new_id = cur.lastrowid
    row = cur.execute("SELECT id, name, lat, lng, min_price, emoji FROM camps WHERE id=?", (new_id,)).fetchone()
    conn.commit(); conn.close()
    return dict(row)

@app.put("/api/camps/{camp_id}")
async def api_camps_update(camp_id: int, req: Request):
    data = await req.json()
    fields, values = [], []
    for k in ("name","lat","lng","min_price","emoji"):
        if k in data:
            fields.append(f"{k}=?")
            if k in ("lat","lng"):
                values.append(float(data[k]) if data[k] is not None else None)
            elif k == "min_price":
                values.append(int(data[k]) if data[k] not in (None,"") else None)
            else:
                values.append(data[k])
    if not fields:
        return JSONResponse({"detail": "nothing to update"}, status_code=400)

    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(f"UPDATE camps SET {', '.join(fields)} WHERE id=?", (*values, camp_id))
    row = cur.execute("SELECT id, name, lat, lng, min_price, emoji FROM camps WHERE id=?", (camp_id,)).fetchone()
    conn.commit(); conn.close()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)

@app.delete("/api/camps/{camp_id}")
async def api_camps_delete(camp_id: int):
    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute("DELETE FROM camps WHERE id=?", (camp_id,))
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return {"deleted": deleted}

@app.get("/api/rooms")
async def api_rooms_list(camp_id: int | None = None):
    if camp_id:
        return [r for r in ROOMS if r["camp_id"] == camp_id]
    return ROOMS

@app.post("/api/rooms")
async def api_rooms_create(req: Request):
    data = await req.json()
    new_id = (max([r["id"] for r in ROOMS]) + 1) if ROOMS else 1
    data["id"] = new_id
    data["camp_id"] = int(data["camp_id"])
    data["capacity"] = int(data["capacity"])
    data["price"] = int(data["price"])
    ROOMS.append(data)
    return data

@app.put("/api/rooms/{room_id}")
async def api_rooms_update(room_id: int, req: Request):
    data = await req.json()
    r = next((x for x in ROOMS if x["id"] == room_id), None)
    if not r:
        return JSONResponse({"detail": "not found"}, status_code=404)
    r.update(data)
    if "camp_id" in data: r["camp_id"] = int(r["camp_id"])
    if "capacity" in data: r["capacity"] = int(r["capacity"])
    if "price" in data: r["price"] = int(r["price"])
    return r

@app.delete("/api/rooms/{room_id}")
async def api_rooms_delete(room_id: int):
    global ROOMS
    ROOMS = [r for r in ROOMS if r["id"] != room_id]
    return {"ok": True}

@app.get("/api/users")
async def api_users_list():
    return USERS


# ========== ТЕСТОВЫЙ ВЫЗОВ ==========
@app.get("/api/debug/info")
async def debug_info():
    info = {
        "cwd": os.getcwd(),
        "base_dir": BASE_DIR,
        "static": STATIC_DIR,
    }
    return JSONResponse(info)


# ======= АДМИН-СТРАНИЦЫ (статические HTML) =======

@app.get("/admin", response_class=HTMLResponse)
async def admin_base():
    """Страница администратора баз (таблица броней)."""
    path = os.path.join(BASE_DIR, "admin-base.html")
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>admin-base.html не найден</h1>", status_code=500)

@app.get("/superadmin", response_class=HTMLResponse)
async def superadmin():
    """Страница суперадмина (управление базами/номерами/пользователями)."""
    path = os.path.join(BASE_DIR, "superadmin.html")
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>superadmin.html не найден</h1>", status_code=500)

# Инициализация БД при импортe модуля (старте приложения)
init_camps_db()
init_users_db()

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=True)
