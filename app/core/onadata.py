from urllib.parse import urljoin

import httpx
from app import crud

from app.common_tags import (
    ONADATA_FORMS_ENDPOINT,
    ONADATA_USER_ENDPOINT,
    ONADATA_TOKEN_ENDPOINT,
)
from app.database.session import SessionLocal
from app.core.config import settings
from app.core.security import fernet_decrypt


COMMON_HEADERS = {"User-Agent": f"{settings.APP_NAME}/{settings.APP_VERSION}"}


class FailedExternalRequest(Exception):
    pass


class OnaDataAPIClient:
    def __init__(self, base_url: str, access_token: str, user=None):
        self.transport = httpx.HTTPTransport(retries=3)
        self.client = httpx.Client(transport=self.transport)
        self.headers = self._get_headers(access_token)
        self.base_url = base_url
        self.user = user

    def _get_headers(self, access_token: str) -> dict:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        headers.update(COMMON_HEADERS)
        return headers

    def refresh_access_token(self):
        if not self.user:
            raise ValueError("User is required to refresh access token.")

        url = urljoin(self.base_url, ONADATA_TOKEN_ENDPOINT)
        data = {
            "grant_type": "refresh_token",
            "refresh_token": fernet_decrypt(self.user.refresh_token),
            "client_id": self.user.server.client_id,
        }
        resp = self.client.post(
            url=url,
            data=data,
            auth=(
                self.user.server.client_id,
                fernet_decrypt(self.user.server.client_secret),
            ),
        )
        if resp.status_code == 200:
            data = resp.json()
            self.user = crud.user.update(
                db=SessionLocal(),
                db_obj=self.user,
                obj_in={
                    "access_token": data["access_token"],
                    "refresh_token": data["refresh_token"],
                },
            )
        else:
            raise FailedExternalRequest(resp.text)

    def get_user(self) -> dict:
        resp = self.client.get(
            url=urljoin(self.base_url, ONADATA_USER_ENDPOINT),
            headers=self.headers,
        )

        if resp.status_code != 200:
            raise FailedExternalRequest(resp.text)
        else:
            return resp.json()

    def get_form(self, form_id: int) -> dict:
        forms_path = f"{ONADATA_FORMS_ENDPOINT}/{form_id}"
        resp = self.client.get(
            url=urljoin(self.base_url, forms_path),
            headers=self.headers,
        )

        if resp.status_code == 401:
            self.refresh_access_token()
            return self.get_form(form_id)
        elif resp.status_code != 200:
            raise FailedExternalRequest(resp.text)
        else:
            return resp.json()
