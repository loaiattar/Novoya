"""The advisors' public profiles (#167): the entity and the use cases, with fake ports."""

from datetime import timedelta

import pytest

from novoya_api.accounts.application.use_cases.advisor_profiles import (
    ListAdvisors,
    ListAgentAdvisors,
    UpdateAdvisorProfile,
    UpdateAdvisorProfileCommand,
)
from novoya_api.accounts.domain.advisor_profile import AdvisorProfile, AdvisorService
from novoya_api.accounts.domain.errors import (
    AdvisorConsentRequired,
    InvalidAdvisorProfile,
    NotAnAgent,
    UserNotFound,
)
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import UserStatus
from novoya_api.accounts.domain.value_objects import UserId
from tests.accounts.fakes import FrozenClock, InMemoryStore, make_user

ADMIN = UserId.new()


def edit(profile: AdvisorProfile, clock: FrozenClock, **fields: object) -> None:
    values: dict[str, object] = {
        "public_name": "Camille",
        "title": None,
        "summary": None,
        "services": [],
        "consent": True,
        "shown": True,
        "by": ADMIN,
        "now": clock.now(),
    }
    profile.edit(**{**values, **fields})  # type: ignore[arg-type]


def test_a_service_needs_one_language_at_least():
    assert AdvisorService.of("Grèce", None) == AdvisorService("Grèce", None)
    assert AdvisorService.of(None, " Greece ") == AdvisorService(None, "Greece")
    with pytest.raises(InvalidAdvisorProfile):
        AdvisorService.of(" ", None)
    with pytest.raises(InvalidAdvisorProfile):
        AdvisorService.of("x" * 41, None)


def test_a_profile_is_shown_only_with_the_agents_agreement():
    clock = FrozenClock()
    profile = AdvisorProfile.new(UserId.new(), clock.now())
    with pytest.raises(AdvisorConsentRequired):
        edit(profile, clock, consent=False, shown=True)
    assert not profile.shown

    edit(profile, clock)
    assert profile.shown
    assert (profile.consent_at, profile.consent_by) == (clock.now(), ADMIN)


def test_the_agreement_keeps_its_first_date_and_taking_it_back_hides_the_profile():
    clock = FrozenClock()
    profile = AdvisorProfile.new(UserId.new(), clock.now())
    edit(profile, clock)
    agreed_at = profile.consent_at

    clock.advance(timedelta(days=3))
    edit(profile, clock, summary="Toujours à la recherche de la prochaine pépite.")
    assert profile.consent_at == agreed_at
    assert profile.updated_at == clock.now()

    edit(profile, clock, consent=False, shown=False)
    assert (profile.consent_at, profile.consent_by, profile.shown) == (None, None, False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("public_name", " "),
        ("public_name", "x" * 101),
        ("title", "x" * 61),
        ("summary", "x" * 141),
        ("services", [AdvisorService("x", None)] * 7),
    ],
)
def test_a_profile_refuses_empty_or_too_long_fields(field, value):
    clock = FrozenClock()
    profile = AdvisorProfile.new(UserId.new(), clock.now())
    with pytest.raises(InvalidAdvisorProfile):
        edit(profile, clock, **{field: value})


def test_the_summary_fits_in_140_characters_and_blank_fields_become_none():
    clock = FrozenClock()
    profile = AdvisorProfile.new(UserId.new(), clock.now())
    edit(profile, clock, summary="x" * 140, title="  ")
    assert profile.summary == "x" * 140
    assert profile.title is None


async def agent(store: InMemoryStore, email: str = "agent@x.io", **fields: object) -> UserId:
    user = make_user(email, role=Role.AGENT, **fields)  # type: ignore[arg-type]
    await store.users.add(user)
    return user.id


def command(user_id: UserId, **fields: object) -> UpdateAdvisorProfileCommand:
    values: dict[str, object] = {
        "public_name": "Camille",
        "title": "Fondatrice et responsable",
        "summary": "Toujours à la recherche de la prochaine pépite.",
        "services": [("Grèce", "Greece"), ("Week-ends en amoureux", None)],
        "consent": True,
        "shown": True,
        "by": ADMIN,
    }
    return UpdateAdvisorProfileCommand(user_id=user_id, **{**values, **fields})  # type: ignore[arg-type]


async def test_an_admin_fills_in_an_agents_profile_and_the_home_page_lists_it():
    store = InMemoryStore()
    user_id = await agent(store)
    update = UpdateAdvisorProfile(store.users, store.advisor_profiles, store.uow, FrozenClock())

    view = await update(command(user_id))

    assert view.profile is not None
    assert view.profile.services == (
        AdvisorService("Grèce", "Greece"),
        AdvisorService("Week-ends en amoureux", None),
    )
    assert store.uow.commits == 1
    shown = await ListAdvisors(store.advisor_profiles)()
    assert [p.public_name for p in shown] == ["Camille"]


async def test_editing_again_keeps_the_same_profile():
    store = InMemoryStore()
    user_id = await agent(store)
    update = UpdateAdvisorProfile(store.users, store.advisor_profiles, store.uow, FrozenClock())
    first = await update(command(user_id))
    second = await update(command(user_id, public_name="Cam"))
    assert first.profile is not None and second.profile is not None
    assert second.profile.id == first.profile.id
    assert len(store.advisor_profiles.rows) == 1


async def test_only_an_agent_has_a_profile():
    store = InMemoryStore()
    client = make_user("client@x.io")
    await store.users.add(client)
    update = UpdateAdvisorProfile(store.users, store.advisor_profiles, store.uow, FrozenClock())
    with pytest.raises(NotAnAgent):
        await update(command(client.id))
    with pytest.raises(UserNotFound):
        await update(command(UserId.new()))
    assert store.uow.commits == 0


async def test_hidden_demoted_or_disabled_agents_are_not_listed():
    store = InMemoryStore()
    update = UpdateAdvisorProfile(store.users, store.advisor_profiles, store.uow, FrozenClock())
    hidden = await agent(store, "hidden@x.io")
    await update(command(hidden, public_name="Hidden", shown=False))
    demoted = await agent(store, "demoted@x.io")
    await update(command(demoted, public_name="Demoted"))
    store.users.rows[demoted].role = Role.CLIENT
    disabled = await agent(store, "disabled@x.io")
    await update(command(disabled, public_name="Disabled"))
    store.users.rows[disabled].status = UserStatus.DISABLED

    assert await ListAdvisors(store.advisor_profiles)() == []


async def test_the_back_office_lists_every_agent_with_or_without_a_profile():
    store = InMemoryStore()
    with_profile = await agent(store, "a@x.io")
    await agent(store, "b@x.io")
    await store.users.add(make_user("client@x.io"))
    update = UpdateAdvisorProfile(store.users, store.advisor_profiles, store.uow, FrozenClock())
    await update(command(with_profile))

    views = await ListAgentAdvisors(store.users, store.advisor_profiles)()

    profiles = {v.user.email.value: v.profile is not None for v in views}
    assert profiles == {"a@x.io": True, "b@x.io": False}
