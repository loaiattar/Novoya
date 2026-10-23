"""GET /advisors and /admin/advisors (#167): real routes, fake storage."""

# The fixtures come from test_api.py: each test takes them as arguments.
# ruff: noqa: F811

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email
from tests.accounts.test_api import (  # noqa: F401  (fixtures)
    app,
    client,
    grant_role,
    mailer,
    new_client,
    sign_in,
    sign_up,
    store,
)

PROFILE = {
    "public_name": "Camille",
    "title": "Fondatrice et responsable",
    "summary": "Toujours à la recherche de la prochaine pépite.",
    "services": [{"fr": "Grèce", "en": "Greece"}, {"fr": "Week-ends en amoureux"}],
    "consent": True,
    "shown": True,
}


async def admin_and_agent(admin, agent, store, mailer) -> str:
    """Signs the admin in; returns the agent's account id."""
    await sign_up(admin, mailer, "admin@x.io")
    await sign_up(agent, mailer, "agent@x.io")
    await grant_role(store, "admin@x.io", Role.ADMIN)
    await grant_role(store, "agent@x.io", Role.AGENT)
    await sign_in(admin, "admin@x.io")
    agent_user = await store.users.get_by_email(Email("agent@x.io"))
    assert agent_user is not None
    return str(agent_user.id.value)


async def test_the_home_page_gets_public_fields_only(app, store, mailer):
    async with new_client(app) as admin, new_client(app) as agent, new_client(app) as visitor:
        agent_id = await admin_and_agent(admin, agent, store, mailer)
        assert (await visitor.get("/advisors")).json() == []

        response = await admin.put(f"/admin/advisors/{agent_id}", json=PROFILE)
        assert response.status_code == 200, response.text

        response = await visitor.get("/advisors")
        assert response.status_code == 200
        [advisor] = response.json()
        # Never an email, an account id, a role or the agreement: the exact keys.
        assert set(advisor) == {"id", "name", "title", "summary", "services"}
        assert advisor["id"] != agent_id
        assert advisor["name"] == "Camille"
        assert advisor["services"] == [
            {"fr": "Grèce", "en": "Greece"},
            {"fr": "Week-ends en amoureux", "en": None},
        ]
        assert "agent@x.io" not in response.text


async def test_the_admin_sees_every_agent_and_records_the_agreement(app, store, mailer):
    async with new_client(app) as admin, new_client(app) as agent:
        agent_id = await admin_and_agent(admin, agent, store, mailer)
        [row] = (await admin.get("/admin/advisors")).json()
        assert (row["user_id"], row["email"], row["profile"]) == (agent_id, "agent@x.io", None)

        await admin.put(f"/admin/advisors/{agent_id}", json=PROFILE)
        [row] = (await admin.get("/admin/advisors")).json()
        assert row["profile"]["consent"] is True
        assert row["profile"]["consent_at"] is not None
        assert row["profile"]["shown"] is True


async def test_an_agent_is_shown_only_once_they_agreed(app, store, mailer):
    async with new_client(app) as admin, new_client(app) as agent:
        agent_id = await admin_and_agent(admin, agent, store, mailer)
        response = await admin.put(
            f"/admin/advisors/{agent_id}", json={**PROFILE, "consent": False}
        )
        assert response.status_code == 409
        assert response.json()["code"] == "advisor_consent_required"


async def test_a_service_needs_french_or_english_and_the_summary_140_characters(app, store, mailer):
    async with new_client(app) as admin, new_client(app) as agent:
        agent_id = await admin_and_agent(admin, agent, store, mailer)
        for body in (
            {**PROFILE, "services": [{}]},
            {**PROFILE, "services": [{"fr": " ", "en": ""}]},
            {**PROFILE, "summary": "x" * 141},
            {**PROFILE, "services": [{"fr": "x"}] * 7},
            {**PROFILE, "email": "camille@x.io"},
        ):
            response = await admin.put(f"/admin/advisors/{agent_id}", json=body)
            assert response.status_code == 422, body


async def test_only_an_agent_gets_a_profile_and_only_an_admin_edits_it(app, store, mailer):
    async with new_client(app) as admin, new_client(app) as agent:
        agent_id = await admin_and_agent(admin, agent, store, mailer)
        await sign_in(agent, "agent@x.io")
        assert (await agent.get("/admin/advisors")).status_code == 403
        assert (await agent.put(f"/admin/advisors/{agent_id}", json=PROFILE)).status_code == 403

        admin_user = await store.users.get_by_email(Email("admin@x.io"))
        assert admin_user is not None
        response = await admin.put(f"/admin/advisors/{admin_user.id.value}", json=PROFILE)
        assert response.status_code == 409
        assert response.json()["code"] == "not_an_agent"
