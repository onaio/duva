from unittest.mock import patch, PropertyMock

from httpx._models import Response

from app import schemas
from app.models import HyperFile, Configuration
from app.tests.test_base import TestBase


class TestFileRoute(TestBase):
    @patch("app.routers.file.S3Client.generate_presigned_download_url")
    @patch("app.routers.file.schedule_hyper_file_cron_job")
    @patch("app.utils.onadata_utils.httpx.get")
    @patch("app.utils.onadata_utils.get_access_token")
    def _create_file(
        self,
        auth_credentials,
        mock_access_token,
        mock_get,
        mock_schedule_form,
        mock_presigned_create,
        file_data: dict = None,
    ):
        mock_presigned_create.return_value = "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540"
        mock_access_token.return_value = "some_access_token"
        mock_schedule_form.return_value = True
        mock_get.return_value = Response(
            json={
                "url": "https://testserver/api/v1/forms/1",
                "formid": 1,
                "metadata": [],
                "owner": "https://testserver/api/v1/users/bob",
                "created_by": "https://testserver/api/v1/users/bob",
                "public": True,
                "public_data": True,
                "public_key": "",
                "require_auth": False,
                "submission_count_for_today": 0,
                "tags": [],
                "title": "check_fields",
                "users": [
                    {
                        "is_org": False,
                        "metadata": {},
                        "first_name": "Bob",
                        "last_name": "",
                        "user": "bob",
                        "role": "owner",
                    }
                ],
                "enketo_url": "https://enketo-stage.ona.io/x/Z7k6kqn9",
                "enketo_preview_url": "https://enketo-stage.ona.io/preview/3eZVdQ26",
                "enketo_single_submit_url": "https://enketo-stage.ona.io/x/Z7k6kqn9",
                "num_of_submissions": 3,
                "last_submission_time": "2020-11-16T15:38:28.779972+00:00",
                "form_versions": [],
                "data_views": [],
                "description": "",
                "downloadable": True,
                "allows_sms": False,
                "encrypted": False,
                "sms_id_string": "check_fields",
                "id_string": "check_fields",
                "date_created": "2019-11-21T08:00:06.668073-05:00",
                "date_modified": "2020-11-16T10:38:28.744440-05:00",
                "uuid": "da3eed4893e74723b555f3255c432ae4",
                "bamboo_dataset": "",
                "instances_with_geopoints": True,
                "instances_with_osm": False,
                "version": "201911211300",
                "has_hxl_support": False,
                "last_updated_at": "2020-11-16T10:38:28.744455-05:00",
                "hash": "md5:692e501a01879439dcec79399484de4f",
                "is_merged_dataset": False,
                "project": "https://testserver/api/v1/projects/500",
            },
            status_code=200,
        )

        file_data = (
            file_data
            or schemas.FileRequestBody(
                server_url="http://testserver", form_id=1, immediate_sync=False
            ).dict()
        )
        response = self.client.post(
            "/api/v1/files", json=file_data, headers=auth_credentials
        )
        return response

    def _cleanup_files(self):
        self.db.query(HyperFile).delete()
        self.db.commit()

    def test_file_create(self, create_user_and_login):
        _, jwt = create_user_and_login
        num_of_files = len(HyperFile.get_all(self.db))
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        assert response.status_code == 201
        assert len(HyperFile.get_all(self.db)) == num_of_files + 1
        self._cleanup_files()

    @patch("app.routers.file.S3Client.generate_presigned_download_url")
    def test_file_update(self, mock_presigned_create, create_user_and_login):
        mock_presigned_create.return_value = "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540"
        user, jwt = create_user_and_login
        num_of_files = len(HyperFile.get_all(self.db))
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        assert response.status_code == 201
        assert len(HyperFile.get_all(self.db)) == num_of_files + 1

        file_id = response.json().get("id")
        # Test fails with 400 if update with non-existant
        # configuration
        data = {"configuration_id": 10230}
        response = self.client.patch(
            f"/api/v1/files/{file_id}", json=data, headers=auth_credentials
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Tableau configuration with ID 10230 not found"
        }

        # Correctly updates tableau configuration
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
        data = {"configuration_id": configuration.id}
        response = self.client.patch(
            f"/api/v1/files/{file_id}", json=data, headers=auth_credentials
        )

        assert response.status_code == 200
        assert (
            response.json().get("configuration_url")
            == f"http://testserver/api/v1/configurations/{configuration.id}"
        )
        self._cleanup_files()

    def test_file_delete(self, create_user_and_login):
        _, jwt = create_user_and_login
        num_of_files = len(HyperFile.get_all(self.db))
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        assert response.status_code == 201
        assert len(HyperFile.get_all(self.db)) == num_of_files + 1
        num_of_files += 1
        file_id = response.json().get("id")

        with patch(
            "app.routers.file.S3Client.s3", new_callable=PropertyMock
        ) as S3ClientMock:
            S3ClientMock().meta.client.delete_object.return_value = {
                "ResponseMetadata": {
                    "RequestId": "requestid",
                    "HostId": "hostid",
                    "HTTPStatusCode": 204,
                    "HTTPHeaders": {
                        "x-amz-id-2": "host-id",
                        "x-amz-request-id": "79Z2PTFDP93EHVFD",
                        "date": "Thu, 03 Jun 2021 09:26:28 GMT",
                        "server": "AmazonS3",
                    },
                    "RetryAttempts": 0,
                }
            }
            response = self.client.delete(
                f"/api/v1/files/{file_id}", headers=auth_credentials
            )
            assert response.status_code == 204
            assert len(HyperFile.get_all(self.db)) == num_of_files - 1
            self._cleanup_files()

    @patch("app.routers.file.S3Client.generate_presigned_download_url")
    def test_file_with_config(self, mock_presigned_create, create_user_and_login):
        mock_presigned_create.return_value = "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540"
        user, jwt = create_user_and_login
        num_of_files = len(HyperFile.get_all(self.db))
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        config = Configuration.create(
            self.db,
            schemas.ConfigurationCreate(
                user=user.id,
                server_address="http://test",
                site_name="test",
                project_name="test",
                token_name="test",
                token_value="test",
            ),
        )
        file_data = schemas.FileRequestBody(
            server_url="http://testserver",
            form_id=1,
            immediate_sync=False,
            configuration_id=config.id,
        ).dict()
        response = self._create_file(auth_credentials, file_data=file_data)
        response_json = response.json()
        response_json.pop("download_url_valid_till")
        expected_data = {
            "download_url": "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540",
            "filename": "check_fields.hyper",
            "file_status": schemas.FileStatusEnum.queued.value,
            "form_id": 1,
            "id": 1,
            "last_synced": None,
            "last_updated": None,
            "configuration_url": f"http://testserver/api/v1/configurations/{config.id}",
            "meta_data": {"job-id": "", "sync-failures": 0},
        }

        assert response.status_code == 201
        assert response_json == expected_data
        assert len(HyperFile.get_all(self.db)) == num_of_files + 1

        # Able to change Tableau Server Config
        config_2 = Configuration.create(
            self.db,
            schemas.ConfigurationCreate(
                user=user.id,
                server_address="http://tes2",
                site_name="tes2t",
                project_name="test2",
                token_name="test2",
                token_value="test2",
            ),
        )
        file_data = schemas.FilePatchRequestBody(configuration_id=config_2.id).dict()
        response = self.client.patch(
            "/api/v1/files/1", json=file_data, headers=auth_credentials
        )
        assert response.status_code == 200
        response_json = response.json()
        assert (
            response_json.get("configuration_url")
            == f"http://testserver/api/v1/configurations/{config_2.id}"
        )
        # Delete Tableau Configurations
        self.db.query(Configuration).delete()
        self.db.commit()
        self._cleanup_files()

    def test_file_list(self, create_user_and_login):
        user, jwt = create_user_and_login
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        self._create_file(auth_credentials)

        response = self.client.get("/api/v1/files", headers=auth_credentials)
        assert response.status_code == 200
        assert len(user.files) == 1
        assert len(response.json()) == len(user.files)
        hyperfile = user.files[0]
        expected_data = schemas.FileListItem(
            url=f"http://testserver/api/v1/files/{hyperfile.id}",
            id=hyperfile.id,
            form_id=hyperfile.form_id,
            filename=hyperfile.filename,
            last_updated=hyperfile.last_updated,
            last_synced=hyperfile.last_synced,
            meta_data=hyperfile.meta_data,
        ).dict()
        expected_data.update({"file_status": schemas.FileStatusEnum.queued.value})
        assert response.json()[0] == expected_data

        # Test filtering
        response = self.client.get(
            "/api/v1/files?form_id=000", headers=auth_credentials
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = self.client.get("/api/v1/files?form_id=1", headers=auth_credentials)
        assert response.status_code == 200
        assert len(response.json()) == len(user.files)

        self._cleanup_files()

    @patch("app.routers.file.start_csv_import_to_hyper")
    def test_trigger_hyper_file_sync(
        self, mock_start_csv_import, create_user_and_login
    ):
        _, jwt = create_user_and_login
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        # User is able to trigger a force update
        file_id = response.json().get("id")

        with patch("app.utils.utils.redis.Redis"):
            response = self.client.post(
                f"/api/v1/files/{file_id}/sync", headers=auth_credentials
            )

            assert response.status_code == 202
            expected_json = response.json()
            update_count = mock_start_csv_import.call_count

            # Returns a 202 status_code when update is on-going
            # and doesn't trigger another update
            response = self.client.post(
                f"/api/v1/files/{file_id}/sync", headers=auth_credentials
            )
            assert response.status_code == 202
            assert update_count == mock_start_csv_import.call_count
            assert response.json() == expected_json
        self._cleanup_files()

    @patch("app.routers.file.S3Client.generate_presigned_download_url")
    def test_file_get(self, mock_presigned_create, create_user_and_login):
        mock_presigned_create.return_value = "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540"
        user, jwt = create_user_and_login
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        self._create_file(auth_credentials)

        hyperfile = user.files[0]
        response = self.client.get(
            f"/api/v1/files/{hyperfile.id}", headers=auth_credentials
        )
        expected_keys = [
            "form_id",
            "id",
            "filename",
            "file_status",
            "last_updated",
            "last_synced",
            "download_url",
            "download_url_valid_till",
            "configuration_url",
            "meta_data",
        ]
        assert response.status_code == 200
        assert list(response.json().keys()) == expected_keys
        assert response.json()["id"] == hyperfile.id
        self._cleanup_files()

    def test_file_get_raises_error_on_invalid_id(self, create_user_and_login):
        user, jwt = create_user_and_login
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}

        response = self.client.get("/api/v1/files/form_id=1", headers=auth_credentials)
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid file ID"}
