import sqlalchemy.types as types
from typing import Optional
from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql.schema import ForeignKey

from app import schemas
from app.common_tags import SYNC_FAILURES_METADATA, JOB_ID_METADATA
from app.database import Base
from app.settings import settings
from app.libs.s3.client import S3Client


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


class ModelMixin(object):
    @classmethod
    def get(cls, db: Session, object_id: int):
        return db.query(cls).filter(cls.id == object_id).first()

    @classmethod
    def get_all(cls, db: Session, skip: int = 0, limit: int = 100):
        return db.query(cls).offset(skip).limit(limit).all()

    @classmethod
    def delete(cls, db: Session, object_id: int):
        return (
            db.query(cls)
            .filter(cls.id == object_id)
            .delete(synchronize_session="fetch")
        )


class EncryptionMixin(object):
    @classmethod
    def _get_encryption_key(cls):
        return Fernet(settings.secret_key)

    @classmethod
    def encrypt_value(cls, raw_value):
        key = cls._get_encryption_key()
        return key.encrypt(raw_value.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_value(cls, encrypted_value):
        key = cls._get_encryption_key()
        return key.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")


class HyperFile(ModelMixin, Base):
    __tablename__ = "hyper_file"
    __table_args__ = (UniqueConstraint("user", "form_id", name="_user_form_id_uc"),)

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=False)
    user = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))
    form_id = Column(Integer, nullable=False)
    last_updated = Column(DateTime)
    last_synced = Column(DateTime)
    is_active = Column(Boolean, default=True)
    file_status = Column(
        ChoiceType(schemas.FileStatusEnum),
        default=schemas.FileStatusEnum.file_unavailable,
    )
    configuration_id = Column(
        Integer, ForeignKey("configuration.id", ondelete="SET NULL")
    )
    meta_data = Column(JSON, default={SYNC_FAILURES_METADATA: 0, JOB_ID_METADATA: ""})
    configuration = relationship("Configuration")

    def get_file_path(self, db: Session):
        user = User.get(db, self.user)
        s3_path = f"{user.server}/{user.username}/{self.form_id}_{self.filename}"
        return s3_path

    def retrieve_latest_file(self, db: Session):
        local_path = f"{settings.media_path}/{self.form_id}_{self.filename}"
        s3_path = self.get_file_path(db)
        client = S3Client()
        client.download(local_path, s3_path)
        return local_path

    @classmethod
    def get_using_file_create(cls, db: Session, file_create: schemas.FileCreate):
        return (
            db.query(cls)
            .filter(cls.user == file_create.user, cls.form_id == file_create.form_id)
            .first()
        )

    @classmethod
    def get_active_files(cls, db: Session):
        return db.query(cls).filter(cls.is_active == True).all()  # noqa

    @classmethod
    def create(cls, db: Session, hyperfile: schemas.FileCreate):
        instance = cls(**hyperfile.dict())
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    @classmethod
    def filter(cls, user: schemas.User, form_id: int, db: Session):
        return db.query(cls).filter(cls.user == user.id, cls.form_id == form_id).all()


class Server(ModelMixin, EncryptionMixin, Base):
    __tablename__ = "server"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    client_id = Column(String)
    client_secret = Column(String)

    @classmethod
    def get_using_url(cls, db: Session, url: str) -> Optional[schemas.Server]:
        return db.query(cls).filter(cls.url == url).first()

    @classmethod
    def create(cls, db: Session, server: schemas.ServerCreate) -> schemas.Server:
        encrypted_secret = cls.encrypt_value(server.client_secret)
        server = cls(
            url=server.url,
            client_id=server.client_id,
            client_secret=encrypted_secret,
        )
        db.add(server)
        db.commit()
        db.refresh(server)
        return server


class User(ModelMixin, EncryptionMixin, Base):
    __tablename__ = "user"
    __table_args__ = (UniqueConstraint("server", "username", name="_server_user_uc"),)

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    refresh_token = Column(String)
    server = Column(Integer, ForeignKey("server.id", ondelete="CASCADE"))
    files = relationship("HyperFile")

    @classmethod
    def get_using_username(cls, db: Session, username: str):
        return db.query(cls).filter(cls.username == username).first()

    @classmethod
    def get_using_server_and_username(cls, db: Session, username: str, server_id: int):
        return (
            db.query(cls)
            .filter(cls.username == username, cls.server == server_id)
            .first()
        )

    @classmethod
    def create(cls, db: Session, user: schemas.User):
        encrypted_token = cls.encrypt_value(user.refresh_token)
        user = cls(
            username=user.username, refresh_token=encrypted_token, server=user.server
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


class Configuration(ModelMixin, EncryptionMixin, Base):
    """
    Tableau server authentication configurations; Used to publish
    Hyper files.
    """

    __tablename__ = "configuration"
    __table_args__ = (
        UniqueConstraint(
            "server_address", "token_name", "user", name="_server_token_name_uc"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    server_address = Column(String)
    site_name = Column(String)
    token_name = Column(String)
    token_value = Column(String)
    project_name = Column(String, default="default")
    user = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))

    @classmethod
    def filter_using_user_id(cls, db: Session, user_id: int):
        return db.query(cls).filter(cls.user == user_id)

    @classmethod
    def create(cls, db: Session, config: schemas.ConfigurationCreate):
        encrypted_token = cls.encrypt_value(config.token_value)
        data = config.dict()
        data.update({"token_value": encrypted_token})
        configuration = cls(**data)
        db.add(configuration)
        db.commit()
        db.refresh(configuration)
        return configuration
