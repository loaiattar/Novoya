from dataclasses import dataclass

from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.wishes.application.ports.answers_in_progress import AnswersInProgress
from novoya_api.wishes.application.ports.planner import CustomRequest, Planner
from novoya_api.wishes.application.ports.wish_repository import WishRepository
from novoya_api.wishes.application.use_cases.answer_panel import (
    ANSWER_LIMIT,
    ANSWER_WINDOW,
    AnswerPanelCommand,
)
from novoya_api.wishes.domain.errors import WishNotFound
from novoya_api.wishes.domain.wish import Wish


@dataclass(frozen=True)
class SendCustomRequestResult:
    wish: Wish
    plan: CustomRequest


class SendCustomRequest:
    """Send the panel answers to the agency as they are, when no offer fits them (#184).

    The same rules as AnswerPanel, whose answers these are: only the owner, checked dates,
    one answer at a time (409 while another runs), the same limit per hour, and a wish is
    answered once, so a second send is an invalid transition (409) and never a second
    request. The answers, the custom plan and the planned wish are committed together; then
    the client gets the email that the agency has the trip (#168)."""

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

    async def __call__(self, cmd: AnswerPanelCommand) -> SendCustomRequestResult:
        cmd.answers.check_dates(self._clock.now().date())
        await self._rate_limiter.hit(f"wishes:answer:{cmd.user_id}", ANSWER_LIMIT, ANSWER_WINDOW)
        wish = await self._wishes.get(cmd.wish_id)
        if wish is None or wish.user_id != cmd.user_id:
            raise WishNotFound("no such wish")
        async with self._in_progress.hold(wish.id):
            # Read again: another answer may have planned it before this request held it.
            wish = await self._wishes.get(cmd.wish_id)
            assert wish is not None  # wishes are never deleted while their owner is signed in
            wish.answer(cmd.answers, self._clock.now())
            plan = await self._planner.request_custom(wish)
            wish.mark_planned(self._clock.now())
            await self._wishes.save(wish)
            await self._uow.commit()
        # After the commit: a failed email never undoes the request.
        await self._planner.confirm(plan.id, cmd.user_id)
        return SendCustomRequestResult(wish, plan)
