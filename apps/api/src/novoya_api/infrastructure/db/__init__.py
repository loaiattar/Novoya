"""PostgreSQL with SQLAlchemy 2 (async).

- base.py: the declarative Base
- session.py: engine and session factory
- models/: ORM tables, one file per table, mapped to and from domain entities
- repositories/: the repository ports implemented with SQLAlchemy
- probe.py: DatabaseProbe implemented with SELECT 1
- seed/: partners and offers for local development (#17)
"""
