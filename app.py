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
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("tourist03.superadmin")

from fastapi import FastAPI, Request, HTTPException, Depends, status
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


def _conn_camps():
    # данные по базам отдыха → схема catalog
    return _pg_connect('catalog')


def _conn_users():
    return _pg_connect("auth")


def _conn_crm():
    return _pg_connect("crm")

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
        import logging
        logging.exception('Error hashing password')
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


def get_current_admin(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    conn = _conn_crm()
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
    conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def _get_admin_camp_ids(admin_id: int) -> list[int]:
    conn = _conn_crm()
    cur = conn.cursor()
    cur.execute(
        "SELECT camp_id FROM crm.camp_admin_links WHERE admin_id = %s",
        (admin_id,),
    )
    camp_ids = [row["camp_id"] for row in cur.fetchall()]
    conn.close()
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
       description
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
    conn = _conn_camps()
    cur = conn.cursor()
    try:
        cur.execute('CREATE SCHEMA IF NOT EXISTS catalog;')
        cur.execute('SET search_path TO catalog;')
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
                description TEXT
            )
            """
        )
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
    finally:
        conn.close()



def init_users_db():
    conn = _conn_users()
    cur = conn.cursor()
    try:
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
        conn.commit()
    finally:
        conn.close()



def init_crm_db():
    conn = _conn_crm()
    cur = conn.cursor()
    try:
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
    finally:
        conn.close()





def create_test_admin(email: str, password: str, display_name: str = "Тестовый админ"):
    """Создание тестового управляющего (используется для отладки)."""
    if not email or not password:
        return
    conn = _conn_crm()
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
    conn.close()

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
    conn = _conn_users()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, role FROM auth.users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/superadmin/camps", dependencies=[Depends(get_superadmin)])
def superadmin_list_camps():
    """
    Упрощенный список баз отдыха для суперадминки.
    """
    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, address, lake_name, status
        FROM catalog.camps
        ORDER BY id
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _create_camp_admin_account(payload: SuperAdminCreateAccountRequest):
    email = payload.email.lower().strip()
    display_name = (payload.display_name or "").strip() or email
    password_raw = (payload.password or "").strip()
    if not password_raw:
        raise HTTPException(status_code=400, detail="Пароль не может быть пустым")

    logger.info("Запрос на создание учётки управляющего: email=%s, camps=%s", email, payload.camp_ids)
    conn = _conn_crm()
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
    finally:
        conn.close()


@app.get("/api/superadmin/accounts", dependencies=[Depends(get_superadmin)])
def superadmin_list_accounts():
    """
    Список всех управляющих и привязанных к ним баз.
    """
    conn = _conn_crm()
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
    conn.close()
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


# === API: Базы отдыха ===
@app.get("/api/camps")
def api_camps_list():
    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(CAMP_SELECT_ALL + " ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/camps/{camp_id}")
def api_camp_one(camp_id: int):
    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(CAMP_SELECT_ALL + " WHERE id=%s", (camp_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)


@app.get("/api/camps/{camp_id}/photos")
def api_camp_photos(camp_id: int):
    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, url, sort, cover FROM catalog.camp_photos WHERE camp_id=%s ORDER BY sort, id",
        (camp_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/rooms")
def api_rooms_list(camp_id: int):
    conn = _conn_camps()
    cur = conn.cursor()
    cur.execute(ROOM_SELECT + " WHERE camp_id=%s ORDER BY id", (camp_id,))
    rows = cur.fetchall()
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


@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    """Авторизация управляющего."""
    conn = _conn_crm()
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
    conn.close()
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
    conn = _conn_camps()
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
    conn.close()
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
    conn = _conn_crm()
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
            b.source
        FROM crm.bookings b
        LEFT JOIN catalog.camps c ON c.id = b.camp_id
        LEFT JOIN catalog.rooms r ON r.id = b.room_id
        WHERE {where_clause}
        ORDER BY b.check_in DESC, b.id DESC
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
    conn = _conn_crm()
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
    conn.close()
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
            INSERT INTO catalog.camps(
                name, lake_name, address, lat, lng, status,
                emoji, emoji_size, description,
                owner, manager, admin_phones, site_url,
                min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                pools_private_count, pools_shared_count, beds_count
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            name, lake, addr, lat, lng, status,
            emoji, emoji_size, description,
            owner, manager, admin_phones, site_url,
            min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
            pools_private_count, pools_shared_count, beds_count
        ))
        camp_id = cur.fetchone()["id"]
    else:
        cur.execute("""
            UPDATE catalog.camps SET
                name=%s, lake_name=%s, address=%s, lat=%s, lng=%s, status=%s,
                emoji=%s, emoji_size=%s, description=%s,
                owner=%s, manager=%s, admin_phones=%s, site_url=%s,
                min_price=%s, bbq_count=%s, bbq_shared_count=%s, bath_count=%s, sauna_count=%s,
                pools_private_count=%s, pools_shared_count=%s, beds_count=%s
            WHERE id=%s
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
