# Utility functions for Ona Data Aggregate Servers
import time
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

import httpx
import sentry_sdk
from sqlalchemy.orm.session import Session
from tableauhyperapi import HyperProcess

from app import schemas
from app.common_tags import (
    ONADATA_TOKEN_ENDPOINT,
    ONADATA_FORMS_ENDPOINT,
    ONADATA_USER_ENDPOINT,
)
from app.database import SessionLocal
from app.models import HyperFile, Server, User
from app.settings import settings
from app.utils.hyper_utils import handle_csv_import_to_hyperfile


class UnsupportedForm(Exception):
    pass


class ConnectionRequestError(Exception):
    pass


class CSVExportFailure(Exception):
    pass


class DoesNotExist(Exception):
    pass


def get_access_token(user: User, server: Server, db: SessionLocal) -> Optional[str]:
    url = f"{server.url}{ONADATA_TOKEN_ENDPOINT}"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": user.decrypt_value(user.refresh_token),
        "client_id": server.client_id,
    }
    resp = httpx.post(
        url,
        data=data,
        auth=(server.client_id, server.decrypt_value(server.client_secret)),
    )
    if resp.status_code == 200:
        resp = resp.json()
        user = User.get(db, user.id)
        user.refresh_token = user.encrypt_value(resp.get("refresh_token"))
        db.commit()
        return resp.get("access_token")
    return None


def _get_csv_export(
    url: str, headers: dict = None, temp_token: str = None, retries: int = 0
):
    def _write_export_to_temp_file(export_url, headers, retry: int = 0):
        print("Writing to temporary CSV Export to temporary file.")
        retry = 0 or retry
        status = 0
        with NamedTemporaryFile(delete=False, suffix=".csv") as export:
            with httpx.stream("GET", export_url, headers=headers) as response:
                if response.status_code == 200:
                    for chunk in response.iter_bytes():
                        export.write(chunk)
                    return export
                status = response.status_code
        if retry < 3:
            print(
                f"Retrying export write: Status {status}, Retry {retry}, URL {export_url}"
            )
            _write_export_to_temp_file(
                export_url=export_url, headers=headers, retry=retry + 1
            )

    print("Checking on export status.")
    resp = httpx.get(url, headers=headers)

    if resp.status_code == 202:
        resp = resp.json()
        job_status = resp.get("job_status")
        if "export_url" in resp and job_status == "SUCCESS":
            export_url = resp.get("export_url")
            if temp_token:
                export_url += f"&temp_token={temp_token}"
            return _write_export_to_temp_file(export_url, headers)
        elif job_status == "FAILURE":
            reason = resp.get("progress")
            raise CSVExportFailure(f"CSV Export Failure. Reason: {reason}")

        job_uuid = resp.get("job_uuid")
        if job_uuid:
            print(f"Waiting for CSV Export to be ready. Job UUID: {job_uuid}")
            time.sleep(30 * (retries + 1))
            url += f"&job_uuid={job_uuid}"

        if retries < 3:
            return _get_csv_export(
                url, headers=headers, temp_token=temp_token, retries=retries + 1
            )
        else:
            raise ConnectionRequestError(
                f"Failed to retrieve CSV Export. URL: {url}, took too long for CSV Export to be ready"
            )
    else:
        raise ConnectionRequestError(
            f"Failed to retrieve CSV Export. URL: {url}, Status Code: {resp.status_code}"
        )


def get_csv_export(
    hyperfile: HyperFile, user: schemas.User, server: schemas.Server, db: SessionLocal
) -> str:
    """
    Retrieves a CSV Export for an XForm linked to a Hyperfile
    """
    bearer_token = get_access_token(user, server, db)
    headers = {
        "user-agent": f"{settings.app_name}/{settings.app_version}",
        "Authorization": f"Bearer {bearer_token}",
    }
    form_url = f"{server.url}{ONADATA_FORMS_ENDPOINT}/{hyperfile.form_id}"
    resp = httpx.get(form_url + ".json", headers=headers)
    if resp.status_code == 200:
        form_data = resp.json()
        public = form_data.get("public")
        url = f"{form_url}/export_async.json?format=csv"
        temp_token = None

        # Retrieve auth credentials if XForm is private
        # Onadatas' Export Endpoint only support TempToken or Basic Authentication
        if not public:
            resp = httpx.get(
                f"{server.url}{ONADATA_USER_ENDPOINT}.json", headers=headers
            )
            temp_token = resp.json().get("temp_token")
        csv_export = _get_csv_export(url, headers, temp_token)
        if csv_export:
            return Path(csv_export.name)


def start_csv_import_to_hyper(hyperfile_id: int, process: HyperProcess):
    db = SessionLocal()
    hyperfile = HyperFile.get(db, object_id=hyperfile_id)
    if hyperfile:
        hyperfile.file_status = schemas.FileStatusEnum.syncing.value
        db.commit()
        user = User.get(db, hyperfile.user)
        server = Server.get(db, user.server)
        try:
            export = get_csv_export(hyperfile, user, server, db)
            if export:
                handle_csv_import_to_hyperfile(
                    hyperfile=hyperfile, csv_path=export, process=process, db=db
                )
                hyperfile.last_updated = datetime.now()
                hyperfile.file_status = schemas.FileStatusEnum.file_available.value
            else:
                hyperfile.file_status = schemas.FileStatusEnum.file_unavailable.value
        except (CSVExportFailure, ConnectionRequestError, Exception) as err:
            sentry_sdk.capture_exception(err)
            hyperfile.file_status = schemas.FileStatusEnum.latest_sync_failed.value
        db.commit()
    db.close()


def create_or_get_hyperfile(
    db: Session, file_data: schemas.FileCreate, process: HyperProcess
):
    hyperfile = HyperFile.get_using_file_create(db, file_data)
    if hyperfile:
        return hyperfile, False

    headers = {"user-agent": f"{settings.app_name}/{settings.app_version}"}
    user = User.get(db, file_data.user)
    server = Server.get(db, user.server)
    bearer_token = get_access_token(user, server, db)
    headers.update({"Authorization": f"Bearer {bearer_token}"})

    url = f"{server.url}{ONADATA_FORMS_ENDPOINT}/{file_data.form_id}.json"
    resp = httpx.get(url, headers=headers)

    if resp.status_code == 200:
        resp = resp.json()
        if "public_key" in resp and resp.get("public_key"):
            raise UnsupportedForm("Encrypted forms are not supported")

        title = resp.get("title")
        file_data.filename = f"{title}.hyper"
        return HyperFile.create(db, file_data), True
    else:
        raise ConnectionRequestError(
            f"Currently unable to start connection to form. Aggregate status code: {resp.status_code}"
        )
