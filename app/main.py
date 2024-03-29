import os

import sentry_sdk
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_cache import caches, close_caches
from fastapi_cache.backends.redis import CACHE_KEY, RedisCacheBackend
from redis import Redis
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_exporter import PrometheusMiddleware, handle_metrics
from tableauhyperapi import HyperProcess, Telemetry

from app.common_tags import HYPER_PROCESS_CACHE_KEY
from app.database import SessionLocal, engine
from app.jobs.scheduler import clear_scheduler_queue
from app.models import Base, HyperFile
from app.routers.configuration import router as configurations_router
from app.routers.file import router as file_router
from app.routers.oauth import router as oauth_router
from app.routers.server import router as server_router
from app.settings import settings
from app.utils.onadata_utils import schedule_all_active_forms

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
)

# Include middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.enable_secure_sessions,
    same_site=settings.session_same_site,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
    max_age=settings.cors_max_age,
)
app.add_middleware(
    PrometheusMiddleware, app_name="duva", prefix="duva", filter_unhandled_paths=True
)
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, release=settings.app_version)
    app.add_middleware(SentryAsgiMiddleware)

# Include routes
app.add_route("/metrics", handle_metrics)
app.include_router(server_router, tags=["Server Configuration"])
app.include_router(oauth_router, tags=["OAuth2"])
app.include_router(file_router, tags=["Hyper File"])
app.include_router(configurations_router, tags=["Tableau Server Configuration"])


@app.get("/", tags=["Application"])
def home(request: Request):
    return {
        "app_name": settings.app_name,
        "app_description": settings.app_description,
        "app_version": settings.app_version,
        "docs_url": str(request.base_url.replace(path=app.docs_url)),
    }


@app.get("/health", tags=["Application"])
def service_health(request: Request):
    db = SessionLocal()
    database_reachable = True
    cache_reachable = True

    try:
        HyperFile.get_active_files(db)
    except Exception:
        database_reachable = False

    db.close()

    redis_client = Redis(
        host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
    )
    try:
        redis_client.ping()
    except Exception:
        cache_reachable = False

    return JSONResponse(
        {
            "Database": "OK" if database_reachable else "FAILING",
            "Cache": "OK" if cache_reachable else "FAILING",
        },
        200 if (database_reachable and cache_reachable) else 500,
    )


@app.on_event("startup")
async def on_startup() -> None:
    # Ensure media file path exists
    if not os.path.isdir(settings.media_path):
        os.mkdir(settings.media_path)

    # Connect to redis cache
    rc = RedisCacheBackend(settings.redis_url)
    caches.set(CACHE_KEY, rc)

    # Check if Hyper Process has started
    # Note: Doing this in order to ensure only one
    # Hyper process is started.
    if not caches.get(HYPER_PROCESS_CACHE_KEY):
        caches.set(
            HYPER_PROCESS_CACHE_KEY,
            HyperProcess(telemetry=Telemetry.SEND_USAGE_DATA_TO_TABLEAU),
        )

    if settings.schedule_all_active:
        clear_scheduler_queue()
        schedule_all_active_forms(close_db=True)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    try:
        await close_caches()
    except TypeError:
        pass

    # Check if hyper process is running and shut it down
    process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)
    if process:
        print("Shutting down hyper process")
        process.close()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
