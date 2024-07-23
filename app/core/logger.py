"""
Logging configuration to be set for the server
"""

from pydantic import BaseModel, Field
from typing import Any, ClassVar, Dict


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
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    handlers={
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": "app.log",
        },
    },
    loggers={
        "": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": True,
        },
        "uvicorn.error": {
            "level": "ERROR",
            "handlers": ["console", "file"],
            "propagate": True,
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": True,
        },
    },
)
