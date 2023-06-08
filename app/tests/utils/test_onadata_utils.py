"""
Tests for the onadata_utils module
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx._models import Response

from app import schemas
from app.models import Configuration, HyperFile, Server, User
from app.tests.test_base import TestBase
from app.utils.onadata_utils import (
    ConnectionRequestError,
    CSVExportFailure,
    _get_csv_export,
    get_access_token,
    get_csv_export,
)


class TestOnadataUtils(TestBase):
    @patch("app.utils.onadata_utils.httpx.post")
    def test_get_access_token(self, mock_httpx_post, create_user_and_login):
        """
        Test the get_access_token function correctly retrieves the
        access_token and resets the refresh_token
        """
        user, _ = create_user_and_login
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

    @patch("app.utils.onadata_utils.httpx.Client")
    @patch("app.utils.onadata_utils.get_access_token")
    def test_get_csv_export(
        self,
        mock_get_access_token,
        mock_httpx_client,
        create_user_and_login,
    ):
        """
        Test the get_csv_export function correctly generates the correct
        requests to retrieve a CSV Export
        """
        user, _ = create_user_and_login
        server = user.server
        configuration = Configuration.create(
            self.db,
            schemas.ConfigurationCreate(
                user=user.id,
                server_address="http://testserver",
                site_name="test",
                token_name="test",
                token_value="test",
                project_name="test",
            ),
        )
        hyperfile = HyperFile.create(
            self.db,
            schemas.FileCreate(
                user=user.id, filename="test.hyper", is_active=True, form_id="111"
            ),
        )
        hyperfile.configuration_id = configuration.id
        self.db.commit()
        file_mock = MagicMock()
        file_mock.name = "/tmp/test"
        mock_httpx_client().__enter__().get.return_value = Response(
            json={"id_string": "test"}, status_code=200
        )
        with patch("app.utils.onadata_utils._get_csv_export") as mock_get_csv_export:
            mock_get_csv_export.return_value = file_mock
            mock_get_access_token.return_value = "bob"

            ret = get_csv_export(
                hyperfile,
                user,
                user.server,
                self.db,
            )
            assert ret == Path(file_mock.name)
            mock_get_access_token.assert_called_with(user, server, self.db)
            expected_query_params = (
                "include_labels=True&remove_group_name=True&do_not_split_select_multiple=False"
                "&include_reviews=False&include_labels_only=True&value_select_multiples=True&"
                "show_choice_labels=True&binary_select_multiples=True"
            )
            mock_get_csv_export.assert_called_with(
                f"{server.url}/api/v1/forms/{hyperfile.form_id}/export_async.json?format=csv&{expected_query_params}",
                mock_httpx_client().__enter__(),
            )

        # Test that the _get_csv_export functionality works as expected
        in_progress_resp = Response(
            json={
                "job_status": "IN PROGRESS",
                "job_uuid": "d52c74ae-fed8-4d69-86b1-109572ddf5b8",
            },
            status_code=202,
        )
        complete_resp = Response(
            json={
                "job_status": "SUCCESS",
                "export_url": f"{server.url}/api/v1/exports/1",
            },
            status_code=202,
        )

        client_mock = MagicMock()
        client_mock.get.side_effect = [in_progress_resp, complete_resp]
        with patch(
            "app.utils.onadata_utils.write_export_to_temp_file"
        ) as mock_write_export_to_temp_file:
            mock_write_export_to_temp_file.return_value = file_mock
            ret = _get_csv_export(
                f"{server.url}/api/v1/export_async",
                client_mock,
                sleep_when_in_progress=False,
            )
            assert ret == file_mock
            assert client_mock.get.called
            assert client_mock.get.call_count == 2

        # Raises error when a `FAILURE` status is returned
        resp = Response(
            json={
                "job_status": "FAILURE",
            },
            status_code=202,
        )
        client_mock = MagicMock()
        client_mock.get.return_value = resp

        with pytest.raises(CSVExportFailure):
            _get_csv_export(
                f"{server.url}/api/v1/export_async",
                client_mock,
                sleep_when_in_progress=False,
            )
        assert client_mock.get.call_count == 1

        # Retries request a maximum of 4 times
        resp = Response(
            json={
                "job_status": "IN PROGRESS",
            },
            status_code=202,
        )
        client_mock = MagicMock()
        client_mock.get.return_value = resp

        with pytest.raises(ConnectionRequestError):
            _get_csv_export(
                f"{server.url}/api/v1/export_async",
                client_mock,
                sleep_when_in_progress=False,
            )
        assert client_mock.get.call_count == 4
