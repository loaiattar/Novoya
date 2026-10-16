"""ORM models. Import every model here so Alembic autogenerate sees it.

One file per table: user.py, partner.py, offer.py, wish.py, plan.py, quote.py.
They are persistence details: repositories map them to domain entities, so the
rest of the code never sees a SQLAlchemy object. Empty in M0; users arrives with #15.
"""

from novoya_api.infrastructure.db.base import Base

__all__ = ["Base"]
