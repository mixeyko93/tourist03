import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from tourist03.bootstrap import bootstrap_database
from tourist03.config import SESSION_SECRET_KEY, STATIC_DIR, logger
from tourist03.routers import admin, auth, bookings, catalog, pages, superadmin


bootstrap_database()

app = FastAPI(title="Tourist_03 Admin")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled application error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY or secrets.token_hex(32),
    session_cookie="t03_admin_session",
    max_age=60 * 60 * 24 * 7,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(bookings.router)
app.include_router(superadmin.router)
app.include_router(catalog.router)
app.include_router(admin.router)
