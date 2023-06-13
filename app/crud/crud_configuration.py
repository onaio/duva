from IPython.core.debugger import exception_colors
from sqlalchemy.orm import Session
from typing import Union

from app.core.security import fernet_decrypt, fernet_encrypt
from app.crud.base import CRUDBase
from app.libs.tableau.client import TableauClient
from app.models.configuration import Configuration
from app.schemas.configuration import ConfigurationCreate, ConfigurationPatchRequest


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
            export_settings=obj_in.export_settings.dict(exclude_unset=True),
        )
        db.add(configuration_obj)
        db.commit()
        db.refresh(configuration_obj)
        return configuration_obj

    def update(
        self, db: Session, *, db_obj: Configuration, obj_in: ConfigurationPatchRequest
    ) -> Configuration:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        if update_data.get("token_value"):
            update_data["token_value"] = fernet_encrypt(update_data["token_value"])
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def validate(
        self,
        *,
        obj: Union[Configuration, ConfigurationCreate, ConfigurationPatchRequest]
    ):
        try:
            TableauClient.validate_configuration(obj)
        except Exception:
            return False
        else:
            return True


configuration = CRUDConfiguration(Configuration)
