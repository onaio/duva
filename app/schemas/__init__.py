# Schema Definitions
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.common_tags import JOB_ID_METADATA, SYNC_FAILURES_METADATA

from .configuration import (
    Configuration,
    ConfigurationCreate,
    ConfigurationCreateRequest,
    ConfigurationListResponse,
    ConfigurationPatchRequest,
    ConfigurationResponse,
    ExportConfigurationSettings,
)
from .hyperfile import (
    File,
    FileCreate,
    FileListItem,
    FilePatchRequestBody,
    FileRequestBody,
    FileResponseBody,
    FileStatusEnum,
)
from .server import Server, ServerCreate, ServerResponse, ServerUpdate
from .token import Token, TokenPayload
from .user import User, UserBearerTokenResponse, UserCreate, UserUpdate


class EventResponse(BaseModel):
    status: Optional[str] = ""
    name: Optional[str] = ""
    object_url: Optional[str] = ""
