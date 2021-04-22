# Authentication/Authorization Utilities
import uuid
from datetime import datetime, timedelta
from typing import Tuple

import redis
import jwt
from fastapi import Request, Depends
from fastapi.exceptions import HTTPException

from app import schemas
from app.settings import settings
from app.models import User
from app.utils.utils import get_db, get_redis_client


def create_session(
    user: schemas.User, redis_client: redis.Redis, request: Request = None
) -> Tuple[Request, str]:
    session_key = f"{user.username}-sessions"
    session_id = str(uuid.uuid4())
    expiry_time = datetime.now() + timedelta(days=14)
    expiry_timestamp = datetime.timestamp(expiry_time)
    stored_session = session_id + f":{expiry_timestamp}"
    redis_client.sadd(session_key, stored_session)
    jwt_data = {
        "username": user.username,
        "session-id": session_id,
        "server_id": user.server,
    }
    encoded_jwt = jwt.encode(jwt_data, settings.secret_key, algorithm="HS256")

    if request:
        request.session["session-data"] = jwt_data
    return request, encoded_jwt


class IsAuthenticatedUser:
    def __init__(self, raise_errors: bool = True) -> None:
        self.raise_errors = raise_errors

    def __call__(
        self, request: Request, db=Depends(get_db), redis=Depends(get_redis_client)
    ):
        def _raise_error(exception: Exception):
            if self.raise_errors:
                if request.session:
                    request.session.clear()
                raise exception
            return None

        self.db = db
        self.redis_client = redis

        session_data = request.session.get("session-data")
        invalid_credentials_error = HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )
        if not session_data:
            auth = request.headers.get("authorization")
            if auth:
                auth_type, value = auth.split(" ")

                if auth_type != "Bearer":
                    return _raise_error(invalid_credentials_error)

                try:
                    session_data = jwt.decode(
                        value, settings.secret_key, algorithms=["HS256"]
                    )
                except jwt.DecodeError:
                    return _raise_error(invalid_credentials_error)

        if session_data:
            session_id = session_data.get("session-id")
            username = session_data.get("username")
            server_id = session_data.get("server_id")
            session_key = f"{username}-sessions"

            if self.is_valid_session(session_id=session_id, session_key=session_key):
                user = User.get_using_server_and_username(self.db, username, server_id)
                if not user:
                    return _raise_error(invalid_credentials_error)
                return user

        return _raise_error(
            HTTPException(status_code=401, detail="Authentication required")
        )

    def is_valid_session(self, session_key: str, session_id: str) -> bool:
        sessions = self.redis_client.smembers(session_key)
        for session in sessions:
            sess_id, expiry = session.decode("utf-8").split(":")

            try:
                expiry = int(expiry)
            except ValueError:
                expiry = float(expiry)

            if expiry and datetime.fromtimestamp(expiry) > datetime.now():
                if sess_id == session_id:
                    return True
            else:
                self.redis_client.srem(session_key, session)

        return False
