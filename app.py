# app.py — Tourist_03 (FastAPI + SQLite)

import os
import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles


# === НАСТРОЙКИ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_DIR = Path(BASE_DIR) / "db"
DB_DIR.mkdir(exist_ok=True)
CAMPS_DB = DB_DIR / "camps.db"
USERS_DB = DB_DIR / "users.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tourist03.app")

# === ПРИЛОЖЕНИЕ ===
app = FastAPI(title="Tourist_03")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ======== DB HELPERS ========
def _conn_camps():
    conn = sqlite3.connect(CAMPS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _conn_users():
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ======== INIT DBS ========
def init_camps_db():
    """Создаём БД баз/номеров (и мягко добавляем недостающие поля)."""
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
        room_type TEXT,
        floors INTEGER DEFAULT 1,
        beds_single INTEGER DEFAULT 0,
        beds_double INTEGER DEFAULT 0,
        wc_count INTEGER DEFAULT 0,
        bath_type TEXT,                 -- shower | bath | NULL
        has_ac INTEGER DEFAULT 0,
        has_bbq INTEGER DEFAULT 0,
        has_kitchen INTEGER DEFAULT 0,
        capacity INTEGER,               -- beds_single + 2*beds_double
        price INTEGER,
        photo_main TEXT,
        FOREIGN KEY(camp_id) REFERENCES camps(id) ON DELETE CASCADE
    );
    """)
    # --- Мягкие миграции для старых БД: добавим недостающие колонки в rooms
    for col, ddl in [
        ("room_type", "TEXT"),
        ("floors", "INTEGER DEFAULT 1"),
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
        ("photos_json", "TEXT"),  # <— добавили колонку под массив фото

    ]:

        try:
            cur.execute(f"ALTER TABLE rooms ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            # колонка уже есть — игнорируем
            pass

    # Фото баз
    cur.execute("""
    CREATE TABLE IF NOT EXISTS camp_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camp_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        sort INTEGER DEFAULT 0,
        cover INTEGER DEFAULT 0,
        FOREIGN KEY(camp_id) REFERENCES camps(id) ON DELETE CASCADE
    );
    """)

    # Брони (для admin-base)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
        date_from TEXT NOT NULL,
        date_to   TEXT NOT NULL,
        guests INTEGER NOT NULL,
        customer_name TEXT,
        phone TEXT,
        status TEXT DEFAULT 'pending'  -- pending | confirmed | cancelled
    );
    """)

    # Администраторы баз (на будущее)
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

    # Мягкие миграции недостающих колонок camps (для суперадмина/карты)
    for col, ddl in [
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
        ("bbq_shared_count", "INTEGER"),  # <— добавили
        ("bath_count", "INTEGER"),
        ("sauna_count", "INTEGER"),
        ("pools_private_count", "INTEGER"),  # <— добавили
        ("pools_shared_count", "INTEGER"),  # <— добавили
    ]:

        try:
            cur.execute(f"ALTER TABLE camps ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # колонка уже есть

    # Сид минимальных данных (один раз)
    cnt = cur.execute("SELECT COUNT(*) FROM camps").fetchone()[0]
    if cnt == 0:
        cur.execute(
            "INSERT INTO camps(name, lat, lng, min_price, emoji, lake_name, status) VALUES(?,?,?,?,?,?,?)",
            ("Тестовая база", 51.830, 107.600, 3000, "🏕️", "Байкал", "active")
        )
        camp_id = cur.lastrowid
        cur.execute(
            "INSERT INTO rooms(camp_id, name, capacity, price) VALUES(?,?,?,?)",
            (camp_id, "Домик", 4, 5000)
        )

    conn.commit()
    conn.close()


def init_users_db():
    """Мини-БД пользователей (отдельный файл)."""
    conn = sqlite3.connect(USERS_DB)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        verified_phone INTEGER DEFAULT 0,
        verified_email INTEGER DEFAULT 0,
        created_at TEXT
    );
    """)
    # мягкие миграции users
    for col, ddl in [
        ("email", "TEXT"),
        ("verified_phone", "INTEGER DEFAULT 0"),
        ("verified_email", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT"),
    ]:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass

    # сид одного пользователя
    cnt = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if cnt == 0:
        cur.execute(
            "INSERT INTO users(name, phone, email, verified_phone, verified_email, created_at) VALUES(?,?,?,?,?,?)",
            ("Иван Петров", "+7 900 000-00-00", "ivan@example.com", 1, 0, datetime.utcnow().isoformat())
        )
    conn.commit()
    conn.close()


# ======== PAGES ========
@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>index.html не найден</h1>", status_code=500)


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    path = os.path.join(BASE_DIR, "admin-base.html")
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>admin-base.html не найден</h1>", status_code=500)


@app.get("/superadmin", response_class=HTMLResponse)
def superadmin_page():
    path = os.path.join(BASE_DIR, "superadmin.html")
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>superadmin.html не найден</h1>", status_code=500)


# ======== CAMPS API ========
CAMP_SELECT_ALL = """
SELECT id, name, lat, lng, min_price, emoji, lake_name, photo_main,
       status, owner, manager, admin_phones, rooms_count, beds_count,
       address, phone, site_url, emoji_size, bbq_count, bath_count, sauna_count
FROM camps
"""

@app.get("/api/camps/{camp_id}/photos")
async def api_camp_photos(camp_id: int):
    conn = _conn_camps()
    rows = conn.execute(
        "SELECT url, sort, cover FROM camp_photos WHERE camp_id=? ORDER BY sort, id",
        (camp_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/camps")
async def api_camps_list():
    conn = _conn_camps()
    rows = conn.execute(CAMP_SELECT_ALL).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/camps")
async def api_camps_create(req: Request):
    data = await req.json()

    # обязательные
    name = (data.get("name") or "").strip()
    if not name:
        return JSONResponse({"detail": "name required"}, status_code=400)
    lat = float(data.get("lat"))
    lng = float(data.get("lng"))

    # базовые
    min_price = int(data["min_price"]) if data.get("min_price") not in (None, "") else None
    emoji = (data.get("emoji") or "🏕️").strip()

    # доп. поля
    lake_name    = data.get("lake_name")
    photo_main   = data.get("photo_main")
    status       = data.get("status") or "active"
    owner        = data.get("owner")
    manager      = data.get("manager")
    admin_phones = data.get("admin_phones")
    rooms_count  = int(data.get("rooms_count") or 0)
    beds_count   = int(data.get("beds_count") or 0)
    address      = data.get("address")
    phone        = data.get("phone")
    site_url     = data.get("site_url")
    emoji_size   = data.get("emoji_size") or "standard"
    bbq_count    = int(data.get("bbq_count") or 0)
    bath_count   = int(data.get("bath_count") or 0)
    sauna_count  = int(data.get("sauna_count") or 0)
    bbq_shared_count = int(data.get("bbq_shared_count") or 0)
    pools_private_count = int(data.get("pools_private_count") or 0)
    pools_shared_count = int(data.get("pools_shared_count") or 0)

    photos      = data.get("photos") or []        # [{url, sort, cover}]
    rooms_full  = data.get("rooms_full") or []    # [{... как во фронте ...}]

    conn = _conn_camps(); cur = conn.cursor()
    cur.execute(
        """INSERT INTO camps
           (name, lat, lng, min_price, emoji, lake_name, photo_main,
            status, owner, manager, admin_phones, rooms_count, beds_count,
            address, phone, site_url, emoji_size,
            bbq_count, bbq_shared_count, bath_count, sauna_count,
            pools_private_count, pools_shared_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (name, lat, lng, min_price, emoji, lake_name, photo_main,
         status, owner, manager, admin_phones, rooms_count, beds_count,
         address, phone, site_url, emoji_size,
         bbq_count, bbq_shared_count, bath_count, sauna_count,
         pools_private_count, pools_shared_count)
    )

    new_id = cur.lastrowid

    # фото
    cur.execute("DELETE FROM camp_photos WHERE camp_id=?", (new_id,))
    for p in photos[:20]:
        cur.execute(
            "INSERT INTO camp_photos(camp_id, url, sort, cover) VALUES(?,?,?,?)",
            (new_id, p.get("url"), int(p.get("sort", 0)), int(bool(p.get("cover"))))
        )

    # комнаты
    for r in rooms_full:
        cap = r.get("capacity")
        photos = r.get("photos")
        photos_json = (
            json.dumps(photos, ensure_ascii=False)
            if isinstance(photos, list) else (r.get("photos_json") or None)
        )
        cur.execute(
            """INSERT INTO rooms(camp_id,name,room_type,floors,beds_single,beds_double,
                                 wc_count,bath_type,has_ac,has_bbq,has_kitchen,capacity,price,
                                 photo_main, photos_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (new_id, r.get("name"), r.get("room_type"), int(r.get("floors", 1)),
             int(r.get("beds_single", 0)), int(r.get("beds_double", 0)),
             int(r.get("wc_count", 0)), r.get("bath_type"),
             int(r.get("has_ac", 0)), int(r.get("has_bbq", 0)), int(r.get("has_kitchen", 0)),
             int(cap if cap is not None else (int(r.get("beds_single", 0)) + 2 * int(r.get("beds_double", 0)))),
             r.get("price"),
             r.get("photo_main"), photos_json)
        )

    row = cur.execute(CAMP_SELECT_ALL + " WHERE id=?", (new_id,)).fetchone()
    conn.commit(); conn.close()
    return dict(row)


@app.put("/api/camps/{camp_id}")
async def api_camps_update(camp_id: int, req: Request):
    data = await req.json()
    fields, values = [], []

    # обновляем простые поля
    for k in ("name", "lat", "lng", "min_price", "emoji", "lake_name", "photo_main",
              "status", "owner", "manager", "admin_phones", "rooms_count", "beds_count",
              "address", "phone", "site_url", "emoji_size",
              "bbq_count", "bbq_shared_count", "bath_count", "sauna_count",
              "pools_private_count", "pools_shared_count"):

        if k in data:
            fields.append(f"{k}=?")
            v = data[k]
            if k in ("lat", "lng"):
                v = float(v) if v not in (None, "") else None
            elif k in ("min_price", "rooms_count", "beds_count", "bbq_count", "bath_count", "sauna_count"):
                v = int(v) if v not in (None, "") else None
            values.append(v)

    if fields:
        conn = _conn_camps(); cur = conn.cursor()
        cur.execute(f"UPDATE camps SET {', '.join(fields)} WHERE id=?", (*values, camp_id))

        # если пришли фото — перезапишем
        photos = data.get("photos")
        if photos is not None:
            cur.execute("DELETE FROM camp_photos WHERE camp_id=?", (camp_id,))
            for p in photos[:20]:
                cur.execute(
                    "INSERT INTO camp_photos(camp_id, url, sort, cover) VALUES(?,?,?,?)",
                    (camp_id, p.get("url"), int(p.get("sort", 0)), int(bool(p.get("cover"))))
                )

        # если пришёл полный набор комнат — перезапишем
        rooms_full = data.get("rooms_full")
        if rooms_full is not None:
            cur.execute("DELETE FROM rooms WHERE camp_id=?", (camp_id,))
            for r in rooms_full:
                cap = r.get("capacity")
                photos = r.get("photos")
                photos_json = (
                    json.dumps(photos, ensure_ascii=False)
                    if isinstance(photos, list) else (r.get("photos_json") or None)
                )
                cur.execute(
                    """INSERT INTO rooms(camp_id,name,room_type,floors,beds_single,beds_double,
                                         wc_count,bath_type,has_ac,has_bbq,has_kitchen,capacity,price,
                                         photo_main, photos_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (camp_id, r.get("name"), r.get("room_type"), int(r.get("floors", 1)),
                     int(r.get("beds_single", 0)), int(r.get("beds_double", 0)),
                     int(r.get("wc_count", 0)), r.get("bath_type"),
                     int(r.get("has_ac", 0)), int(r.get("has_bbq", 0)), int(r.get("has_kitchen", 0)),
                     int(cap if cap is not None else (int(r.get("beds_single", 0)) + 2 * int(r.get("beds_double", 0)))),
                     r.get("price"),
                     r.get("photo_main"), photos_json)
                )

        row = cur.execute(CAMP_SELECT_ALL + " WHERE id=?", (camp_id,)).fetchone()
        conn.commit(); conn.close()
        if not row:
            return JSONResponse({"detail": "not found"}, status_code=404)
        return dict(row)

    return JSONResponse({"detail": "nothing to update"}, status_code=400)


@app.delete("/api/camps/{camp_id}")
async def api_camps_delete(camp_id: int):
    conn = _conn_camps(); cur = conn.cursor()
    cur.execute("DELETE FROM camps WHERE id=?", (camp_id,))
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return {"deleted": deleted}


# ======== ROOMS API ========
ROOM_SELECT = """
SELECT id, camp_id, name, room_type, floors, beds_single, beds_double,
       wc_count, bath_type, has_ac, has_bbq, has_kitchen, capacity, price, photo_main, photos_json
FROM rooms
"""


@app.get("/api/rooms")
async def api_rooms_list(camp_id: int | None = None):
    conn = _conn_camps()
    if camp_id is None:
        rows = conn.execute(ROOM_SELECT).fetchall()
    else:
        rows = conn.execute(ROOM_SELECT + " WHERE camp_id=?", (camp_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/rooms")
async def api_rooms_create(req: Request):
    data = await req.json()
    name = (data.get("name") or "").strip()
    if not name:
        return JSONResponse({"detail": "name required"}, status_code=400)

    camp_id  = int(data["camp_id"])
    capacity = int(data.get("capacity") or 0)
    price    = int(data["price"]) if data.get("price") not in (None, "") else None
    photo_main  = data.get("photo_main")
    photos_json = data.get("photos_json")
    if isinstance(data.get("photos"), list) and not photos_json:
        photos_json = json.dumps(data["photos"], ensure_ascii=False)

    conn = _conn_camps(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO rooms(camp_id, name, capacity, price, photo_main, photos_json) VALUES(?,?,?,?,?,?)",
        (camp_id, name, capacity, price, photo_main, photos_json)
    )

    new_id = cur.lastrowid
    row = cur.execute(ROOM_SELECT + " WHERE id=?", (new_id,)).fetchone()
    conn.commit(); conn.close()
    return dict(row)


@app.put("/api/rooms/{room_id}")
async def api_rooms_update(room_id: int, req: Request):
    data = await req.json()
    fields, values = [], []
    for k in ("camp_id", "name", "capacity", "price", "photo_main", "photos_json"):
        if k in data:
            fields.append(f"{k}=?")
            v = data[k]
            if k in ("camp_id","capacity","price") and v not in (None, ""):
                v = int(v)
            values.append(v)
    if not fields:
        return JSONResponse({"detail": "nothing to update"}, status_code=400)

    if "photos" in data and "photos_json" not in data and isinstance(data["photos"], list):
        data["photos_json"] = json.dumps(data["photos"], ensure_ascii=False)

    conn = _conn_camps(); cur = conn.cursor()
    cur.execute(f"UPDATE rooms SET {', '.join(fields)} WHERE id=?", (*values, room_id))
    row = cur.execute(ROOM_SELECT + " WHERE id=?", (room_id,)).fetchone()
    conn.commit(); conn.close()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)


@app.delete("/api/rooms/{room_id}")
async def api_rooms_delete(room_id: int):
    conn = _conn_camps(); cur = conn.cursor()
    cur.execute("DELETE FROM rooms WHERE id=?", (room_id,))
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return {"deleted": deleted}


# ======== UPLOAD (мультизагрузка фото) ========
@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    name = file.filename or "photo"
    ext = os.path.splitext(name)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return JSONResponse({"detail": "Разрешены: jpg, png, webp, gif"}, status_code=400)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S%f")
    safe = f"{ts}{ext}"
    dest = os.path.join(UPLOAD_DIR, safe)
    with open(dest, "wb") as f:
        f.write(await file.read())
    url = f"/static/uploads/{safe}"
    return {"url": url}


# ======== BOOKINGS API (для admin-base.html) ========
@app.get("/api/bookings")
async def api_bookings_list(status: str | None = None, q: str | None = None):
    conn = _conn_camps()
    sql = """
      SELECT b.id, b.date_from, b.date_to, b.guests, b.status,
             b.customer_name, b.phone,
             r.name AS room_name,
             c.name AS camp_name
      FROM bookings b
      JOIN rooms r ON r.id = b.room_id
      JOIN camps c ON c.id = r.camp_id
    """
    where, vals = [], []
    if status:
        where.append("b.status=?"); vals.append(status)
    if q:
        like = f"%{q}%"
        where.append("(b.customer_name LIKE ? OR b.phone LIKE ? OR c.name LIKE ? OR r.name LIKE ?)")
        vals += [like, like, like, like]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY b.id DESC"
    rows = conn.execute(sql, vals).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/bookings/{booking_id}/status")
async def api_bookings_status(booking_id: int, status: str):
    conn = _conn_camps(); cur = conn.cursor()
    cur.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))
    conn.commit(); conn.close()
    return {"ok": True}


@app.delete("/api/bookings/{booking_id}")
async def api_bookings_delete(booking_id: int):
    conn = _conn_camps(); cur = conn.cursor()
    cur.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return {"deleted": deleted}


# ======== AVAILABILITY ========
@app.post("/api/availability/check")
async def availability_check(req: Request):
    """
    Вход: { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "guests": 3 }
    Выход: { camp_id: [room_id, ...], ... } — только свободные комнаты нужной вместимости.
    """
    data = await req.json()
    date_from = (data.get("from") or "").strip()
    date_to   = (data.get("to") or "").strip()
    guests    = int(data.get("guests") or 1)

    if not date_from or not date_to:
        return JSONResponse({"detail": "from/to required"}, status_code=400)

    conn = _conn_camps()
    sql = """
      SELECT r.id AS room_id, r.camp_id
      FROM rooms r
      WHERE r.capacity >= ?
        AND NOT EXISTS (
          SELECT 1 FROM bookings b
          WHERE b.room_id = r.id
            AND NOT (b.date_to <= ? OR b.date_from >= ?)
        )
    """
    rows = conn.execute(sql, (guests, date_from, date_to)).fetchall()
    conn.close()

    result = {}
    for r in rows:
        cid, rid = r["camp_id"], r["room_id"]
        result.setdefault(cid, []).append(rid)
    return result


# ======== USERS ========
@app.get("/api/users")
async def api_users_list():
    conn = _conn_users()
    rows = conn.execute(
        "SELECT id, name, phone, email, verified_phone, verified_email, created_at FROM users ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [
        {
            **dict(r),
            "verified_phone": bool(r["verified_phone"]),
            "verified_email": bool(r["verified_email"]),
        } for r in rows
    ]


# ======== DEBUG ========
@app.get("/api/debug/info")
async def debug_info():
    info = {"cwd": os.getcwd(), "base_dir": BASE_DIR, "static": STATIC_DIR}
    return JSONResponse(info)


# ======== STARTUP ========
init_camps_db()
init_users_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=True)
