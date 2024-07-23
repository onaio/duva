from typing import Optional

from pydantic import BaseModel


class ExportConfigurationSettings(BaseModel):
    include_labels: Optional[bool] = True
    remove_group_name: Optional[bool] = True
    do_not_split_select_multiple: Optional[bool] = False
    include_reviews: Optional[bool] = False
    include_labels_only: Optional[bool] = True
    value_select_multiples: Optional[bool] = True
    show_choice_labels: Optional[bool] = True
    binary_select_multiples: Optional[bool] = True


class ConfigurationResponse(BaseModel):
    id: Optional[int] = None
    server_address: Optional[str] = None
    site_name: Optional[str] = None
    token_name: Optional[str] = None
    project_name: Optional[str] = None
    export_settings: Optional[ExportConfigurationSettings] = (
        ExportConfigurationSettings()
    )

    class Config:
        from_attributes = True


class ConfigurationListResponse(BaseModel):
    url: Optional[str] = None
    id: Optional[int] = None
    site_name: Optional[str] = None
    token_name: Optional[str] = None
    project_name: Optional[str] = None
    export_settings: Optional[ExportConfigurationSettings] = (
        ExportConfigurationSettings()
    )

    class Config:
        from_attributes = True


class ConfigurationCreateRequest(BaseModel):
    server_address: Optional[str] = None
    site_name: Optional[str] = None
    token_name: Optional[str] = None
    project_name: Optional[str] = None
    token_value: Optional[str] = None
    export_settings: Optional[ExportConfigurationSettings] = (
        ExportConfigurationSettings()
    )


class ConfigurationPatchRequest(BaseModel):
    server_address: Optional[str] = None
    site_name: Optional[str] = None
    token_name: Optional[str] = None
    project_name: Optional[str] = None
    token_value: Optional[str] = None
    export_settings: Optional[ExportConfigurationSettings] = None


class ConfigurationCreate(ConfigurationCreateRequest):
    user_id: Optional[int] = None


class Configuration(ConfigurationCreate):
    id: Optional[int] = None

    class Config:
        from_attributes = True
