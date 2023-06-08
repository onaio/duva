import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.orm import Session
from app.api.deps import get_db
from app import crud
from app.models.user import User
from app.schemas.token import TokenPayload
from app.core.config import settings

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"/api/v1/oauth/login", auto_error=False
)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
    *,
    request: Request,
) -> User:
    if not token:
        token = request.session.get("token")

    if token:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
        except jwt.PyJWTError:
            if request.session.get("token"):
                del request.session["token"]
            raise HTTPException(
                status_code=403, detail="Could not validate credentials"
            )

        user = crud.user.get(db, id=token_data.sub)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user
    else:
        return None
