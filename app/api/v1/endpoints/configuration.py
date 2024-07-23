# Routes for the Tableau Configuration (/configurations) endpoint
from typing import List

from fastapi import Depends
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api.auth_deps import get_current_user
from app.api.deps import get_db, APIRouter
from app.models import User

router = APIRouter()


@router.get(
    "/",
    status_code=200,
    response_model=List[schemas.ConfigurationListResponse],
)
def list_configurations(
    user: User = Depends(get_current_user),
    *,
    request: Request,
):
    """
    Lists out all the Tableau Configurations currently accessible for to the logged in user
    """
    resp = []
    configurations = user.configurations

    for config in configurations:
        config = schemas.ConfigurationListResponse.model_validate(config)
        config.url = f"{request.base_url.scheme}://{request.base_url.netloc}"
        config.url += router.url_path_for("get_configuration", config_id=config.id)
        resp.append(config)
    return resp


@router.get(
    "/{config_id}",
    status_code=200,
    response_model=schemas.ConfigurationResponse,
)
def get_configuration(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    config_id: int,
):
    """
    Retrieve a specific configuration
    """
    config = crud.configuration.get(db, id=config_id)

    if config and config.user_id == user.id:
        return config
    else:
        raise HTTPException(status_code=404, detail="Configuration not found.")


@router.post(
    "/",
    status_code=201,
    response_model=schemas.ConfigurationResponse,
)
def create_configuration(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    config_data: schemas.ConfigurationCreateRequest,
):
    """
    Create a new Tableau Server Configuration that can be attached
    to a hyper file to define where the hyper file should be pushed to.
    """
    config_data = schemas.ConfigurationCreate(user_id=user.id, **config_data.dict())
    if not crud.configuration.validate(obj=config_data):
        raise HTTPException(status_code=400, detail="Invalid Configuration")

    try:
        config = crud.configuration.create(db, obj_in=config_data)
        return config
    except (UniqueViolation, IntegrityError):
        raise HTTPException(status_code=400, detail="Configuration already exists")


@router.patch(
    "/{config_id}",
    status_code=200,
    response_model=schemas.ConfigurationResponse,
)
def patch_configuration(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    config_id: int,
    config_data: schemas.ConfigurationPatchRequest,
):
    """
    Partially update a Configuration
    """
    config = crud.configuration.get(db, id=config_id)
    if config and config.user_id == user.id:
        crud.configuration.validate(obj=config_data)
        try:
            config = crud.configuration.update(db, db_obj=config, obj_in=config_data)
        except (UniqueViolation, IntegrityError):
            raise HTTPException(status_code=400, detail="Configuration already exists")
        else:
            return config
    raise HTTPException(status_code=404, detail="Configuration not found.")


@router.delete("/{config_id}", status_code=204)
def delete_configuration(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    *,
    config_id: int,
):
    """
    Permanently delete a configuration
    """
    config = crud.configuration.get(db, id=config_id)

    if config and config.user_id == user.id:
        crud.configuration.delete(db, id=config_id)
    else:
        raise HTTPException(status_code=404, detail="Configuration not found.")
