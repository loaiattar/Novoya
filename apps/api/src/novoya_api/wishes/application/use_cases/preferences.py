from collections.abc import Iterable, Set
from dataclasses import dataclass
from uuid import UUID

from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.wishes.application.ports.plan_statuses import PlanStatuses
from novoya_api.wishes.application.ports.wish_repository import WishRepository
from novoya_api.wishes.domain.errors import PreferenceLocked
from novoya_api.wishes.domain.wish import Wish


@dataclass(frozen=True)
class PreferenceTag:
    id: str
    label: str
    # At least one wish carrying it can still change: no plan of it is requested,
    # negotiating, quoted, accepted or rejected.
    removable: bool = True


@dataclass(frozen=True)
class PreferenceSection:
    """One panel section and the tags the client picked in it, across their wishes."""

    id: str
    title: str
    tags: tuple[PreferenceTag, ...]


def group_preferences(wishes: Iterable[Wish], locked: Set[UUID]) -> list[PreferenceSection]:
    """The tags picked on these wishes, grouped by section, each tag once. Sections and tags
    keep the order of the wishes (newest first); the titles and labels are the ones the
    panel showed. A tag is removable when a wish carrying it is not in `locked`."""
    titles: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    removable: set[tuple[str, str]] = set()
    for wish in wishes:
        if wish.answers is None:
            continue
        for selected in wish.answers.selected_tags:
            panel_section = wish.panel.section(selected.section) if wish.panel else None
            titles.setdefault(
                selected.section,
                panel_section.title if panel_section else _label(selected.section),
            )
            shown = panel_section.tags if panel_section else ()
            label = next((t.label for t in shown if t.id == selected.tag), None)
            labels.setdefault(selected.section, {}).setdefault(
                selected.tag, label or _label(selected.tag)
            )
            if wish.id not in locked:
                removable.add((selected.section, selected.tag))
    return [
        PreferenceSection(
            section,
            titles[section],
            tuple(
                PreferenceTag(tag, label, (section, tag) in removable)
                for tag, label in section_tags.items()
            ),
        )
        for section, section_tags in labels.items()
    ]


class ListPreferences:
    """The tags the client picked on the panels of their own wishes, grouped by section, and
    whether each can still be removed (see RemovePreference)."""

    def __init__(self, wishes: WishRepository, plans: PlanStatuses) -> None:
        self._wishes = wishes
        self._plans = plans

    async def __call__(self, user_id: UUID) -> list[PreferenceSection]:
        wishes = await self._wishes.list_for_user(user_id)
        answered = [wish.id for wish in wishes if wish.answers is not None]
        locked = await self._plans.locked_wish_ids(answered) if answered else set()
        return group_preferences(wishes, locked)


class RemovePreference:
    """Withdraw one preference from the client's wishes that can still change: answered or
    planned wishes with no plan requested, negotiating, quoted, accepted or rejected (only
    a proposed plan does not hold the tags). Those wishes keep their tags: the agency worked
    from them, and the plan page, the quote and staff screens read them.

    The wishes are read with a row lock (FOR UPDATE), so two removals at once wait for each
    other instead of one overwriting the other, and a quote request, which reads the wish FOR
    SHARE, cannot move a plan to requested between the status read and the commit. Other
    clients' wishes are never read. A tag the client does not have changes nothing; a tag
    only on locked wishes raises PreferenceLocked (409)."""

    def __init__(
        self, wishes: WishRepository, plans: PlanStatuses, uow: UnitOfWork, clock: Clock
    ) -> None:
        self._wishes = wishes
        self._plans = plans
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UUID, section: str, tag: str) -> None:
        carrying = [
            wish
            for wish in await self._wishes.list_for_user(user_id, lock=True)
            if wish.answers is not None
            and any(t.section == section and t.tag == tag for t in wish.answers.selected_tags)
        ]
        if not carrying:
            return
        locked = await self._plans.locked_wish_ids([wish.id for wish in carrying])
        changeable = [wish for wish in carrying if wish.id not in locked]
        if not changeable:
            raise PreferenceLocked("this preference is part of a trip sent to the agency")
        now = self._clock.now()
        for wish in changeable:
            wish.remove_tag(section, tag, now)
            await self._wishes.save(wish)
        await self._uow.commit()


def _label(identifier: str) -> str:
    text = identifier.replace("_", " ").replace("-", " ")
    return text[:1].upper() + text[1:]
