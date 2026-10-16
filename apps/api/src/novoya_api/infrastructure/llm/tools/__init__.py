"""Travel tools the LLM can call (#20): covered_destinations() and
search_offers(destination, tags, persons, dates), with their JSON tool definitions.
They read the catalog through the OfferRepository port, not through SQL directly.
"""
