# Routes for the Tableau Configuration (/configurations) endpoint
from typing import List

from fastapi import Depends
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from fastapi.routing import APIRouter
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.api.deps import get_db
from app.libs.tableau.client import InvalidConfiguration, TableauClient
from app.models import Configuration, User
from app.utils.auth_utils import IsAuthenticatedUser

router = APIRouter()


@router.get(
    "/",
    status_code=200,
    response_model=List[schemas.ConfigurationListResponse],
)
def list_configurations(
    request: Request,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Lists out all the Tableau Configurations currently accessible for to the logged in user
    """
    resp = []
    configurations = Configuration.filter_using_user_id(db, user.id)

    for config in configurations:
        config = schemas.ConfigurationListResponse.from_orm(config)
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
    config_id: int,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific configuration
    """
    config = Configuration.get(db, config_id)

    if config and config.user == user.id:
        return config
    else:
        raise HTTPException(status_code=404, detail="Tableau configuration not found.")


@router.post(
    "/",
    status_code=201,
    response_model=schemas.ConfigurationResponse,
)
def create_configuration(
    config_data: schemas.ConfigurationCreateRequest,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Create a new Tableau Server Configuration that can be attached
    to a hyper file to define where the hyper file should be pushed to.
    """
    config_data = schemas.ConfigurationCreate(user=user.id, **config_data.dict())
    try:
        TableauClient.validate_configuration(config_data)
        config = Configuration.create(db, config_data)
        return config
    except (UniqueViolation, IntegrityError):
        raise HTTPException(status_code=400, detail="Configuration already exists")
    except InvalidConfiguration as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{config_id}",
    status_code=200,
    response_model=schemas.ConfigurationResponse,
)
def patch_configuration(
    config_id: int,
    config_data: schemas.ConfigurationPatchRequest,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Partially update a Configuration
    """
    config = Configuration.get(db, config_id)

    if config and config.user == user.id:
        try:
            for key, value in config_data.dict().items():
                if value:
                    if key == "token_value":
                        value = Configuration.encrypt_value(value)
                    setattr(config, key, value)
            TableauClient.validate_configuration(config)
            db.commit()
            db.refresh(config)
            return config
        except (UniqueViolation, IntegrityError):
            raise HTTPException(status_code=400, detail="Configuration already exists")
        except InvalidConfiguration as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(404, detail="Tableau Configuration not found.")


@router.delete("/{config_id}", status_code=204)
def delete_configuration(
    config_id: int,
    user: User = Depends(IsAuthenticatedUser()),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a configuration
    """
    config = Configuration.get(db, config_id)

    if config and config.user == user.id:
        Configuration.delete(db, config.id)
        db.commit()
    else:
        raise HTTPException(status_code=400)
