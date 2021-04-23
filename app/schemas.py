# Schema Definitions
from enum import Enum

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from app.common_tags import SYNC_FAILURES_METADATA, JOB_ID_METADATA


class FileStatusEnum(str, Enum):
    queued = "Sync Queued"
    syncing = "Syncing file"
    latest_sync_failed = "Latest Sync Failed"
    file_available = "File available"
    file_unavailable = "File unavailable"


class ServerBase(BaseModel):
    url: str


class ServerResponse(BaseModel):
    id: int
    url: str

    class Config:
        orm_mode = True


class ServerCreate(ServerBase):
    client_id: str
    client_secret: str


class Server(ServerCreate):
    id: int

    class Config:
        orm_mode = True


class User(BaseModel):
    username: str
    refresh_token: str
    server: int


class FileBase(BaseModel):
    form_id: int


class FileListItem(BaseModel):
    url: str
    id: int
    form_id: int
    filename: str
    file_status: FileStatusEnum = FileStatusEnum.file_unavailable.value


class FileCreate(FileBase):
    user: int
    filename: Optional[str]
    is_active: bool = True
    meta_data: dict = {SYNC_FAILURES_METADATA: 0, JOB_ID_METADATA: ""}


class ConfigurationResponse(BaseModel):
    id: int
    server_address: str
    site_name: str
    token_name: str
    project_name: str

    class Config:
        orm_mode = True


class ConfigurationListResponse(BaseModel):
    url: Optional[str]
    id: int
    site_name: str
    token_name: str
    project_name: str

    class Config:
        orm_mode = True


class ConfigurationCreateRequest(BaseModel):
    server_address: str
    site_name: str
    token_name: str
    project_name: str
    token_value: str


class ConfigurationPatchRequest(BaseModel):
    server_address: Optional[str]
    site_name: Optional[str]
    token_name: Optional[str]
    project_name: Optional[str]


class ConfigurationCreate(ConfigurationCreateRequest):
    user: int


class Configuration(ConfigurationCreate):
    id: int

    class Config:
        orm_mode = True


class File(FileCreate):
    id: int
    file_status: FileStatusEnum = FileStatusEnum.file_unavailable.value
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    configuration: Optional[Configuration] = None

    class Config:
        orm_mode = True


class FileResponseBody(FileBase):
    id: int
    filename: str
    file_status: FileStatusEnum = FileStatusEnum.file_unavailable.value
    last_updated: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    download_url: Optional[str]
    download_url_valid_till: Optional[str]
    configuration_url: Optional[str]

    class Config:
        orm_mode = True


class FilePatchRequestBody(BaseModel):
    configuration_id: int


class UserBearerTokenResponse(BaseModel):
    bearer_token: str


class FileRequestBody(FileBase):
    sync_immediately: bool = False
    configuration_id: Optional[int]


class EventResponse(BaseModel):
    status: Optional[str] = ""
    name: Optional[str] = ""
    object_url: Optional[str] = ""
