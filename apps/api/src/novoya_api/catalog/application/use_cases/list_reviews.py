from novoya_api.catalog.application.ports import ReviewRepository
from novoya_api.catalog.domain import Review

REVIEWS_LIMIT = 100


class ListReviews:
    """Published reviews, newest first. None for country or city means any."""

    def __init__(self, reviews: ReviewRepository) -> None:
        self._reviews = reviews

    async def __call__(self, country: str | None, city: str | None) -> list[Review]:
        return await self._reviews.list_at(country, city, REVIEWS_LIMIT)
