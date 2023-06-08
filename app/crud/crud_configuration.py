from sqlalchemy.orm import Session
from typing import Union
import tableauserverclient as TSC

from app.core.security import fernet_decrypt, fernet_encrypt
from app.crud.base import CRUDBase
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
            export_settings=obj_in.export_settings,
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

        if update_data["token_value"]:
            update_data["token_value"] = fernet_encrypt(update_data["token_value"])
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def validate(
        self,
        *,
        obj: Union[Configuration, ConfigurationCreate, ConfigurationPatchRequest]
    ):
        if isinstance(obj, Configuration):
            token = fernet_decrypt(obj.token_value)
        else:
            token = obj.token_value

        auth = TSC.PersonalAccessTokenAuth(
            token_name=obj.token_name,
            personal_access_token=token,
            site_id=obj.site_name,
        )
        try:
            server = TSC.Server(obj.server_address, use_server_version=True)
            server.auth.sign_in(auth)
        except Exception:
            return False
        else:
            return True


configuration = CRUDConfiguration(Configuration)
