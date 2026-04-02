import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates


load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("tourist03.superadmin")

BASE_DIR = str(Path(__file__).resolve().parent.parent)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES = os.path.join(BASE_DIR, "templates")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

templates = Jinja2Templates(directory=TEMPLATES)

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "tourist03")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
SUPERADMIN_API_KEY = os.getenv("SUPERADMIN_API_KEY")
SUPERADMIN_LOGIN = os.getenv("SUPERADMIN_LOGIN")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD")
SUPERADMIN_LOCAL_BYPASS = os.getenv("SUPERADMIN_LOCAL_BYPASS", "").strip().lower() in ("1", "true", "yes", "on")
SIM_VERIFY_CODE = os.getenv("SIM_VERIFY_CODE", "0000")
TERMS_VERSION = os.getenv("TERMS_VERSION", "2026-01-04")
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://crm.turist03.ru")
SUPERADMIN_BASE_URL = os.getenv("SUPERADMIN_BASE_URL", "https://superadmin.turist03.ru")
STAFF_BOT_TOKEN = os.getenv("STAFF_BOT_TOKEN", "").strip()
STAFF_BOT_USERNAME = os.getenv("STAFF_BOT_USERNAME", "").strip()
STAFF_BOT_POLL_INTERVAL = int(os.getenv("STAFF_BOT_POLL_INTERVAL", "60"))

DB_INIT = os.getenv("DB_INIT", "1").strip().lower() not in ("0", "false", "no", "off")
TEST_ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL")
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD")
TEST_ADMIN_DISPLAY_NAME = os.getenv("TEST_ADMIN_DISPLAY_NAME", "Тестовый админ")
