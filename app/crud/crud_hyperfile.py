from datetime import datetime, timedelta
from typing import List, Union

import sentry_sdk
from sqlalchemy.orm import Session

from app.common_tags import JOB_ID_METADATA
from app.core.config import settings
from app.crud.base import CRUDBase
from app.jobs.scheduler import cancel_job
from app.libs.s3.client import S3Client
from app.libs.tableau.client import InvalidConfiguration, TableauClient
from app.models.hyperfile import HyperFile
from app.schemas.hyperfile import (
    FileCreate,
    FilePatchRequestBody,
    FileStatusEnum,
    FileUpdate,
)


class CRUDHyperFile(
    CRUDBase[HyperFile, FileCreate, Union[FilePatchRequestBody, FileUpdate]]
):
    def delete(self, db: Session, *, id: int) -> HyperFile:
        obj = self.get(db, id=id)
        if obj.meta_data.get(JOB_ID_METADATA):
            cancel_job(obj.meta_data.get(JOB_ID_METADATA))

        s3_client = S3Client()
        s3_client.delete(self.get_file_path(obj=obj))
        return super().delete(db, id=id)

    def get_active(self, db: Session) -> List[HyperFile]:
        return db.query(self.model).filter(self.model.is_active == True).all()  # noqa

    def get_using_form(
        self, db: Session, *, form_id: int, user_id: int
    ) -> List[HyperFile]:
        return (
            db.query(self.model)
            .filter(self.model.form_id == form_id, self.model.user_id == user_id)
            .all()
        )

    def get_local_path(self, *, obj: HyperFile) -> str:
        return f"{settings.MEDIA_ROOT}/{obj.form_id}_{obj.filename}"

    def get_latest_file(self, *, obj: HyperFile) -> str:
        local_path = self.get_local_path(obj=obj)
        s3_client = S3Client()
        s3_client.download(self.get_file_path(obj=obj), local_path)
        return local_path

    def update_status(
        self, db: Session, *, obj: HyperFile, status: FileStatusEnum
    ) -> HyperFile:
        obj.file_status = status
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def sync_upstreams(self, db: Session, *, obj: HyperFile):
        s3_client = S3Client()
        s3_client.upload(self.get_local_path(obj=obj), self.get_file_path(obj=obj))
        file_path = self.get_latest_file(obj=obj)

        if obj.configuration:
            tableau_client = TableauClient(configuration=obj.configuration)
            try:
                tableau_client.validate_configuration(obj.configuration)
            except InvalidConfiguration as e:
                sentry_sdk.capture_exception(e)
                pass
            else:
                tableau_client.publish_hyper(file_path)
        obj.last_updated = datetime.utcnow()
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

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
