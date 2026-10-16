"""Presentation layer: how the outside world talks to the use cases.

Today only HTTP (FastAPI). It translates requests into use case calls and results
into responses. It must not hold business rules.
"""
