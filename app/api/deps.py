from typing import Generator

import redis

from app.core.config import settings
from app.database.session import SessionLocal


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
