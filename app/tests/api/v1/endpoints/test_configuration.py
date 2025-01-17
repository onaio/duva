from unittest.mock import patch

from app import crud, schemas
from app.models import Configuration
from app.tests.test_base import TestBase


class TestConfiguration(TestBase):
    @patch("app.crud.crud_configuration.TableauClient")
    def _create_configuration(
        self, auth_credentials: dict, mock_client, config_data: dict = None
    ):
        create_req_data = schemas.ConfigurationCreateRequest(
            site_name="test",
            server_address="http://test",
            token_name="test",
            token_value="test",
            project_name="default",
        ).dict()
        config_data = config_data or create_req_data
        mock_client.validate_configuration.return_value = True
        response = self.client.post(
            "/api/v1/configurations/", json=config_data, headers=auth_credentials
        )

        # Returns a 400 exception when configuration already exists
        resp = self.client.post(
            "/api/v1/configurations/", json=config_data, headers=auth_credentials
        )
        assert resp.status_code == 400
        assert resp.json() == {"detail": "Configuration already exists"}
        return response

    def _cleanup_configs(self):
        self.db.query(Configuration).delete()
        self.db.commit()

    def test_create_retrieve_config(self, create_user_and_login):
        _, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_configuration(auth_credentials)

        assert response.status_code == 201
        config_id = response.json().get("id")
        expected_data = schemas.ConfigurationResponse(
            site_name="test",
            server_address="http://test",
            token_name="test",
            project_name="default",
            id=config_id,
            export_settings=schemas.ExportConfigurationSettings(),
        ).dict()
        assert response.json() == expected_data

        # Able to retrieve Tableau Configuration
        response = self.client.get(
            f"/api/v1/configurations/{config_id}", headers=auth_credentials
        )
        assert response.status_code == 200
        assert response.json() == expected_data
        self._cleanup_configs()

    def test_delete_config(self, create_user_and_login):
        _, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_configuration(auth_credentials)
        assert response.status_code == 201
        config_id = response.json().get("id")
        current_count = len(crud.configuration.get_multi(self.db))

        response = self.client.delete(
            f"/api/v1/configurations/{config_id}", headers=auth_credentials
        )
        assert response.status_code == 204
        assert len(crud.configuration.get_multi(self.db)) == current_count - 1

    @patch("app.crud.crud_configuration.TableauClient")
    def test_patch_config(self, mock_client, create_user_and_login):
        _, jwt = create_user_and_login
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_configuration(auth_credentials)

        assert response.status_code == 201
        config_id = response.json().get("id")
        data = schemas.ConfigurationPatchRequest(
            site_name="test_change",
        ).dict(exclude_unset=True)
        expected_data = schemas.ConfigurationResponse(
            site_name="test_change",
            server_address="http://test",
            token_name="test",
            project_name="default",
            id=config_id,
            export_settings=schemas.ExportConfigurationSettings(),
        ).dict()
        mock_client.validate_configuration.return_value = True

        # Able to patch Tableau Configuration
        response = self.client.patch(
            f"/api/v1/configurations/{config_id}",
            json=data,
            headers=auth_credentials,
        )
        assert response.status_code == 200
        assert response.json() == expected_data
        self._cleanup_configs()
