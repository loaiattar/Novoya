"""AnswerQuote: the client accepts or rejects their quote, on fakes."""

from datetime import timedelta
from uuid import uuid4

import pytest

from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.quoting.application.use_cases.answer_quote import AnswerQuote
from novoya_api.quoting.domain.errors import QuoteAlreadyAnswered, QuoteExpired, QuoteNotFound
from novoya_api.quoting.domain.quote import QuoteStatus
from novoya_api.shared.domain.errors import PermissionDenied
from tests.quoting_fakes import (
    AGENT_ID,
    CLIENT_ID,
    NOW,
    OTHER_CLIENT,
    PLAN_ID,
    FakePlanQuoting,
    FakeQuotes,
    FakeUow,
    FixedClock,
    stored_quote,
)

QUOTE = stored_quote()


class Setup:
    def __init__(self, quote=QUOTE, now=NOW, answer_error: Exception | None = None) -> None:
        self.quotes = FakeQuotes(quote)
        self.plans = FakePlanQuoting(answer_error=answer_error)
        self.uow = FakeUow()
        self.answer = AnswerQuote(self.quotes, self.plans, self.uow, FixedClock(now))


@pytest.mark.parametrize(
    ("answer", "accepted"), [(QuoteStatus.ACCEPTED, True), (QuoteStatus.REJECTED, False)]
)
async def test_the_client_answers_and_the_plan_follows(answer, accepted):
    setup = Setup()

    await setup.answer(QUOTE.id, CLIENT_ID, False, answer, "Lovely")

    stored = setup.quotes.quotes[QUOTE.id]
    assert (stored.answer, stored.decided_at, stored.client_comment) == (answer, NOW, "Lovely")
    assert setup.plans.answers == [(PLAN_ID, accepted)]
    assert setup.uow.commits == 1


async def test_staff_cannot_answer_for_the_client():
    setup = Setup()

    with pytest.raises(PermissionDenied):
        await setup.answer(QUOTE.id, AGENT_ID, True, QuoteStatus.ACCEPTED, None)
    assert setup.uow.commits == 0


async def test_another_client_gets_not_found():
    with pytest.raises(QuoteNotFound):
        await Setup().answer(QUOTE.id, OTHER_CLIENT, False, QuoteStatus.ACCEPTED, None)


async def test_a_missing_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await Setup().answer(uuid4(), CLIENT_ID, False, QuoteStatus.ACCEPTED, None)


async def test_an_expired_quote_cannot_be_answered():
    setup = Setup(now=QUOTE.valid_until + timedelta(days=2))

    with pytest.raises(QuoteExpired):
        await setup.answer(QUOTE.id, CLIENT_ID, False, QuoteStatus.ACCEPTED, None)
    assert setup.plans.answers == []
    assert setup.uow.commits == 0


async def test_an_answered_quote_cannot_be_answered_again():
    setup = Setup(quote=stored_quote(QuoteStatus.REJECTED))
    quote_id = next(iter(setup.quotes.quotes))

    with pytest.raises(QuoteAlreadyAnswered):
        await setup.answer(quote_id, CLIENT_ID, False, QuoteStatus.ACCEPTED, None)
    assert setup.uow.commits == 0


async def test_nothing_is_committed_when_the_plan_refuses():
    setup = Setup(answer_error=PlanNotFound("no such plan"))

    with pytest.raises(PlanNotFound):
        await setup.answer(QUOTE.id, CLIENT_ID, False, QuoteStatus.ACCEPTED, None)
    assert setup.uow.commits == 0
