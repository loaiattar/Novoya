from dataclasses import dataclass, replace
from uuid import UUID

from novoya_api.catalog.application.ports import ReviewRepository
from novoya_api.catalog.domain import Review, ReviewNotFound
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class UpdateReviewCommand:
    review_id: UUID
    hidden: bool


class UpdateReview:
    """Hide a published review from clients, or show it again. DÉTOUR owns the rest
    (ADR 0014); the import never changes hidden, and still deletes a review that left
    avis_diffusables."""

    def __init__(self, reviews: ReviewRepository, uow: UnitOfWork) -> None:
        self._reviews = reviews
        self._uow = uow

    async def __call__(self, cmd: UpdateReviewCommand) -> Review:
        review = await self._reviews.get(cmd.review_id)
        if review is None:
            raise ReviewNotFound("no such review")
        updated = replace(review, hidden=cmd.hidden)
        await self._reviews.save(updated)
        await self._uow.commit()
        return updated
