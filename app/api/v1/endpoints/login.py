import json
from datetime import timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import sentry_sdk
from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api.deps import get_db, get_redis_client
from app.core import onadata, security
from app.core.config import settings
from app.models.server import Server

router = APIRouter()


@router.get("/login/server", status_code=302)
def login_server(
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    *,
    server_id: Optional[int],
    server_url: Optional[str],
    redirect_url: Optional[str],
):
    """
    OAuth2 compatible token login for Server Users, get an access token for future requests
    """
    if server_id:
        server: Server = crud.server.get(db, id=server_id)
    elif server_url:
        server: Server = crud.server.get_using_url(db, url=server_url)
    else:
        raise HTTPException(
            status_code=400, detail="Either server_id or server_url must be provided."
        )

    if not server:
        raise HTTPException(status_code=404, detail="Server not found.")

    auth_state = {"server_id": server.id}
    if redirect_url:
        auth_state["redirect_url"] = redirect_url

    state_key, state = security.create_oauth_state(auth_state)
    redis_client.setex(state_key, timedelta(minutes=5), state)
    url = urljoin(
        str(server.url),
        f"/o/authorize?client_id={server.client_id}&response_type=code&state={state_key}",
    )
    return RedirectResponse(
        url=url,
        status_code=302,
        headers={"Cache-Control": "no-cache, no-store, revalidate"},
    )


@router.get(
    "/login/server-callback",
    responses={
        200: {"model": schemas.Token},
        302: {"headers": {"Cache-Control": "no-cache, no-store, revalidate"}},
    },
)
def login_server_callback(
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    *,
    code: str,
    state: str,
):
    """
    OAuth2 compatible callback for Server Users

    This endpoint creates a user session for the authorized user and authenticates
    the user granting them access to the Hyper File API.

    User sessions last for 2 weeks. After the 2 weeks pass the user needs to re-authorize
    with the application to gain access to the Hyper file API
    """
    auth_state = redis_client.get(state)
    if not auth_state:
        raise HTTPException(status_code=400, detail="Invalid state")

    auth_state = json.loads(auth_state)
    server = crud.server.get(db, id=auth_state["server_id"])
    if not server:
        raise HTTPException(status_code=404, detail="Server not found.")

    redirect_url = auth_state.get("redirect_url")
    try:
        access_token, refresh_token = security.request_onadata_credentials(server, code)
        profile = onadata.retrieve_onadata_profile(access_token, server.url)
    except security.FailedToRequestOnaDataCredentials as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=400, detail=str(e))
    except onadata.FailedExternalRequest as exc:
        sentry_sdk.capture_exception(exc)
        raise HTTPException(
            status_code=400, detail="Failed to retrieve user profile from Server"
        )
    else:
        username = profile["username"]
        user = crud.user.get_by_username(db, username=username)
        if not user:
            user_in = schemas.UserCreate(
                username=username,
                server_id=server.id,
                refresh_token=refresh_token,
                access_token=access_token,
            )
            user = crud.user.create(db, obj_in=user_in)

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            str(user.id), expires_delta=access_token_expires
        )
        if redirect_url:
            return RedirectResponse(
                redirect_url,
                status_code=302,
                headers={"Cache-Control": "no-cache, no-store, revalidate"},
            )

        return {"access_token": access_token, "token_type": "bearer"}
