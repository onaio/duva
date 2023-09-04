from typing import Generator, Any, Callable
from fastapi import APIRouter as FastAPIRouter
from fastapi.types import DecoratedCallable

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


class APIRouter(FastAPIRouter):
    """
    Custom APIRouter that allows for trailing slashes on endpoints.
    """

    def api_route(
        self, path: str, *, include_in_schema: bool = True, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        if path.endswith("/"):
            path = path[:-1]

        add_path = super().api_route(
            path, include_in_schema=include_in_schema, **kwargs
        )

        alternate_path = path + "/"
        add_alternate_path = super().api_route(
            alternate_path, include_in_schema=False, **kwargs
        )

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            add_alternate_path(func)
            return add_path(func)

        return decorator
