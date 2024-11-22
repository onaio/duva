import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
from urllib.parse import urljoin

import httpx
import requests
from requests.sessions import HTTPAdapter
from urllib3.util.retry import Retry

from app import crud, schemas
from app.common_tags import (
    ONADATA_FORMS_ENDPOINT,
    ONADATA_TOKEN_ENDPOINT,
    ONADATA_USER_ENDPOINT,
)
from app.core.config import settings
from app.core.exceptions import FailedExternalRequest
from app.core.security import fernet_decrypt
from app.database.session import SessionLocal
from app.models.hyperfile import HyperFile

COMMON_HEADERS = {"User-Agent": f"{settings.APP_NAME}/{settings.APP_VERSION}"}

logger = logging.getLogger("onadata")


def write_export_to_temp_file(export_url, client, retry: int = 0):
    print("Writing to temporary CSV Export to temporary file.")
    retry = 0 or retry
    status = 0
    with NamedTemporaryFile(delete=False, suffix=".csv") as export:
        with client.stream("GET", export_url, follow_redirects=True) as response:
            if response.status_code == 200:
                for chunk in response.iter_bytes():
                    export.write(chunk)
                return export
            status = response.status_code
    if retry < 3:
        print(
            f"Retrying export write: Status {status}, Retry {retry}, URL {export_url}"
        )
        write_export_to_temp_file(export_url=export_url, client=client, retry=retry + 1)


class OnaDataAPIClient:
    """
    Client for interacting with the OnaData API
    """

    def __init__(
        self,
        base_url: str,
        access_token: str,
        user=None,
        max_retries: int = 3,
        back_off_factor: float = 1.1,
        status_forcelist: list = [500, 502, 503, 504],
    ):
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=back_off_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.base_url = base_url
        self.user = user
        self.unique_id = "api-client"
        if user:
            self.unique_id += f"-{user.username}"

        self.client = requests.Session()
        self.client.mount("https://", adapter)
        self.client.mount("http://", adapter)
        self.headers = self._get_headers(access_token)

    def _get_headers(self, access_token: str) -> dict:
        if not access_token:
            self.refresh_access_token()
            access_token = fernet_decrypt(self.user.access_token)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        headers.update(COMMON_HEADERS)
        return headers

    def _download_export(
        self, url, retries: int = 0, sleep_when_in_progress: bool = True
    ):
        logger.info(f"{self.unique_id} - Downloading export from {url}")
        resp = self.client.get(url, headers=self.headers)
        if resp.status_code == 202:
            resp = resp.json()
            status = resp.get("job_status")

            if resp.get("export_url") and status == "SUCCESS":
                export_url = resp.get("export_url")
                client = httpx.Client(headers=self.headers)
                logger.info(f"{self.unique_id} - Export ready at {export_url}")
                return write_export_to_temp_file(export_url, client, retry=3)

            elif status == "FAILURE":
                logger.error(f"{self.unique_id} - Failed to export CSV\n{resp}")
                raise FailedExternalRequest(
                    f"Failed to export CSV: {resp.get('progress')}"
                )

            if resp.get("job_uuid"):
                url += f"&job_uuid={resp.get('job_uuid')}"

            if retries < 3:
                logger.info(f"{self.unique_id} - Export in progress. Retrying in a bit")
                if sleep_when_in_progress:
                    sleep(30 * (retries + 1))
                return self._download_export(url, retries=retries + 1)
            else:
                logger.error(f"{self.unique_id} - Export took too long. Aborting")
                raise FailedExternalRequest(
                    f"Failed to export CSV. URL: {url} took too long"
                )
        elif resp.status_code == 401:
            logger.info(f"{self.unique_id} - Access token expired. Refreshing")
            self.refresh_access_token()
            return self._download_export(url)

    def download_export(self, hyperfile: HyperFile) -> Path:
        self.user = hyperfile.user
        export_url = urljoin(
            self.base_url,
            f"{ONADATA_FORMS_ENDPOINT}/{hyperfile.form_id}/export_async.json?format=csv",
        )
        if hyperfile.configuration:
            export_settings = schemas.ExportConfigurationSettings(
                **hyperfile.configuration.export_settings
            ).dict()
            for key, value in export_settings.items():
                export_url += f"&{key}={value}"
        logger.info(
            f"{self.unique_id} - Downloading export for {hyperfile.form_id} - {export_url}"
        )
        return Path(self._download_export(export_url).name)

    def refresh_access_token(self):
        if not self.user:
            raise ValueError("User is required to refresh access token.")

        logger.info(f"{self.unique_id} - Refreshing access token for user")
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
        logger.info(f"{self.unique_id} - Refresh token response: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Got refreshed tokens {data}")
            self.user = crud.user.update(
                db=SessionLocal(),
                db_obj=self.user,
                obj_in={
                    "access_token": data["access_token"],
                    "refresh_token": data["refresh_token"],
                },
            )
            logger.info(f"{self.unique_id} - Refreshed access token")
        else:
            logger.error(f"{self.unique_id} - Failed to refresh access token")
            raise FailedExternalRequest(resp.text)

    def get_user(self) -> dict:
        logger.info(f"{self.unique_id} - Getting user")
        resp = self.client.get(
            url=urljoin(self.base_url, ONADATA_USER_ENDPOINT),
            headers=self.headers,
        )

        if resp.status_code != 200:
            logger.error(f"{self.unique_id} - Failed to get user {resp.status_code}")
            raise FailedExternalRequest(resp.text)
        else:
            logger.info(f"{self.unique_id} - Got user")
            return resp.json()

    def get_form(self, form_id: int) -> dict:
        logger.info(f"{self.unique_id} - Getting form {form_id}")
        forms_path = f"{ONADATA_FORMS_ENDPOINT}/{form_id}"
        resp = self.client.get(
            url=urljoin(self.base_url, forms_path),
            headers=self.headers,
        )

        if resp.status_code == 401:
            self.refresh_access_token()
            return self.get_form(form_id)
        elif resp.status_code != 200:
            logger.debug(
                f"{self.unique_id} - Failed to get form {resp.status_code} - "
                f"Reason {resp.text}"
            )
            raise FailedExternalRequest(resp.text)
        else:
            logger.info(f"{self.unique_id} - Got form {form_id}")
            return resp.json()
