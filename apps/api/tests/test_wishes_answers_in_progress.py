"""The in-memory guard that lets one request at a time answer a wish."""

import pytest

from novoya_api.wishes.domain.errors import AnswerInProgress
from novoya_api.wishes.infrastructure.answers_in_progress import InMemoryAnswersInProgress
from tests.test_wishes_answer_panel import shown_wish


async def test_a_held_wish_cannot_be_held_twice_and_is_free_again_after():
    guard = InMemoryAnswersInProgress()
    wish_id = shown_wish().id

    async with guard.hold(wish_id):
        with pytest.raises(AnswerInProgress):
            async with guard.hold(wish_id):
                pass

    async with guard.hold(wish_id):
        pass


async def test_the_wish_is_free_again_after_an_error():
    guard = InMemoryAnswersInProgress()
    wish_id = shown_wish().id

    with pytest.raises(RuntimeError):
        async with guard.hold(wish_id):
            raise RuntimeError("planning failed")

    async with guard.hold(wish_id):
        pass


async def test_other_wishes_are_not_blocked():
    guard = InMemoryAnswersInProgress()

    async with guard.hold(shown_wish().id):
        async with guard.hold(shown_wish().id):
            pass
