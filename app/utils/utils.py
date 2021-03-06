# Common/General Utilities
import redis

from app.database import SessionLocal
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
