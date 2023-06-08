from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    pass


class UserCreate(UserBase):
    username: str
    server_id: int
    access_token: str
    refresh_token: str


class UserUpdate(UserBase):
    refresh_token: Optional[str]
    access_token: Optional[str]


class User(UserBase):
    id: int
    username: str
    refresh_token: str
    server_id: int

    class Config:
        orm_mode = True


class UserBearerTokenResponse(BaseModel):
    bearer_token: str
