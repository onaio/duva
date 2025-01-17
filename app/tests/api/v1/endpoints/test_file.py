from unittest.mock import PropertyMock, patch


from app import crud, schemas
from app.models import Configuration
from app.tests.test_base import TestBase


class TestFileRoute(TestBase):
    @patch("app.api.v1.endpoints.file.crud.hyperfile.get_download_links")
    @patch("app.api.v1.endpoints.file.schedule_import_to_hyper_job")
    @patch("app.api.v1.endpoints.file.OnaDataAPIClient")
    def _create_file(
        self,
        auth_credentials,
        mock_onadata_client,
        mock_schedule_form,
        mock_presigned_create,
        file_data: dict = None,
    ):
        mock_presigned_create.return_value = (
            "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540",
            "1609838540",
        )
        mock_schedule_form.return_value = True
        mock_onadata_client().get_form.return_value = {
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
        }

        file_data = file_data or schemas.FileRequestBody(
            server_url="http://testserver", form_id=1, immediate_sync=False
        ).dict(exclude_unset=True)
        response = self.client.post(
            "/api/v1/files/", json=file_data, headers=auth_credentials
        )
        return response

    def test_file_create(self, create_user_and_login):
        _, jwt = create_user_and_login
        num_of_files = len(crud.hyperfile.get_multi(self.db))
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        assert response.status_code == 201
        assert len(crud.hyperfile.get_multi(self.db)) == num_of_files + 1

    @patch("app.api.v1.endpoints.file.crud.hyperfile.get_download_links")
    def test_file_update(self, mock_presigned_create, create_user_and_login):
        mock_presigned_create.return_value = (
            "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540",
            "1609838540",
        )
        user, jwt = create_user_and_login
        num_of_files = len(crud.hyperfile.get_multi(self.db))
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        assert response.status_code == 201
        assert len(crud.hyperfile.get_multi(self.db)) == num_of_files + 1

        file_id = response.json().get("id")
        # Test fails with 400 if update with non-existant
        # configuration
        data = {"configuration_id": 10230}
        response = self.client.patch(
            f"/api/v1/files/{file_id}", json=data, headers=auth_credentials
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Configuration not found with given ID"}

        # Correctly updates tableau configuration
        configuration = crud.configuration.create(
            self.db,
            obj_in=schemas.ConfigurationCreate(
                user_id=user.id,
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
        config_url = response.json().get("configuration_url")
        assert config_url == f"http://testserver/configurations/{configuration.id}/"

    def test_file_delete(self, create_user_and_login):
        _, jwt = create_user_and_login
        num_of_files = len(crud.hyperfile.get_multi(self.db))
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        assert response.status_code == 201
        assert len(crud.hyperfile.get_multi(self.db)) == num_of_files + 1
        num_of_files += 1
        file_id = response.json().get("id")

        with patch(
            "app.crud.crud_hyperfile.S3Client.s3", new_callable=PropertyMock
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
            assert len(crud.hyperfile.get_multi(self.db)) == num_of_files - 1

    @patch("app.api.v1.endpoints.file.crud.hyperfile.get_download_links")
    def test_file_with_config(self, mock_presigned_create, create_user_and_login):
        mock_presigned_create.return_value = (
            "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540",
            "1609838540",
        )
        user, jwt = create_user_and_login
        num_of_files = len(crud.hyperfile.get_multi(self.db))
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        config = crud.configuration.create(
            self.db,
            obj_in=schemas.ConfigurationCreate(
                user_id=user.id,
                server_address="http://test",
                site_name="test",
                project_name="test",
                token_name="test",
                token_value="test",
            ),
        )
        file_data = schemas.FileRequestBody(
            form_id=1,
            sync_immediately=False,
            configuration_id=config.id,
        ).dict(exclude_unset=True)
        response = self._create_file(auth_credentials, file_data=file_data)
        response_json = response.json()
        response_json.pop("download_url_valid_till")
        file_id = response_json.pop("id")
        expected_data = {
            "download_url": "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540",
            "filename": "check_fields.hyper",
            "file_status": schemas.FileStatusEnum.file_unavailable.value,
            "form_id": 1,
            "last_updated": None,
            "configuration_url": f"http://testserver/configurations/{config.id}/",
            "meta_data": {"job-id": "", "sync-failures": 0},
        }

        assert response.status_code == 201
        assert response_json == expected_data
        assert len(crud.hyperfile.get_multi(self.db)) == num_of_files + 1

        # Able to change Tableau Server Config
        config_2 = crud.configuration.create(
            self.db,
            obj_in=schemas.ConfigurationCreate(
                user_id=user.id,
                server_address="http://tes2",
                site_name="tes2t",
                project_name="test2",
                token_name="test2",
                token_value="test2",
            ),
        )
        file_data = schemas.FilePatchRequestBody(configuration_id=config_2.id).dict(
            exclude_unset=True
        )
        response = self.client.patch(
            f"/api/v1/files/{file_id}", json=file_data, headers=auth_credentials
        )
        assert response.status_code == 200
        response_json = response.json()
        config_url = response_json.get("configuration_url")
        assert config_url == f"http://testserver/configurations/{config_2.id}/"
        # Delete Tableau Configurations
        self.db.query(Configuration).delete()
        self.db.commit()

    def test_file_list(self, create_user_and_login):
        user, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        self._create_file(auth_credentials)

        response = self.client.get("/api/v1/files/", headers=auth_credentials)
        assert response.status_code == 200
        assert len(user.hyper_files) == 1
        assert len(response.json()) == len(user.hyper_files)
        hyperfile = user.hyper_files[0]
        url = f"http://testserver/api/v1/files/{hyperfile.id}/"
        expected_data = schemas.FileListItem(
            url=url,
            download_url=url + "?file_format=hyper",
            id=hyperfile.id,
            form_id=hyperfile.form_id,
            filename=hyperfile.filename,
            last_updated=hyperfile.last_updated,
            meta_data=hyperfile.meta_data,
        ).dict()
        expected_data.update(
            {"file_status": schemas.FileStatusEnum.file_unavailable.value}
        )
        assert response.json()[0] == expected_data

        # Test filtering
        response = self.client.get(
            "/api/v1/files/?form_id=000", headers=auth_credentials
        )
        assert response.status_code == 200
        assert response.json() == []

        response = self.client.get("/api/v1/files/?form_id=1", headers=auth_credentials)
        assert response.status_code == 200
        assert response.json()[0] == expected_data

        response = self.client.get(
            "/api/v1/files/?form_id=1:", headers=auth_credentials
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid form_id provided: 1:"}

    def test_trigger_hyper_file_sync(self, create_user_and_login):
        _, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_file(auth_credentials)

        # User is able to trigger a force update
        file_id = response.json().get("id")

        with patch("app.api.v1.endpoints.file.import_to_hyper") as _:
            response = self.client.post(
                f"/api/v1/files/{file_id}/sync", headers=auth_credentials
            )

            assert response.status_code == 200

    @patch("app.api.v1.endpoints.file.crud.hyperfile.get_download_links")
    def test_file_get(self, mock_presigned_create, create_user_and_login):
        mock_presigned_create.return_value = (
            "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540",
            "1609838540",
        )
        user, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        self._create_file(auth_credentials)

        hyperfile = user.hyper_files[0]
        response = self.client.get(
            f"/api/v1/files/{hyperfile.id}", headers=auth_credentials
        )
        expected_keys = [
            "form_id",
            "id",
            "filename",
            "file_status",
            "last_updated",
            "download_url",
            "download_url_valid_till",
            "configuration_url",
            "meta_data",
        ]
        assert response.status_code == 200
        assert list(response.json().keys()) == expected_keys
        assert response.json()["id"] == hyperfile.id

    @patch("app.api.v1.endpoints.file.crud.hyperfile.get_download_links")
    def test_file_get_hyper(self, mock_presigned_create, create_user_and_login):
        redirect_url = "https://testing.s3.amazonaws.com/1/bob/check_fields.hyper?AWSAccessKeyId=key&Signature=sig&Expires=1609838540"
        mock_presigned_create.return_value = (
            redirect_url,
            "1609838540",
        )
        user, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        self._create_file(auth_credentials)

        hyperfile = user.hyper_files[0]
        response = self.client.get(
            f"/api/v1/files/{hyperfile.id}?file_format=hyper", headers=auth_credentials
        )
        assert response.url == redirect_url
        assert response.history[0].status_code == 307

    def test_file_get_raises_error_on_invalid_id(self, create_user_and_login):
        _, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}

        response = self.client.get("/api/v1/files/43234", headers=auth_credentials)
        assert response.status_code == 404
        assert response.json() == {"detail": "File not found."}
