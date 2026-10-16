"""What other modules may use from catalog. Nothing else in catalog may be imported.

Planned:
- covered_destinations() -> list of destinations with at least one active partner
- search_offers(destination, tags, persons, dates) -> list of OfferView
- tags_at(destination) -> the tags of the active offers there (for the panel)
- get_offers(ids) -> list of OfferView, only active ones (to check a plan)
OfferView carries partner name and contact; other modules decide who may see them.
"""
