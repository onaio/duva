from sqlalchemy.orm import Session

from app.core.security import fernet_encrypt
from app.crud.base import CRUDBase
from app.models.server import Server
from app.schemas.server import ServerCreate, ServerUpdate


class CRUDServer(CRUDBase[Server, ServerCreate, ServerUpdate]):
    def get_using_url(self, db: Session, *, url: str) -> Server:
        return db.query(Server).filter(Server.url == url).first()

    def create(self, db: Session, *, obj_in: ServerCreate) -> Server:
        server_obj = Server(
            url=obj_in.url,
            client_id=obj_in.client_id,
            client_secret=fernet_encrypt(obj_in.client_secret),
        )
        db.add(server_obj)
        db.commit()
        db.refresh(server_obj)
        return server_obj


server = CRUDServer(Server)
