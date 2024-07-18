"""
DEPRECATED: This file is no longer used. It is kept for reference purposes only.
Please utilize api/deps.py instead.
"""

import redis

from app.database.session import SessionLocal
from app.core.config import settings


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis_client():
    redis_client = redis.Redis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB
    )
    try:
        yield redis_client
    finally:
        pass
