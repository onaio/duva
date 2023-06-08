from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from app.core.onadata import FailedExternalRequest, OnaDataAPIClient
from app.core.security import fernet_decrypt

from app.crud.base import CRUDBase
from app.core.config import settings
from app.libs.s3.client import S3Client
from app.models.hyperfile import HyperFile
from app.models.user import User
from app.schemas.hyperfile import FileCreate, FilePatchRequestBody
from app.utils.onadata_utils import UnsupportedForm


class CRUDHyperFile(CRUDBase[HyperFile, FileCreate, FilePatchRequestBody]):
    def create(self, db: Session, *, obj_in: FileCreate, user: User) -> HyperFile:
        client = OnaDataAPIClient(
            user.server.url, fernet_decrypt(user.token.token_value), user
        )
        try:
            form_data = client.get_form(obj_in.form_id)
        except FailedExternalRequest as e:
            raise ValueError(f"Error retrieving form {obj_in.form_id}: {e}")

        if form_data.get("public_key"):
            raise UnsupportedForm("Encrypted forms are not supported")
        obj_in.filename = f"{form_data['title']}.hyper"
        return super().create(db, obj_in=obj_in)

    def get_active(self, db: Session) -> List[HyperFile]:
        return db.query(self.model).filter(self.model.is_active == True).all()

    def get_using_form(
        self, db: Session, *, form_id: str, user_id: str
    ) -> List[HyperFile]:
        return (
            db.query(self.model)
            .filter(self.model.form_id == form_id, self.model.user_id == user_id)
            .all()
        )

    def get_file_path(self, *, obj: HyperFile) -> str:
        return f"{obj.user.server_id}/{obj.user.username}/{obj.form_id}_{obj.filename}"

    def get_download_links(self, *, obj: HyperFile):
        s3_client = S3Client()
        exp = timedelta(seconds=settings.DOWNLOAD_EXPIRE_SECONDS)
        url = s3_client.generate_presigned_download_url(
            self.get_file_path(obj=obj), expiration=settings.DOWNLOAD_EXPIRE_SECONDS
        )
        if url:
            expiry = datetime.utcnow() + exp
            return url, expiry.isoformat()
        return None, None


hyperfile = CRUDHyperFile(HyperFile)
