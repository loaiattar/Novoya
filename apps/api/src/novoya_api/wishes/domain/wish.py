from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.errors import InvalidWish
from novoya_api.wishes.domain.panel import Panel


@dataclass(frozen=True, slots=True)
class Destination:
    country: str
    city: str | None = None


def find_covered(destination: Destination, covered: Sequence[Destination]) -> Destination | None:
    """The covered destination that matches, ignoring case. A destination without a city
    matches any covered city in its country; a covered entry without a city covers the whole
    country."""
    country = _key(destination.country)
    city = _key(destination.city) if destination.city else None
    for candidate in covered:
        if _key(candidate.country) != country:
            continue
        if city is None or candidate.city is None or _key(candidate.city) == city:
            return candidate
    return None


def _key(name: str) -> str:
    return name.strip().casefold()


class WishStatus(StrEnum):
    DRAFT = "draft"
    NOT_COVERED = "not_covered"
    PANEL_SHOWN = "panel_shown"
    ANSWERED = "answered"
    PLANNED = "planned"


@dataclass(slots=True)
class Wish:
    """What the client asks for, in their own words. A draft becomes not_covered or
    panel_shown once the destination is checked; a draft without a destination stays a
    draft so the client can say where. A panel_shown wish is answered once, then planned
    once its plan is built."""

    id: UUID
    user_id: UUID
    text: str
    status: WishStatus
    destination: Destination | None
    panel: Panel | None
    created_at: datetime
    updated_at: datetime
    answers: Answers | None = None

    @classmethod
    def create(cls, user_id: UUID, text: str, now: datetime) -> "Wish":
        text = text.strip()
        if not text:
            raise InvalidWish("the wish is empty")
        return cls(uuid4(), user_id, text, WishStatus.DRAFT, None, None, now, now)

    def mark_not_covered(self, destination: Destination, now: datetime) -> None:
        self._leave_draft(WishStatus.NOT_COVERED)
        self.destination = destination
        self.updated_at = now

    def show_panel(self, destination: Destination, panel: Panel, now: datetime) -> None:
        self._leave_draft(WishStatus.PANEL_SHOWN)
        self.destination = destination
        self.panel = panel
        self.updated_at = now

    def answer(self, answers: Answers, now: datetime) -> None:
        if self.status is not WishStatus.PANEL_SHOWN or self.panel is None:
            raise InvalidTransition(f"a {self.status} wish cannot be answered")
        answers.check_against(self.panel)
        self.status = WishStatus.ANSWERED
        self.answers = answers
        self.updated_at = now

    def remove_tag(self, section: str, tag: str, now: datetime) -> None:
        """The client withdraws one preference they picked (#165). This is not a new answer:
        the wish keeps its status, budget, travellers and dates, the plan already built stays
        as it is, and answer() still happens once. Only a wish with answers has tags to
        withdraw."""
        if self.answers is None or self.status not in (WishStatus.ANSWERED, WishStatus.PLANNED):
            raise InvalidTransition(f"a {self.status} wish has no answers to change")
        removed = SelectedTag(section, tag)
        self.answers = replace(
            self.answers,
            selected_tags=tuple(t for t in self.answers.selected_tags if t != removed),
        )
        self.updated_at = now

    def mark_planned(self, now: datetime) -> None:
        if self.status is not WishStatus.ANSWERED:
            raise InvalidTransition(f"a {self.status} wish cannot be planned")
        self.status = WishStatus.PLANNED
        self.updated_at = now

    def _leave_draft(self, status: WishStatus) -> None:
        if self.status is not WishStatus.DRAFT:
            raise InvalidTransition(f"a {self.status} wish cannot become {status}")
        self.status = status
