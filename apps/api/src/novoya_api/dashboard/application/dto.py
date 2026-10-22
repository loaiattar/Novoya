from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RowCounts:
    """Rows clients may see, rows an admin hid, and rows that left the DÉTOUR export
    (inactive, not hidden). An offer counts with its partner, as in the client search.

    The same shape as catalog's RowCounts, kept apart on purpose: the dashboard's inner
    layers may not import another module, so the adapter copies one into the other."""

    active: int
    hidden: int
    inactive: int


@dataclass(frozen=True)
class CatalogStats:
    partners: RowCounts
    offers: RowCounts
    extras: RowCounts
    reviews_published: int
    reviews_hidden: int


@dataclass(frozen=True)
class AdminStats:
    """The admin home's numbers. users, plans and quotes are keyed by role or status, every
    one of them present, 0 when nobody or nothing has it."""

    catalog: CatalogStats
    users: Mapping[str, int]
    plans: Mapping[str, int]
    quotes: Mapping[str, int]
