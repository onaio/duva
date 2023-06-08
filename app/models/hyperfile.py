import sqlalchemy.types as types
from sqlalchemy import (JSON, Boolean, Column, DateTime, ForeignKey, Integer,
                        String, UniqueConstraint)
from sqlalchemy.orm import relationship

from app import schemas
from app.common_tags import JOB_ID_METADATA, SYNC_FAILURES_METADATA
from app.database.base_class import Base


class ChoiceType(types.TypeDecorator):
    """
    ChoiceField Implementation for SQL Alchemy

    Credits: https://stackoverflow.com/a/6264027
    """

    impl = types.String

    def __init__(self, enum, **kwargs):
        self.choices = enum
        super(ChoiceType, self).__init__(**kwargs)

    def process_bind_param(self, value, dialect):
        for member in dir(self.choices):
            if getattr(self.choices, member) == value:
                return member

    def process_result_value(self, value, dialect):
        return getattr(self.choices, value).value


class HyperFile(Base):  # noqa
    __tablename__ = "hyper_file"
    __table_args__ = (UniqueConstraint("user_id", "form_id", name="_user_form_id_uc"),)

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=False)
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime)
    file_status = Column(
        ChoiceType(schemas.FileStatusEnum),
        default=schemas.FileStatusEnum.file_unavailable,
    )
    meta_data = Column(JSON, default={SYNC_FAILURES_METADATA: 0, JOB_ID_METADATA: 0})

    form_id = Column(Integer, nullable=False)

    configuration_id = Column(
        Integer, ForeignKey("configuration.id", ondelete="SET NULL")
    )
    configuration = relationship("configuration", back_populates="hyper_files")
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))
    user = relationship("user", back_populates="hyper_files")
