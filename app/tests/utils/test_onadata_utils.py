"""
Tests for the onadata_utils module
"""
from unittest.mock import patch

from httpx._models import Response

from app import schemas
from app.models import Server, User, HyperFile
from app.tests.test_base import TestBase
from app.utils.onadata_utils import get_access_token


class TestOnadataUtils(TestBase):
    @patch("app.utils.onadata_utils.httpx.post")
    def test_get_access_token(self, mock_httpx_post, create_user_and_login):
        """
        Test the get_access_token function correctly retrieves the
        access_token and resets the refresh_token
        """
        user, jwt = create_user_and_login
        mock_httpx_post.return_value = Response(
            json={
                "refresh_token": "new_token",
                "access_token": "new_access_token",
                "expiresIn": "somedate",
            },
            status_code=200,
        )
        old_refresh_token = user.refresh_token
        server = user.server
        ret = get_access_token(user, server, self.db)

        assert ret == "new_access_token"
        mock_httpx_post.assert_called_with(
            f"{server.url}/o/token/",
            data={
                "grant_type": "refresh_token",
                "refresh_token": User.decrypt_value(user.refresh_token),
                "client_id": server.client_id,
            },
            auth=(server.client_id, Server.decrypt_value(server.client_secret)),
        )
        user = User.get(self.db, user.id)
        assert user.refresh_token != old_refresh_token
        assert User.decrypt_value(user.refresh_token) == "new_token"

    @patch("app.utils.onadata_utils._get_csv_export")
    def test_get_csv_export(self, mock_get_csv_export, create_user_and_login):
        """
        Test the get_csv_export function correctly generates the correct
        requests to retrieve a CSV Export
        """
        user, jwt = create_user_and_login
        server = user.server
        hyperfile = HyperFile.create(
            self.db,
            schemas.FileCreate(
                user=user.id, filename="test.hyper", is_active=True, form_id="111"
            ),
        )
        pass
