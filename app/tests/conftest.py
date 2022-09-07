import fakeredis
import pytest

from app.main import app
from app.tests.test_base import TestingSessionLocal
from app.utils.utils import get_db, get_redis_client

TEST_REDIS_SERVER = fakeredis.FakeServer()


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def override_get_redis_client():
    redis_client = fakeredis.FakeRedis(server=TEST_REDIS_SERVER)
    try:
        yield redis_client
    finally:
        pass


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis_client] = override_get_redis_client


@pytest.fixture(scope="function")
def create_user_and_login():
    from app import schemas
    from app.models import Server, User
    from app.utils.auth_utils import create_session

    db = TestingSessionLocal()
    redis_client = fakeredis.FakeRedis(server=TEST_REDIS_SERVER)
    server = Server.create(
        db,
        schemas.ServerCreate(
            url="http://testserver",
            client_id="some_client_id",
            client_secret="some_secret_value",
        ),
    )
    if User.get_using_username(db, "bob"):
        db.query(User).filter(User.username == "bob").delete()
        db.commit()

    user = User.create(
        db,
        schemas.User(
            username="bob", refresh_token="somes3cr3tvalu3", server_id=server.id
        ),
    )

    _, bearer_token = create_session(user, redis_client)
    yield user, bearer_token

    # Clean up created objects
    db.query(User).filter(User.id == user.id).delete()
    db.query(Server).filter(Server.id == server.id).delete()
    db.commit()
    db.close()
