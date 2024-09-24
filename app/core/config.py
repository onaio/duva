import os

from typing import Any, List, Optional, Union
from urllib.parse import quote_plus

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Duva"
    APP_DESCRIPTION: str = (
        "Duva is an application that converts CSV to Tableau Hyper Databases"
    )
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    MEDIA_ROOT: str = os.getenv("MEDIA_ROOT", "/app/media")
    DEBUG: bool = False
    SECRET_KEY: str = Fernet.generate_key().decode()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = (
        60 * 24 * 7
    )  # 60 minutes * 24 hours * 7 days = 7 days
    SESSION_EXPIRE_MINUTES: int = 60 * 24 * 14
    DOWNLOAD_EXPIRE_SECONDS: int = 3600

    POSTGRES_SERVER: str = "postgres"
    POSTGRES_USER: str = "duva"
    POSTGRES_PASSWORD: str = "duva"
    POSTGRES_DB: str = "duva"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    DEBUG: bool = False

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], values: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v

        values = values.data
        return (
            f"postgresql://{quote_plus(values.get('POSTGRES_USER'))}:"
            f"{quote_plus(values.get('POSTGRES_PASSWORD'))}@"
            f"{values.get('POSTGRES_SERVER')}/"
            f"{values.get('POSTGRES_DB')}"
        )

    SENTRY_DSN: Optional[str] = ""

    @field_validator("SENTRY_DSN", mode="before")
    def sentry_dsn_can_be_blank(cls, v: str = "") -> Optional[str]:
        if len(v) == 0:
            return None
        return v

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_USERNAME: Optional[str] = None
    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode="before")
    def assemble_redis_connection(cls, v: Optional[str], values: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v

        values = values.data
        user_info = (
            f"{quote_plus(values.get('REDIS_USERNAME'))}:{quote_plus(values.get('REDIS_PASSWORD'))}@"
            if values.get("REDIS_USERNAME") and values.get("REDIS_PASSWORD")
            else ""
        )
        if not user_info:
            return f"redis://{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/{values.get('REDIS_DB')}"

    SECURE_SESSIONS: bool = True
    SESSION_SAME_SITE: str = "lax"

    # CORS_ALLOWED_ORIGINS is a JSON-formatted list of origins
    # e.g: '["http://localhost", "http://localhost:4200", "http://localhost:3000", \
    # "http://localhost:8080", "http://local.dockertoolbox.tiangolo.com"]'
    CORS_ALLOWED_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    CORS_MAX_AGE: int = 3600

    # S3 Configurations
    S3_REGION: str = "eu-west-1"
    S3_BUCKET: str = "duva"

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        case_sensitive = True


settings = Settings()
