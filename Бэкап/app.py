import os
import json
import random
from typing import List, Optional, Dict
from datetime import date, datetime

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import aiohttp
from dotenv import load_dotenv

import sqlite3

# ================= ENV =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080/")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}/" if BOT_TOKEN else ""

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "tourist.db"))

# ================= APP =================
app = FastAPI(title="Tourist03")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ---------- SQLite: пользователи ----------
def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                email TEXT,
                username TEXT,
                verified_phone INTEGER NOT NULL DEFAULT 0,
                verified_email INTEGER NOT NULL DEFAULT 0,
                bookings TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()

# ---------- Хелперы Users в SQLite ----------
import json as _json

class User(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str] = None
    username: Optional[str] = None  # телеграм username (при наличии)
    verified_phone: bool = False
    verified_email: bool = False
    bookings: List[int] = []  # id броней
    created_at: datetime = Field(default_factory=datetime.utcnow)


def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        email=row["email"],
        username=row["username"],
        verified_phone=bool(row["verified_phone"]),
        verified_email=bool(row["verified_email"]),
        bookings=_json.loads(row["bookings"] or "[]"),
        created_at=datetime.fromisoformat(row["created_at"])
    )

def db_user_get_by_phone(phone: str) -> Optional[User]:
    conn = db_connect()
    try:
        cur = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        row = cur.fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()

def db_user_get_by_id(uid: int) -> Optional[User]:
    conn = db_connect()
    try:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (uid,))
        row = cur.fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()

def db_user_upsert_name_phone(name: str, phone: str) -> User:
    now = datetime.utcnow().isoformat()
    existing = db_user_get_by_phone(phone)
    conn = db_connect()
    try:
        if existing:
            conn.execute("UPDATE users SET name = COALESCE(?, name) WHERE phone = ?", (name, phone))
            conn.commit()
            return db_user_get_by_phone(phone)
        else:
            conn.execute("""INSERT INTO users(name, phone, created_at)
                            VALUES(?,?,?)""", (name, phone, now))
            conn.commit()
            return db_user_get_by_phone(phone)
    finally:
        conn.close()

def db_user_set_verified_phone(phone: str, v: bool = True) -> Optional[User]:
    conn = db_connect()
    try:
        conn.execute("UPDATE users SET verified_phone = ? WHERE phone = ?", (1 if v else 0, phone))
        conn.commit()
    finally:
        conn.close()
    return db_user_get_by_phone(phone)

def db_user_set_email(uid: int, email: str, verified: bool) -> Optional[User]:
    conn = db_connect()
    try:
        conn.execute("UPDATE users SET email = ?, verified_email = ? WHERE id = ?", (email, 1 if verified else 0, uid))
        conn.commit()
    finally:
        conn.close()
    return db_user_get_by_id(uid)

def db_user_add_booking(phone: str, booking_id: int):
    u = db_user_get_by_phone(phone)
    if not u: return
    arr = list(u.bookings or [])
    if booking_id not in arr:
        arr.append(booking_id)
        conn = db_connect()
        try:
            conn.execute("UPDATE users SET bookings = ? WHERE id = ?", (_json.dumps(arr), u.id))
            conn.commit()
        finally:
            conn.close()

def db_users_list() -> List[User]:
    conn = db_connect()
    try:
        cur = conn.execute("SELECT * FROM users ORDER BY id DESC LIMIT 1000")
        return [_row_to_user(r) for r in cur.fetchall()]
    finally:
        conn.close()


db_init()


# ================= STATIC =================
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
if not os.path.isdir(WEB_DIR):
    raise RuntimeError("Папка web/ не найдена рядом с app.py")

@app.get("/")
async def root_index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))

@app.get("/index.html")
async def index_alias():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))

# --- Новые маршруты админок ---
# admin-bot -> admin-base, admin-camps -> superadmin
@app.get("/admin-base")
@app.get("/admin-base.html")
async def admin_base_page():
    return FileResponse(os.path.join(WEB_DIR, "admin-base.html"))

# Совместимость со старым именем
@app.get("/admin-bot")
@app.get("/admin-bot.html")
async def admin_bot_compat():
    return FileResponse(os.path.join(WEB_DIR, "admin-base.html"))

@app.get("/superadmin")
@app.get("/superadmin.html")
async def superadmin_page():
    return FileResponse(os.path.join(WEB_DIR, "superadmin.html"))

# Совместимость со старым именем
@app.get("/admin-camps")
@app.get("/admin-camps.html")
async def superadmin_compat():
    return FileResponse(os.path.join(WEB_DIR, "superadmin.html"))

# Отдаём статику по /static
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

# ================= МОДЕЛИ =================
class Camp(BaseModel):
    id: int
    name: str
    lat: float
    lng: float
    lake_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    site_url: Optional[str] = None
    min_price: Optional[int] = None
    photos: Optional[List[str]] = None

class Room(BaseModel):
    id: int
    camp_id: int
    name: str
    capacity: int
    price: int
    photos: Optional[List[str]] = None

class AvailabilityItem(BaseModel):
    room_id: int
    room_name: str
    capacity: int
    nights: int
    total_price: int

class BookingIn(BaseModel):
    room_id: int
    date_from: date
    date_to: date
    guests: int
    adults: int
    children: int
    customer_name: str
    phone: str
    room_name: Optional[str] = None

class BookingOut(BookingIn):
    id: int
    camp_name: Optional[str] = None
    status: str = Field(default="pending", pattern="^(pending|confirmed|cancelled)$")


# ================= ДАННЫЕ (in-memory) =================
CAMPS: List[Camp] = [
    Camp(
        id=1, name="База «Сагаан-Нур»", lat=51.291, lng=106.528,
        lake_name="Гусиное озеро", phone="+7 900 000-00-01",
        site_url="https://example.com/camp1", min_price=3500,
        photos=["https://images.unsplash.com/photo-1521401830884-6c03c1c87ebb?q=80&w=1200&auto=format&fit=crop"]
    ),
    Camp(
        id=2, name="Эко-усадьба «Баргуджин»", lat=51.21, lng=106.23,
        lake_name="Гусиное озеро", phone="+7 900 000-00-02",
        site_url=None, min_price=4200,
        photos=["https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1200&auto=format&fit=crop"]
    ),
]
ROOMS: List[Room] = [
    Room(id=11, camp_id=1, name="Стандарт", capacity=3, price=3500),
    Room(id=12, camp_id=1, name="Семейный", capacity=5, price=4900),
    Room(id=21, camp_id=2, name="Домик у озера", capacity=4, price=5200),
]
BOOKINGS: List[BookingOut] = []

booking_seq = 1000
camp_seq = max([c.id for c in CAMPS], default=0)
room_seq = max([r.id for r in ROOMS], default=0)

# OTP-хранилища (телефон/почта)
PHONE_OTP: Dict[str, str] = {}
EMAIL_OTP: Dict[str, str] = {}
# Временные простые токены авторизации: token -> user_id
TOKENS: Dict[str, int] = {}

# ================== УТИЛИТЫ ==================
def gen_code() -> str:
    return f"{random.randint(1000, 9999)}"

def nights_between(d1: date, d2: date) -> int:
    return max(0, (d2 - d1).days)

# ================= API: CAMPS =================
@app.get("/api/camps", response_model=List[Camp])
async def api_camps():
    return CAMPS

@app.post("/api/camps", response_model=Camp)
async def api_camp_create(payload: dict):
    global camp_seq
    camp_seq += 1
    c = Camp(
        id=camp_seq,
        name=payload.get("name"),
        lat=float(payload.get("lat")),
        lng=float(payload.get("lng")),
        lake_name=payload.get("lake_name"),
        address=payload.get("address"),
        phone=payload.get("phone"),
        site_url=payload.get("site_url"),
        min_price=int(payload["min_price"]) if payload.get("min_price") not in (None, "") else None,
        photos=payload.get("photos") or [],
    )
    CAMPS.append(c)
    return c

@app.put("/api/camps/{camp_id}", response_model=Camp)
async def api_camp_update(camp_id: int, payload: dict):
    c = next((x for x in CAMPS if x.id == camp_id), None)
    if not c:
        raise HTTPException(404, "Camp not found")
    for f in ["name", "lat", "lng", "lake_name", "address", "phone", "site_url", "min_price", "photos"]:
        if f in payload:
            setattr(c, f, payload[f] if f != "min_price" else (int(payload[f]) if payload[f] not in (None, "") else None))
    return c

@app.delete("/api/camps/{camp_id}")
async def api_camp_delete(camp_id: int):
    global CAMPS, ROOMS
    before = len(CAMPS)
    CAMPS = [x for x in CAMPS if x.id != camp_id]
    ROOMS = [r for r in ROOMS if r.camp_id != camp_id]
    if len(CAMPS) == before:
        raise HTTPException(404, "Camp not found")
    return {"ok": True}

# ================= API: ROOMS =================
@app.get("/api/rooms", response_model=List[Room])
async def api_rooms(camp_id: Optional[int] = None):
    return [r for r in ROOMS if (camp_id is None or r.camp_id == camp_id)]

@app.post("/api/rooms", response_model=Room)
async def api_room_create(payload: dict):
    global room_seq
    room_seq += 1
    r = Room(
        id=room_seq,
        camp_id=int(payload["camp_id"]),
        name=payload["name"],
        capacity=int(payload["capacity"]),
        price=int(payload["price"]),
        photos=payload.get("photos") or [],
    )
    ROOMS.append(r)
    return r

@app.put("/api/rooms/{room_id}", response_model=Room)
async def api_room_update(room_id: int, payload: dict):
    r = next((x for x in ROOMS if x.id == room_id), None)
    if not r:
        raise HTTPException(404, "Room not found")
    for f in ["camp_id", "name", "capacity", "price", "photos"]:
        if f in payload:
            setattr(r, f, int(payload[f]) if f in ("camp_id", "capacity", "price") else payload[f])
    return r

@app.delete("/api/rooms/{room_id}")
async def api_room_delete(room_id: int):
    global ROOMS
    before = len(ROOMS)
    ROOMS = [x for x in ROOMS if x.id != room_id]
    if len(ROOMS) == before:
        raise HTTPException(404, "Room not found")
    return {"ok": True}

# ================= API: AVAILABILITY =================
@app.get("/api/availability", response_model=List[AvailabilityItem])
async def api_availability(
    camp_id: int,
    date_from: date,
    date_to: date,
    guests: int,
    adults: int,
    children: int,
):
    n = nights_between(date_from, date_to)
    if n <= 0:
        return []
    items: List[AvailabilityItem] = []
    for r in [x for x in ROOMS if x.camp_id == camp_id and x.capacity >= guests]:
        items.append(AvailabilityItem(
            room_id=r.id, room_name=r.name, capacity=r.capacity, nights=n, total_price=r.price * n
        ))
    return items

# ================= API: BOOKINGS =================
@app.get("/api/bookings", response_model=List[BookingOut])
async def api_get_bookings():
    return BOOKINGS[-200:]

@app.post("/api/bookings", response_model=BookingOut)
async def api_create_booking(payload: BookingIn):
    global booking_seq
    booking_seq += 1

    room = next((r for r in ROOMS if r.id == payload.room_id), None)
    camp = next((c for c in CAMPS if room and c.id == room.camp_id), None)

    out = BookingOut(
        id=booking_seq,
        **payload.model_dump(),
        room_name=payload.room_name or (room.name if room else None),
        camp_name=(camp.name if camp else None),
        status="pending",
    )
    BOOKINGS.append(out)

    # Привязать бронь к пользователю по номеру телефона (если есть)
    db_user_add_booking(payload.phone, out.id)
    return out

@app.post("/api/bookings/{booking_id}/status")
async def api_booking_status(booking_id: int, status: str = Query(..., pattern="^(pending|confirmed|cancelled)$")):
    b = next((x for x in BOOKINGS if x.id == booking_id), None)
    if not b:
        raise HTTPException(404, "Booking not found")
    b.status = status
    return {"ok": True, "id": b.id, "status": b.status}

@app.delete("/api/bookings/{booking_id}")
async def api_booking_delete(booking_id: int):
    global BOOKINGS
    before = len(BOOKINGS)
    BOOKINGS = [x for x in BOOKINGS if x.id != booking_id]
    if len(BOOKINGS) == before:
        raise HTTPException(404, "Booking not found")
    return {"ok": True}

# ================= API: AUTH / USERS =================
class StartRegisterIn(BaseModel):
    name: str
    phone: str

class VerifyPhoneIn(BaseModel):
    phone: str
    code: str

class StartLoginIn(BaseModel):
    phone: str

class StartEmailVerifyIn(BaseModel):
    token: str
    email: str

class VerifyEmailIn(BaseModel):
    token: str
    code: str

@app.post("/api/auth/register/start")
async def api_auth_register_start(body: StartRegisterIn):
    code = gen_code()
    PHONE_OTP[body.phone] = code
    # upsert пользователя в БД
    db_user_upsert_name_phone(body.name, body.phone)
    return {"ok": True, "sent_to": body.phone[-4:], "debug_code": code}

@app.post("/api/auth/register/verify")
async def api_auth_register_verify(body: VerifyPhoneIn):
    if PHONE_OTP.get(body.phone) != body.code:
        raise HTTPException(400, "Неверный код")
    user = db_user_get_by_phone(body.phone)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    user = db_user_set_verified_phone(body.phone, True)
    token = f"tok_{random.randint(10**8, 10**9-1)}"
    TOKENS[token] = user.id
    return {"ok": True, "token": token, "user": user.model_dump()}

@app.post("/api/auth/login/start")
async def api_auth_login_start(body: StartLoginIn):
    user = db_user_get_by_phone(body.phone)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    code = gen_code()
    PHONE_OTP[body.phone] = code
    return {"ok": True, "sent_to": body.phone[-4:], "debug_code": code}

@app.post("/api/auth/login/verify")
async def api_auth_login_verify(body: VerifyPhoneIn):
    if PHONE_OTP.get(body.phone) != body.code:
        raise HTTPException(400, "Неверный код")
    user = db_user_get_by_phone(body.phone)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    token = f"tok_{random.randint(10**8, 10**9-1)}"
    TOKENS[token] = user.id
    return {"ok": True, "token": token, "user": user.model_dump()}

@app.get("/api/me")
async def api_me(token: str):
    uid = TOKENS.get(token)
    if not uid:
        raise HTTPException(401, "Не авторизовано")
    user = db_user_get_by_id(uid)
    return {"ok": True, "user": user.model_dump()}

@app.post("/api/auth/email/start")
async def api_auth_email_start(body: StartEmailVerifyIn):
    uid = TOKENS.get(body.token)
    if not uid:
        raise HTTPException(401, "Не авторизовано")
    # "Отправляем" код
    code = gen_code()
    EMAIL_OTP[body.email] = code
    return {"ok": True, "debug_code": code}

@app.post("/api/auth/email/verify")
async def api_auth_email_verify(body: VerifyEmailIn):
    uid = TOKENS.get(body.token)
    if not uid:
        raise HTTPException(401, "Не авторизовано")
    # ищем email с кодом
    for email, code in list(EMAIL_OTP.items()):
        if code == body.code:
            user = db_user_set_email(uid, email, True)
            del EMAIL_OTP[email]
            return {"ok": True, "user": user.model_dump()}
    raise HTTPException(400, "Неверный код")

# --- Список пользователей для Суперадмина ---
@app.get("/api/users", response_model=List[User])
async def api_users():
    return db_users_list()

# ================= Telegram helper =================
async def tg_call(method: str, payload: dict):
    if not API_BASE:
        return
    async with aiohttp.ClientSession() as s:
        async with s.post(API_BASE + method, json=payload, timeout=20) as r:
            try:
                return await r.json()
            except Exception:
                return {"ok": False, "status": r.status, "text": await r.text()}

# ================= TELEGRAM WEBHOOK =================
@app.post(f"/tg/webhook/{BOT_TOKEN}")
async def tg_webhook(req: Request):
    if not BOT_TOKEN:
        raise HTTPException(500, "BOT_TOKEN is not configured")

    update = await req.json()
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    inline_keyboard = {"inline_keyboard": [[{"text": "Турист_03 ⛺️", "web_app": {"url": WEBAPP_URL}}]]}

    async def show_inline_only(txt: str):
        await tg_call("sendMessage", {
            "chat_id": chat_id, "text": "…", "disable_notification": True,
            "reply_markup": {"remove_keyboard": True}
        })
        await tg_call("sendMessage", {"chat_id": chat_id, "text": txt, "reply_markup": inline_keyboard})

    if text == "/start":
        welcome = (
            "👋 Приветствуем!\n"
            "✨ Это бот приложения для поиска и бронирования баз отдыха.\n"
            "➡️ Откройте приложение кнопкой ниже."
        )
        await show_inline_only(welcome)
        return {"ok": True}

    wad = message.get("web_app_data")
    if wad and "data" in wad:
        try:
            payload = json.loads(wad["data"])  # {room_id, date_from, ...}
        except Exception:
            await tg_call("sendMessage", {"chat_id": chat_id, "text": "Не понял данные из мини-приложения 🤔", "reply_markup": inline_keyboard})
            return {"ok": True}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post("http://127.0.0.1:8080/api/bookings", json=payload, timeout=20) as r:
                    if r.status != 200:
                        txt = await r.text()
                        await tg_call("sendMessage", {"chat_id": chat_id, "text": f"Не удалось создать бронь: {txt}", "reply_markup": inline_keyboard})
                        return {"ok": True}
                    data = await r.json()
        except Exception as e:
            await tg_call("sendMessage", {"chat_id": chat_id, "text": f"Ошибка API: {e}", "reply_markup": inline_keyboard})
            return {"ok": True}

        bid = data.get("id")
        df, dt = data.get("date_from"), data.get("date_to")
        await tg_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"✅ Заявка создана!\nНомер #{bid}\nДаты: {df} — {dt}\nСтатус: {data.get('status')}",
            "reply_markup": inline_keyboard
        })
        return {"ok": True}

    if text:
        await show_inline_only("Используйте кнопку «Турист_03 ⛺️», чтобы открыть приложение.")
        return {"ok": True}

    return {"ok": True}
