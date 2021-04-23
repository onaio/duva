from typing import Tuple
from fastapi.responses import Response
from app import schemas
from app.models import Server
from app.tests.test_base import TestBase


class TestServerRoute(TestBase):
    def _create_server(self, url: str = "http://testserver") -> Tuple[Response, int]:
        initial_count = len(Server.get_all(self.db))
        data = schemas.ServerCreate(
            url=url,
            client_id="some_client_id",
            client_secret="some_client_secret",
        ).dict()
        response = self.client.post("/api/v1/servers", json=data)
        return response, initial_count

    def _cleanup_server(self):
        self.db.query(Server).filter(Server.url == "http://testserver").delete()
        self.db.commit()

    def test_bad_url_rejected(self):
        url = "bad_url"
        response, _ = self._create_server(url=url)
        assert response.status_code == 400
        assert response.json() == {"detail": f"Invalid url {url}"}

    def test_create_server(self):
        response, initial_count = self._create_server()
        expected_keys = ["id", "url"]
        assert response.status_code == 201
        assert expected_keys == list(response.json().keys())
        assert len(Server.get_all(self.db)) == initial_count + 1

        # Test trying to create a different server with the same URL
        # returns a 400 response
        response, _ = self._create_server()
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Server with url 'http://testserver' already exists."
        }
        self._cleanup_server()

    def test_retrieve_server(self):
        """
        Test the retrieve server configuration routes
        """
        response, _ = self._create_server()
        expected_response = response.json()
        server_id = expected_response.get("id")
        response = self.client.get(f"/api/v1/servers/{server_id}")
        assert response.status_code == 200
        assert response.json() == expected_response
        self._cleanup_server()
