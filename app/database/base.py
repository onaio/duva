# Import all the models so that Base has them before being
# imported by Alembic
from app.models import Configuration, HyperFile, Server, User  # noqa

from .base_class import Base  # noqa
