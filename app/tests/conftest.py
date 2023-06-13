import fakeredis
import pytest

from app import crud, schemas
from app.api.deps import get_db, get_redis_client
from app.core import security
from app.main import app
from app.tests.test_base import TEST_REDIS_SERVER, TestingSessionLocal


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
    db = TestingSessionLocal()
    if prev_server := crud.server.get_using_url(db, url="http://testserver"):
        crud.server.delete(db, id=prev_server.id)

    server = crud.server.create(
        db,
        obj_in=schemas.ServerCreate(
            url="http://testserver",
            client_id="some_client_id",
            client_secret="some_secret_value",
        ),
    )

    if prev_user := crud.user.get_by_username(db, username="bob", server_id=server.id):
        crud.user.delete(db, id=prev_user.id)

    user = crud.user.create(
        db,
        obj_in=schemas.UserCreate(
            username="bob",
            refresh_token="somes3cr3tvalu3",
            access_token="somes3cr3valu3",
            server_id=server.id,
        ),
    )

    bearer_token = security.create_access_token(user.id)
    yield user, bearer_token

    # Clean up created objects
    crud.user.delete(db, id=user.id)
    crud.server.delete(db, id=server.id)
