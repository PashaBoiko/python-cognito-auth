"""ORM model registry for the application.

Importing this package is sufficient to register all models on
``Base.metadata``, which is required before Alembic can introspect the
schema or before ``Base.metadata.create_all`` is called in tests.
"""

from app.models.role import Role
from app.models.user import User

__all__ = ["Role", "User"]
