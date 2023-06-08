from sqlalchemy.orm import Session

from app.core.security import fernet_encrypt
from app.crud.base import CRUDBase
from app.models.configuration import Configuration
from app.schemas.configuration import (ConfigurationCreate,
                                       ConfigurationPatchRequest)


class CRUDConfiguration(
    CRUDBase[Configuration, ConfigurationCreate, ConfigurationPatchRequest]
):
    def create(self, db: Session, *, obj_in: ConfigurationCreate) -> Configuration:
        configuration_obj = Configuration(
            server_address=obj_in.server_address,
            site_name=obj_in.site_name,
            token_name=obj_in.token_name,
            token_value=fernet_encrypt(obj_in.token_value),
            project_name=obj_in.project_name,
            user_id=obj_in.user_id,
            export_settings=obj_in.export_settings,
        )
        db.add(configuration_obj)
        db.commit()
        db.refresh(configuration_obj)
        return configuration_obj
