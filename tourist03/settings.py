"""Typed runtime configuration for the application and operational commands."""

from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DEVELOPMENT_SESSION_SECRET = "development-only-session-secret-change-before-production"
INSECURE_SECRET_VALUES = {
    "",
    "change-me",
    "changeme",
    "secret",
    "development-only-session-secret-change-before-production",
}


def _is_placeholder_secret(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return (
        normalized in INSECURE_SECRET_VALUES
        or normalized.startswith(("replace-", "your-", "example-"))
        or "placeholder" in normalized
    )


class Settings(BaseSettings):
    """All environment-controlled application settings.

    ``environment=production`` intentionally validates more strictly. This keeps
    development and isolated tests easy to run while refusing unsafe deployment
    configuration before the HTTP application starts.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    app_version: str = ""
    public_base_url: str = "http://localhost:8000"

    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_db: str = "tourist03"
    pg_user: str = "postgres"
    pg_password: str = "postgres"

    session_secret_key: str = DEFAULT_DEVELOPMENT_SESSION_SECRET
    session_cookie_name: str = "t03_admin_session"
    session_cookie_max_age: int = 60 * 60 * 24 * 7
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: Optional[str] = None

    cors_origins: str = "http://localhost:8000,http://localhost:5173"
    cors_allow_headers: str = "Content-Type,Authorization,X-CSRF-Token,X-Superadmin-Key"

    superadmin_api_key: Optional[str] = None
    superadmin_login: Optional[str] = None
    superadmin_password: Optional[str] = None
    superadmin_local_bypass: bool = False
    sim_verify_code: Optional[str] = "0000"
    allow_simulated_auth: bool = True
    terms_version: str = "2026-01-04"

    crm_base_url: str = "https://crm.turist03.ru"
    superadmin_base_url: str = "https://superadmin.turist03.ru"
    telegram_bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    telegram_webapp_url: str = Field(default="", validation_alias="WEBAPP_URL")
    staff_bot_token: str = ""
    staff_bot_username: str = ""
    staff_bot_poll_interval: int = 60
    vk_token: str = ""
    vk_group_id: str = ""
    tourist_webapp_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    upload_dir: str = str(PROJECT_DIR / "static" / "uploads")
    upload_image_max_bytes: int = 10 * 1024 * 1024
    upload_video_max_bytes: int = 100 * 1024 * 1024
    allow_server_video_upload: bool = False

    rate_limit_storage: Literal["memory", "redis"] = "memory"
    redis_url: str = ""
    rate_limit_memory_max_keys: int = Field(default=10_000, ge=1)
    rate_limit_auth_per_minute: int = 10
    rate_limit_login_per_minute: int = 10
    rate_limit_upload_per_minute: int = 20
    rate_limit_public_post_per_minute: int = 20
    csrf_legacy_compatibility: bool = False

    feature_public_booking: bool = False
    feature_public_user_auth: bool = False
    feature_owner_portal: bool = False
    feature_services: bool = False
    feature_telegram_webapp: bool = False
    feature_paid_placement: bool = False
    feature_legacy_tourist_app: bool = False

    test_admin_email: Optional[str] = None
    test_admin_password: Optional[str] = None
    test_admin_display_name: str = "Тестовый админ"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_legacy_debug_value(cls, value):
        """Accept the project's former DEBUG=release convention."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "off", "no"}:
                return False
            if normalized in {"debug", "development", "on", "yes"}:
                return True
        return value

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        normalized = (value or "").strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PUBLIC_BASE_URL must be an absolute http(s) URL")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cors_header_list(self) -> List[str]:
        return [header.strip() for header in self.cors_allow_headers.split(",") if header.strip()]

    @property
    def public_features(self) -> dict:
        return {
            "public_booking": self.feature_public_booking,
            "public_user_auth": self.feature_public_user_auth,
            "owner_portal": self.feature_owner_portal,
            "services": self.feature_services,
            "telegram_webapp": self.feature_telegram_webapp,
            "paid_placement": self.feature_paid_placement,
            "legacy_tourist_app": self.feature_legacy_tourist_app,
        }

    @model_validator(mode="after")
    def validate_production_settings(self):
        if not self.is_production:
            return self

        if len(self.session_secret_key) < 32 or _is_placeholder_secret(self.session_secret_key):
            raise ValueError("SESSION_SECRET_KEY must be a stable secret of at least 32 characters in production")
        if _is_placeholder_secret(self.pg_password) or self.pg_password.lower() in {"postgres", "password"}:
            raise ValueError("PG_PASSWORD must be explicitly configured in production")
        if self.pg_host.lower() in {"", "localhost"}:
            raise ValueError("PG_HOST must be explicitly configured in production")
        if not self.cors_origin_list or "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must be an explicit non-wildcard list in production")
        if not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE=true is required in production")
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires secure cookies")
        if self.superadmin_local_bypass:
            raise ValueError("SUPERADMIN_LOCAL_BYPASS cannot be enabled in production")
        if self.allow_simulated_auth or self.sim_verify_code:
            raise ValueError("simulated user authentication must be disabled in production")
        if self.csrf_legacy_compatibility:
            raise ValueError("CSRF_LEGACY_COMPATIBILITY cannot be enabled in production")
        if self.rate_limit_storage == "redis" and not self.redis_url:
            raise ValueError("REDIS_URL is required when RATE_LIMIT_STORAGE=redis")
        return self


_settings_override: Optional[Settings] = None


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    return _settings_override or _load_settings()


def configure_settings(settings: Settings) -> None:
    """Install a process-local settings override, used by ``create_app`` tests."""
    global _settings_override
    _settings_override = settings


def clear_settings_override() -> None:
    global _settings_override
    _settings_override = None
    _load_settings.cache_clear()
