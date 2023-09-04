# Routes for the Server (/server) endpoint
from typing import List
from urllib.parse import urljoin

from fastapi import Depends, HTTPException
from starlette.datastructures import URL

from app import crud, schemas
from app.api.deps import get_db, APIRouter

router = APIRouter()


@router.post("/", response_model=schemas.ServerResponse, status_code=201)
def create_server_object(server: schemas.ServerCreate, db=Depends(get_db)):
    """
    Create new Server configuration objects.

    Server configuration objects are used to authorize the
    Duva Application against an OnaData server; Users authorize
    against a server configuration.

    After creation of a server object, users & 3rd party applications
    can utilize the OAuth login route with the server url as the `server_url` query param to authorize users and enable the application to pull & sync forms that the user has access to.
    """
    url = URL(server.url)
    if not url.scheme or not url.netloc:
        raise HTTPException(status_code=400, detail=f"Invalid url {server.url}")
    server.url = urljoin(f"{url.scheme}://{url.netloc}", url.path)
    if crud.server.get_using_url(db, url=server.url):
        raise HTTPException(
            status_code=400, detail=f"Server {server.url} already configured."
        )
    server = crud.server.create(db, obj_in=server)
    return server


@router.get(
    "/{obj_id}",
    response_model=schemas.ServerResponse,
)
def retrieve_server(obj_id: int, db=Depends(get_db)):
    """
    Retrieve a specific server configuration
    """
    server = crud.server.get(db, obj_id)
    if not server:
        raise HTTPException(
            status_code=404,
            detail=f"Server configuration with ID {obj_id} can not be found.",
        )
    return server


@router.get("/", response_model=List[schemas.ServerResponse])
def list_servers(db=Depends(get_db), *, skip: int = 0, limit: int = 100):
    """
    List all servers configured to work with the application that users can authorize against.
    """
    servers = crud.server.get_multi(db, skip=skip, limit=limit)
    return servers
