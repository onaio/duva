from app.tests.test_base import TestBase
from app.settings import settings


class TestMain(TestBase):
    def test_home_route(self):
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json() == {
            "app_name": settings.app_name,
            "app_description": settings.app_description,
            "app_version": settings.app_version,
            "docs_url": "http://testserver/docs",
        }
