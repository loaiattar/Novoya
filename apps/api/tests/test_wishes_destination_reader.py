"""The destination reader and the static catalog are tested without a model: a fake
orchestrator scripts the answers."""

import asyncio
import time

import pytest

from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.wishes.application.ports.destination_reader import DestinationReading
from novoya_api.wishes.domain.wish import Destination
from novoya_api.wishes.infrastructure.llm.destination_reader import (
    LlmDestinationReader,
    NameMatchingReader,
)

LISBON = Destination("Portugal", "Lisbon")
PORTO = Destination("Portugal", "Porto")
MARRAKECH = Destination("Morocco", "Marrakech")
COVERED = [LISBON, PORTO, MARRAKECH]


class FakeOrchestrator:
    """Scripted answers: a string is the assistant's content, an exception is raised."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    async def converse(self, messages, tools=()):
        self.calls.append({"messages": list(messages), "tools": tools})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return [*messages, {"role": "assistant", "content": answer}]


async def read(text: str, *answers) -> DestinationReading:
    return await LlmDestinationReader(FakeOrchestrator(*answers)).read(text, COVERED)


# Model answers


async def test_answer_with_destination_and_suggestions_is_mapped():
    answer = (
        '{"destination": {"country": "Portugal", "city": "Lisbon"}, '
        '"suggestions": [{"country": "Portugal", "city": "Porto"}, '
        '{"country": "Morocco", "city": null}]}'
    )

    reading = await read("A week in Lisbon", answer)

    assert reading == DestinationReading(
        destination=LISBON, suggestions=[PORTO, Destination("Morocco", None)]
    )


async def test_answer_with_country_only_has_no_city():
    answer = '{"destination": {"country": "Spain", "city": null}, "suggestions": []}'

    reading = await read("Somewhere in Spain", answer)

    assert reading == DestinationReading(destination=Destination("Spain"), suggestions=[])


async def test_answer_without_destination_returns_none():
    answer = '{"destination": null, "suggestions": [{"country": "Portugal", "city": "Lisbon"}]}'

    reading = await read("Somewhere warm", answer)

    assert reading == DestinationReading(destination=None, suggestions=[LISBON])


async def test_prompt_contains_the_wish_text_and_every_covered_destination():
    orchestrator = FakeOrchestrator('{"destination": null, "suggestions": []}')

    await LlmDestinationReader(orchestrator).read("A quiet week by the sea", COVERED)

    prompt = "\n".join(str(m.get("content")) for m in orchestrator.calls[0]["messages"])
    assert "A quiet week by the sea" in prompt
    for name in ["Portugal", "Lisbon", "Porto", "Morocco", "Marrakech"]:
        assert name in prompt


# Fallback when the model fails


async def test_llm_error_falls_back_to_a_covered_city_in_the_text():
    reading = await read("A week in lisbon please", LLMError("every model failed"))

    assert reading == DestinationReading(destination=LISBON, suggestions=[])


async def test_fallback_matches_a_city_next_to_punctuation():
    reading = await read("Marrakech!", LLMError("every model failed"))

    assert reading == DestinationReading(destination=MARRAKECH, suggestions=[])


async def test_llm_error_falls_back_to_a_covered_country_in_the_text():
    reading = await read("Anywhere in MOROCCO", LLMError("every model failed"))

    assert reading == DestinationReading(destination=Destination("Morocco"), suggestions=[])


async def test_fallback_prefers_the_city_over_the_country():
    reading = await read("Portugal, ideally Porto", LLMError("every model failed"))

    assert reading == DestinationReading(destination=PORTO, suggestions=[])


async def test_llm_error_without_any_covered_name_returns_no_destination():
    reading = await read("Somewhere warm", LLMError("every model failed"))

    assert reading == DestinationReading(destination=None, suggestions=[])


async def test_fallback_matches_whole_words_only():
    reading = await read("A week in Portofino", LLMError("every model failed"))

    assert reading == DestinationReading(destination=None, suggestions=[])


async def test_answer_invalid_twice_falls_back_to_name_matching():
    reading = await read("A week in Porto", "not json", "still not json")

    assert reading == DestinationReading(destination=PORTO, suggestions=[])


@pytest.mark.parametrize(
    "country",
    ['""', '"   "', '"' + "x" * 101 + '"', '"<img src=x onerror=alert(1)>"', '"Call +1 555 0100"'],
    ids=["empty", "blank", "too_long", "markup", "digits"],
)
async def test_answer_with_an_invalid_place_name_falls_back(country):
    bad = '{"destination": {"country": ' + country + ', "city": null}, "suggestions": []}'

    reading = await read("A week in Porto", bad, bad)

    assert reading == DestinationReading(destination=PORTO, suggestions=[])


async def test_prompt_asks_for_the_catalog_spelling():
    orchestrator = FakeOrchestrator('{"destination": null, "suggestions": []}')

    await LlmDestinationReader(orchestrator).read("Marrakesh", COVERED)

    assert "exactly as written" in orchestrator.calls[0]["messages"][0]["content"]


async def test_name_matching_reader_finds_a_covered_name():
    reading = await NameMatchingReader().read("A riad in Marrakech", COVERED)

    assert reading == DestinationReading(destination=MARRAKECH, suggestions=[])


async def test_truncated_answer_falls_back_to_name_matching():
    reading = await read("A week in Porto", 'Sure: {"destination":', 'Sure: {"destination":')

    assert reading == DestinationReading(destination=PORTO, suggestions=[])


class SlowOrchestrator:
    """Each answer takes `delay` seconds and is invalid, so run_structured retries."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.calls = 0

    async def converse(self, messages, tools=()):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return [*messages, {"role": "assistant", "content": "not json"}]


async def test_one_deadline_covers_the_answer_and_its_retry():
    # Each answer fits the deadline, but the answer plus its retry do not.
    reader = LlmDestinationReader(SlowOrchestrator(delay=0.3), deadline_seconds=0.5)
    started = time.monotonic()

    reading = await reader.read("A week in Porto", COVERED)

    assert time.monotonic() - started < 0.55
    assert reading == DestinationReading(destination=PORTO, suggestions=[])


async def test_fallback_matches_a_country_named_in_french():
    chania = Destination("Greece", "Chania")
    reader = LlmDestinationReader(FakeOrchestrator(LLMError("every model failed")))

    reading = await reader.read("Une semaine en Grèce, au calme", [chania])

    assert reading == DestinationReading(destination=Destination("Greece"), suggestions=[])


async def test_name_matching_reader_finds_a_country_named_in_french():
    reading = await NameMatchingReader().read("Partir au Maroc en mai", COVERED)

    assert reading == DestinationReading(destination=Destination("Morocco"), suggestions=[])


@pytest.mark.parametrize(
    ("text", "country"),
    [
        ("Je rêve de visiter l'Italie en mai", "Italy"),
        ("Deux semaines d’Espagne, au soleil", "Spain"),
        ("Un tour de L’Italie", "Italy"),
    ],
)
async def test_a_french_country_after_an_elided_article_is_found(text, country):
    covered = [Destination("Italy", "Rome"), Destination("Spain", "Seville")]

    reading = await NameMatchingReader().read(text, covered)

    assert reading == DestinationReading(destination=Destination(country), suggestions=[])


async def test_cote_d_ivoire_is_still_found_whole():
    covered = [Destination("Ivory Coast", "Abidjan")]

    reading = await NameMatchingReader().read("Une semaine en Côte d’Ivoire", covered)

    assert reading == DestinationReading(destination=Destination("Ivory Coast"), suggestions=[])
