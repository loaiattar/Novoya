from novoya_api.catalog.application.ports import ReviewRepository
from novoya_api.catalog.domain import Review


class ListAllReviews:
    """Every review still imported, hidden ones too, so an admin can show one again."""

    def __init__(self, reviews: ReviewRepository) -> None:
        self._reviews = reviews

    async def __call__(self) -> list[Review]:
        return await self._reviews.list_all()
