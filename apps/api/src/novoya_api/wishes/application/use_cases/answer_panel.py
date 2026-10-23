from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.wishes.application.ports.answers_in_progress import AnswersInProgress
from novoya_api.wishes.application.ports.planner import Planner, ProposedPlan
from novoya_api.wishes.application.ports.wish_repository import WishRepository
from novoya_api.wishes.domain.answers import Answers
from novoya_api.wishes.domain.errors import WishNotFound
from novoya_api.wishes.domain.wish import Wish

# Each answer runs the planner's model; free models share their quota between all clients.
ANSWER_LIMIT = 20
ANSWER_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class AnswerPanelCommand:
    user_id: UUID
    wish_id: UUID
    answers: Answers


@dataclass(frozen=True)
class AnswerPanelResult:
    wish: Wish
    plan: ProposedPlan


class AnswerPanel:
    """Save the client's panel answers on their wish and build its proposed plan.

    Only the owner can answer; another user's wish is reported as not found, so its
    existence does not leak. The answers, the plan and the planned wish are committed
    together: when no offer fits, nothing is saved and the client can change the dates or
    the travellers and send again. While a plan is built, another answer to the same wish
    is turned away (409) before it starts a model run. A departure in the past or a trip
    too long is refused before anything else runs (Answers.check_dates). Each client sends
    at most ANSWER_LIMIT answers per ANSWER_WINDOW."""

    def __init__(
        self,
        wishes: WishRepository,
        planner: Planner,
        in_progress: AnswersInProgress,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._wishes = wishes
        self._planner = planner
        self._in_progress = in_progress
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock

    async def __call__(self, cmd: AnswerPanelCommand) -> AnswerPanelResult:
        cmd.answers.check_dates(self._clock.now().date())
        await self._rate_limiter.hit(f"wishes:answer:{cmd.user_id}", ANSWER_LIMIT, ANSWER_WINDOW)
        wish = await self._wishes.get(cmd.wish_id)
        if wish is None or wish.user_id != cmd.user_id:
            raise WishNotFound("no such wish")
        # After the owner check: another user's wish is never reported as busy.
        async with self._in_progress.hold(wish.id):
            # Read again: another answer may have planned it before this request held it.
            wish = await self._wishes.get(cmd.wish_id)
            assert wish is not None  # wishes are never deleted while their owner is signed in
            wish.answer(cmd.answers, self._clock.now())
            plan = await self._planner.propose(wish)
            wish.mark_planned(self._clock.now())
            await self._wishes.save(wish)
            await self._uow.commit()
        return AnswerPanelResult(wish, plan)
