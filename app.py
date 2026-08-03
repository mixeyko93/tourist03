from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from tourist03.config import STATIC_DIR, logger
from tourist03.http_middleware import (
    CsrfMiddleware,
    FeatureGateMiddleware,
    OwnerNoStoreMiddleware,
    RateLimitMiddleware,
    StaticAssetCompressionMiddleware,
)
from tourist03.routers import (
    admin,
    auth,
    bookings,
    bot_webhook,
    catalog,
    discovery,
    owners,
    pages,
    submissions,
    superadmin,
    telegram_support,
)
from tourist03.settings import Settings, configure_settings, get_settings
from tourist03.static_files import ProtectedStaticFiles


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Build the HTTP app without touching the database or applying migrations."""
    resolved_settings = settings or get_settings()
    if settings is not None:
        configure_settings(settings)

    application = FastAPI(
        title="Turistika API",
        description="API сервиса «Туристика»: каталог баз отдыха, бронирования, CRM и администрирование.",
        debug=resolved_settings.debug,
    )
    application.state.settings = resolved_settings

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):
        logger.exception("Unhandled application error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    # Middleware executes in reverse registration order. Session must therefore
    # be registered last so CSRF can safely access ``request.session``.
    application.add_middleware(FeatureGateMiddleware)
    application.add_middleware(StaticAssetCompressionMiddleware)
    application.add_middleware(OwnerNoStoreMiddleware)
    application.add_middleware(
        RateLimitMiddleware,
        memory_max_keys=resolved_settings.rate_limit_memory_max_keys,
    )
    application.add_middleware(CsrfMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=resolved_settings.cors_header_list,
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key=resolved_settings.session_secret_key,
        session_cookie=resolved_settings.session_cookie_name,
        max_age=resolved_settings.session_cookie_max_age,
        same_site=resolved_settings.session_cookie_samesite,
        https_only=resolved_settings.session_cookie_secure,
        domain=resolved_settings.session_cookie_domain,
    )

    application.mount(
        "/static",
        ProtectedStaticFiles(directory=STATIC_DIR),
        name="static",
    )

    application.include_router(pages.router)
    application.include_router(auth.router)
    application.include_router(bot_webhook.router)
    application.include_router(telegram_support.router)
    application.include_router(bookings.router)
    application.include_router(superadmin.router)
    application.include_router(catalog.router)
    application.include_router(discovery.router)
    application.include_router(submissions.router)
    application.include_router(owners.router)
    application.include_router(admin.router)
    return application


# Compatibility entrypoint for uvicorn and the existing deployment unit.
app = create_app()
