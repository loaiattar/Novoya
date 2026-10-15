"""ORM models. Import every model here so Alembic autogenerate sees it.

Empty in M0; the users table arrives with M1 (auth).
"""

from novoya_api.db import Base

__all__ = ["Base"]
