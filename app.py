# app.py — Tourist03_win
# Полный рабочий файл. Сделано максимально «по-человечески»:
# — комментарии рядом с «хрупкими» местами
# — мягкие миграции БД (ALTER IF NOT EXISTS)
# — аккуратные INSERT/UPDATE для rooms (включая новую колонку floor)

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# === Папки проекта ===
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES  = BASE_DIR  # html лежат в корне
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_DIR = Path(BASE_DIR) / "db"
DB_DIR.mkdir(exist_ok=True)
CAMPS_DB = DB_DIR / "camps.db"
USERS_DB = DB_DIR / "users.db"

# Если старая БД лежала в корне, переносим её в ./db/
old_camps = Path(BASE_DIR) / "camps.db"
if old_camps.exists() and not CAMPS_DB.exists():
    CAMPS_DB.write_bytes(old_camps.read_bytes())
    try:
        old_camps.unlink()
    except Exception:
        pass

# === Подключение FastAPI ===
app = FastAPI(title="Tourist_03 Admin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# === SQL SELECT константы ===
CAMP_SELECT_ALL = """
SELECT id, name, lat, lng, min_price, emoji,
       lake_name, photo_main, status, owner, manager, admin_phones,
       rooms_count, beds_count, address, phone, site_url, emoji_size,
       bbq_count, bbq_shared_count, bath_count, sauna_count,
       pools_private_count, pools_shared_count
FROM camps
"""

ROOM_SELECT = """
SELECT id, camp_id, name, room_type, floors, floor, beds_single, beds_double, wc_count, bath_type,
       has_ac, has_bbq, has_kitchen, capacity, price, photo_main, photos_json,
       desc, price_adult, price_child, discount_pct, discount_from_nights,
       wc_type, bbq_type, kitchen_type, gazebo_type, terrace_type, balcony_type, pool_type
FROM rooms
"""


# === Утилиты БД ===
def _conn_camps() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CAMPS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _conn_users() -> sqlite3.Connection:
    conn = sqlite3.connect(str(USERS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init_camps_db():
    """Создаём таблицы (если их нет) и выполняем мягкие миграции."""
    conn = _conn_camps()
    cur = conn.cursor()

    # camps
    cur.execute("""
    CREATE TABLE IF NOT EXISTS camps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        lat REAL, lng REAL,
        min_price INTEGER,
        emoji TEXT,
        lake_name TEXT,
        photo_main TEXT,
        status TEXT,
        owner TEXT,
        manager TEXT,
        admin_phones TEXT,
        rooms_count INTEGER,
        beds_count INTEGER,
        address TEXT,
        phone TEXT,
        site_url TEXT,
        emoji_size TEXT,
        bbq_count INTEGER,
        bbq_shared_count INTEGER,
        bath_count INTEGER,
        sauna_count INTEGER,
        pools_private_count INTEGER,
        pools_shared_count INTEGER
    )
    """)

    # rooms
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camp_id INTEGER,
        name TEXT,
        room_type TEXT,
        floors INTEGER,
        floor INTEGER,
        beds_single INTEGER,
        beds_double INTEGER,
        wc_count INTEGER,
        bath_type TEXT,
        has_ac INTEGER,
        has_bbq INTEGER,
        has_kitchen INTEGER,
        capacity INTEGER,
        price INTEGER,
        photo_main TEXT,
        photos_json TEXT,
        desc TEXT,
        price_adult INTEGER,
        price_child INTEGER,
        discount_pct INTEGER,
        discount_from_nights INTEGER,
        wc_type TEXT,
        bbq_type TEXT,
        kitchen_type TEXT,
        gazebo_type TEXT,
        terrace_type TEXT,
        balcony_type TEXT,
        pool_type TEXT
    )
    """)

    # camp_photos
    cur.execute("""
    CREATE TABLE IF NOT EXISTS camp_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camp_id INTEGER,
        url TEXT,
        sort INTEGER,
        cover INTEGER
    )
    """)

    # --- rooms: мягкие миграции (ALTER COLUMN IF NOT EXISTS) ---
    rooms_alter = [
        ("room_type", "TEXT"),
        ("floors", "INTEGER DEFAULT 1"),
        ("floor", "INTEGER DEFAULT 1"),  # этаж
        ("beds_single", "INTEGER DEFAULT 0"),
        ("beds_double", "INTEGER DEFAULT 0"),
        ("wc_count", "INTEGER DEFAULT 0"),
        ("bath_type", "TEXT"),
        ("has_ac", "INTEGER DEFAULT 0"),
        ("has_bbq", "INTEGER DEFAULT 0"),
        ("has_kitchen", "INTEGER DEFAULT 0"),
        ("capacity", "INTEGER"),
        ("price", "INTEGER"),
        ("photo_main", "TEXT"),
        ("photos_json", "TEXT"),
        ("desc", "TEXT"),
        ("price_adult", "INTEGER"),
        ("price_child", "INTEGER"),
        ("discount_pct", "INTEGER"),
        ("discount_from_nights", "INTEGER"),
        ("wc_type", "TEXT"),
        ("bbq_type", "TEXT"),
        ("kitchen_type", "TEXT"),
        ("gazebo_type", "TEXT"),
        ("terrace_type", "TEXT"),
        ("balcony_type", "TEXT"),
        ("pool_type", "TEXT"),
    ]
    # Для каждой колонки пробуем добавить, если её нет
    existing_cols = set()
    for r in cur.execute("PRAGMA table_info(rooms)").fetchall():
        existing_cols.add(r["name"])
    for col, ddl in rooms_alter:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE rooms ADD COLUMN {col} {ddl}")

    # camps: мягкие миграции под новые агрегаты
    camps_alter = [
        ("min_price", "INTEGER"),
        ("emoji", "TEXT"),
        ("lake_name", "TEXT"),
        ("photo_main", "TEXT"),
        ("status", "TEXT"),
        ("owner", "TEXT"),
        ("manager", "TEXT"),
        ("admin_phones", "TEXT"),
        ("rooms_count", "INTEGER"),
        ("beds_count", "INTEGER"),
        ("address", "TEXT"),
        ("phone", "TEXT"),
        ("site_url", "TEXT"),
        ("emoji_size", "TEXT"),
        ("bbq_count", "INTEGER"),
        ("bbq_shared_count", "INTEGER"),
        ("bath_count", "INTEGER"),
        ("sauna_count", "INTEGER"),
        ("pools_private_count", "INTEGER"),
        ("pools_shared_count", "INTEGER"),
    ]
    existing_cols_camps = set()
    for r in cur.execute("PRAGMA table_info(camps)").fetchall():
        existing_cols_camps.add(r["name"])
    for col, ddl in camps_alter:
        if col not in existing_cols_camps:
            cur.execute(f"ALTER TABLE camps ADD COLUMN {col} {ddl}")

    conn.commit()
    conn.close()


def init_users_db():
    conn = _conn_users()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        role TEXT
    )
    """)
    conn.commit()
    conn.close()


# Инициализация БД при старте
init_camps_db()
init_users_db()


# === Простые страницы ===
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/superadmin", response_class=HTMLResponse)
def superadmin_page():
    return FileResponse(os.path.join(BASE_DIR, "superadmin.html"))

@app.get("/admin-base", response_class=HTMLResponse)
def admin_base_page():
    return FileResponse(os.path.join(BASE_DIR, "admin-base.html"))


# === API: Пользователи (минимально, фронт опрашивает /api/users) ===
@app.get("/api/users")
def api_users_list():
    conn = _conn_users()
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name, phone, role FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# === API: Базы отдыха ===
@app.get("/api/camps")
def api_camps_list():
    conn = _conn_camps(); cur = conn.cursor()
    rows = cur.execute(CAMP_SELECT_ALL + " ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/camps/{camp_id}")
def api_camp_one(camp_id: int):
    conn = _conn_camps(); cur = conn.cursor()
    row = cur.execute(CAMP_SELECT_ALL + " WHERE id=?", (camp_id,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)


@app.get("/api/camps/{camp_id}/photos")
def api_camp_photos(camp_id: int):
    conn = _conn_camps(); cur = conn.cursor()
    rows = cur.execute("SELECT id, url, sort, cover FROM camp_photos WHERE camp_id=? ORDER BY sort, id", (camp_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/rooms")
def api_rooms_list(camp_id: int):
    conn = _conn_camps(); cur = conn.cursor()
    rows = cur.execute(ROOM_SELECT + " WHERE camp_id=? ORDER BY id", (camp_id,)).fetchall()
    conn.close()
    # фронту удобно отдавать photos как массив
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["photos"] = json.loads(d.get("photos_json") or "[]")
        except Exception:
            d["photos"] = []
        out.append(d)
    return out


@app.post("/api/camps")
async def api_camps_create(req: Request):
    data = await req.json()

    name = (data.get("name") or "").strip()
    if not name:
        return JSONResponse({"detail": "name required"}, status_code=400)

    lat = float(data.get("lat")) if data.get("lat") not in (None, "") else None
    lng = float(data.get("lng")) if data.get("lng") not in (None, "") else None

    # агрегаты базы (числа могут прийти пустыми)
    def _int_or_none(x):
        return int(x) if x not in (None, "") else None

    min_price = _int_or_none(data.get("min_price"))
    rooms_count = _int_or_none(data.get("rooms_count"))
    beds_count  = _int_or_none(data.get("beds_count"))
    bbq_count   = _int_or_none(data.get("bbq_count"))
    bbq_shared_count    = _int_or_none(data.get("bbq_shared_count"))
    bath_count  = _int_or_none(data.get("bath_count"))
    sauna_count = _int_or_none(data.get("sauna_count"))
    pools_private_count = _int_or_none(data.get("pools_private_count"))
    pools_shared_count  = _int_or_none(data.get("pools_shared_count"))

    conn = _conn_camps(); cur = conn.cursor()

    cur.execute(
        """INSERT INTO camps(
             name, lat, lng, min_price, emoji,
             lake_name, photo_main, status, owner, manager, admin_phones,
             rooms_count, beds_count, address, phone, site_url, emoji_size,
             bbq_count, bbq_shared_count, bath_count, sauna_count,
             pools_private_count, pools_shared_count
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            name, lat, lng, min_price, (data.get("emoji") or "🏕️"),
            data.get("lake_name"), data.get("photo_main"), (data.get("status") or "active"),
            data.get("owner"), data.get("manager"), data.get("admin_phones"),
            rooms_count, beds_count, data.get("address"), data.get("phone"),
            data.get("site_url"), (data.get("emoji_size") or "standard"),
            bbq_count, bbq_shared_count, bath_count, sauna_count,
            pools_private_count, pools_shared_count
        )
    )
    new_id = cur.lastrowid

    # Фото базы
    photos = data.get("photos") or []
    cur.execute("DELETE FROM camp_photos WHERE camp_id=?", (new_id,))
    for p in photos[:20]:
        cur.execute(
            "INSERT INTO camp_photos(camp_id, url, sort, cover) VALUES(?,?,?,?)",
            (new_id, p.get("url"), int(p.get("sort", 0)), int(bool(p.get("cover"))))
        )

    # Комнаты
    rooms_full = data.get("rooms_full") or []
    for r in rooms_full:
        photos_json = None
        if isinstance(r.get("photos"), list):
            photos_json = json.dumps(r["photos"], ensure_ascii=False)
        elif isinstance(r.get("photos_json"), str):
            photos_json = r["photos_json"]

        cap = r.get("capacity")
        capacity = int(cap) if cap is not None else (int(r.get("beds_single", 0)) + 2 * int(r.get("beds_double", 0)))

        cur.execute(
            """INSERT INTO rooms(
                 camp_id,name,room_type,floors,floor,beds_single,beds_double,wc_count,bath_type,
                 has_ac,has_bbq,has_kitchen,capacity,price,photo_main,photos_json,
                 desc, price_adult, price_child, discount_pct, discount_from_nights,
                 wc_type, bbq_type, kitchen_type, gazebo_type, terrace_type, balcony_type, pool_type
               )
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                new_id,
                r.get("name"),
                r.get("room_type"),
                int(r.get("floors", 1)),
                int(r.get("floor", 1)),   # ВАЖНО: этаж добавлен в VALUES
                int(r.get("beds_single", 0)),
                int(r.get("beds_double", 0)),
                int(r.get("wc_count", 0)),
                r.get("bath_type"),
                int(r.get("has_ac", 0)),
                int(r.get("has_bbq", 0)),
                int(r.get("has_kitchen", 0)),
                int(capacity),
                r.get("price"),
                r.get("photo_main"),
                photos_json,
                r.get("desc"),
                r.get("price_adult"),
                r.get("price_child"),
                r.get("discount_pct"),
                r.get("discount_from_nights"),
                r.get("wc_type"),
                r.get("bbq_type"),
                r.get("kitchen_type"),
                r.get("gazebo_type"),
                r.get("terrace_type"),
                r.get("balcony_type"),
                r.get("pool_type"),
            )
        )

    row = cur.execute(CAMP_SELECT_ALL + " WHERE id=?", (new_id,)).fetchone()
    conn.commit(); conn.close()
    return dict(row)


@app.put("/api/camps/{camp_id}")
async def api_camps_update(camp_id: int, req: Request):
    data = await req.json()

    # Список полей, которые можно обновлять в camps
    fields = []
    values = []
    for k in (
        "name", "lat", "lng", "min_price", "emoji", "lake_name", "photo_main",
        "status", "owner", "manager", "admin_phones", "rooms_count", "beds_count",
        "address", "phone", "site_url", "emoji_size",
        "bbq_count", "bbq_shared_count", "bath_count", "sauna_count",
        "pools_private_count", "pools_shared_count",
    ):
        if k in data:
            fields.append(f"{k}=?")
            v = data[k]
            if k in ("lat", "lng"):
                v = float(v) if v not in (None, "") else None
            elif k in (
                "min_price", "rooms_count", "beds_count",
                "bbq_count", "bbq_shared_count",
                "bath_count", "sauna_count",
                "pools_private_count", "pools_shared_count",
            ):
                v = int(v) if v not in (None, "") else None
            values.append(v)

    if fields:
        conn = _conn_camps(); cur = conn.cursor()
        cur.execute(f"UPDATE camps SET {', '.join(fields)} WHERE id=?", (*values, camp_id))

        # Фотографии базы (если прислали — пересоздаём)
        photos = data.get("photos")
        if photos is not None:
            cur.execute("DELETE FROM camp_photos WHERE camp_id=?", (camp_id,))
            for p in photos[:20]:
                cur.execute(
                    "INSERT INTO camp_photos(camp_id, url, sort, cover) VALUES(?,?,?,?)",
                    (camp_id, p.get("url"), int(p.get("sort", 0)), int(bool(p.get("cover"))))
                )

        # Комнаты (если прислали — пересоздаём)
        rooms_full = data.get("rooms_full")
        if rooms_full is not None:
            cur.execute("DELETE FROM rooms WHERE camp_id=?", (camp_id,))
            for r in rooms_full:
                photos_json = None
                if isinstance(r.get("photos"), list):
                    photos_json = json.dumps(r["photos"], ensure_ascii=False)
                elif isinstance(r.get("photos_json"), str):
                    photos_json = r["photos_json"]

                cap = r.get("capacity")
                capacity = int(cap) if cap is not None else (int(r.get("beds_single", 0)) + 2 * int(r.get("beds_double", 0)))

                cur.execute(
                    """INSERT INTO rooms(
                         camp_id,name,room_type,floors,floor,beds_single,beds_double,wc_count,bath_type,
                         has_ac,has_bbq,has_kitchen,capacity,price,photo_main,photos_json,
                         desc, price_adult, price_child, discount_pct, discount_from_nights,
                         wc_type, bbq_type, kitchen_type, gazebo_type, terrace_type, balcony_type, pool_type
                       )
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        camp_id,                          # camp_id
                        r.get("name"),                    # name
                        r.get("room_type"),               # room_type
                        int(r.get("floors", 1)),          # этажность
                        int(r.get("floor", 1)),           # этаж
                        int(r.get("beds_single", 0)),     # beds_single
                        int(r.get("beds_double", 0)),     # beds_double
                        int(r.get("wc_count", 0)),        # wc_count
                        r.get("bath_type"),               # bath_type
                        int(r.get("has_ac", 0)),          # has_ac
                        int(r.get("has_bbq", 0)),         # has_bbq
                        int(r.get("has_kitchen", 0)),     # has_kitchen
                        int(                              # capacity
                            (r.get("capacity")
                             if r.get("capacity") is not None
                             else (int(r.get("beds_single", 0)) + 2 * int(r.get("beds_double", 0))))
                        ),
                        r.get("price"),                   # price
                        r.get("photo_main"),              # photo_main
                        photos_json,                      # photos_json (строка JSON)
                        r.get("desc"),                    # описание
                        r.get("price_adult"),             # ₽ взрослый
                        r.get("price_child"),             # ₽ детский
                        r.get("discount_pct"),            # скидка %
                        r.get("discount_from_nights"),    # от скольких суток
                        r.get("wc_type"),                 # тип санузла
                        r.get("bbq_type"),                # тип BBQ
                        r.get("kitchen_type"),            # тип кухни
                        r.get("gazebo_type"),             # тип беседки
                        r.get("terrace_type"),            # тип террасы
                        r.get("balcony_type"),            # тип балкона
                        r.get("pool_type"),               # тип бассейна
                    )
                )


        conn.commit()
        conn.close()

    # Отдаём обновлённую карточку
    conn2 = _conn_camps(); cur2 = conn2.cursor()
    row = cur2.execute(CAMP_SELECT_ALL + " WHERE id=?", (camp_id,)).fetchone()
    conn2.close()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)


# === Upload (фото) ===
@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    # сохраняем с префиксом «датавремя-рандом»
    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    # чуть более случайности — добавим микросекунды в конец
    target_name = f"{now}{str(id(file))[-6:]}.{file.filename.split('.')[-1].lower()}"
    path = os.path.join(UPLOAD_DIR, target_name)

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # Отдаём путь для фронта
    rel = f"/static/uploads/{target_name}"
    return {"url": rel}


# === Favicon-заглушка (чтобы не было 404 в логах) ===
@app.get("/favicon.ico")
def favicon():
    # можно положить свой логотип в static/favicon.ico
    icon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    return JSONResponse({"ok": True})
