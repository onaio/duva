from sqlalchemy import JSON, Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.base_class import Base


class Server(Base):
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True)
    client_id = Column(String)
    client_secret = Column(String)
    users = relationship("user", back_populates="server")
    configuration = Column(JSON, default={})
