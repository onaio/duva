"""
Logging configuration to be set for the server
"""

from pydantic import BaseModel, Field
from typing import Any, ClassVar, Dict, List


class LogConfig(BaseModel):
    version: ClassVar[int] = 1
    disable_existing_loggers: ClassVar[bool] = False
    formatters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    handlers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    loggers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True  # Enable from_orm usage


log_config = LogConfig(
    formatters={
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    handlers={
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    loggers={
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
    },
)
