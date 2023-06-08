from typing import List

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.hyperfile import HyperFile
from app.schemas.hyperfile import FileCreate, FileUpdate


class CRUDHyperFile(CRUDBase[HyperFile, FileCreate, FileUpdate]):
    def get_active(self, db: Session) -> List[HyperFile]:
        return db.query(self.model).filter(self.model.is_active == True).all()
