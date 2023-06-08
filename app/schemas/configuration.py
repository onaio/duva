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
    id: int
    server_address: str
    site_name: str
    token_name: str
    project_name: str
    export_settings: ExportConfigurationSettings

    class Config:
        orm_mode = True


class ConfigurationListResponse(BaseModel):
    url: Optional[str]
    id: int
    site_name: str
    token_name: str
    project_name: str
    export_settings: ExportConfigurationSettings

    class Config:
        orm_mode = True


class ConfigurationCreateRequest(BaseModel):
    server_address: str
    site_name: str
    token_name: str
    project_name: str
    token_value: str
    export_settings: Optional[
        ExportConfigurationSettings
    ] = ExportConfigurationSettings()


class ConfigurationPatchRequest(BaseModel):
    server_address: Optional[str]
    site_name: Optional[str]
    token_name: Optional[str]
    project_name: Optional[str]
    token_value: Optional[str]
    export_settings: Optional[ExportConfigurationSettings]


class ConfigurationCreate(ConfigurationCreateRequest):
    user_id: int


class Configuration(ConfigurationCreate):
    id: int

    class Config:
        orm_mode = True