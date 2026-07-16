"""Compatibility exports backed by :mod:`tourist03.settings`.

New code should obtain typed values through ``get_settings()``. The constants
remain during the gradual migration of legacy services and bot scripts.
"""

import logging
import os
from pathlib import Path

from fastapi.templating import Jinja2Templates

from tourist03.settings import get_settings


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("tourist03.superadmin")

BASE_DIR = str(Path(__file__).resolve().parent.parent)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES = os.path.join(BASE_DIR, "templates")
UPLOAD_DIR = settings.upload_dir
templates = Jinja2Templates(directory=TEMPLATES)

PG_HOST = settings.pg_host
PG_PORT = settings.pg_port
PG_DB = settings.pg_db
PG_USER = settings.pg_user
PG_PASSWORD = settings.pg_password

SESSION_SECRET_KEY = settings.session_secret_key
SUPERADMIN_API_KEY = settings.superadmin_api_key
SUPERADMIN_LOGIN = settings.superadmin_login
SUPERADMIN_PASSWORD = settings.superadmin_password
SUPERADMIN_LOCAL_BYPASS = settings.superadmin_local_bypass
SIM_VERIFY_CODE = settings.sim_verify_code
TERMS_VERSION = settings.terms_version
CRM_BASE_URL = settings.crm_base_url
SUPERADMIN_BASE_URL = settings.superadmin_base_url
STAFF_BOT_TOKEN = settings.staff_bot_token.strip()
STAFF_BOT_USERNAME = settings.staff_bot_username.strip().lstrip("@")
STAFF_BOT_POLL_INTERVAL = settings.staff_bot_poll_interval

# Compatibility only. Importing the application no longer applies migrations.
DB_INIT = False
TEST_ADMIN_EMAIL = settings.test_admin_email
TEST_ADMIN_PASSWORD = settings.test_admin_password
TEST_ADMIN_DISPLAY_NAME = settings.test_admin_display_name
