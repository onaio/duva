from pydantic import BaseModel


class ServerBase(BaseModel):
    url: str


class ServerConfiguration(BaseModel):
    redirect_url: str
    scopes: list[str]
    authorization_url: str


class ServerResponse(BaseModel):
    id: int
    url: str

    class Config:
        from_attributes = True


class ServerCreate(ServerBase):
    client_id: str
    client_secret: str


class ServerUpdate(ServerBase):
    pass


class Server(ServerCreate):
    id: int

    class Config:
        from_attributes = True
