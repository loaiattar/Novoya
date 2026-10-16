"""Domain layer: the heart of Novoya. Pure Python, no framework.

Entities, value objects and business rules (for example "a plan can only be quoted
when every item has a price"). This package imports nothing outside novoya_api.domain
and the standard library. tests/test_architecture.py enforces it.
"""
