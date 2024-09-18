from typing import List, Optional
from urllib.parse import urljoin

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api.auth_deps import get_current_user
from app.api.deps import get_db, APIRouter
from app.core.importer import import_to_hyper, schedule_import_to_hyper_job
from app.models.configuration import Configuration
from app.models.hyperfile import HyperFile
from app.models.user import User

router = APIRouter()


def inject_urls(
    resp: schemas.FileResponseBody, request: Request, file: HyperFile
) -> schemas.FileResponseBody:
    from app.api.v1.api import api_router

    url = f"{request.base_url.scheme}://{request.base_url.netloc}"
    configuration_url = urljoin(
        url,
        api_router.url_path_for("get_configuration", config_id=file.configuration_id),
    )
    download_url, download_url_expires = crud.hyperfile.get_download_links(obj=file)
    resp.configuration_url = configuration_url
    resp.download_url = download_url
    resp.download_url_valid_till = download_url_expires
    return resp


@router.get("/", response_model=List[schemas.FileListItem])
def list_files(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    form_id: Optional[str] = None,
    request: Request,
):
    """
    Lists out all the Hyper Files currently accessible to the logged in user

    If a form_id is provided, only files associated with that form will be returned
    """
    response = []
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    if form_id:
        files = crud.hyperfile.get_using_form(db=db, form_id=form_id, user_id=user.id)
    else:
        files = user.hyper_files

    for file in files:
        if file.user_id == user.id:
            url = f"{request.base_url.scheme}://{request.base_url.netloc}"
            url += router.url_path_for("get_file", file_id=file.id)
            entry = schemas.FileListItem.model_validate(file)
            entry.url = url
            entry.download_url = url + "?file_format=hyper"
            response.append(entry)
    return response


@router.get("/{file_id}", response_model=schemas.FileResponseBody)
def get_file(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    file_id: int,
    request: Request,
    file_format: Optional[str] = None,
):
    """
    Retrieve a specific Hyper File
    """
    file = crud.hyperfile.get(db=db, id=file_id)

    if file and file.user_id == user.id:
        response = inject_urls(
            schemas.FileResponseBody.model_validate(file), request, file
        )
        if file_format == "hyper":
            return RedirectResponse(response.download_url)

        return response
    else:
        raise HTTPException(status_code=404, detail="File not found.")


@router.patch("/{file_id}", response_model=schemas.FileResponseBody)
def update_file(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    file_id: int,
    request: Request,
    body: schemas.FilePatchRequestBody,
):
    """
    Update a specific Hyper File
    """
    file = crud.hyperfile.get(db=db, id=file_id)
    if body.configuration_id:
        configuration: Optional[Configuration] = crud.configuration.get(
            db, id=body.configuration_id
        )
        if not configuration or not configuration.user_id == user.id:
            raise HTTPException(
                status_code=400, detail="Configuration not found with given ID"
            )

    if file and file.user_id == user.id:
        file = crud.hyperfile.update(db=db, db_obj=file, obj_in=body)
        return inject_urls(schemas.FileResponseBody.model_validate(file), request, file)
    else:
        raise HTTPException(status_code=404, detail="File not found.")


@router.delete("/{file_id}", status_code=204)
def delete_file(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    file_id: int,
):
    """
    Delete a specific Hyper File
    """
    file = crud.hyperfile.get(db=db, id=file_id)
    if file and file.user_id == user.id:
        crud.hyperfile.delete(db=db, id=file_id)
    else:
        raise HTTPException(status_code=404, detail="File not found.")


@router.post("/{file_id}/sync")
def sync_file(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    background_tasks: BackgroundTasks,
    file_id: int,
):
    """
    Trigger a sync task for a specific Hyper File
    """
    hyper_file = crud.hyperfile.get(db=db, id=file_id)

    if not hyper_file:
        raise HTTPException(404, "File not found.")

    if hyper_file.configuration and not crud.configuration.validate(
        obj=hyper_file.configuration
    ):
        raise HTTPException(
            400,
            detail=f"Invalid configuration ID {hyper_file.configuration.id}",
        )

    if hyper_file.user_id == user.id:
        status_code = 200
        if hyper_file.file_status not in [
            schemas.FileStatusEnum.queued,
            schemas.FileStatusEnum.syncing,
        ]:
            background_tasks.add_task(import_to_hyper, hyper_file.id, False)
        else:
            status_code = 202

        return JSONResponse(
            {"message": "File syncing is currently on-going"}, status_code=status_code
        )
    else:
        raise HTTPException(401)


# TODO Add import route
# @router.post("/csv_import", status_code=200, response_class=FileResponse)
# def import_data(id_string: str, csv_file: UploadFile = File(...)):
#     """
#     Experimental Endpoint: Creates and imports `csv_file` data into a hyper file.
#     """
#     process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)
#     suffix = Path(csv_file.filename).suffix
#     csv_file.file.seek(0)
#     file_path = f"{settings.media_path}/{id_string}.hyper"
#     with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_upload:
#         shutil.copyfileobj(csv_file.file, tmp_upload)
#         tmp_upload.flush()
#         handle_csv_import(
#             file_path=file_path, csv_path=Path(tmp_upload.name), process=process
#         )
#     return FileResponse(file_path, filename=f"{id_string}.hyper")


@router.post("/", status_code=201, response_model=schemas.FileResponseBody)
def create_file(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    background_tasks: BackgroundTasks,
    request: Request,
    body: schemas.FileRequestBody,
):
    """
    Create a new HyperFile

    JSON Data Parameters:
      - `form_id`: An integer representing the ID of the form whose data should be exported
                   into a Hyperfile & tracked.
      - `sync_immediately`: An optional boolean field that determines whether a forms data should
                            be synced immediately after creation of a Hyper file object. _Note: Hyper files are updated
                            periodically on a schedule by default i.e 15 minutes after creation of object or every 24 hours_
      - `configuration_id`: An integer representing the ID of a Configuration(_See docs on /configurations route_).
                            Determines where the hyper file is pushed to after it has been updated with the latest form data.
    """
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    create_data = schemas.FileCreate(form_id=body.form_id, user_id=user.id)
    if body.configuration_id:
        configuration: Optional[Configuration] = crud.configuration.get(
            db, id=body.configuration_id
        )
        if not configuration or not configuration.user_id == user.id:
            raise HTTPException(
                status_code=400, detail="Configuration not found with given ID"
            )
        create_data.configuration_id = body.configuration_id

    try:
        hfile = crud.hyperfile.create(db=db, obj_in=create_data, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.sync_immediately:
        background_tasks.add_task(import_to_hyper, hfile.id, False)
    schedule_import_to_hyper_job(db, hfile)
    return inject_urls(schemas.FileResponseBody.model_validate(hfile), request, hfile)
