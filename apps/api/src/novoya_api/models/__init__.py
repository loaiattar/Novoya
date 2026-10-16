"""ORM models. Import every model here so Alembic autogenerate sees it.

Put one model per file (user.py, partner.py, offer.py, wish.py, plan.py, quote.py)
and import each one here. Empty in M0; users arrives with #15.
"""

from novoya_api.db import Base

__all__ = ["Base"]
