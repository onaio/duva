# Routes for the Hyperfile (/files) endpoint
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from datetime import datetime, timedelta
from typing import List, Optional, Union

from fastapi import BackgroundTasks, Depends, HTTPException, UploadFile, File, Request
from fastapi.routing import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from fastapi_cache import caches
from redis.client import Redis
from sqlalchemy.orm import Session
from tableauhyperapi.hyperprocess import HyperProcess

from app import schemas
from app.common_tags import HYPER_PROCESS_CACHE_KEY
from app.libs.s3.client import S3Client
from app.models import HyperFile, Configuration, User
from app.settings import settings
from app.utils.auth_utils import IsAuthenticatedUser
from app.utils.utils import get_db, get_redis_client
from app.utils.hyper_utils import handle_csv_import
from app.utils.onadata_utils import (
    ConnectionRequestError,
    DoesNotExist,
    UnsupportedForm,
    create_or_get_hyperfile,
    start_csv_import_to_hyper,
    schedule_hyper_file_cron_job,
    start_csv_import_to_hyper_job,
)


router = APIRouter()


def _create_hyper_file_response(
    hyper_file: HyperFile, db: Session, request: Request
) -> schemas.FileResponseBody:
    from app.main import app

    s3_client = S3Client()
    file_path = hyper_file.get_file_path(db)
    download_url = s3_client.generate_presigned_download_url(
        file_path, expiration=settings.download_url_lifetime
    )
    data = schemas.File.from_orm(hyper_file).dict()
    if download_url:
        expiry_date = datetime.utcnow() + timedelta(
            seconds=settings.download_url_lifetime
        )
        data.update(
            {
                "download_url": download_url,
                "download_url_valid_till": expiry_date.isoformat(),
            }
        )
    if hyper_file.configuration_id:
        config_url = f"{request.base_url.scheme}://{request.base_url.netloc}"
        config_url += app.url_path_for(
            "get_configuration", config_id=hyper_file.configuration_id
        )
        data.update({"configuration_url": config_url})
    response = schemas.FileResponseBody(**data)
    return response


@router.post("/api/v1/files", status_code=201, response_model=schemas.FileResponseBody)
def create_hyper_file(
    request: Request,
    file_request: schemas.FileRequestBody,
    background_tasks: BackgroundTasks,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Creates a Hyper file object.

    JSON Data Parameters:
      - `form_id`: An integer representing the ID of the form whose data should be exported
                   into a Hyperfile & tracked.
      - `sync_immediately`: An optional boolean field that determines whether a forms data should
                            be synced immediately after creation of a Hyper file object. _Note: Hyper files are updated
                            periodically on a schedule by default i.e 15 minutes after creation of object or every 24 hours_
      - `configuration_id`: An integer representing the ID of a Configuration(_See docs on /api/v1/configurations route_).
                            Determines where the hyper file is pushed to after it has been updated with the latest form data.
    """
    process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)
    configuration = None
    try:
        file_data = schemas.FileCreate(form_id=file_request.form_id, user=user.id)
        if file_request.configuration_id:
            configuration = Configuration.get(db, file_request.configuration_id)
            if not configuration or not configuration.user == user.id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tableau configuration with ID {file_request.configuration_id} not found",
                )
        file_instance, created = create_or_get_hyperfile(db, file_data, process)
    except (DoesNotExist, UnsupportedForm) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionRequestError as e:
        raise HTTPException(status_code=502, detail=str(e))
    else:
        if not created:
            raise HTTPException(status_code=400, detail="File already exists.")

        if configuration:
            file_instance.configuration_id = configuration.id

        if file_request.sync_immediately:
            background_tasks.add_task(
                start_csv_import_to_hyper, file_instance.id, process
            )
        background_tasks.add_task(
            schedule_hyper_file_cron_job,
            start_csv_import_to_hyper_job,
            file_instance.id,
        )
        file_instance.file_status = schemas.FileStatusEnum.queued.value
        db.commit()
        return _create_hyper_file_response(file_instance, db, request)


@router.get("/api/v1/files", response_model=List[schemas.FileListItem])
def list_hyper_files(
    request: Request,
    user: User = Depends(IsAuthenticatedUser()),
    form_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    This endpoint lists out all the hyper files currently owned by the
    logged in user.

    Query Parameters:
      - `form_id`: An integer representing an ID of a form on the users authenticated
                   server.
    """
    response = []
    hyperfiles = []
    if form_id:
        hyperfiles = HyperFile.filter(user, form_id, db)
    else:
        hyperfiles = user.files

    for hyperfile in hyperfiles:
        url = request.base_url.scheme + "://" + request.base_url.netloc
        url += router.url_path_for("get_hyper_file", file_id=hyperfile.id)
        response.append(
            schemas.FileListItem(
                url=url,
                id=hyperfile.id,
                form_id=hyperfile.form_id,
                filename=hyperfile.filename,
                file_status=hyperfile.file_status,
            )
        )
    return response


@router.get("/api/v1/files/{file_id}", response_model=schemas.FileResponseBody)
def get_hyper_file(
    file_id: Union[str, int],
    request: Request,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Retrieves a specific hyper file. _This endpoint supports both `.json` and `.hyper` response_

    The `.json` response provides the JSON representation of the hyper file object. While the `.hyper`
    response provides a FileResponse that contains the latest hyper file download.
    """
    response_type = None
    file_parts = file_id.split(".")
    if len(file_parts) == 2:
        file_id, response_type = file_parts

    try:
        file_id = int(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    hyperfile = HyperFile.get(db, file_id)

    if hyperfile and user.id == hyperfile.user:
        if not response_type or response_type == "json":
            return _create_hyper_file_response(hyperfile, db, request)
        elif response_type == "hyper":
            file_path = hyperfile.retrieve_latest_file(db)
            if os.path.exists(file_path):
                return FileResponse(file_path, filename=hyperfile.filename)
            else:
                raise HTTPException(
                    status_code=404, detail="File currently not available"
                )
        else:
            raise HTTPException(status_code=400, detail="Unsupported content type")
    else:
        raise HTTPException(status_code=404, detail="File not found")


@router.patch(
    "/api/v1/files/{file_id}", status_code=200, response_model=schemas.FileResponseBody
)
def patch_hyper_file(
    file_id: int,
    request: Request,
    data: schemas.FilePatchRequestBody,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Partially updates a specific hyper file object
    """
    hyper_file = HyperFile.get(db, file_id)

    if not hyper_file or hyper_file.user != user.id:
        raise HTTPException(status_code=404, detail="File not found")

    configuration = Configuration.get(db, data.configuration_id)
    if not configuration or not configuration.user == user.id:
        raise HTTPException(
            status_code=400,
            detail=f"Tableau configuration with ID {data.configuration_id} not found",
        )
    hyper_file.configuration_id = configuration.id
    db.commit()
    db.refresh(hyper_file)
    return _create_hyper_file_response(hyper_file, db, request)


@router.post("/api/v1/files/csv_import", status_code=200, response_class=FileResponse)
def import_data(id_string: str, csv_file: UploadFile = File(...)):
    """
    Experimental Endpoint: Creates and imports `csv_file` data into a hyper file.
    """
    process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)
    suffix = Path(csv_file.filename).suffix
    csv_file.file.seek(0)
    file_path = f"{settings.media_path}/{id_string}.hyper"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_upload:
        shutil.copyfileobj(csv_file.file, tmp_upload)
        tmp_upload.flush()
        handle_csv_import(
            file_path=file_path, csv_path=Path(tmp_upload.name), process=process
        )
    return FileResponse(file_path, filename=f"{id_string}.hyper")


@router.delete("/api/v1/files/{file_id}", status_code=204)
def delete_hyper_file(
    file_id: int,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a Hyper File Object
    """
    hyper_file = HyperFile.get(db, file_id)

    if hyper_file and hyper_file.user == user.id:
        # Delete file from S3
        s3_client = S3Client()
        if s3_client.delete(hyper_file.get_file_path(db)):
            # Delete Hyper File object from database
            HyperFile.delete(db, file_id)
            db.commit()
    else:
        raise HTTPException(status_code=400)


@router.post("/api/v1/files/{file_id}/sync")
def trigger_hyper_file_sync(
    request: Request,
    file_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(IsAuthenticatedUser()),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Trigger Hyper file sync; Starts a process that updates the
    hyper files data.
    """
    hyper_file = HyperFile.get(db, file_id)

    if not hyper_file:
        raise HTTPException(404, "File not found.")
    if hyper_file.user == user.id:
        status_code = 200
        if hyper_file.file_status not in [
            schemas.FileStatusEnum.queued,
            schemas.FileStatusEnum.syncing,
        ]:
            process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)
            background_tasks.add_task(start_csv_import_to_hyper, hyper_file.id, process)
        else:
            status_code = 202

        return JSONResponse(
            {"message": "File syncing is currently on-going"}, status_code=status_code
        )
    else:
        raise HTTPException(401)
