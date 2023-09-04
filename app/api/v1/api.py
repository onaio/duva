from fastapi import APIRouter

from app.api.v1.endpoints import configuration, file, oauth, server

api_router = APIRouter()
api_router.include_router(
    configuration.router, prefix="/configurations", tags=["configuration"]
)
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(server.router, prefix="/servers", tags=["server"])
api_router.include_router(file.router, prefix="/files", tags=["file"])
