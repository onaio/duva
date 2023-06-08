# Utility functions for Ona Data Aggregate Servers
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

import httpx
from fastapi_cache import caches
from prometheus_client import Counter, Gauge
from redis import Redis
from redis.exceptions import LockError
from sqlalchemy.orm.session import Session
from tableauhyperapi import HyperProcess, Telemetry

from app import schemas
from app.common_tags import (
    HYPER_PROCESS_CACHE_KEY,
    HYPERFILE_SYNC_LOCK_PREFIX,
    JOB_ID_METADATA,
    ONADATA_FORMS_ENDPOINT,
    ONADATA_TOKEN_ENDPOINT,
)
from app.database.session import SessionLocal
from app.models import HyperFile, Server, User
from app.settings import settings
from app.utils.hyper_utils import (
    handle_csv_import_to_hyperfile,
    handle_hyper_file_job_completion,
    schedule_hyper_file_cron_job,
)

IN_PROGRESS_HYPER_IMPORT = Gauge(
    "in_progress_hyper_import",
    "Number of Import processes currently running for Tableau Hyper databases",
)
SUCCESSFUL_IMPORTS = Counter(
    "successful_hyper_database_imports",
    "Number of successfull imports to a hyper database",
)
FAILED_IMPORTS = Counter(
    "failed_hyper_database_imports", "Number of failed imports to a hyper database"
)


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


def write_export_to_temp_file(export_url, client, retry: int = 0):
    print("Writing to temporary CSV Export to temporary file.")
    retry = 0 or retry
    status = 0
    with NamedTemporaryFile(delete=False, suffix=".csv") as export:
        with client.stream("GET", export_url) as response:
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


def _get_csv_export(
    url: str, client, retries: int = 0, sleep_when_in_progress: bool = True
):
    print("Checking on export status.")
    resp = client.get(url)

    if resp.status_code == 202:
        resp = resp.json()
        job_status = resp.get("job_status")
        if "export_url" in resp and job_status == "SUCCESS":
            export_url = resp.get("export_url")
            return write_export_to_temp_file(export_url, client)
        elif job_status == "FAILURE":
            reason = resp.get("progress")
            raise CSVExportFailure(f"CSV Export Failure. Reason: {reason}")

        job_uuid = resp.get("job_uuid")
        if job_uuid:
            print(f"Waiting for CSV Export to be ready. Job UUID: {job_uuid}")
            url += f"&job_uuid={job_uuid}"

        if retries < 3:
            if sleep_when_in_progress:
                time.sleep(30 * (retries + 1))
            return _get_csv_export(
                url,
                client,
                retries=retries + 1,
                sleep_when_in_progress=sleep_when_in_progress,
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
    hyperfile: HyperFile,
    user: schemas.User,
    server: schemas.Server,
    db: SessionLocal,
) -> str:
    """
    Retrieves a CSV Export for an XForm linked to a Hyperfile
    """
    bearer_token = get_access_token(user, server, db)
    headers = {
        "user-agent": f"{settings.app_name}/{settings.app_version}",
        "Authorization": f"Bearer {bearer_token}",
    }
    with httpx.Client(headers=headers) as client:
        form_url = f"{server.url}{ONADATA_FORMS_ENDPOINT}/{hyperfile.form_id}"
        resp = client.get(form_url + ".json")
        if resp.status_code == 200:
            url = f"{form_url}/export_async.json?format=csv"
            if hyperfile.configuration:
                export_settings = schemas.ExportConfigurationSettings(
                    **hyperfile.configuration.export_settings
                ).dict()

                for key, value in export_settings.items():
                    url += f"&{key}={value}"

            csv_export = _get_csv_export(url, client)
            if csv_export:
                return Path(csv_export.name)


@IN_PROGRESS_HYPER_IMPORT.track_inprogress()
def start_csv_import_to_hyper(
    hyperfile_id: int,
    process: HyperProcess,
    schedule_cron: bool = True,
):
    """
    Starts a CSV Export importation process that imports CSV Data into
    a Tableau hyper database.

    params:
    hyperfile_id :: int : A unique identifier for a HyperFile object
    schedule_cron :: bool : Whether to schedule a cron job that triggers a CSV Import
                            periodically.
    """
    db = SessionLocal()
    redis_client = Redis(
        host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
    )
    hyperfile: HyperFile = HyperFile.get(db, object_id=hyperfile_id)
    user = User.get(db, hyperfile.user)
    job_status = schemas.FileStatusEnum.latest_sync_failed.value
    err = None

    if hyperfile and user and user.server:
        try:
            with redis_client.lock(f"{HYPERFILE_SYNC_LOCK_PREFIX}{hyperfile.id}"):
                server = user.server
                hyperfile.file_status = schemas.FileStatusEnum.syncing.value
                db.commit()
                db.refresh(hyperfile)

                try:
                    export = get_csv_export(
                        hyperfile,
                        user,
                        server,
                        db,
                    )

                    if export:
                        handle_csv_import_to_hyperfile(hyperfile, export, process, db)
                        job_status = schemas.FileStatusEnum.file_available.value

                        if schedule_cron and not hyperfile.meta_data.get(
                            JOB_ID_METADATA
                        ):
                            schedule_hyper_file_cron_job(
                                start_csv_import_to_hyper_job, hyperfile_id
                            )
                    else:
                        job_status = schemas.FileStatusEnum.file_unavailable.value
                except (CSVExportFailure, ConnectionRequestError, Exception) as exc:
                    err = str(exc)
                    job_status = schemas.FileStatusEnum.latest_sync_failed.value

            successful_import = (
                job_status == schemas.FileStatusEnum.file_available.value
            )
            if successful_import:
                SUCCESSFUL_IMPORTS.inc()
            else:
                FAILED_IMPORTS.inc()

            handle_hyper_file_job_completion(
                hyperfile.id,
                db,
                job_succeeded=successful_import,
                object_updated=successful_import,
                file_status=job_status,
                failure_reason=err,
            )
            db.close()
            return successful_import
        except LockError:
            pass


def start_csv_import_to_hyper_job(hyperfile_id: int, schedule_cron: bool = False):
    if not caches.get(HYPER_PROCESS_CACHE_KEY):
        caches.set(
            HYPER_PROCESS_CACHE_KEY,
            HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU),
        )
    process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)
    start_csv_import_to_hyper(hyperfile_id, process, schedule_cron=schedule_cron)


def create_or_get_hyperfile(
    db: Session, file_data: schemas.FileCreate, process: HyperProcess
):
    hyperfile = HyperFile.get_using_file_create(db, file_data)
    if hyperfile:
        return hyperfile, False

    headers = {"user-agent": f"{settings.app_name}/{settings.app_version}"}
    user = User.get(db, file_data.user)
    server = user.server
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


def schedule_all_active_forms(db: Session = SessionLocal(), close_db: bool = False):
    """
    Schedule CSV Import Jobs for all active Hyper Files
    """
    for hf in HyperFile.get_active_files(db):
        schedule_hyper_file_cron_job(start_csv_import_to_hyper_job, hf.id)

    if close_db:
        db.close()
