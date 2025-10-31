import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import re

from fastapi import FastAPI, Request, HTTPException   # ← добавили HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# === Утилиты для имён папок (транслит) ===
def _slug_latin(s: str) -> str:
    s = (s or "").strip()
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
        "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
        "х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
    }
    out = []
    for ch in s.lower():
        out.append(table.get(ch, ch))
    slug = "".join(out)
    slug = "".join(c for c in slug if c.isalnum() or c in "-_ ")
    return re.sub(r"\s+", "-", slug).strip("-") or "noname"


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
       pools_private_count, pools_shared_count,
       description
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
    # timeout даёт до 5 секунд на ожидание блокировки; WAL лучше работает с конкурентными записями
    conn = sqlite3.connect(str(CAMPS_DB), timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn

def _conn_users() -> sqlite3.Connection:
    conn = sqlite3.connect(str(USERS_DB), timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn


# --- мягкая миграция схемы: добавляет недостающие столбцы и таблицы ---
def ensure_schema():
    conn = _conn_camps()
    cur = conn.cursor()

    # camps: добавим описание + счётчики и настройки, если их ещё нет
    cur.execute("PRAGMA table_info(camps)")
    cols = {row[1] for row in cur.fetchall()}

    def add_camp_col(name: str, ddl: str, default_literal: str | None = None):
        if name in cols:
            return
        # собираем ALTER с литеральным DEFAULT, без плейсхолдеров
        if default_literal is None:
            sql = f"ALTER TABLE camps ADD COLUMN {name} {ddl}"
        else:
            sql = f"ALTER TABLE camps ADD COLUMN {name} {ddl} DEFAULT {default_literal}"
        cur.execute(sql)

    # строковые DEFAULT оборачиваем в одинарные кавычки, числа — как есть
    add_camp_col("description",         "TEXT",    "''")
    add_camp_col("emoji",               "TEXT",    "'🏕️'")
    add_camp_col("emoji_size",          "TEXT",    "'standard'")
    add_camp_col("bbq_count",           "INTEGER", "0")
    add_camp_col("bbq_shared_count",    "INTEGER", "0")
    add_camp_col("bath_count",          "INTEGER", "0")
    add_camp_col("sauna_count",         "INTEGER", "0")
    add_camp_col("pools_private_count", "INTEGER", "0")
    add_camp_col("pools_shared_count",  "INTEGER", "0")
    add_camp_col("beds_count",          "INTEGER", "0")
    add_camp_col("min_price",           "INTEGER", "0")

    # фото комнат (если ещё нет)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS room_photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camp_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,   -- индекс апартамента (0..N-1)
            url TEXT NOT NULL,
            cover INTEGER DEFAULT 0,
            sort INTEGER DEFAULT 0
        )
    """)

    # rooms: недостающие колонки
    cur.execute("PRAGMA table_info(rooms)")
    rcols = {row[1] for row in cur.fetchall()}

    def add_room_col(name: str, ddl: str, default_literal: str | None = None):
        if name in rcols:
            return
        if default_literal is None:
            sql = f"ALTER TABLE rooms ADD COLUMN {name} {ddl}"
        else:
            sql = f"ALTER TABLE rooms ADD COLUMN {name} {ddl} DEFAULT {default_literal}"
        cur.execute(sql)

    add_room_col("room_type", "TEXT")
    add_room_col("floors", "INTEGER", "1")
    add_room_col("floor", "INTEGER", "1")
    add_room_col("beds_single", "INTEGER", "0")
    add_room_col("beds_double", "INTEGER", "0")
    add_room_col("bath_type", "TEXT")
    add_room_col("wc_type", "TEXT")
    add_room_col("bbq_type", "TEXT")
    add_room_col("kitchen_type", "TEXT")
    add_room_col("gazebo_type", "TEXT")
    add_room_col("terrace_type", "TEXT")
    add_room_col("pool_type", "TEXT")
    add_room_col("balcony_type", "TEXT")
    add_room_col("has_ac", "INTEGER", "0")
    add_room_col("price_adult", "INTEGER", "0")
    add_room_col("price_child", "INTEGER", "0")
    add_room_col("discount_pct", "INTEGER", "0")
    add_room_col("discount_from_nights", "INTEGER", "0")
    add_room_col("photos_json", "TEXT")

    conn.commit()
    conn.close()


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
ensure_schema()


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


def _normalize_move(url: str, camp_id: int, room_db_id: int | None = None, camp_name: str | None = None, room_name: str | None = None) -> str:
    """
    Переносим файл из временной папки в:
      база:  /static/uploads/{camp_id}_{camp-name-latin}/
      апартамент: /static/uploads/{camp_id}_{camp-name-latin}/{camp_id}-{room_id}_{room-name-latin}/
    Возвращает новый URL.
    """
    if not url or not url.startswith("/static/uploads/"):
        return url

    p = Path(url.lstrip("/"))
    if "uploads/temp/" not in str(p.as_posix()):
        return url  # уже переложен

    base = Path("static/uploads")
    base.mkdir(parents=True, exist_ok=True)

    camp_slug = _slug_latin(camp_name or f"camp-{camp_id}")
    dst = base / f"{camp_id}_{camp_slug}"

    if room_db_id is not None:
        room_slug = _slug_latin(room_name or f"room-{room_db_id}")
        dst = dst / f"{camp_id}-{room_db_id}_{room_slug}"

    dst.mkdir(parents=True, exist_ok=True)

    src = Path(url.lstrip("/"))
    newp = dst / src.name
    try:
        newp.write_bytes(src.read_bytes())
        src.unlink(missing_ok=True)
    except Exception:
        pass

    return "/" + newp.as_posix()



def _int(val, default=0):
    try:
        if val is None or val == "": return default
        return int(val)
    except Exception:
        return default

def _sum_derived(rooms: list[dict]) -> dict:
    beds = 0
    bbq_private = 0
    pool_private = 0
    min_price = None
    for r in rooms:
        b1 = _int(r.get("beds_single"))
        b2 = _int(r.get("beds_double"))
        beds += b1 + b2 * 2
        if r.get("bbq_type") == "private":
            bbq_private += 1
        if r.get("pool_type") == "private":
            pool_private += 1
        pa = _int(r.get("price_adult"), None)
        if pa is not None:
            min_price = pa if (min_price is None or pa < min_price) else min_price
    return {
        "beds": beds,
        "bbq_private": bbq_private,
        "pool_private": pool_private,
        "min_price": (min_price or 0),
    }

@app.post("/api/camps")
async def api_camps_upsert_new(req: Request):
    data = await req.json()
    return await _upsert_camp(None, data)

@app.put("/api/camps/{camp_id}")
async def api_camps_upsert(camp_id: int, req: Request):
    data = await req.json()
    return await _upsert_camp(camp_id, data)

async def _upsert_camp(camp_id: int | None, data: dict):
    conn = _conn_camps()
    cur  = conn.cursor()

    # 1) базовые поля из payload
    name   = (data.get("name") or "").strip()
    lake   = (data.get("lake_name") or data.get("lake") or "").strip()
    addr   = (data.get("address") or data.get("addr") or "").strip()
    lat    = data.get("lat")
    lng    = data.get("lng")
    status = (data.get("status") or "active").strip().lower()
    emoji  = (data.get("emoji") or "🏕️").strip()
    emoji_size = (data.get("emoji_size") or "standard").strip()
    description = (data.get("description") or data.get("desc") or "").strip()

    owner   = (data.get("owner")   or "").strip()       # "ФИО, +7..."
    manager = (data.get("manager") or "").strip()       # "ФИО, +7..."
    admin_phones = (data.get("admin_phones") or "").strip()
    site_url = (data.get("site_url") or data.get("site") or "").strip()

    rooms_payload = data.get("rooms_full") or data.get("rooms") or []

    # 2) агрегаты
    def _i(x, d=0):
        try:
            return int(x)
        except Exception:
            return d

    beds_count = _i(data.get("beds_count"))
    bbq_count = _i(data.get("bbq_count"))
    bbq_shared_count = _i(data.get("bbq_shared_count"))
    bath_count = _i(data.get("bath_count"))
    sauna_count = _i(data.get("sauna_count"))
    pools_private_count = _i(data.get("pools_private_count"))
    pools_shared_count  = _i(data.get("pools_shared_count"))
    min_price = data.get("min_price")
    min_price = _i(min_price, None) if min_price is not None else None

    # 3) camps: INSERT / UPDATE
    if camp_id is None:
        cur.execute("""
            INSERT INTO camps(
                name, lake_name, address, lat, lng, status,
                emoji, emoji_size, description,
                owner, manager, admin_phones, site_url,
                min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                pools_private_count, pools_shared_count, beds_count
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            name, lake, addr, lat, lng, status,
            emoji, emoji_size, description,
            owner, manager, admin_phones, site_url,
            min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
            pools_private_count, pools_shared_count, beds_count
        ))
        camp_id = cur.lastrowid
    else:
        cur.execute("""
            UPDATE camps SET
                name=?, lake_name=?, address=?, lat=?, lng=?, status=?,
                emoji=?, emoji_size=?, description=?,
                owner=?, manager=?, admin_phones=?, site_url=?,
                min_price=?, bbq_count=?, bbq_shared_count=?, bath_count=?, sauna_count=?,
                pools_private_count=?, pools_shared_count=?, beds_count=?
            WHERE id=?
        """, (
            name, lake, addr, lat, lng, status,
            emoji, emoji_size, description,
            owner, manager, admin_phones, site_url,
            min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
            pools_private_count, pools_shared_count, beds_count,
            camp_id
        ))

    # 4) фото базы — сначала чистим, потом вставляем, заодно переносим из temp в конечную папку
    photos = data.get("photos") or []
    cur.execute("DELETE FROM camp_photos WHERE camp_id=?", (camp_id,))

    cover_url = None
    first_url = None
    for sort, p in enumerate(photos[:20]):
        url = p.get("url") if isinstance(p, dict) else str(p)
        cover = int(bool(isinstance(p, dict) and p.get("cover")))
        url = _normalize_move(url, camp_id, None, camp_name=name)
        if first_url is None:
            first_url = url
        if cover and cover_url is None:
            cover_url = url
        cur.execute(
            "INSERT INTO camp_photos(camp_id,url,sort,cover) VALUES(?,?,?,?)",
            (camp_id, url, sort, cover)
        )

    # пишем главную фотку прямо в camps — для карты/балунов
    cur.execute("UPDATE camps SET photo_main=? WHERE id=?", (cover_url or first_url, camp_id))

    # 5) апартаменты + их фото  — БЕЗ тотального удаления, со стабильными id
    # Список id, которые пришли с фронта (существующие комнаты)
    incoming_ids = []
    for r in rooms_payload:
        if isinstance(r, dict) and r.get("id"):
            try:
                incoming_ids.append(int(r["id"]))
            except Exception:
                pass

    # Удалим из БД только те комнаты, которых нет в payload (пользователь удалил строку)
    cur.execute("SELECT id FROM rooms WHERE camp_id=?", (camp_id,))
    existing_ids = {row["id"] for row in cur.fetchall()}
    to_delete = [rid for rid in existing_ids if rid not in set(incoming_ids)]
    if to_delete:
        qmarks = ",".join("?" for _ in to_delete)
        cur.execute(f"DELETE FROM rooms WHERE camp_id=? AND id IN ({qmarks})", (camp_id, *to_delete))
        cur.execute(f"DELETE FROM room_photos WHERE camp_id=? AND room_id IN ({qmarks})", (camp_id, *to_delete))

    # Обновим/вставим комнаты из payload
    for idx, r in enumerate(rooms_payload):
        def _i(x, d=0):
            try:
                return int(x)
            except Exception:
                return d

        beds_single = _i(r.get("beds_single"))
        beds_double = _i(r.get("beds_double"))
        capacity    = beds_single + beds_double * 2

        # если пришёл id — обновляем, иначе вставляем новую (получим новый room_id)
        room_id = r.get("id")
        if room_id:
            # UPDATE; если такой id вдруг отсутствует — вставим с явным id
            cur.execute("""
                UPDATE rooms SET
                    camp_id=?, name=?, room_type=?, floors=?, floor=?,
                    beds_single=?, beds_double=?, bath_type=?, wc_type=?,
                    bbq_type=?, kitchen_type=?, gazebo_type=?, terrace_type=?, pool_type=?, balcony_type=?, has_ac=?,
                    capacity=?, price_adult=?, price_child=?, price=?, discount_pct=?, discount_from_nights=?, desc=?
                WHERE id=?
            """, (
                camp_id,
                (r.get("name") or "").strip(),
                (r.get("room_type") or "").strip(),
                _i(r.get("floors"), 1),
                _i(r.get("floor"), 1),
                beds_single,
                beds_double,
                (r.get("bath_type") or "").strip(),
                (r.get("wc_type") or "").strip(),
                (r.get("bbq_type") or "").strip(),
                (r.get("kitchen_type") or "").strip(),
                (r.get("gazebo_type") or "").strip(),
                (r.get("terrace_type") or "").strip(),
                (r.get("pool_type") or "").strip(),
                (r.get("balcony_type") or "").strip(),
                _i(r.get("has_ac")),
                capacity,
                _i(r.get("price_adult")),
                _i(r.get("price_child")),
                _i(r.get("price")),
                _i(r.get("discount_pct")),
                _i(r.get("discount_from_nights")),
                (r.get("desc") or "").strip(),
                int(room_id)
            ))
            if cur.rowcount == 0:
                # строки не было — вставим с фиксированным id
                # строки не было — вставим с фиксированным id
                cur.execute("""
                    INSERT INTO rooms(
                        id, camp_id, name, room_type, floors, floor,
                        beds_single, beds_double, bath_type, wc_type,
                        bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                        capacity, price_adult, price_child, price, discount_pct, discount_from_nights, desc, photo_main, photos_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    int(room_id), camp_id,
                    (r.get("name") or "").strip(),
                    (r.get("room_type") or "").strip(),
                    _i(r.get("floors"), 1),
                    _i(r.get("floor"), 1),
                    beds_single, beds_double,
                    (r.get("bath_type") or "").strip(),
                    (r.get("wc_type") or "").strip(),
                    (r.get("bbq_type") or "").strip(),
                    (r.get("kitchen_type") or "").strip(),
                    (r.get("gazebo_type") or "").strip(),
                    (r.get("terrace_type") or "").strip(),
                    (r.get("pool_type") or "").strip(),
                    (r.get("balcony_type") or "").strip(),
                    _i(r.get("has_ac")),
                    capacity,
                    _i(r.get("price_adult")), _i(r.get("price_child")), _i(r.get("price")),
                    _i(r.get("discount_pct")), _i(r.get("discount_from_nights")),
                    (r.get("desc") or "").strip(),
                    None, "[]"
                ))

            room_db_id = int(room_id)
        else:
            # Вставляем новую комнату
            # Вставляем новую комнату
            cur.execute("""
                INSERT INTO rooms(
                    camp_id, name, room_type, floors, floor,
                    beds_single, beds_double, bath_type, wc_type,
                    bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                    capacity, price_adult, price_child, price, discount_pct, discount_from_nights, desc, photo_main, photos_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                camp_id,
                (r.get("name") or "").strip(),
                (r.get("room_type") or "").strip(),
                _i(r.get("floors"), 1),
                _i(r.get("floor"), 1),
                beds_single, beds_double,
                (r.get("bath_type") or "").strip(),
                (r.get("wc_type") or "").strip(),
                (r.get("bbq_type") or "").strip(),
                (r.get("kitchen_type") or "").strip(),
                (r.get("gazebo_type") or "").strip(),
                (r.get("terrace_type") or "").strip(),
                (r.get("pool_type") or "").strip(),
                (r.get("balcony_type") or "").strip(),
                _i(r.get("has_ac")),
                capacity,
                _i(r.get("price_adult")), _i(r.get("price_child")), _i(r.get("price")),
                _i(r.get("discount_pct")), _i(r.get("discount_from_nights")),
                (r.get("desc") or "").strip(),
                None, "[]"
            ))

            room_db_id = cur.lastrowid

        # Фото: перенос из temp + обложка + photos_json
        room_photos = (r.get("photos") or [])[:5]
        urls = []
        cover_url = None
        cur.execute("DELETE FROM room_photos WHERE camp_id=? AND room_id=?", (camp_id, room_db_id))
        for s, ph in enumerate(room_photos):
            if isinstance(ph, dict):
                u = ph.get("url") or ""
                cov = int(bool(ph.get("cover")))
            else:
                u = str(ph); cov = 0

            u = _normalize_move(u, camp_id, room_db_id, camp_name=name, room_name=r.get("name"))
            urls.append(u)
            if cov and cover_url is None:
                cover_url = u
            cur.execute(
                "INSERT INTO room_photos(camp_id,room_id,url,cover,sort) VALUES(?,?,?,?,?)",
                (camp_id, room_db_id, u, cov, s)
            )

        if not cover_url and urls:
            cover_url = urls[0]

        # обновим главную картинку + JSON для удобной подгрузки
        cur.execute(
            "UPDATE rooms SET photo_main=?, photos_json=? WHERE id=?",
            (cover_url, json.dumps(urls, ensure_ascii=False), room_db_id)
        )

    conn.commit()
    conn.close()
    return {"ok": True, "id": camp_id}


# === Upload (фото) ===
@app.post("/api/upload")
async def api_upload(request: Request):
    """
    Принимает файл и опциональные поля:
      - camp_id: int (если уже есть база)
      - room_idx: int (если фото относится к апартаментам)
    Складывает в /static/uploads/camp_<id>/[rooms/room_<idx>/]fname.jpg
    Если camp_id не пришёл — кладём во временную папку, а при сохранении базы файлы будут "перенормированы".
    """
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(400, "file not provided")

    # параметры из формы
    camp_id  = form.get("camp_id")
    room_idx = form.get("room_idx")

    # базовая папка
    base_dir = Path("static/uploads")
    base_dir.mkdir(parents=True, exist_ok=True)

    sub = Path("temp")
    if camp_id and str(camp_id).isdigit():
        sub = Path(f"camp_{int(camp_id)}")
        if room_idx is not None and str(room_idx).isdigit():
            sub = sub / "rooms" / f"room_{int(room_idx)}"

    save_dir = base_dir / sub
    save_dir.mkdir(parents=True, exist_ok=True)

    # имя файла — оставим таймштамп + оригинальное расширение
    suffix = Path(file.filename).suffix or ".jpg"
    fname  = datetime.now().strftime("%Y%m%d-%H%M%S%f") + suffix
    path   = save_dir / fname
    with path.open("wb") as f:
        f.write(await file.read())

    url = f"/static/uploads/{sub.as_posix()}/{fname}"
    return {"url": url}



# === Favicon-заглушка (чтобы не было 404 в логах) ===
@app.get("/favicon.ico")
def favicon():
    # можно положить свой логотип в static/favicon.ico
    icon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    return JSONResponse({"ok": True})
