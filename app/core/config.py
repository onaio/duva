from typing import Any, Dict, List, Optional, Union
from cryptography.fernet import Fernet

from pydantic import AnyHttpUrl, BaseSettings, HttpUrl, PostgresDsn, RedisDsn, validator


class Settings(BaseSettings):
    APP_NAME: str = "Duva"
    APP_DESCRIPTION: str = (
        "Duva is an application that converts CSV to Tableau Hyper Databases"
    )
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    MEDIA_ROOT: str = "/app/media"
    DEBUG: bool = False
    SECRET_KEY: str  # Fernet.generate_key().decode()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = (
        60 * 24 * 7
    )  # 60 minutes * 24 hours * 7 days = 7 days
    SESSION_EXPIRE_MINUTES: int = 60 * 24 * 14
    DOWNLOAD_EXPIRE_SECONDS: int = 3600

    FIRST_SUPERUSER: str = "admin@duva.ona.io"
    FIRST_SUPERUSER_PASSWORD: str = "admin"

    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_USER: str = "duva"
    POSTGRES_PASSWORD: str = "duva"
    POSTGRES_DB: str = "duva"
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    SENTRY_DSN: Optional[HttpUrl] = ""

    @validator("SENTRY_DSN", pre=True)
    def sentry_dsn_can_be_blank(cls, v: str) -> Optional[str]:
        if len(v) == 0:
            return None
        return v

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: Optional[str] = None
    REDIS_USERNAME: Optional[str] = None
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            user=values.get("REDIS_USERNAME"),
            password=values.get("REDIS_PASSWORD"),
            host=values.get("REDIS_HOST"),
            port=str(values.get("REDIS_PORT")),
            path=f"/{values.get('REDIS_DB') or ''}",
        )

    SECURE_SESSIONS: bool = True
    SESSION_SAME_SITE: str = "lax"

    # CORS_ALLOWED_ORIGINS is a JSON-formatted list of origins
    # e.g: '["http://localhost", "http://localhost:4200", "http://localhost:3000", \
    # "http://localhost:8080", "http://local.dockertoolbox.tiangolo.com"]'
    CORS_ALLOWED_ORIGINS: List[AnyHttpUrl] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    CORS_MAX_AGE: int = 3600

    @validator("CORS_ALLOWED_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        case_sensitive = True


settings = Settings()
