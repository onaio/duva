from unittest.mock import patch

from httpx._models import Response

from app import schemas
from app.models import Server, User
from app.tests.test_base import TestBase


class TestOAuthRoute(TestBase):
    def setup_class(cls):
        super().setup_class()
        cls.mock_server = Server.create(
            cls.db,
            schemas.ServerCreate(
                url="http://testserver",
                client_id="some_client_id",
                client_secret="some_client_secret",
            ),
        )
        cls.mock_server_2 = Server.create(
            cls.db,
            schemas.ServerCreate(
                url="http://dupli.testserver",
                client_id="some_client_id",
                client_secret="some_client_secret",
            ),
        )

    def teardown_class(cls):
        cls.db.query(Server).filter(Server.id == cls.mock_server.id).delete()
        cls.db.query(Server).filter(Server.id == cls.mock_server_2.id).delete()
        cls.db.commit()
        super().teardown_class()

    @patch("app.routers.oauth.uuid.uuid4")
    def test_oauth_login_redirects(self, mock_uuid):
        """
        Test that the "oauth/login" route redirects
        to the correct URL
        """
        # Ensure a 400 is raised when a user tries
        # to login to a server that isn't configured
        response = self.client.get("/api/v1/oauth/login?server_url=http://testserve")
        assert response.status_code == 400
        assert response.json() == {"detail": "Server not configured"}

        mock_uuid.return_value = "some_uuid"
        response = self.client.get("/api/v1/oauth/login?server_url=http://testserver")
        assert (
            response.url
            == f"http://testserver/o/authorize?client_id={self.mock_server.client_id}&response_type=code&state=some_uuid"
        )

    @patch("app.routers.oauth.httpx")
    @patch("app.routers.oauth.redis.Redis.get")
    def test_oauth_callback(self, mock_redis_get, mock_httpx):
        """
        Test that the OAuth2 callback URL confirms the
        auth state and creates a User object
        """
        mock_redis_get.return_value = None
        url = "/api/v1/oauth/callback?code=some_code&state=some_uuid"
        response = self.client.get(url)
        assert response.status_code == 401
        assert response.json() == {
            "detail": "Authorization state can not be confirmed."
        }

        assert len(User.get_all(self.db)) == 0
        mock_auth_state = f'{{"server_id": {self.mock_server.id}}}'
        mock_redis_get.return_value = mock_auth_state
        mock_httpx.post.return_value = Response(
            json={
                "access_token": "some_access_token",
                "token_type": "Bearer",
                "expires_in": 36000,
                "refresh_token": "some_refresh_token",
                "scope": "read write groups",
            },
            status_code=200,
        )
        mock_httpx.get.return_value = Response(
            json={
                "api_token": "some_api_token",
                "temp_token": "some_temp_token",
                "city": "Nairobi",
                "country": "Kenya",
                "gravatar": "avatar.png",
                "name": "Bob",
                "email": "bob@user.com",
                "organization": "",
                "require_auth": False,
                "twitter": "",
                "url": "http://testserver/api/v1/profiles/bob",
                "user": "http://testserver/api/v1/users/bob",
                "username": "bob",
                "website": "",
            },
            status_code=200,
        )
        self.redis_client.set("some_uuid", mock_auth_state)
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(User.get_all(self.db)) == 1
        assert "bearer_token" in response.json().keys()

        # Create user from different server with same username
        self.client.cookies.clear()
        mock_auth_state = f'{{"server_id": {self.mock_server_2.id}}}'
        mock_redis_get.return_value = mock_auth_state
        mock_httpx.get.return_value = Response(
            json={
                "api_token": "some_api_token",
                "temp_token": "some_temp_token",
                "city": "Nairobi",
                "country": "Kenya",
                "gravatar": "avatar.png",
                "name": "Bob",
                "email": "bob@user.com",
                "organization": "",
                "require_auth": False,
                "twitter": "",
                "url": "http://dupli.testserver/api/v1/profiles/bob",
                "user": "http://dupli.testserver/api/v1/users/bob",
                "username": "bob",
                "website": "",
            },
            status_code=200,
        )
        self.redis_client.set("some_uuid", mock_auth_state)
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(User.get_all(self.db)) == 2
