"""Shared kernel: the few things every module needs. It never imports a module.

- domain/: domain errors and common value objects (Money, DateRange, Destination, Locale)
- application/: ports used by every module (UnitOfWork)
- infrastructure/: database base and session, the OpenRouter LLM client
- presentation/: turning domain errors into HTTP responses
"""
