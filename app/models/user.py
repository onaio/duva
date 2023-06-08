from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.base_class import Base


class User(Base):
    __table_args__ = (
        UniqueConstraint("server_id", "username", name="_server_user_uc"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    refresh_token = Column(String)
    access_token = Column(String)
    server_id = Column(Integer, ForeignKey("server.id", ondelete="CASCADE"))
    server = relationship("Server", back_populates="users")
    hyper_files = relationship("HyperFile", back_populates="user")
    configurations = relationship("Configuration", back_populates="user")
