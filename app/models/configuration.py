import json

from sqlalchemy import (JSON, Column, ForeignKey, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from app.database.base_class import Base


class Configuration(Base):
    __table_args__ = (
        UniqueConstraint(
            "server_address", "token_name", "user_id", name="_server_token_name_uc"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    server_address = Column(String)
    site_name = Column(String)
    token_name = Column(String)
    token_value = Column(String)
    project_name = Column(String)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))
    user = relationship("user", back_populates="configurations")
    export_settings = Column(
        JSON,
        nullable=False,
        server_default=json.dumps(
            {
                "include_labels": True,
                "remove_group_name": True,
                "do_not_split_select_multiple": False,
                "include_reviews": False,
                "include_labels_only": True,
                "value_select_multiples": True,
            }
        ),
    )
