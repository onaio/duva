# Common/General Utilities
import json
import redis

from app import schemas
from app.database import SessionLocal
from app.settings import settings


def create_event(redis_client: redis.Redis = None, **event_data) -> bool:
    if not redis_client:
        redis_client = redis.Redis(
            host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
        )
    destroy_after = event_data.get("destroy_after")
    event_id = event_data.get("event_id")

    if event_id:
        event = redis_client.get(event_id)
        if event:
            event = json.loads(event)
            for k, v in event_data.items():
                if k in ["name", "status", "object_url"]:
                    if v:
                        event[k] = v
        else:
            event = schemas.EventResponse(
                status=event_data.get("status") or "Queued",
                name=event_data.get("name"),
                object_url=event_data.get("object_url"),
            ).dict()

        if destroy_after:
            redis_client.setex(event_id, destroy_after, json.dumps(event))
        else:
            redis_client.set(event_id, json.dumps(event))

        return True
    return False


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
