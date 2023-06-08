from fastapi import APIRouter

from app.api.v1.endpoints import configuration, file, oauth, server

api_router = APIRouter()
api_router.include_router(
    configuration.router, prefix="/configuration", tags=["configuration"]
)
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(server.router, prefix="/server", tags=["server"])
api_router.include_router(file.router, prefix="/file", tags=["file"])
