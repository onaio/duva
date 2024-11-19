import logging
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.token import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/oauth/login", auto_error=False)

logger = logging.getLogger("auth_deps")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
    *,
    request: Request,
) -> User:
    logger.info(f"Get current user token {token}")
    if not token:
        token = request.session.get("token")
        logger.info(f"Get current user session token {token}")

    if token:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
        except jwt.PyJWTError:
            logger.error(f"Get current user could not validate credentials {token}")
            if request.session.get("token"):
                del request.session["token"]
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )

        user = crud.user.get(db, id=token_data.sub)
        if not user:
            logger.info(f"Get current user: user not found {token_data.sub}")
            raise HTTPException(status_code=401, detail="User not found")

        return user
    logger.info(f"Get current user: missing token {token}")

    raise HTTPException(status_code=401, detail="Could not validate credentials")
