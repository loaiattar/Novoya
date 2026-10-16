"""Application layer: the use cases, one per thing a user can do.

Use cases orchestrate entities and talk to the outside world only through ports
(interfaces in application/ports). They import the domain, never infrastructure,
presentation, FastAPI, SQLAlchemy or an SDK. tests/test_architecture.py enforces it.
"""
