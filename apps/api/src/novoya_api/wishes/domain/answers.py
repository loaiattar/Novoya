from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from novoya_api.wishes.domain.errors import InvalidAnswers
from novoya_api.wishes.domain.panel import Panel

# The budget is in euros (#27): quotes are in EUR, so the agent compares like with like.
CURRENCY = "EUR"
# The days of a trip, the first and the last included (TripRequest.trip_days): the plan
# writer numbers them up to 366.
MAX_TRIP_DAYS = 366
# The web app checks the departure against the client's own day, which can be the day before
# the server's (UTC) day, down to UTC-12.
START_TOLERANCE = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SelectedTag:
    """A tag the client clicked, stored as {"section": "style", "tag": "beach"}."""

    section: str
    tag: str


@dataclass(frozen=True, slots=True)
class Answers:
    """What the client chose on the panel: the tags, then budget, travellers and dates.

    No tags is a valid answer: the plan then starts from featured offers.

    The dates rule, the same as in the web app's constraints.ts: the departure is not in the
    past, the return is after it and the trip lasts 366 days at most, the first and the last
    day included. Only new answers are checked against the past and the length
    (check_dates): answers saved before these rules still load."""

    selected_tags: tuple[SelectedTag, ...]
    budget_max: Decimal
    currency: str
    persons: int
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.budget_max <= 0:
            raise InvalidAnswers("the budget must be more than 0")
        if self.currency != CURRENCY:
            raise InvalidAnswers(f"the budget must be in {CURRENCY}")
        if self.persons < 1:
            raise InvalidAnswers("at least 1 traveller is needed")
        if self.end_date <= self.start_date:
            raise InvalidAnswers("the end date must be after the start date")
        if len(set(self.selected_tags)) != len(self.selected_tags):
            raise InvalidAnswers("a tag is selected twice")

    def check_dates(self, today: date) -> None:
        """New answers: the departure is not in the past and the trip is not too long."""
        check_trip_dates(self.start_date, self.end_date, today)

    def check_against(self, panel: Panel) -> None:
        """Every tag must come from the panel shown, at most one in a single-choice section."""
        picked: defaultdict[str, int] = defaultdict(int)
        for selected in self.selected_tags:
            section = panel.section(selected.section)
            if section is None or selected.tag not in {tag.id for tag in section.tags}:
                raise InvalidAnswers(f"{selected.section}:{selected.tag} was not in the panel")
            picked[section.id] += 1
            if not section.multi and picked[section.id] > 1:
                raise InvalidAnswers(f"only one tag can be picked in {section.id}")


def check_trip_dates(start: date, end: date, today: date) -> None:
    """The dates of a new trip: the end after the start, the departure not in the past, at
    most MAX_TRIP_DAYS. The answer and the panel's fit check (#183) both use it, so the panel
    never says yes to dates the answer refuses.

    `today` is the server's day (UTC): one day earlier is still accepted, because it can be
    today for the client."""
    if end <= start:
        raise InvalidAnswers("the end date must be after the start date")
    if start < today - START_TOLERANCE:
        raise InvalidAnswers("the start date is in the past")
    if (end - start).days + 1 > MAX_TRIP_DAYS:
        raise InvalidAnswers(f"a trip lasts {MAX_TRIP_DAYS} days at most")
