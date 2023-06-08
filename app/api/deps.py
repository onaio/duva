from typing import Generator
from fastapi.security import OAuth2PasswordBearer

import redis

from app.core.config import settings
from app.database.session import SessionLocal


reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"/api/v1/login/access-token")


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_redis_client() -> Generator:
    try:
        client = redis.from_url(str(settings.REDIS_URL))
        yield client
    finally:
        client.close()
