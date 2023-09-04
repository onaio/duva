# Schema Definitions
from typing import Optional

from pydantic import BaseModel

from .configuration import (  # noqa
    Configuration,
    ConfigurationCreate,
    ConfigurationCreateRequest,
    ConfigurationListResponse,
    ConfigurationPatchRequest,
    ConfigurationResponse,
    ExportConfigurationSettings,
)
from .hyperfile import (  # noqa
    File,
    FileCreate,
    FileListItem,
    FilePatchRequestBody,
    FileRequestBody,
    FileResponseBody,
    FileStatusEnum,
)
from .server import Server, ServerCreate, ServerResponse, ServerUpdate  # noqa
from .token import Token, TokenPayload  # noqa
from .user import User, UserBearerTokenResponse, UserCreate, UserUpdate  # noqa


class EventResponse(BaseModel):
    status: Optional[str] = ""
    name: Optional[str] = ""
    object_url: Optional[str] = ""
