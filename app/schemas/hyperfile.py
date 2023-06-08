from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.common_tags import JOB_ID_METADATA, SYNC_FAILURES_METADATA
from app.schemas.configuration import Configuration


class FileStatusEnum(str, Enum):
    queued = "Sync Queued"
    syncing = "Syncing file"
    latest_sync_failed = "Latest Sync Failed"
    file_available = "File available"
    file_unavailable = "File unavailable"


class FileBase(BaseModel):
    form_id: int


class FileListItem(BaseModel):
    url: str
    id: int
    form_id: int
    filename: str
    file_status: FileStatusEnum = FileStatusEnum.file_unavailable
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    meta_data: Optional[dict] = None


class FileCreate(FileBase):
    user_id: int
    filename: Optional[str] = ""
    configuration_id: Optional[int] = None
    is_active: bool = True
    meta_data: dict = {SYNC_FAILURES_METADATA: 0, JOB_ID_METADATA: ""}


class FileUpdate(FileBase):
    filename: Optional[str]
    is_active: bool = True
    meta_data: dict = {SYNC_FAILURES_METADATA: 0, JOB_ID_METADATA: ""}


class File(FileCreate):
    id: int
    file_status: FileStatusEnum = FileStatusEnum.file_unavailable
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    configuration: Optional[Configuration] = None

    class Config:
        orm_mode = True


class FileResponseBody(FileBase):
    id: int
    filename: str
    file_status: FileStatusEnum = FileStatusEnum.file_unavailable
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    download_url: Optional[str]
    download_url_valid_till: Optional[str]
    configuration_url: Optional[str]
    meta_data: Optional[dict] = None

    class Config:
        orm_mode = True


class FilePatchRequestBody(BaseModel):
    configuration_id: int


class FileRequestBody(FileBase):
    sync_immediately: bool = False
    configuration_id: Optional[int]
