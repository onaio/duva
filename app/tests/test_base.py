import os

import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker

from app.database.base import Base
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
TEST_REDIS_SERVER = fakeredis.FakeServer()

# Delete existing test database
if os.path.exists("./test.db"):
    os.remove("./test.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


class TestBase:
    @classmethod
    def setup_class(cls):
        cls.client = TestClient(app=app)
        cls.db = TestingSessionLocal()
        cls.redis_client = fakeredis.FakeRedis(server=TEST_REDIS_SERVER)

    @classmethod
    def teardown_class(cls):
        cls.redis_client.flushall()
        cls.db.close()
