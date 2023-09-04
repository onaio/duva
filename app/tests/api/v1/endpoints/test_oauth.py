from unittest.mock import patch


from app import crud, schemas
from app.tests.test_base import TestBase


class TestOAuthRoute(TestBase):
    def setup_class(cls):
        super().setup_class()
        cls.mock_server = crud.server.create(
            cls.db,
            obj_in=schemas.ServerCreate(
                url="http://testserver",
                client_id="some_client_id",
                client_secret="some_client_secret",
            ),
        )
        cls.mock_server_2 = crud.server.create(
            cls.db,
            obj_in=schemas.ServerCreate(
                url="http://dupli.testserver",
                client_id="some_client_id",
                client_secret="some_client_secret",
            ),
        )

    def teardown_class(cls):
        crud.server.delete(cls.db, id=cls.mock_server.id)
        crud.server.delete(cls.db, id=cls.mock_server_2.id)
        super().teardown_class()

    @patch("app.api.v1.endpoints.oauth.security.create_oauth_state")
    def test_oauth_login_redirects(self, mock_create_auth_state):
        """
        Test that the "oauth/login" route redirects
        to the correct URL
        """
        # Ensure a 400 is raised when a user tries
        # to login to a server that isn't configured
        response = self.client.get("/api/v1/oauth/login?server_url=http://testserve")
        assert response.status_code == 400
        assert response.json() == {"detail": "Server not configured"}

        mock_create_auth_state.return_value = "some_uuid", '{{"server_id": 1}}'
        response = self.client.get("/api/v1/oauth/login?server_url=http://testserver")
        assert (
            response.url
            == f"http://testserver/o/authorize?client_id={self.mock_server.client_id}&response_type=code&state=some_uuid"
        )

    @patch("app.api.v1.endpoints.oauth.security.request_onadata_credentials")
    @patch("app.api.v1.endpoints.oauth.onadata.OnaDataAPIClient")
    def test_oauth_callback(
        self, mock_onadata_client, mock_request_onadata_credentials
    ):
        """
        Test that the OAuth2 callback URL confirms the
        auth state and creates a User object
        """
        url = "/api/v1/oauth/callback?code=some_code&state=some_uuid"
        self.redis_client.delete("some_uuid")
        response = self.client.get(url)
        assert response.status_code == 401
        assert response.json() == {
            "detail": "Authorization state can not be confirmed."
        }

        assert len(crud.user.get_multi(self.db)) == 0
        mock_auth_state = f'{{"server_id": {self.mock_server.id}}}'
        mock_request_onadata_credentials.return_value = (
            "some_access_token",
            "some_refresh_token",
        )
        mock_onadata_client().get_user.return_value = {
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
        }
        self.redis_client.set("some_uuid", mock_auth_state)
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(crud.user.get_multi(self.db)) == 1
        assert "access_token" in response.json().keys()
        assert "token_type" in response.json().keys()

        # Create user from different server with same username
        self.client.cookies.clear()
        mock_auth_state = f'{{"server_id": {self.mock_server_2.id}}}'
        self.redis_client.set("some_uuid", mock_auth_state)
        mock_request_onadata_credentials.return_value = (
            "some_access_token",
            "some_refresh_token",
        )
        mock_onadata_client().get_user.return_value = {
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
        }
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(crud.user.get_multi(self.db)) == 2
