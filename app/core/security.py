import json
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple, Union
from uuid import uuid4
from fastapi import Depends

import httpx
import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from requests.sessions import Request
from app.api.deps import get_redis_client

from app.common_tags import ONADATA_TOKEN_ENDPOINT
from app.core.config import settings
from app.models.server import Server
from app.schemas.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class FailedToRequestOnaDataCredentials(Exception):
    pass


def fernet_encrypt(value: str) -> str:
    """Encrypts a string using Fernet encryption."""
    return Fernet(settings.SECRET_KEY).encrypt(value.encode("utf-8")).decode("utf-8")


def fernet_decrypt(value: str) -> str:
    """Decrypts a string using Fernet key."""
    return Fernet(settings.SECRET_KEY).decrypt(value.encode("utf-8")).decode("utf-8")


def create_oauth_state(state: dict) -> Tuple[str, str]:
    """Creates a state token for OAuth2."""
    state_key = str(uuid4())
    return state_key, json.dumps(state)


def request_onadata_credentials(server: Server, code: str) -> Tuple[str, str]:
    """
    Requests OnaData credentials using the provided code.
    """
    resp = httpx.post(
        url=f"{server.url}{ONADATA_TOKEN_ENDPOINT}",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": server.client_id,
        },
        auth=(server.client_id, fernet_decrypt(server.client_secret)),
    )

    if resp.status_code != 200:
        raise FailedToRequestOnaDataCredentials(resp.text)
    else:
        resp_json = resp.json()
        return resp_json["access_token"], resp_json["refresh_token"]


def create_session(request: Request, user: User, expires_timedelta: timedelta, redis_client = Depends(get_redis_client)) -> Tuple[str, str]:
    session_key = f"{user.id}-sessions"
    session_id = str(uuid4())
    expires = datetime.utcnow() + expires_timedelta

    session_data = {"sub": str(user.id), "id": session_id, "exp": expires}
    request.session["session"] = json.dumps(session_data)
    redis_client.hset(session_key, session_id, json.dumps(session_data))
    return session_id, jwt.encode(session_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    expire = None
    if expires_delta:
        expire = datetime.utcnow() + expires_delta

    data = {"sub": str(subject), "exp": expire}
    encoded_jwt = jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
