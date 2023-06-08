from logging.config import dictConfig
import os

import sentry_sdk
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette_exporter import PrometheusMiddleware, handle_metrics

from app.api.deps import get_db, get_redis_client
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logger import LogConfig

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
)

dictConfig(LogConfig().dict())


# Include middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    https_only=settings.SECURE_SESSIONS,
    same_site=settings.SESSION_SAME_SITE,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
    max_age=settings.CORS_MAX_AGE,
)
app.add_middleware(
    PrometheusMiddleware, app_name="duva", prefix="duva", filter_unhandled_paths=True
)
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, release=settings.APP_VERSION)
    app.add_middleware(SentryAsgiMiddleware)

# Include routes
app.add_route("/metrics", handle_metrics)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def home(request: Request):
    return {
        "app_name": app.title,
        "app_description": app.description,
        "app_version": app.version,
        "docs_url": str(request.base_url.replace(path=app.docs_url)),
        "openapi_url": str(request.base_url.replace(path=app.openapi_url)),
    }


@app.get("/health", include_in_schema=False)
def service_health(
    _: Request, db: Session = Depends(get_db), redis_client=Depends(get_redis_client)
):
    database_reachable = True
    cache_reachable = True

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
    if not os.path.isdir(settings.MEDIA_ROOT):
        os.mkdir(settings.MEDIA_ROOT)
