from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.security import fernet_encrypt
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_username(
        self, db: Session, *, username: str, server_id: int
    ) -> Optional[User]:
        return (
            db.query(User)
            .filter(User.username == username, User.server_id == server_id)
            .first()
        )

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        user_obj = User(
            username=obj_in.username,
            refresh_token=fernet_encrypt(obj_in.refresh_token),
            access_token=fernet_encrypt(obj_in.access_token),
            server_id=obj_in.server_id,
        )
        db.add(user_obj)
        db.commit()
        db.refresh(user_obj)
        return user_obj

    def update(
        self, db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        if update_data["refresh_token"]:
            update_data["refresh_token"] = fernet_encrypt(update_data["refresh_token"])
            del update_data["refresh_token"]

        if update_data["access_token"]:
            update_data["access_token"] = fernet_encrypt(update_data["access_token"])
            del update_data["access_token"]

        return super().update(db, obj_in=update_data, db_obj=db_obj)


user = CRUDUser(User)
