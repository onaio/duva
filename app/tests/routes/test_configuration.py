from app.models import Configuration
from app import schemas
from app.tests.test_base import TestBase


class TestConfiguration(TestBase):
    def _create_configuration(self, auth_credentials: dict, config_data: dict = None):
        config_data = (
            config_data
            or schemas.ConfigurationCreateRequest(
                site_name="test",
                server_address="http://test",
                token_name="test",
                token_value="test",
                project_name="default",
            ).dict()
        )
        response = self.client.post(
            "/api/v1/configurations", json=config_data, headers=auth_credentials
        )

        # Returns a 400 exception when configuration already exists
        resp = self.client.post(
            "/api/v1/configurations", json=config_data, headers=auth_credentials
        )
        assert resp.status_code == 400
        assert resp.json() == {"detail": "Configuration already exists"}
        return response

    def _cleanup_configs(self):
        self.db.query(Configuration).delete()
        self.db.commit()

    def test_create_retrieve_config(self, create_user_and_login):
        _, jwt = create_user_and_login
        jwt = jwt.decode("utf-8")
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
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_configuration(auth_credentials)
        assert response.status_code == 201
        config_id = response.json().get("id")
        current_count = len(Configuration.get_all(self.db))

        response = self.client.delete(
            f"/api/v1/configurations/{config_id}", headers=auth_credentials
        )
        assert response.status_code == 204
        assert len(Configuration.get_all(self.db)) == current_count - 1

    def test_patch_config(self, create_user_and_login):
        _, jwt = create_user_and_login
        jwt = jwt.decode("utf-8")
        auth_credentials = {"Authorization": f"Bearer {jwt}"}
        response = self._create_configuration(auth_credentials)

        assert response.status_code == 201
        config_id = response.json().get("id")
        data = schemas.ConfigurationPatchRequest(
            site_name="test_change",
        ).dict()
        expected_data = schemas.ConfigurationResponse(
            site_name="test_change",
            server_address="http://test",
            token_name="test",
            project_name="default",
            id=config_id,
            export_settings=schemas.ExportConfigurationSettings(),
        ).dict()

        # Able to patch Tableau Configuration
        response = self.client.patch(
            f"/api/v1/configurations/{config_id}",
            json=data,
            headers=auth_credentials,
        )
        assert response.status_code == 200
        assert response.json() == expected_data
        self._cleanup_configs()
