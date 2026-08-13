"""Typed runtime configuration for the application and operational commands."""

from functools import lru_cache
from pathlib import Path
import re
from typing import List, Literal, Optional
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    owner_base_url: str = "http://localhost:8000"

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
    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"),
    )
    telegram_bot_username: str = ""
    telegram_webhook_secret: str = ""
    telegram_deep_link_secret: str = ""
    telegram_support_chat_id: int = 0
    telegram_support_topic_general: int = 0
    telegram_support_topic_placement: int = 0
    telegram_support_topic_premium: int = 0
    telegram_support_topic_bug: int = 0
    telegram_support_topic_suggestion: int = 0
    telegram_support_operator_ids: str = ""
    telegram_support_worker_interval: int = Field(default=2, ge=1, le=60)
    telegram_support_worker_batch_size: int = Field(default=50, ge=1, le=200)
    telegram_support_lease_seconds: int = Field(default=60, ge=10, le=600)
    telegram_support_max_attempts: int = Field(default=10, ge=1, le=100)
    telegram_support_rate_per_minute: int = Field(default=12, ge=1, le=120)
    telegram_support_max_document_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
    )
    telegram_webapp_url: str = Field(default="", validation_alias="WEBAPP_URL")
    staff_bot_token: str = ""
    staff_bot_username: str = ""
    staff_bot_poll_interval: int = 60
    vk_token: str = ""
    vk_group_id: str = ""
    tourist_webapp_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_USER", "SMTP_USERNAME"),
    )
    smtp_password: str = ""
    smtp_from: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_FROM", "SMTP_FROM_EMAIL"),
    )
    smtp_from_name: str = "Туристика"
    smtp_reply_to: str = ""
    smtp_test_email: str = ""
    support_notification_email: str = ""
    smtp_security: Literal["ssl", "starttls", "plain"] = "starttls"
    smtp_use_ssl: Optional[bool] = None
    smtp_use_starttls: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USE_STARTTLS", "SMTP_USE_TLS"),
    )
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=120)
    notification_worker_poll_interval_seconds: int = Field(default=30, ge=5, le=3600)
    notification_delivery_lease_seconds: int = Field(default=120, ge=30, le=900)

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
    rate_limit_public_search_per_minute: int = 240
    csrf_legacy_compatibility: bool = False

    feature_public_booking: bool = False
    feature_public_user_auth: bool = False
    feature_owner_portal: bool = False
    feature_owner_change_requests: bool = False
    feature_owner_password_reset: bool = False
    feature_email_delivery: bool = False
    feature_services: bool = False
    feature_telegram_webapp: bool = False
    feature_telegram_contact: bool = False
    feature_paid_placement: bool = False
    feature_legacy_tourist_app: bool = False
    feature_placement_submissions: bool = False
    feature_discovery_search: bool = False
    feature_editorial_collections: bool = False
    feature_tourism_routes: bool = False
    feature_nearby_discovery: bool = False
    feature_related_entities: bool = False
    feature_local_recent_history: bool = False

    discovery_search_synonyms: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "сап": ["sup", "сапборд"],
            "квадроцикл": ["atv", "квадрик"],
            "баня": ["сауна"],
            "гостевой дом": ["гостевой"],
            "экскурсия": ["тур"],
            "санкт-петербург": ["питер", "спб"],
            "нижний новгород": ["нижний"],
            "московская область": ["подмосковье"],
            "глэмпинг": ["glamping"],
            "байкал": ["baikal"],
        }
    )
    discovery_recommendation_weights: dict[str, int] = Field(
        default_factory=lambda: {
            "same_type": 24,
            "same_subtype": 18,
            "shared_tags": 16,
            "shared_amenities": 8,
            "same_region": 10,
            "same_city": 12,
            "nearby_distance": 10,
            "shared_collection": 12,
            "shared_route": 12,
            "editorial_boost": 4,
            "freshness": 4,
        }
    )
    discovery_geojson_max_bytes: int = Field(default=256 * 1024, ge=1024, le=2 * 1024 * 1024)
    discovery_geojson_max_coordinates: int = Field(default=5000, ge=2, le=50_000)

    owner_password_reset_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    owner_change_request_ttl_days: int = Field(default=30, ge=1, le=365)
    owner_change_max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    owner_change_max_image_pixels: int = Field(default=40_000_000, ge=1_000_000, le=100_000_000)
    owner_card_completeness_weights: dict[str, int] = Field(
        default_factory=lambda: {
            "name": 8,
            "short_description": 8,
            "description": 10,
            "photos": 12,
            "cover": 8,
            "contacts": 10,
            "amenities": 8,
            "rooms": 8,
            "room_descriptions": 5,
            "prices": 5,
            "videos": 5,
            "coordinates": 5,
            "working_hours": 4,
            "seasonality": 2,
            "surroundings": 2,
        }
    )

    submission_max_place_photos: int = Field(default=20, ge=1, le=100)
    submission_max_room_photos: int = Field(default=5, ge=1, le=20)
    submission_max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    submission_max_image_pixels: int = Field(default=40_000_000, ge=1_000_000, le=100_000_000)
    submission_max_json_bytes: int = Field(default=1024 * 1024, ge=16 * 1024, le=10 * 1024 * 1024)
    submission_draft_ttl_hours: int = Field(default=24 * 7, ge=1, le=24 * 90)
    submission_upload_ttl_hours: int = Field(default=48, ge=1, le=24 * 30)
    submission_min_fill_seconds: int = Field(default=20, ge=0, le=3600)
    submission_max_links: int = Field(default=12, ge=0, le=100)
    submission_rate_per_hour: int = Field(default=5, ge=1, le=1000)
    submission_captcha_provider: Literal["test", "http"] = "test"
    submission_captcha_verify_url: str = ""
    submission_captcha_secret: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TURNSTILE_SECRET_KEY",
            "SUBMISSION_CAPTCHA_SECRET",
        ),
    )
    submission_captcha_client_script_url: str = ""
    submission_captcha_site_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TURNSTILE_SITE_KEY",
            "SUBMISSION_CAPTCHA_SITE_KEY",
        ),
    )
    submission_captcha_test_token: str = "test-pass"
    submission_captcha_expected_hostname: str = ""
    submission_captcha_expected_action: str = "placement_submission"
    submission_captcha_max_age_seconds: int = Field(default=600, ge=60, le=3600)
    submission_retention_rejected_days: int = Field(default=365, ge=1, le=3650)
    submission_retention_abandoned_days: int = Field(default=30, ge=1, le=365)
    submission_retention_technical_days: int = Field(default=90, ge=1, le=730)
    submission_cleanup_enabled: bool = False

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

    @field_validator("public_base_url", "owner_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = (value or "").strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Base URLs must be absolute http(s) URLs")
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
    def telegram_support_operator_id_list(self) -> list[int]:
        values: set[int] = set()
        for raw in self.telegram_support_operator_ids.split(","):
            try:
                value = int(raw.strip())
            except ValueError:
                continue
            if value > 0:
                values.add(value)
        return sorted(values)

    @property
    def public_features(self) -> dict:
        return {
            "public_booking": self.feature_public_booking,
            "public_user_auth": self.feature_public_user_auth,
            "owner_portal": self.feature_owner_portal,
            "owner_change_requests": self.feature_owner_change_requests,
            "owner_password_reset": self.feature_owner_password_reset,
            "email_delivery": self.feature_email_delivery,
            "services": self.feature_services,
            "telegram_webapp": self.feature_telegram_webapp,
            "telegram_contact": self.feature_telegram_contact,
            "paid_placement": self.feature_paid_placement,
            "legacy_tourist_app": self.feature_legacy_tourist_app,
            "placement_submissions": self.feature_placement_submissions,
            "discovery_search": self.feature_discovery_search,
            "editorial_collections": self.feature_editorial_collections,
            "tourism_routes": self.feature_tourism_routes,
            "nearby_discovery": self.feature_nearby_discovery,
            "related_entities": self.feature_related_entities,
            "local_recent_history": self.feature_local_recent_history,
        }

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.smtp_use_ssl and self.smtp_use_starttls:
            raise ValueError("SMTP_USE_SSL and SMTP_USE_STARTTLS cannot both be enabled")
        if self.smtp_use_ssl is True:
            self.smtp_security = "ssl"
        elif self.smtp_use_starttls is True:
            self.smtp_security = "starttls"
        elif self.smtp_use_ssl is False and self.smtp_use_starttls is False:
            self.smtp_security = "plain"
        if self.feature_owner_change_requests and not self.feature_owner_portal:
            raise ValueError("FEATURE_OWNER_CHANGE_REQUESTS requires FEATURE_OWNER_PORTAL")
        if self.feature_owner_password_reset and not self.feature_owner_portal:
            raise ValueError("FEATURE_OWNER_PASSWORD_RESET requires FEATURE_OWNER_PORTAL")
        if self.feature_telegram_contact and self.feature_telegram_webapp:
            raise ValueError(
                "FEATURE_TELEGRAM_CONTACT cannot share BOT_TOKEN with legacy Telegram WebApp polling"
            )
        if (
            self.feature_telegram_contact
            and self.telegram_bot_token
            and self.staff_bot_token
            and self.telegram_bot_token == self.staff_bot_token
        ):
            raise ValueError(
                "Telegram contact and staff polling must use different bot tokens"
            )
        if not self.owner_card_completeness_weights or any(
            not isinstance(weight, int) or weight <= 0
            for weight in self.owner_card_completeness_weights.values()
        ):
            raise ValueError("OWNER_CARD_COMPLETENESS_WEIGHTS must contain positive integer weights")
        if not self.discovery_search_synonyms or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(values, list)
            or not all(isinstance(value, str) and value.strip() for value in values)
            for key, values in self.discovery_search_synonyms.items()
        ):
            raise ValueError("DISCOVERY_SEARCH_SYNONYMS must contain non-empty string lists")
        if not self.discovery_recommendation_weights or any(
            not isinstance(weight, int) or weight < 0
            for weight in self.discovery_recommendation_weights.values()
        ):
            raise ValueError("DISCOVERY_RECOMMENDATION_WEIGHTS must contain non-negative integer weights")

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
        if self.superadmin_api_key and (
            len(self.superadmin_api_key) < 32
            or _is_placeholder_secret(self.superadmin_api_key)
        ):
            raise ValueError(
                "SUPERADMIN_API_KEY must be blank or a non-placeholder value "
                "of at least 32 characters in production"
            )
        if self.allow_simulated_auth or self.sim_verify_code:
            raise ValueError("simulated user authentication must be disabled in production")
        if self.csrf_legacy_compatibility:
            raise ValueError("CSRF_LEGACY_COMPATIBILITY cannot be enabled in production")
        if self.rate_limit_storage == "redis" and not self.redis_url:
            raise ValueError("REDIS_URL is required when RATE_LIMIT_STORAGE=redis")
        if self.feature_email_delivery:
            if not self.smtp_host or not self.smtp_from:
                raise ValueError("SMTP_HOST and SMTP_FROM are required when email delivery is enabled")
            if self.smtp_user and not self.smtp_password:
                raise ValueError("SMTP_PASSWORD is required when SMTP_USER is configured")
            if self.smtp_security == "plain":
                raise ValueError("SMTP_SECURITY=plain cannot be used for production email delivery")
        if self.feature_telegram_contact:
            username = self.telegram_bot_username.strip().lstrip("@")
            if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
                raise ValueError("TELEGRAM_BOT_USERNAME is invalid")
            if _is_placeholder_secret(self.telegram_bot_token):
                raise ValueError("TELEGRAM_BOT_TOKEN must be configured")
            if len(self.telegram_webhook_secret) < 32 or _is_placeholder_secret(
                self.telegram_webhook_secret
            ):
                raise ValueError(
                    "TELEGRAM_WEBHOOK_SECRET must be a non-placeholder value of at least 32 characters"
                )
            if len(self.telegram_deep_link_secret) < 32 or _is_placeholder_secret(
                self.telegram_deep_link_secret
            ):
                raise ValueError(
                    "TELEGRAM_DEEP_LINK_SECRET must be a non-placeholder value of at least 32 characters"
                )
            if self.telegram_support_chat_id >= 0:
                raise ValueError("TELEGRAM_SUPPORT_CHAT_ID must be a negative supergroup ID")
            topic_ids = [
                self.telegram_support_topic_general,
                self.telegram_support_topic_placement,
                self.telegram_support_topic_premium,
                self.telegram_support_topic_bug,
                self.telegram_support_topic_suggestion,
            ]
            if any(topic_id <= 0 for topic_id in topic_ids) or len(set(topic_ids)) != len(topic_ids):
                raise ValueError("Telegram support topic ids must be positive and distinct")
            if not self.telegram_support_operator_id_list:
                raise ValueError("TELEGRAM_SUPPORT_OPERATOR_IDS must contain at least one positive ID")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("Telegram contact support requires an HTTPS PUBLIC_BASE_URL")
        if self.feature_owner_portal and not self.owner_base_url.startswith("https://"):
            raise ValueError("Owner Portal requires an HTTPS OWNER_BASE_URL in production")
        if self.feature_placement_submissions:
            if self.submission_captcha_provider == "test":
                raise ValueError("test CAPTCHA provider cannot be used for placement submissions in production")
            if not self.submission_captcha_verify_url.startswith("https://"):
                raise ValueError("SUBMISSION_CAPTCHA_VERIFY_URL must be an absolute HTTPS URL in production")
            if _is_placeholder_secret(self.submission_captcha_secret):
                raise ValueError("SUBMISSION_CAPTCHA_SECRET must be configured in production")
            if not self.submission_captcha_client_script_url.startswith("https://"):
                raise ValueError(
                    "SUBMISSION_CAPTCHA_CLIENT_SCRIPT_URL must be an absolute HTTPS URL in production"
                )
            if _is_placeholder_secret(self.submission_captcha_site_key):
                raise ValueError("SUBMISSION_CAPTCHA_SITE_KEY must be configured in production")
            if not self.submission_captcha_expected_hostname.strip():
                raise ValueError("SUBMISSION_CAPTCHA_EXPECTED_HOSTNAME must be configured in production")
            if not self.submission_captcha_expected_action.strip():
                raise ValueError("SUBMISSION_CAPTCHA_EXPECTED_ACTION must be configured in production")
            if not self.smtp_host or not self.smtp_from:
                raise ValueError("SMTP_HOST and SMTP_FROM are required for placement submissions in production")
            if not self.feature_email_delivery:
                raise ValueError(
                    "FEATURE_PLACEMENT_SUBMISSIONS requires FEATURE_EMAIL_DELIVERY in production"
                )
        if self.feature_owner_password_reset and not self.feature_email_delivery:
            raise ValueError("FEATURE_OWNER_PASSWORD_RESET requires FEATURE_EMAIL_DELIVERY")
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
