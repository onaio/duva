# Routes for the OAuth (/oauth) endpoint
import json
import uuid
from typing import Optional

import httpx
import redis
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRouter

from app import schemas
from app.api.deps import get_db, get_redis_client
from app.common_tags import ONADATA_TOKEN_ENDPOINT, ONADATA_USER_ENDPOINT
from app.models import Server, User
from app.utils.auth_utils import IsAuthenticatedUser, create_session

router = APIRouter()


@router.get("/login", status_code=302)
def start_login_flow(
    server_url: str,
    redirect_url: Optional[str] = None,
    user=Depends(IsAuthenticatedUser(raise_errors=False)),
    db=Depends(get_db),
    redis: redis.Redis = Depends(get_redis_client),
):
    """
    Starts OAuth2 Code Flow; The flow authenticates a user against one of the configured
    servers. _For more info on server configurations check the `/api/v1/server` docs_

    This endpoint redirects the client to the `server_url` for authentication if the server
    has a server configuration in the system. Once the user is authorized on the server
    the user should be redirected back to `/callback` which will handle
    creation of a user session that will allow the user to access the applications Hyper File
    resources.
    """
    if not user:
        server: Optional[schemas.Server] = Server.get_using_url(db, server_url)
        if not server:
            raise HTTPException(status_code=400, detail="Server not configured")
        auth_state = {"server_id": server.id}
        if redirect_url:
            auth_state["redirect_url"] = redirect_url

        state_key = str(uuid.uuid4())
        redis.setex(state_key, 600, json.dumps(auth_state))
        url = f"{server.url}/o/authorize?client_id={server.client_id}&response_type=code&state={state_key}"
        return RedirectResponse(
            url=url,
            status_code=302,
            headers={
                "Cache-Control": "no-cache, no-store, revalidate",
            },
        )
    else:
        return RedirectResponse(url=redirect_url or "/", status_code=302)


@router.get(
    "/callback",
    status_code=302,
    responses={200: {"model": schemas.UserBearerTokenResponse}},
)
def handle_oauth_callback(
    code: str,
    state: str,
    request: Request,
    db=Depends(get_db),
    user=Depends(IsAuthenticatedUser(raise_errors=False)),
    redis: redis.Redis = Depends(get_redis_client),
):
    """
    Handles OAuth2 Code flow callback. This url should be registered
    as the "redirect_uri" for your Server OAuth Application(Onadata).

    This endpoint creates a user session for the authorized user and authenticates
    the user granting them access to the Hyper File API.

    User sessions last for 2 weeks. After the 2 weeks pass the user needs to re-authorize
    with the application to gain access to the Hyper file API
    """
    if user:
        return RedirectResponse(url="/", status_code=302)

    auth_state = redis.get(state)
    if not auth_state:
        raise HTTPException(
            status_code=401, detail="Authorization state can not be confirmed."
        )

    auth_state = json.loads(auth_state)
    redis.delete(state)
    server: Optional[schemas.Server] = Server.get(
        db, object_id=auth_state.get("server_id")
    )
    redirect_url = auth_state.get("redirect_url")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": server.client_id,
    }
    url = f"{server.url}{ONADATA_TOKEN_ENDPOINT}"
    resp = httpx.post(
        url,
        data=data,
        auth=(
            server.client_id,
            Server.decrypt_value(server.client_secret),
        ),
    )

    if resp.status_code == 200:
        resp = resp.json()
        access_token = resp.get("access_token")
        refresh_token = resp.get("refresh_token")

        user_url = f"{server.url}{ONADATA_USER_ENDPOINT}.json"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = httpx.get(user_url, headers=headers)
        if resp.status_code == 200:
            resp = resp.json()
            username = resp.get("username")
            user = User.get_using_server_and_username(db, username, server.id)
            if not user:
                user_data = schemas.User(
                    username=username, refresh_token=refresh_token, server_id=server.id
                )
                user = User.create(db, user_data)
            else:
                user.refresh_token = User.encrypt_value(refresh_token)
                db.commit()

            request, session_data = create_session(user, redis, request)
            if redirect_url:
                return RedirectResponse(
                    redirect_url,
                    status_code=302,
                    headers={
                        "Cache-Control": "no-cache, no-store, revalidate",
                    },
                )
            return JSONResponse(
                schemas.UserBearerTokenResponse(bearer_token=session_data).dict()
            )
    raise HTTPException(status_code=401, detail="Authentication failed.")
