import os
import json
import logging
import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import datetime, date
import re
import secrets
from contextlib import contextmanager
from dotenv import load_dotenv
from typing import List, Optional
from glob import glob

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("tourist03.superadmin")

from fastapi import FastAPI, Request, HTTPException, Depends, status, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

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
templates = Jinja2Templates(directory=TEMPLATES)
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB   = os.getenv("PG_DB", "tourist03")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
SUPERADMIN_API_KEY = os.getenv("SUPERADMIN_API_KEY")
SIM_VERIFY_CODE = os.getenv("SIM_VERIFY_CODE", "0000")
TERMS_VERSION = os.getenv("TERMS_VERSION", "2026-01-04")

def _pg_connect(schema: str):
    # Ensure values passed to psycopg2 are proper Python strings.
    # On some Windows setups environment variables may contain bytes
    # or be decoded with a different encoding which causes
    # psycopg2 to raise UnicodeDecodeError during connection.
    def _safe_str(val):
        if isinstance(val, bytes):
            try:
                return val.decode("utf-8")
            except Exception:
                return val.decode("utf-8", errors="replace")
        if val is None:
            return None
        return str(val)

    kwargs = dict(
        host=_safe_str(PG_HOST),
        port=PG_PORT,
        dbname=_safe_str(PG_DB),
        user=_safe_str(PG_USER),
        password=_safe_str(PG_PASSWORD),
        # Request server to use UTF-8 for client messages to avoid
        # UnicodeDecodeError when server returns localized (e.g. CP1251) text.
        options='-c client_encoding=UTF8',
        cursor_factory=RealDictCursor,
    )

    try:
        conn = psycopg2.connect(**kwargs)
    except UnicodeDecodeError as e:
        # Raise a clearer error with the problematic parameter values
        msg = (
            "UnicodeDecodeError while connecting to Postgres. "
            "Sanitized connection parameters (repr):\n"
            f"host={repr(kwargs.get('host'))}, dbname={repr(kwargs.get('dbname'))}, "
            f"user={repr(kwargs.get('user'))}, password={repr(kwargs.get('password'))}\n"
            f"Original error: {e!r}"
        )
        raise RuntimeError(msg) from e
    except Exception:
        # Re-raise other exceptions but include connection parameters for easier debugging.
        raise

    try:
        with conn.cursor() as cur:
            cur.execute('SET search_path TO %s', (schema,))
    except errors.InvalidSchemaName:
        conn.rollback()
    return conn


@contextmanager
def _db_conn(schema: str):
    conn = _pg_connect(schema)
    try:
        yield conn
    finally:
        conn.close()


def _normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        return ""
    s = re.sub(r"[^\d+]", "", phone)
    if not s:
        return ""
    if s.startswith("+"):
        # keep only one leading '+'
        s = "+" + re.sub(r"[^\d]", "", s[1:])
        # Normalize rare case: +8... -> +7...
        if s.startswith("+8"):
            s = "+7" + s[2:]
        return s

    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return ""
    # Common RU inputs:
    # 9XXXXXXXXX -> +79XXXXXXXXX
    # 8XXXXXXXXXX -> +7XXXXXXXXXX
    # 7XXXXXXXXXX -> +7XXXXXXXXXX
    if digits.startswith("8"):
        return "+7" + digits[1:]
    if digits.startswith("9"):
        return "+7" + digits
    if digits.startswith("7"):
        return "+" + digits
    return digits


def _get_user_by_phone_email(conn, phone: str, email: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, phone, email, role, phone_verified, email_verified
        FROM auth.users
        WHERE phone = %s OR email = %s
        """,
        (phone, email),
    )
    return cur.fetchall()


def _get_user_by_phone(conn, phone: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, phone, email, role, phone_verified, email_verified
        FROM auth.users
        WHERE phone = %s
        """,
        (phone,),
    )
    return cur.fetchone()


def _user_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "role": row.get("role") or "user",
        "phone_verified": bool(row.get("phone_verified")),
        "email_verified": bool(row.get("email_verified")),
    }


def log_user_event(user_id: int, event_type: str, payload: Optional[dict] = None) -> None:
    if not user_id or not event_type:
        return
    try:
        with _db_conn("auth") as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO auth.user_events (user_id, event_type, payload) VALUES (%s, %s, %s::jsonb)",
                (int(user_id), str(event_type), json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
    except Exception:
        # Logging must never break main flows.
        pass


def issue_user_token(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    try:
        with _db_conn("auth") as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO auth.user_tokens (token, user_id) VALUES (%s, %s)",
                (token, int(user_id)),
            )
            conn.commit()
    except Exception:
        pass
    return token


def get_current_user(request: Request) -> dict:
    authz = (request.headers.get("authorization") or "").strip()
    if not authz.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    token = authz.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.name, u.phone, u.email, u.role, u.phone_verified, u.email_verified, u.created_at
            FROM auth.user_tokens t
            JOIN auth.users u ON u.id = t.user_id
            WHERE t.token = %s AND t.revoked = FALSE
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
        user = dict(row)
        if not user.get("email_verified"):
            user["email"] = ""
        return user

def hash_password(password: str) -> str:
    # bcrypt backend only supports passwords up to 72 bytes.
    # Ensure we don't pass longer byte sequences to the backend which cause ValueError.
    if password is None:
        password = ""
    try:
        # Truncate to 72 bytes in UTF-8 encoding (safe fallback)
        b = str(password).encode('utf-8', errors='ignore')
        if len(b) > 72:
            b = b[:72]
            # decode back to str for passlib
            password = b.decode('utf-8', errors='ignore')
        return pwd_context.hash(password)
    except Exception:
        logger.exception("Error hashing password")
        # raise a generic exception to be handled by caller
        raise


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminMeResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str


class SuperAdminCreateAccountRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    camp_ids: List[int]


class SuperAdminUpdateAccountRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    camp_ids: Optional[List[int]] = None


class RegisterStartRequest(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    accept_terms: bool = False


class VerifyPhoneRequest(BaseModel):
    phone: str
    code: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class SkipEmailRequest(BaseModel):
    phone: str


class LoginStartRequest(BaseModel):
    phone: str


class LoginVerifyRequest(BaseModel):
    phone: str
    code: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class BookingEditRequest(BaseModel):
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests_count: Optional[int] = None
    comment: Optional[str] = None


class BookingCreateRequest(BaseModel):
    camp_id: int
    room_id: int
    check_in: date
    check_out: date
    adults: int = 1
    kids: int = 0
    guests_count: Optional[int] = None
    comment: Optional[str] = None


class BookingAdminUpdateRequest(BaseModel):
    status: Optional[str] = None
    payment_required: Optional[bool] = None
    payment_status: Optional[str] = None

class AdminCreateBookingRequest(BaseModel):
    camp_id: int
    room_id: Optional[int] = None
    check_in: date
    check_out: date
    guests_count: int = 1
    status: str = "pending"
    payment_status: str = "unpaid"
    payment_required: bool = False
    guest_name: Optional[str] = None
    guest_phone: Optional[str] = None
    guest_email: Optional[EmailStr] = None
    comment: Optional[str] = None

def get_current_admin(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, display_name
            FROM auth.camp_admin_accounts
            WHERE id = %s AND is_active = TRUE
            """,
            (admin_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def _get_admin_camp_ids(admin_id: int) -> list[int]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT camp_id FROM crm.camp_admin_links WHERE admin_id = %s",
            (admin_id,),
        )
        camp_ids = [row["camp_id"] for row in cur.fetchall()]
    return camp_ids


def get_superadmin(request: Request):
    """
    Простая проверка прав суперадмина.
    Если в сессии уже выставлен флаг superadmin (например, через внешний логин), пропускаем запрос.
    При наличии SUPERADMIN_API_KEY дополнительно проверяем заголовок, чтобы при необходимости ограничить доступ.
    """
    if request.session.get("superadmin") is True:
        return True
    if not SUPERADMIN_API_KEY:
        return True
    header_token = request.headers.get("x-superadmin-key") or request.headers.get("x-superadmin-token")
    if header_token == SUPERADMIN_API_KEY:
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет доступа")



# === Подключение FastAPI ===
app = FastAPI(title="Tourist_03 Admin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", secrets.token_hex(32)),
    session_cookie="t03_admin_session",
    max_age=60 * 60 * 24 * 7,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# === SQL SELECT константы ===
CAMP_SELECT_ALL = """
	SELECT id, name, lat, lng, min_price, emoji,
	       lake_name, photo_main, status, owner, manager, admin_phones,
	       rooms_count, beds_count, address, phone, site_url, emoji_size,
	       bbq_count, bbq_shared_count, bath_count, sauna_count,
	       pools_private_count, pools_shared_count,
	       description,
	       housing_type
	FROM catalog.camps
"""


ROOM_SELECT = """
SELECT id, camp_id, name, room_type, floors, floor, beds_single, beds_double, wc_count, bath_type,
       has_ac, has_bbq, has_kitchen, capacity, price, photo_main, photos_json,
       description AS desc, price_adult, price_child, discount_pct, discount_from_nights,
       wc_type, bbq_type, kitchen_type, gazebo_type, terrace_type, balcony_type, pool_type
FROM catalog.rooms
"""



def init_camps_db():
    """Создает схему catalog и таблицы каталога."""
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS catalog;")
        cur.execute("SET search_path TO catalog;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.camps (
                id SERIAL PRIMARY KEY,
                name TEXT,
                lat DOUBLE PRECISION,
                lng DOUBLE PRECISION,
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
                pools_shared_count INTEGER,
                description TEXT,
                housing_type TEXT NOT NULL DEFAULT 'apartments'
            )
            """
        )
        cur.execute("ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS housing_type TEXT NOT NULL DEFAULT 'apartments'")
        cur.execute("UPDATE catalog.camps SET housing_type='apartments' WHERE housing_type IS NULL OR housing_type=''")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.rooms (
                id SERIAL PRIMARY KEY,
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
                description TEXT,
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
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.camp_photos (
                id SERIAL PRIMARY KEY,
                camp_id INTEGER,
                url TEXT,
                sort INTEGER,
                cover INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.room_photos (
                id SERIAL PRIMARY KEY,
                camp_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                cover INTEGER DEFAULT 0,
                sort INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()



def init_users_db():
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute('CREATE SCHEMA IF NOT EXISTS auth;')
        cur.execute('SET search_path TO auth;')
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.users (
                id SERIAL PRIMARY KEY,
                name TEXT,
                phone TEXT,
                role TEXT
            )
            """
        )
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email TEXT")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS terms_version TEXT")
        # Best-effort uniqueness (do not break startup if legacy data contains duplicates).
        cur.execute(
            """
            DO $$
            BEGIN
                BEGIN
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique ON auth.users(phone)
                    WHERE phone IS NOT NULL AND phone <> '';
                EXCEPTION WHEN unique_violation THEN
                    -- duplicates exist; skip unique index
                END;

                BEGIN
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON auth.users((lower(email)))
                    WHERE email IS NOT NULL AND email <> '';
                EXCEPTION WHEN unique_violation THEN
                    -- duplicates exist; skip unique index
                END;
            END $$;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.user_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_events_user_created ON auth.user_events(user_id, created_at DESC)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.user_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_tokens_user_created ON auth.user_tokens(user_id, created_at DESC)")
        conn.commit()



def init_crm_db():
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute('CREATE SCHEMA IF NOT EXISTS auth;')
        cur.execute('CREATE SCHEMA IF NOT EXISTS crm;')
        cur.execute('SET search_path TO crm;')
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.camp_admin_accounts (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.camp_admin_links (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                camp_id INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.bookings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                camp_id INTEGER NOT NULL,
                room_id INTEGER,
                check_in DATE NOT NULL,
                check_out DATE NOT NULL,
                guests_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'crm',
                comment TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        # Миграция: добавляем столбцы source и comment если их нет
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'source'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'crm';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'comment'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN comment TEXT;
                END IF;
            END $$;
            """
        )

        # Миграция: поля оплаты/статуса оплаты
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'payment_status'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'payment_required'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN payment_required BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
            """
        )

        # Миграция: гостевые поля (для броней без user_id)
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'guest_name'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN guest_name TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'guest_phone'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN guest_phone TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'guest_email'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN guest_email TEXT;
                END IF;
            END $$;
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.admins (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                camp_id INTEGER,
                role TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.commit()





def create_test_admin(email: str, password: str, display_name: str = "Тестовый админ"):
    """Создание тестового управляющего (используется для отладки)."""
    if not email or not password:
        return
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            """,
            (email.lower().strip(), hash_password(password), (display_name or "Тестовый админ").strip()),
        )
        conn.commit()

# Ensure database schemas exist on startup
init_camps_db()
init_users_db()
init_crm_db()

TEST_ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL")
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD")
if TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD:
    create_test_admin(
        TEST_ADMIN_EMAIL,
        TEST_ADMIN_PASSWORD,
        os.getenv("TEST_ADMIN_DISPLAY_NAME", "Тестовый админ"),
    )


# === Простые страницы ===
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/index.html", response_class=HTMLResponse)
def index_html():
    # Дополнительный маршрут: некоторые клиенты (прокси/вебвью) могут запрашивать /index.html
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/superadmin", response_class=HTMLResponse)
def superadmin_page():
    return FileResponse(os.path.join(BASE_DIR, "superadmin.html"))

@app.get("/admincamps", response_class=HTMLResponse)
def admin_camps_page(request: Request):
    """CRM-интерфейс для администраторов баз."""
    return templates.TemplateResponse("admin-camps.html", {"request": request})


# === API: Пользователи (минимально, фронт опрашивает /api/users) ===
@app.get("/api/users")
def api_users_list():
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, role, email, email_verified, phone_verified, created_at
            FROM auth.users
            ORDER BY id
            """
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if not d.get("email_verified"):
            d["email"] = ""
        out.append(d)
    return out


@app.post("/api/auth/register/start")
def auth_register_start(payload: RegisterStartRequest):
    name = (payload.name or "").strip()
    phone = _normalize_phone(payload.phone)
    email = (payload.email or "").strip().lower() if payload.email else ""
    if not name or not phone:
        raise HTTPException(status_code=400, detail="Заполните имя и телефон")
    if payload.accept_terms is not True:
        raise HTTPException(status_code=400, detail="Нужно принять пользовательское соглашение")

    user_id = None
    with _db_conn("auth") as conn:
        if email:
            rows = _get_user_by_phone_email(conn, phone, email)
        else:
            row = _get_user_by_phone(conn, phone)
            rows = [row] if row else []

        rows = [r for r in rows if r]
        ids = {r["id"] for r in rows}
        if len(ids) > 1:
            raise HTTPException(status_code=409, detail="Телефон или email уже используется")

        if rows:
            row = rows[0]
            user_id = row["id"]
            row_email = (row.get("email") or "").strip().lower()
            email_present = bool(row_email)
            complete = bool(row.get("phone_verified")) and (not email_present or bool(row.get("email_verified")))
            if complete:
                raise HTTPException(status_code=409, detail="Пользователь уже зарегистрирован")

            cur = conn.cursor()
            if email:
                cur.execute(
                    """
                    UPDATE auth.users
                    SET name=%s, email=%s, phone_verified=FALSE, email_verified=FALSE
                    WHERE id=%s
                    RETURNING id
                    """,
                    (name, email, row["id"]),
                )
            else:
                cur.execute(
                    """
                    UPDATE auth.users
                    SET name=%s, email=NULL, phone_verified=FALSE, email_verified=FALSE
                    WHERE id=%s
                    RETURNING id
                    """,
                    (name, row["id"]),
                )
            user_id = cur.fetchone()["id"]
            cur.execute(
                """
                UPDATE auth.users
                SET terms_accepted_at=NOW(), terms_version=%s
                WHERE id=%s
                """,
                (TERMS_VERSION, user_id),
            )
            conn.commit()
        else:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth.users (
                    name, phone, email, role,
                    phone_verified, email_verified,
                    terms_accepted_at, terms_version
                )
                VALUES (%s, %s, %s, %s, FALSE, FALSE, NOW(), %s)
                RETURNING id
                """,
                (name, phone, email or None, "user", TERMS_VERSION),
            )
            user_id = cur.fetchone()["id"]
            conn.commit()

    log_user_event(
        user_id,
        "register_start",
        {
            "name": name,
            "phone": phone,
            "email": email or None,
            "accept_terms": True,
            "terms_version": TERMS_VERSION,
        },
    )
    return {"ok": True}


@app.post("/api/auth/register/verify-phone")
def auth_register_verify_phone(payload: VerifyPhoneRequest):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")

    user_id = None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET phone_verified=TRUE
            WHERE phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (phone,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        conn.commit()

    log_user_event(user_id, "verify_phone", {"phone": phone})
    email_present = bool((row.get("email") or "").strip())
    if not email_present:
        return {
            "ok": True,
            "token": issue_user_token(user_id),
            "user": _user_public(row),
        }
    return {"ok": True, "user": _user_public(row)}


@app.post("/api/auth/register/verify-email")
def auth_register_verify_email(payload: VerifyEmailRequest):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")

    user_id = None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email_verified=TRUE
            WHERE email=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (email,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        conn.commit()

    log_user_event(user_id, "verify_email", {"email": email})
    if row.get("phone_verified") and row.get("email_verified"):
        return {
            "ok": True,
            "token": issue_user_token(user_id),
            "user": _user_public(row),
        }
    return {"ok": True, "user": _user_public(row)}


@app.get("/api/superadmin/users/{user_id}/history", dependencies=[Depends(get_superadmin)])
def superadmin_user_history(user_id: int):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, role, phone_verified, email_verified, created_at
            FROM auth.users
            WHERE id = %s
            """,
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="not found")

        cur.execute(
            """
            SELECT id, event_type, payload, created_at
            FROM auth.user_events
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 500
            """,
            (user_id,),
        )
        events = [dict(r) for r in cur.fetchall()]

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 500
            """,
            (user_id,),
        )
        bookings = [dict(r) for r in cur.fetchall()]

    u = dict(user)
    if not u.get("email_verified"):
        u["email"] = ""

    return {"user": u, "bookings": bookings, "events": events, "payments": []}


@app.post("/api/auth/register/skip-email")
def auth_register_skip_email(payload: SkipEmailRequest):
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    user_id = None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email=NULL, email_verified=FALSE, phone_verified=TRUE
            WHERE phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (phone,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        conn.commit()
    log_user_event(user_id, "skip_email", {"phone": phone})
    return {"ok": True, "token": issue_user_token(user_id), "user": _user_public(row)}


@app.post("/api/auth/login/start")
def auth_login_start(payload: LoginStartRequest):
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    user_id = None
    with _db_conn("auth") as conn:
        row = _get_user_by_phone(conn, phone)
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        if not row.get("phone_verified"):
            raise HTTPException(status_code=403, detail="Номер телефона не подтверждён")
        email_present = bool((row.get("email") or "").strip())
        if email_present and not row.get("email_verified"):
            raise HTTPException(status_code=403, detail="Email не подтверждён")
    log_user_event(user_id, "login_start", {"phone": phone})
    return {"ok": True}


@app.post("/api/auth/login/verify")
def auth_login_verify(payload: LoginVerifyRequest):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")
    user_id = None
    with _db_conn("auth") as conn:
        row = _get_user_by_phone(conn, phone)
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
    log_user_event(user_id, "login_ok", {"phone": phone})
    return {
        "ok": True,
        "token": issue_user_token(user_id),
        "user": _user_public(row),
    }


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    return {"ok": True, "user": user}


@app.post("/api/auth/logout")
def auth_logout(request: Request, user: dict = Depends(get_current_user)):
    authz = (request.headers.get("authorization") or "").strip()
    token = authz.split(" ", 1)[1].strip() if " " in authz else ""
    if token:
        try:
            with _db_conn("auth") as conn:
                cur = conn.cursor()
                cur.execute("UPDATE auth.user_tokens SET revoked=TRUE WHERE token=%s", (token,))
                conn.commit()
        except Exception:
            pass
    log_user_event(user["id"], "logout", {})
    return {"ok": True}


@app.put("/api/auth/profile")
def auth_update_profile(payload: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip() if payload.name is not None else None
    phone = _normalize_phone(payload.phone) if payload.phone is not None else None
    email = (str(payload.email).strip().lower() if payload.email is not None else None) if payload.email is not None else None

    need_phone_verify = False
    need_email_verify = False
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, phone_verified, email_verified
            FROM auth.users
            WHERE id=%s
            """,
            (user["id"],),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        current = dict(row)

        new_name = name if name is not None else (current.get("name") or "")
        new_phone = phone if phone is not None else (current.get("phone") or "")
        new_email = email if email is not None else ((current.get("email") or "").strip().lower())

        if new_phone != (current.get("phone") or ""):
            need_phone_verify = True
        if (new_email or "") != ((current.get("email") or "").strip().lower()):
            need_email_verify = bool(new_email)

        if new_phone:
            cur.execute(
                "SELECT 1 FROM auth.users WHERE phone=%s AND id<>%s LIMIT 1",
                (new_phone, user["id"]),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Телефон уже используется")
        if new_email:
            cur.execute(
                "SELECT 1 FROM auth.users WHERE lower(email)=lower(%s) AND id<>%s LIMIT 1",
                (new_email, user["id"]),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email уже используется")

        try:
            cur.execute(
                """
                UPDATE auth.users
                SET name=%s,
                    phone=%s,
                    email=%s,
                    phone_verified=%s,
                    email_verified=%s
                WHERE id=%s
                RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
                """,
                (
                    new_name,
                    new_phone or None,
                    new_email or None,
                    (False if need_phone_verify else bool(current.get("phone_verified"))),
                    (False if need_email_verify else (bool(current.get("email_verified")) if new_email else False)),
                    user["id"],
                ),
            )
        except errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Телефон или email уже используется")

        updated = cur.fetchone()
        conn.commit()

    updated_user = dict(updated)
    if not updated_user.get("email_verified"):
        updated_user["email"] = ""

    log_user_event(user["id"], "profile_update", {"name": new_name, "phone": new_phone, "email": new_email or None})
    return {"ok": True, "user": updated_user, "need_phone_verify": need_phone_verify, "need_email_verify": need_email_verify}


@app.post("/api/auth/profile/verify-phone")
def auth_profile_verify_phone(payload: VerifyPhoneRequest, user: dict = Depends(get_current_user)):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET phone_verified=TRUE
            WHERE id=%s AND phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (user["id"], phone),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        conn.commit()
    d = dict(row)
    if not d.get("email_verified"):
        d["email"] = ""
    log_user_event(user["id"], "profile_verify_phone", {"phone": phone})
    return {"ok": True, "user": d}


@app.post("/api/auth/profile/verify-email")
def auth_profile_verify_email(payload: VerifyEmailRequest, user: dict = Depends(get_current_user)):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email_verified=TRUE
            WHERE id=%s AND lower(email)=lower(%s)
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (user["id"], email),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        conn.commit()
    d = dict(row)
    if not d.get("email_verified"):
        d["email"] = ""
    log_user_event(user["id"], "profile_verify_email", {"email": email})
    return {"ok": True, "user": d}


def _booking_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "camp_id": row.get("camp_id"),
        "camp_name": row.get("camp_name") or "",
        "room_id": row.get("room_id"),
        "room_name": row.get("room_name") or "",
        "check_in": row.get("check_in"),
        "check_out": row.get("check_out"),
        "guests_count": row.get("guests_count"),
        "status": row.get("status") or "",
        "payment_required": bool(row.get("payment_required")),
        "payment_status": row.get("payment_status") or "unpaid",
        "comment": row.get("comment") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@app.get("/api/auth/bookings")
def auth_my_bookings(mode: str = "active", user: dict = Depends(get_current_user)):
    mode = (mode or "active").strip().lower()
    today = date.today()
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.payment_required,
                b.payment_status,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC, b.id DESC
            """,
            (user["id"],),
        )
        rows = [dict(r) for r in cur.fetchall()]

    active_statuses = {"pending", "confirmed", "awaiting_payment"}
    terminal_statuses = {"cancelled_by_user", "rejected", "completed", "cancelled"}

    active = []
    history = []
    for r in rows:
        st = (r.get("status") or "").strip().lower()
        is_terminal = st in terminal_statuses
        is_past = r.get("check_out") is not None and r["check_out"] < today
        if is_past and not is_terminal:
            r["status"] = "completed"
        if is_terminal or is_past:
            history.append(_booking_public(r))
        else:
            if not st or st in active_statuses:
                active.append(_booking_public(r))
            else:
                active.append(_booking_public(r))

    return {"ok": True, "items": (history if mode == "history" else active)}


@app.post("/api/auth/bookings")
def auth_booking_create(payload: BookingCreateRequest, user: dict = Depends(get_current_user)):
    guests_count = payload.guests_count
    if guests_count is None:
        guests_count = int(payload.adults or 0) + int(payload.kids or 0)
    try:
        guests_count = int(guests_count)
    except Exception:
        guests_count = 0
    if guests_count <= 0:
        raise HTTPException(status_code=400, detail="Укажите количество гостей")
    if payload.check_out <= payload.check_in:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")

    # Validate room belongs to camp
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, camp_id, name FROM catalog.rooms WHERE id=%s",
            (payload.room_id,),
        )
        room = cur.fetchone()
    if not room or int(room.get("camp_id") or 0) != int(payload.camp_id):
        raise HTTPException(status_code=400, detail="Неверный номер/база")

    # Check overlap with existing bookings
    blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM crm.bookings
            WHERE room_id=%s
              AND camp_id=%s
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            LIMIT 1
            """,
            (payload.room_id, payload.camp_id, blocked_statuses, payload.check_out, payload.check_in),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Этот вариант уже забронирован на выбранные даты")

        cur.execute(
            """
            INSERT INTO crm.bookings(user_id, camp_id, room_id, check_in, check_out, guests_count, status, source, comment)
            VALUES (%s,%s,%s,%s,%s,%s,'pending','webapp',%s)
            RETURNING id
            """,
            (user["id"], payload.camp_id, payload.room_id, payload.check_in, payload.check_out, guests_count, payload.comment),
        )
        row = cur.fetchone()
        conn.commit()

    booking_id = int(row["id"])
    log_user_event(
        user["id"],
        "booking_create",
        {
            "booking_id": booking_id,
            "camp_id": payload.camp_id,
            "room_id": payload.room_id,
            "check_in": str(payload.check_in),
            "check_out": str(payload.check_out),
            "guests_count": guests_count,
        },
    )
    return {"ok": True, "booking_id": booking_id}


@app.get("/api/auth/bookings/{booking_id}")
def auth_booking_one(booking_id: int, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.payment_required,
                b.payment_status,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.id = %s AND b.user_id = %s
            """,
            (booking_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, "item": _booking_public(dict(row))}


@app.put("/api/auth/bookings/{booking_id}")
def auth_booking_edit(booking_id: int, payload: BookingEditRequest, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status, payment_status FROM crm.bookings WHERE id=%s AND user_id=%s",
            (booking_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        booking = dict(row)
        st = (booking.get("status") or "").strip().lower()
        if st in ("completed", "rejected", "cancelled_by_user", "cancelled"):
            raise HTTPException(status_code=400, detail="Нельзя редактировать завершённую бронь")
        if (booking.get("payment_status") or "").strip().lower() == "paid":
            raise HTTPException(status_code=400, detail="Нельзя редактировать оплаченную бронь")

        updates = []
        params = []
        if payload.check_in is not None:
            updates.append("check_in=%s")
            params.append(payload.check_in)
        if payload.check_out is not None:
            updates.append("check_out=%s")
            params.append(payload.check_out)
        if payload.guests_count is not None:
            updates.append("guests_count=%s")
            params.append(int(payload.guests_count))
        if payload.comment is not None:
            updates.append("comment=%s")
            params.append((payload.comment or "").strip())
        if not updates:
            return {"ok": True}
        updates.append("updated_at=NOW()")
        params.extend([booking_id, user["id"]])
        cur.execute(
            f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s AND user_id=%s",
            tuple(params),
        )
        conn.commit()
    log_user_event(user["id"], "booking_edit", {"booking_id": booking_id})
    return {"ok": True}


@app.post("/api/auth/bookings/{booking_id}/cancel")
def auth_booking_cancel(booking_id: int, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status FROM crm.bookings WHERE id=%s AND user_id=%s",
            (booking_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        st = (row.get("status") or "").strip().lower()
        if st in ("completed", "rejected", "cancelled_by_user", "cancelled"):
            raise HTTPException(status_code=400, detail="Бронь уже завершена")
        cur.execute(
            "UPDATE crm.bookings SET status='cancelled_by_user', updated_at=NOW() WHERE id=%s AND user_id=%s",
            (booking_id, user["id"]),
        )
        conn.commit()
    log_user_event(user["id"], "booking_cancel", {"booking_id": booking_id})
    return {"ok": True}


@app.post("/api/auth/bookings/{booking_id}/pay")
def auth_booking_pay(booking_id: int, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, payment_required, payment_status
            FROM crm.bookings
            WHERE id=%s AND user_id=%s
            """,
            (booking_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        st = (row.get("status") or "").strip().lower()
        pay_required = bool(row.get("payment_required"))
        pay_status = (row.get("payment_status") or "").strip().lower()
        if st != "confirmed":
            raise HTTPException(status_code=400, detail="Оплата доступна после подтверждения брони")
        if not pay_required:
            raise HTTPException(status_code=400, detail="Оплата пока не запрошена администратором")
        if pay_status != "unpaid":
            raise HTTPException(status_code=400, detail="Бронь уже оплачена или отмечена как наличная")
    log_user_event(user["id"], "booking_pay_click", {"booking_id": booking_id})
    return {"ok": True, "payment_url": None}


@app.get("/api/superadmin/camps", dependencies=[Depends(get_superadmin)])
def superadmin_list_camps():
    """
    Упрощенный список баз отдыха для суперадминки.
    """
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, address, lake_name, status
            FROM catalog.camps
            ORDER BY id
            """
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def _create_camp_admin_account(payload: SuperAdminCreateAccountRequest):
    email = payload.email.lower().strip()
    display_name = (payload.display_name or "").strip() or email
    password_raw = (payload.password or "").strip()
    if not password_raw:
        raise HTTPException(status_code=400, detail="Пароль не может быть пустым")

    logger.info("Запрос на создание учётки управляющего: email=%s, camps=%s", email, payload.camp_ids)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id
                FROM auth.camp_admin_accounts
                WHERE email = %s
                """,
                (email,),
            )
            existing = cur.fetchone()
            if existing:
                logger.warning("Попытка создать дубликат учётки для email=%s", email)
                raise HTTPException(status_code=400, detail="Учётная запись с таким логином уже существует")

            password_hash = hash_password(password_raw)
            cur.execute(
                """
                INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (email, password_hash, display_name),
            )
            row = cur.fetchone()
            admin_id = row["id"]

            linked: set[int] = set()
            for camp_id in payload.camp_ids:
                try:
                    cid = int(camp_id)
                except (ValueError, TypeError):
                    continue
                if cid in linked:
                    continue
                linked.add(cid)
                cur.execute(
                    """
                    INSERT INTO crm.camp_admin_links (admin_id, camp_id)
                    VALUES (%s, %s)
                    """,
                    (admin_id, cid),
                )

            conn.commit()
            logger.info("Учётка управляющего создана: id=%s, email=%s", admin_id, email)
            return {"status": "ok", "admin_id": admin_id}
        except HTTPException:
            conn.rollback()
            logger.exception("Ошибка валидации при создании учётки email=%s", email)
            raise
        except Exception:
            conn.rollback()
            logger.exception("Техническая ошибка при создании учётки email=%s", email)
            raise


def _update_camp_admin_account(admin_id: int, payload: SuperAdminUpdateAccountRequest):
    email = payload.email.lower().strip() if payload.email is not None else None
    display_name = (payload.display_name or "").strip() if payload.display_name is not None else None
    password_raw = (payload.password or "").strip() if payload.password is not None else None
    is_active = payload.is_active
    camp_ids = payload.camp_ids if payload.camp_ids is not None else None

    if email is not None and not email:
        raise HTTPException(status_code=400, detail="Email не может быть пустым")
    if display_name is not None and not display_name:
        raise HTTPException(status_code=400, detail="Имя управляющего не может быть пустым")

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, email, display_name, is_active
                FROM auth.camp_admin_accounts
                WHERE id=%s
                """,
                (admin_id,),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Учётная запись не найдена")

            updates = []
            params = []

            if email is not None and email != (existing.get("email") or "").lower().strip():
                cur.execute(
                    """
                    SELECT 1
                    FROM auth.camp_admin_accounts
                    WHERE lower(email) = lower(%s) AND id <> %s
                    """,
                    (email, admin_id),
                )
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Учётная запись с таким email уже существует")
                updates.append("email=%s")
                params.append(email)

            if display_name is not None and display_name != (existing.get("display_name") or ""):
                updates.append("display_name=%s")
                params.append(display_name)

            if password_raw is not None:
                if password_raw:
                    updates.append("password_hash=%s")
                    params.append(hash_password(password_raw))

            if is_active is not None and bool(is_active) != bool(existing.get("is_active")):
                updates.append("is_active=%s")
                params.append(bool(is_active))

            if updates:
                params.append(admin_id)
                cur.execute(
                    f"UPDATE auth.camp_admin_accounts SET {', '.join(updates)} WHERE id=%s",
                    tuple(params),
                )

            if camp_ids is not None:
                cur.execute("DELETE FROM crm.camp_admin_links WHERE admin_id=%s", (admin_id,))
                linked: set[int] = set()
                for camp_id in camp_ids:
                    try:
                        cid = int(camp_id)
                    except (ValueError, TypeError):
                        continue
                    if cid in linked:
                        continue
                    linked.add(cid)
                    cur.execute(
                        """
                        INSERT INTO crm.camp_admin_links (admin_id, camp_id)
                        VALUES (%s, %s)
                        """,
                        (admin_id, cid),
                    )

            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            logger.exception("Техническая ошибка при обновлении учётки id=%s", admin_id)
            raise

    logger.info("Учётка управляющего обновлена: id=%s", admin_id)
    return {"ok": True}


@app.get("/api/superadmin/accounts", dependencies=[Depends(get_superadmin)])
def superadmin_list_accounts():
    """
    Список всех управляющих и привязанных к ним баз.
    """
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.email,
                a.display_name,
                a.is_active,
                a.created_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'camp_id', l.camp_id,
                            'camp_name', c.name
                        )
                        ORDER BY c.name
                    ) FILTER (WHERE l.camp_id IS NOT NULL),
                    '[]'::json
                ) AS camps
            FROM auth.camp_admin_accounts AS a
            LEFT JOIN crm.camp_admin_links AS l ON l.admin_id = a.id
            LEFT JOIN catalog.camps AS c ON c.id = l.camp_id
            GROUP BY a.id
            ORDER BY a.created_at DESC, a.id DESC
            """
        )
        rows = cur.fetchall()
    accounts = []
    for row in rows:
        raw_camps = row.get("camps")
        camps_data = []
        if isinstance(raw_camps, str):
            try:
                camps_data = json.loads(raw_camps)
            except Exception:
                camps_data = []
        elif isinstance(raw_camps, list):
            camps_data = raw_camps
        accounts.append(
            {
                "id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "camps": camps_data,
            }
        )
    return accounts


@app.get("/api/admincamps/accounts", dependencies=[Depends(get_superadmin)])
def superadmin_list_accounts_legacy():
    """
    Совместимость для клиентов, использующих admincamps-префикс.
    """
    return superadmin_list_accounts()


@app.post("/api/superadmin/accounts", dependencies=[Depends(get_superadmin)])
def superadmin_create_account(payload: SuperAdminCreateAccountRequest):
    """
    Создание учетной записи управляющего и привязка ее к выбранным базам отдыха.
    """
    return _create_camp_admin_account(payload)


@app.post("/api/admincamps/accounts", dependencies=[Depends(get_superadmin)])
def superadmin_create_account_legacy(payload: SuperAdminCreateAccountRequest):
    """
    Совместимость с фронтами, которые ожидают другой путь.
    """
    return _create_camp_admin_account(payload)


@app.post("/api/admincamps/account", dependencies=[Depends(get_superadmin)])
def superadmin_create_account_legacy_single(payload: SuperAdminCreateAccountRequest):
    return _create_camp_admin_account(payload)


@app.post("/api/admin/accounts", dependencies=[Depends(get_superadmin)])
def superadmin_create_account_admin_prefix(payload: SuperAdminCreateAccountRequest):
    return _create_camp_admin_account(payload)


@app.post("/api/admin/account", dependencies=[Depends(get_superadmin)])
def superadmin_create_account_admin_single(payload: SuperAdminCreateAccountRequest):
    return _create_camp_admin_account(payload)


@app.patch("/api/superadmin/accounts/{account_id}", dependencies=[Depends(get_superadmin)])
def superadmin_update_account(account_id: int, payload: SuperAdminUpdateAccountRequest):
    return _update_camp_admin_account(account_id, payload)


@app.patch("/api/admincamps/accounts/{account_id}", dependencies=[Depends(get_superadmin)])
def superadmin_update_account_legacy(account_id: int, payload: SuperAdminUpdateAccountRequest):
    return _update_camp_admin_account(account_id, payload)


@app.patch("/api/admin/accounts/{account_id}", dependencies=[Depends(get_superadmin)])
def superadmin_update_account_admin_prefix(account_id: int, payload: SuperAdminUpdateAccountRequest):
    return _update_camp_admin_account(account_id, payload)


# === API: Базы отдыха ===
@app.get("/api/camps")
def api_camps_list():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " ORDER BY id")
        rows = cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/api/camps/{camp_id}")
def api_camp_one(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " WHERE id=%s", (camp_id,))
        row = cur.fetchone()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)


@app.get("/api/camps/{camp_id}/photos")
def api_camp_photos(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url, sort, cover FROM catalog.camp_photos WHERE camp_id=%s ORDER BY sort, id",
            (camp_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/api/camps/{camp_id}/available-rooms")
def api_camp_available_rooms(
    camp_id: int,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
):
    """
    Публичная выдача доступных апартаментов/домов/номеров по датам.
    Возвращает комнаты с полем available=true/false и housing_type базы.
    """
    from_d: Optional[date] = None
    to_d: Optional[date] = None
    if from_:
        try:
            from_d = date.fromisoformat(from_)
        except Exception:
            raise HTTPException(status_code=400, detail="Неверная дата заезда")
    if to:
        try:
            to_d = date.fromisoformat(to)
        except Exception:
            raise HTTPException(status_code=400, detail="Неверная дата выезда")
    if from_d and to_d and to_d <= from_d:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, housing_type FROM catalog.camps WHERE id=%s", (camp_id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="not found")
        housing_type = (camp.get("housing_type") or "apartments").strip().lower()
        if housing_type not in ("apartments", "houses", "rooms"):
            housing_type = "apartments"

        cur.execute(
            """
            SELECT
              r.*,
              COALESCE(
                json_agg(
                  json_build_object('url', p.url, 'cover', p.cover, 'sort', p.sort)
                  ORDER BY p.sort, p.id
                ) FILTER (WHERE p.url IS NOT NULL AND p.url <> ''),
                '[]'::json
              ) AS photos
            FROM catalog.rooms AS r
            LEFT JOIN catalog.room_photos AS p
              ON p.camp_id = r.camp_id AND p.room_id = r.id
            WHERE r.camp_id = %s
            GROUP BY r.id
            ORDER BY r.id
            """,
            (camp_id,),
        )
        rows = cur.fetchall()

    # Determine which room types to show depending on camp housing_type.
    room_type_filter: Optional[set[str]] = None
    if housing_type == "apartments":
        room_type_filter = {"Апартамент"}
    elif housing_type == "houses":
        room_type_filter = {"Дом", "Коттедж"}
    elif housing_type == "rooms":
        room_type_filter = {"Номер", "Комната"}

    booked_room_ids: set[int] = set()
    booked_all = False
    if from_d and to_d:
        blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
        with _db_conn("crm") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT room_id
                FROM crm.bookings
                WHERE camp_id=%s
                  AND (status IS NULL OR lower(status) NOT IN %s)
                  AND check_in < %s
                  AND check_out > %s
                """,
                (camp_id, blocked_statuses, to_d, from_d),
            )
            for r in cur.fetchall():
                rid = r.get("room_id")
                if rid is None:
                    booked_all = True
                    continue
                try:
                    booked_room_ids.add(int(rid))
                except Exception:
                    pass

    out = []
    for r in rows:
        d = dict(r)
        if room_type_filter:
            rt = (d.get("room_type") or "").strip()
            if rt and rt not in room_type_filter:
                continue

        photos = d.get("photos") or []
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []
        norm = []
        for idx, p in enumerate(photos or []):
            if isinstance(p, str):
                url = p.strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": idx == 0, "sort": idx})
                continue
            if isinstance(p, dict):
                url = str(p.get("url") or "").strip()
                if not url:
                    continue
                norm.append(
                    {
                        "url": url,
                        "cover": bool(p.get("cover")) or idx == 0,
                        "sort": int(p.get("sort") or idx),
                    }
                )
        if norm and not any(x.get("cover") for x in norm):
            norm[0]["cover"] = True
        d["photos"] = norm[:5]
        d["available"] = (not booked_all) and (int(d.get("id") or 0) not in booked_room_ids)
        out.append(d)

    # Fallback: if no rooms match selected housing_type — return all rooms for camp
    if room_type_filter and not out:
        out = []
        for r in rows:
            d = dict(r)
            photos = d.get("photos") or []
            if isinstance(photos, str):
                try:
                    photos = json.loads(photos)
                except Exception:
                    photos = []
            norm = []
            for idx, p in enumerate(photos or []):
                if isinstance(p, str):
                    url = p.strip()
                    if not url:
                        continue
                    norm.append({"url": url, "cover": idx == 0, "sort": idx})
                    continue
                if isinstance(p, dict):
                    url = str(p.get("url") or "").strip()
                    if not url:
                        continue
                    norm.append(
                        {
                            "url": url,
                            "cover": bool(p.get("cover")) or idx == 0,
                            "sort": int(p.get("sort") or idx),
                        }
                    )
            if norm and not any(x.get("cover") for x in norm):
                norm[0]["cover"] = True
            d["photos"] = norm[:5]
            d["available"] = (not booked_all) and (int(d.get("id") or 0) not in booked_room_ids)
            out.append(d)

    return {"ok": True, "camp_id": camp_id, "housing_type": housing_type, "rooms": out}


@app.get("/api/rooms")
def api_rooms_list(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              r.*,
              COALESCE(
                json_agg(
                  json_build_object('url', p.url, 'cover', p.cover, 'sort', p.sort)
                  ORDER BY p.sort, p.id
                ) FILTER (WHERE p.url IS NOT NULL AND p.url <> ''),
                '[]'::json
              ) AS photos
            FROM catalog.rooms AS r
            LEFT JOIN catalog.room_photos AS p
              ON p.camp_id = r.camp_id AND p.room_id = r.id
            WHERE r.camp_id = %s
            GROUP BY r.id
            ORDER BY r.id
            """,
            (camp_id,),
        )
        rows = cur.fetchall()

        cur.execute("SELECT name FROM catalog.camps WHERE id=%s", (camp_id,))
        camp_row = cur.fetchone()
        camp_name = (camp_row or {}).get("name") if camp_row else None

    out = []
    for r in rows:
        d = dict(r)
        photos = d.get("photos") or []
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []
        # Fallback to photos_json (legacy) if join returned nothing
        if not photos:
            try:
                legacy = json.loads(d.get("photos_json") or "[]")
            except Exception:
                legacy = []
            photos = []
            for idx, p in enumerate(legacy):
                url = p if isinstance(p, str) else (p.get("url") if isinstance(p, dict) else None)
                url = (url or "").strip()
                if not url:
                    continue
                cover = (idx == 0) if isinstance(p, str) else bool(p.get("cover")) or (idx == 0)
                photos.append({"url": url, "cover": cover, "sort": idx})

        # Fallback to filesystem if DB is empty/corrupted
        if not photos:
            photos = _room_photos_from_fs(camp_id, int(d.get("id") or 0), camp_name=camp_name)

        # Normalize output: keep only valid items and ensure cover/sort
        norm = []
        for idx, p in enumerate(photos or []):
            if isinstance(p, str):
                url = p.strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": idx == 0, "sort": idx})
                continue
            if isinstance(p, dict):
                url = str(p.get("url") or "").strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": bool(p.get("cover")) or idx == 0, "sort": int(p.get("sort") or idx)})
        if norm:
            # ensure exactly one cover
            if not any(x.get("cover") for x in norm):
                norm[0]["cover"] = True
        d["photos"] = norm[:5]
        out.append(d)
    return out


@app.get("/api/rooms/all")
def api_rooms_all():
    """Возвращает ВСЕ комнаты из всех баз (для фильтрации на фронте)"""
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              r.*,
              COALESCE(
                json_agg(
                  json_build_object('url', p.url, 'cover', p.cover, 'sort', p.sort)
                  ORDER BY p.sort, p.id
                ) FILTER (WHERE p.url IS NOT NULL AND p.url <> ''),
                '[]'::json
              ) AS photos
            FROM catalog.rooms AS r
            LEFT JOIN catalog.room_photos AS p
              ON p.camp_id = r.camp_id AND p.room_id = r.id
            GROUP BY r.id
            ORDER BY r.camp_id, r.id
            """
        )
        rows = cur.fetchall()
        cur.execute("SELECT id, name FROM catalog.camps")
        camp_names = {row["id"]: row.get("name") for row in cur.fetchall()}

    out = []
    for r in rows:
        d = dict(r)
        camp_id = int(d.get("camp_id") or 0)
        camp_name = camp_names.get(camp_id)
        photos = d.get("photos") or []
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []

        if not photos:
            try:
                legacy = json.loads(d.get("photos_json") or "[]")
            except Exception:
                legacy = []
            photos = []
            for idx, p in enumerate(legacy):
                url = p if isinstance(p, str) else (p.get("url") if isinstance(p, dict) else None)
                url = (url or "").strip()
                if not url:
                    continue
                cover = (idx == 0) if isinstance(p, str) else bool(p.get("cover")) or (idx == 0)
                photos.append({"url": url, "cover": cover, "sort": idx})

        if not photos and camp_id and d.get("id"):
            photos = _room_photos_from_fs(camp_id, int(d.get("id") or 0), camp_name=camp_name)

        norm = []
        for idx, p in enumerate(photos or []):
            if isinstance(p, str):
                url = p.strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": idx == 0, "sort": idx})
                continue
            if isinstance(p, dict):
                url = str(p.get("url") or "").strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": bool(p.get("cover")) or idx == 0, "sort": int(p.get("sort") or idx)})
        if norm and not any(x.get("cover") for x in norm):
            norm[0]["cover"] = True
        d["photos"] = norm[:5]
        out.append(d)
    return out


@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    """Авторизация управляющего."""
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, password_hash, display_name, is_active
            FROM auth.camp_admin_accounts
            WHERE email = %s
            """,
            (req.email.lower().strip(),),
        )
        row = cur.fetchone()
    if not row or not row["is_active"] or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный логин или пароль")
    request.session["admin_id"] = row["id"]
    return {"status": "ok"}


@app.post("/api/admin/logout")
def admin_logout(request: Request):
    """Выход из CRM."""
    request.session.clear()
    return {"status": "ok"}


@app.get("/api/admin/me", response_model=AdminMeResponse)
def admin_me(admin: dict = Depends(get_current_admin)):
    """Текущий управляющий."""
    return admin


@app.get("/api/admin/my-camps")
def api_admin_my_camps(admin: dict = Depends(get_current_admin)):
    """Возвращает базы отдыха, закреплённые за управляющим."""
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, address, description, status
            FROM catalog.camps
            WHERE id = ANY(%s)
            ORDER BY name
            """,
            (camp_ids,),
        )
        rows = cur.fetchall()
    response = []
    for row in rows:
        status_value = (row.get("status") or "").strip().lower()
        response.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or "",
                "region": row.get("address") or "Не указано",
                "description": row.get("description") or "",
                "is_active": status_value in ("", "active", "активна", "активный"),
            }
        )
    return response


@app.get("/api/admin/bookings")
def api_admin_bookings(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    """Бронирования управляющего с учётом доступных баз."""
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    conditions = []
    params: list = []
    if camp_id:
        if camp_id not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("b.check_in >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("b.check_out <= %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in DESC, b.id DESC
            """,
            tuple(params),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


@app.post("/api/admin/bookings")
def api_admin_create_booking(payload: AdminCreateBookingRequest, admin: dict = Depends(get_current_admin)):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    if payload.camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    if payload.check_out <= payload.check_in:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")
    if payload.guests_count <= 0:
        raise HTTPException(status_code=400, detail="Некорректное количество гостей")

    allowed_status = {"pending", "confirmed", "rejected", "completed", "cancelled_by_user", "cancelled"}
    allowed_payment = {"unpaid", "paid", "cash"}
    st = (payload.status or "pending").strip().lower()
    ps = (payload.payment_status or "unpaid").strip().lower()
    if st not in allowed_status:
        raise HTTPException(status_code=400, detail="Некорректный статус брони")
    if ps not in allowed_payment:
        raise HTTPException(status_code=400, detail="Некорректный статус оплаты")

    pay_required = bool(payload.payment_required)
    if ps in ("paid", "cash"):
        pay_required = False

    room_id = payload.room_id
    if room_id is not None:
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM catalog.rooms WHERE id=%s AND camp_id=%s", (room_id, payload.camp_id))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Некорректный номер (апартамент) для выбранной базы")

    guest_name = (payload.guest_name or "").strip() or None
    guest_phone = (payload.guest_phone or "").strip() or None
    guest_email = (str(payload.guest_email).strip().lower() if payload.guest_email is not None else None) if payload.guest_email is not None else None
    comment = (payload.comment or "").strip() or None

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.bookings (
                user_id, camp_id, room_id,
                check_in, check_out, guests_count,
                status, source, comment,
                payment_status, payment_required,
                guest_name, guest_phone, guest_email
            )
            VALUES (NULL, %s, %s, %s, %s, %s, %s, 'crm', %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                payload.camp_id,
                room_id,
                payload.check_in,
                payload.check_out,
                payload.guests_count,
                st,
                comment,
                ps,
                pay_required,
                guest_name,
                guest_phone,
                guest_email,
            ),
        )
        booking_id = cur.fetchone()["id"]
        conn.commit()

    return {"ok": True, "id": booking_id}


@app.patch("/api/admin/bookings/{booking_id}")
def api_admin_update_booking(
    booking_id: int,
    payload: BookingAdminUpdateRequest,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    allowed_payment = {"unpaid", "paid", "cash"}
    payment_status = payload.payment_status
    if payment_status is not None:
        payment_status = (payment_status or "").strip().lower()
        if payment_status not in allowed_payment:
            raise HTTPException(status_code=400, detail="Некорректный статус оплаты")

    new_status = payload.status.strip() if payload.status is not None else None
    payment_required = payload.payment_required if payload.payment_required is not None else None

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, camp_id, user_id, status, payment_status, payment_required FROM crm.bookings WHERE id=%s",
            (booking_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        booking = dict(row)
        if booking["camp_id"] not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

        updates = []
        params = []
        if new_status is not None and new_status != booking.get("status"):
            updates.append("status=%s")
            params.append(new_status)
        if payment_status is not None and payment_status != booking.get("payment_status"):
            updates.append("payment_status=%s")
            params.append(payment_status)
        if payment_required is not None and payment_required != booking.get("payment_required"):
            updates.append("payment_required=%s")
            params.append(bool(payment_required))

        # If marked paid/cash, payment no longer required
        if payment_status in ("paid", "cash"):
            if booking.get("payment_required"):
                updates.append("payment_required=FALSE")

        if not updates:
            return {"ok": True}

        updates.append("updated_at=NOW()")
        params.append(booking_id)
        cur.execute(
            f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s",
            tuple(params),
        )
        conn.commit()

    if booking.get("user_id"):
        log_user_event(
            int(booking["user_id"]),
            "booking_admin_update",
            {
                "booking_id": booking_id,
                "status": new_status,
                "payment_status": payment_status,
                "payment_required": payment_required,
                "admin_id": admin.get("id"),
            },
        )
    return {"ok": True}


@app.get("/api/admin/calendar")
def api_admin_calendar(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    """Упрощённый календарь бронирований."""
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    conditions = []
    params: list = []
    if camp_id:
        if camp_id not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
        conditions.append("camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("check_in >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("check_out <= %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT camp_id, room_id, check_in, check_out, status
            FROM crm.bookings
            WHERE {where_clause}
            ORDER BY check_in
            """,
            tuple(params),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


@app.get("/api/admin/bookings/calendar")
def api_admin_bookings_calendar(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    """
    Бронирования для отображения в календаре: выбираем все, которые пересекают [date_from, date_to).
    В отличие от /api/admin/bookings, тут используется overlap-логика, чтобы не терять брони,
    которые начались раньше периода или заканчиваются позже.
    """
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []

    conditions = []
    params: list = []
    if camp_id:
        if camp_id not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)

    # overlap conditions (treat check_out as exclusive)
    if date_from:
        conditions.append("b.check_out > %s")
        params.append(date_from)
    if date_to:
        conditions.append("b.check_in < %s")
        params.append(date_to)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in ASC, b.id ASC
            """,
            tuple(params),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _normalize_move(url: str, camp_id: int, room_db_id: Optional[int] = None, camp_name: Optional[str] = None, room_name: Optional[str] = None) -> str:
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


def _room_photos_from_fs(camp_id: int, room_id: int, camp_name: Optional[str] = None) -> list[dict]:
    """
    Best-effort fallback: if DB does not contain room photos, try to read them from filesystem.
    Supports structure produced by _normalize_move():
      static/uploads/{camp_id}_{camp-slug}/{camp_id}-{room_id}_{room-slug}/file.jpg
    """
    try:
        base = Path("static/uploads")
        if not base.exists():
            return []

        camp_slug = _slug_latin(camp_name or f"camp-{camp_id}")

        # Prefer exact folder, fallback to any matching camp_id_*
        camp_dir = base / f"{camp_id}_{camp_slug}"
        if not camp_dir.exists():
            matches = sorted([p for p in base.glob(f"{camp_id}_*") if p.is_dir()])
            camp_dir = matches[0] if matches else camp_dir
        if not camp_dir.exists():
            return []

        room_dirs = sorted([p for p in camp_dir.glob(f"{camp_id}-{room_id}_*") if p.is_dir()])
        if not room_dirs:
            return []

        room_dir = room_dirs[0]
        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif"):
            files.extend(sorted(room_dir.glob(ext)))
        files = [p for p in files if p.is_file()]
        if not files:
            return []

        out = []
        for idx, p in enumerate(files[:5]):
            out.append({"url": "/" + p.as_posix(), "cover": idx == 0, "sort": idx})
        return out
    except Exception:
        return []



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

async def _upsert_camp(camp_id: Optional[int], data: dict):
    conn = _pg_connect("catalog")
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
    housing_type = (data.get("housing_type") or "").strip().lower()
    if housing_type not in ("apartments", "houses", "rooms"):
        housing_type = "apartments"

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
        cur.execute(
            """
            INSERT INTO catalog.camps(
                name, lake_name, address, lat, lng, status,
                emoji, emoji_size, description,
                housing_type,
                owner, manager, admin_phones, site_url,
                min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                pools_private_count, pools_shared_count, beds_count
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                name, lake, addr, lat, lng, status,
                emoji, emoji_size, description,
                housing_type,
                owner, manager, admin_phones, site_url,
                min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                pools_private_count, pools_shared_count, beds_count,
            ),
        )
        camp_id = cur.fetchone()["id"]
    else:
        cur.execute(
            """
            UPDATE catalog.camps SET
                name=%s, lake_name=%s, address=%s, lat=%s, lng=%s, status=%s,
                emoji=%s, emoji_size=%s, description=%s,
                housing_type=%s,
                owner=%s, manager=%s, admin_phones=%s, site_url=%s,
                min_price=%s, bbq_count=%s, bbq_shared_count=%s, bath_count=%s, sauna_count=%s,
                pools_private_count=%s, pools_shared_count=%s, beds_count=%s
            WHERE id=%s
            """,
            (
                name, lake, addr, lat, lng, status,
                emoji, emoji_size, description,
                housing_type,
                owner, manager, admin_phones, site_url,
                min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                pools_private_count, pools_shared_count, beds_count,
                camp_id,
            ),
        )

    # 4) фото базы — сначала чистим, потом вставляем, заодно переносим из temp в конечную папку
    photos = data.get("photos") or []
    cur.execute("DELETE FROM catalog.camp_photos WHERE camp_id=%s", (camp_id,))

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
            "INSERT INTO catalog.camp_photos(camp_id,url,sort,cover) VALUES(%s,%s,%s,%s)",
            (camp_id, url, sort, cover)
        )

    # пишем главную фотку прямо в camps — для карты/балунов
    cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (cover_url or first_url, camp_id))

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
    cur.execute("SELECT id FROM catalog.rooms WHERE camp_id=%s", (camp_id,))
    existing_ids = {row["id"] for row in cur.fetchall()}
    to_delete = [rid for rid in existing_ids if rid not in set(incoming_ids)]
    if to_delete:
        placeholders = ",".join(["%s"] * len(to_delete))
        params = tuple([camp_id, *to_delete])
        cur.execute(
            f"DELETE FROM catalog.rooms WHERE camp_id=%s AND id IN ({placeholders})",
            params,
        )
        cur.execute(
            f"DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id IN ({placeholders})",
            params,
        )

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
                UPDATE catalog.rooms SET
                    camp_id=%s, name=%s, room_type=%s, floors=%s, floor=%s,
                    beds_single=%s, beds_double=%s, bath_type=%s, wc_type=%s,
                    bbq_type=%s, kitchen_type=%s, gazebo_type=%s, terrace_type=%s, pool_type=%s, balcony_type=%s, has_ac=%s,
                    capacity=%s, price_adult=%s, price_child=%s, price=%s, discount_pct=%s, discount_from_nights=%s, description=%s
                WHERE id=%s
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
                (r.get("description") or r.get("desc") or "").strip(),
                int(room_id)
            ))
            if cur.rowcount == 0:
                # строки не было — вставим с фиксированным id
                # строки не было — вставим с фиксированным id
                cur.execute("""
                    INSERT INTO catalog.rooms(
                        id, camp_id, name, room_type, floors, floor,
                        beds_single, beds_double, bath_type, wc_type,
                        bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                        capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                    (r.get("description") or r.get("desc") or "").strip(),
                    None, "[]"
                ))

            room_db_id = int(room_id)
        else:
            # Вставляем новую комнату
            # Вставляем новую комнату
            cur.execute("""
                INSERT INTO catalog.rooms(
                    camp_id, name, room_type, floors, floor,
                    beds_single, beds_double, bath_type, wc_type,
                    bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                    capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
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
                (r.get("description") or r.get("desc") or "").strip(),
                None, "[]"
            ))
            room_db_id = cur.fetchone()["id"]

        # Фото: перенос из temp + обложка + photos_json
        room_photos = (r.get("photos") or [])[:5]
        urls = []
        cover_url = None
        cur.execute(
            "DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id=%s",
            (camp_id, room_db_id),
        )
        for s, ph in enumerate(room_photos):
            if isinstance(ph, dict):
                u = ph.get("url") or ""
                cov = int(bool(ph.get("cover")))
            else:
                u = str(ph); cov = 0

            u = _normalize_move(u, camp_id, room_db_id, camp_name=name, room_name=r.get("name"))
            u = (u or "").strip()
            if not u:
                continue
            urls.append(u)
            if cov and cover_url is None:
                cover_url = u
            cur.execute(
                "INSERT INTO catalog.room_photos(camp_id,room_id,url,cover,sort) VALUES(%s,%s,%s,%s,%s)",
                (camp_id, room_db_id, u, cov, s)
            )

        if not cover_url and urls:
            cover_url = urls[0]

        # обновим главную картинку + JSON для удобной подгрузки
        cur.execute(
            "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s WHERE id=%s",
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
