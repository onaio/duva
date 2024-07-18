"""
DEPRECATED: This file is no longer used. It is kept for reference purposes only.
Please utilize api/deps.py instead.
"""

import redis

from app.database.session import SessionLocal
from app.settings import settings


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis_client():
    redis_client = redis.Redis(
        host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
    )
    try:
        yield redis_client
    finally:
        pass
