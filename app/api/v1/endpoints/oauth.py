# Routes for the OAuth (/oauth) endpoint
import json
from datetime import timedelta
from typing import Optional
from urllib.parse import urljoin

import redis
import sentry_sdk
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.datastructures import URL

from app import crud, schemas
from app.api.deps import get_db, get_redis_client, APIRouter
from app.core import onadata, security
from app.core.config import settings

router = APIRouter()


@router.get("/login", status_code=302)
def login_oauth(
    server_url: str,
    redirect_url: Optional[str] = None,
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
    url = URL(server_url)
    server_url = urljoin(f"{url.scheme}://{url.netloc}", url.path)
    server: Optional[schemas.Server] = crud.server.get_using_url(db, url=server_url)
    if not server:
        raise HTTPException(status_code=400, detail="Server not configured")
    auth_state = {"server_id": server.id}
    if redirect_url:
        auth_state["redirect_url"] = redirect_url

    state_key, state = security.create_oauth_state(auth_state)
    redis.setex(state_key, timedelta(minutes=5), state)
    url = urljoin(
        f"{server.url}",
        f"/o/authorize?client_id={server.client_id}&response_type=code&state={state_key}",
    )
    return RedirectResponse(
        url=url,
        status_code=302,
        headers={
            "Cache-Control": "no-cache, no-store, revalidate",
        },
    )


@router.get(
    "/callback",
    responses={
        200: {"model": schemas.Token},
        302: {"headers": {"Cache-Control": "no-cache, no-store, revalidate"}},
    },
)
def callback_oauth(
    db=Depends(get_db),
    redis: redis.Redis = Depends(get_redis_client),
    *,
    request: Request,
    code: str,
    state: str,
):
    """
    Handles OAuth2 Code flow callback. This url should be registered
    as the "redirect_uri" for your Server OAuth Application(Onadata).

    This endpoint creates a user session for the authorized user and authenticates
    the user granting them access to the Hyper File API.

    User sessions last for 2 weeks. After the 2 weeks pass the user needs to re-authorize
    with the application to gain access to the Hyper file API
    """
    auth_state = redis.get(state)
    print("CODE: ", code)
    if not auth_state:
        raise HTTPException(
            status_code=401, detail="Authorization state can not be confirmed."
        )

    auth_state = json.loads(auth_state)
    redis.delete(state)
    server: Optional[schemas.Server] = crud.server.get(db, auth_state.get("server_id"))
    if not server:
        raise HTTPException(status_code=400, detail="Server not configured")

    redirect_url = auth_state.get("redirect_url")

    try:
        access_token, refresh_token = security.request_onadata_credentials(server, code)
        print("ACCESS TOKEN", access_token)
        print("REFRESH TOKEN", refresh_token)
        client = onadata.OnaDataAPIClient(server.url, access_token)
        profile = client.get_user()
    except security.FailedToRequestOnaDataCredentials as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=400, detail=str(e))
    except onadata.FailedExternalRequest as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=502, detail=str(e))
    else:
        username = profile["username"]
        user = crud.user.get_by_username(db, username=username, server_id=server.id)
        if not user:
            user_in = schemas.UserCreate(
                username=username,
                server_id=server.id,
                refresh_token=refresh_token,
                access_token=access_token,
            )
            user = crud.user.create(db, obj_in=user_in)
        else:
            user_in = schemas.UserUpdate(
                refresh_token=refresh_token,
                access_token=access_token,
            )
            user = crud.user.update(db, db_obj=user, obj_in=user_in)

        if redirect_url:
            # Create session for subsequent requests
            request, _ = security.create_session(
                request=request,
                user=user,
                expires_timedelta=timedelta(minutes=settings.SESSION_EXPIRE_MINUTES),
                redis_client=redis,
            )
            return RedirectResponse(url=redirect_url, status_code=302)
        return {
            "access_token": security.create_access_token(user.id),
            "token_type": "bearer",
        }
