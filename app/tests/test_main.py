from app.core.config import settings
from app.tests.test_base import TestBase


class TestMain(TestBase):
    def test_home_route(self):
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json() == {
            "app_name": settings.APP_NAME,
            "app_description": settings.APP_DESCRIPTION,
            "app_version": settings.APP_VERSION,
            "docs_url": "http://testserver/docs",
            "openapi_url": "http://testserver/openapi.json",
        }
