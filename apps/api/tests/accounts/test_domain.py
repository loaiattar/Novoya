"""Domain rules of the accounts module: plain Python, no I/O."""

from datetime import timedelta

import pytest

from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.errors import (
    CannotChangeAdminStatus,
    CannotChangeOwnRole,
    CannotChangeOwnStatus,
    EmailNotVerified,
    InvalidEmail,
    InvalidOrExpiredToken,
    WeakPassword,
)
from novoya_api.accounts.domain.one_time_token import OneTimeToken, TokenPurpose
from novoya_api.accounts.domain.policies import PasswordPolicy
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User, UserStatus
from novoya_api.accounts.domain.value_objects import Email, PlainPassword, UserId
from novoya_api.shared.domain.value_objects import Locale
from tests.accounts.fakes import FrozenClock, make_user

NOW = FrozenClock().now()


def test_email_is_trimmed_and_lowercased():
    assert Email("  Alice@Example.COM ").value == "alice@example.com"


@pytest.mark.parametrize("value", ["", "alice", "alice@", "@example.com", "a b@example.com"])
def test_invalid_emails_are_refused(value):
    with pytest.raises(InvalidEmail):
        Email(value)


@pytest.mark.parametrize(
    ("hint", "locale"),
    [("fr-FR,fr;q=0.9", Locale.FR), ("fr", Locale.FR), ("en-US", Locale.EN), ("de", Locale.EN)],
)
def test_locale_comes_from_the_language_hint(hint, locale):
    assert Locale.from_hint(hint) is locale


def test_locale_defaults_to_english():
    assert Locale.from_hint(None) is Locale.EN


@pytest.mark.parametrize(
    "password",
    ["short", "password1234", "my-alice-password-2026", "x" * 129],
)
def test_weak_passwords_are_refused(password):
    with pytest.raises(WeakPassword):
        PasswordPolicy().validate(PlainPassword(password), Email("alice@example.com"))


def test_a_long_unique_password_is_accepted():
    PasswordPolicy().validate(PlainPassword("correct horse battery"), Email("alice@example.com"))


def test_a_new_user_is_a_client():
    assert make_user().role is Role.CLIENT


def test_a_user_changes_their_language():
    user = make_user()
    user.change_locale(Locale.FR)
    assert user.locale is Locale.FR


def test_register_keeps_trimmed_names_and_composes_the_display_name():
    user = User.register(Email("alice@example.com"), " Alice ", " Martin ", Locale.EN, NOW)
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    assert user.name == "Alice Martin"


def test_register_clips_a_display_name_that_would_not_fit():
    first, last = "A" * 100, "B" * 100
    user = User.register(Email("alice@example.com"), first, last, Locale.EN, NOW)
    assert user.first_name == first
    assert user.last_name == last
    assert user.name == (first + " " + last)[:200]
    assert len(user.name) == 200


def test_fill_in_from_provider_does_not_overwrite_a_name_chosen_at_sign_up():
    user = make_user()
    user.fill_in_from_provider(first_name="A.", last_name="M.", name="A. M.")
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    assert user.name == "Alice Martin"


def test_fill_in_from_provider_fills_empty_names():
    user = User.register(Email("alice@example.com"), None, None, Locale.EN, NOW)
    user.fill_in_from_provider(first_name=" Alice ", last_name=" Martin ", name="Alice Martin")
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    assert user.name == "Alice Martin"


def test_fill_in_from_provider_derives_names_from_an_existing_display_name():
    user = User.register(Email("alice@example.com"), None, None, Locale.EN, NOW)
    user.name = "Ali B."
    user.fill_in_from_provider(first_name="Alice", last_name="Martin", name="Alice Martin")
    assert user.first_name == "Ali"
    assert user.last_name == "B."
    assert user.name == "Ali B."


def test_fill_in_from_provider_keeps_a_single_given_or_family_name():
    only_given = User.register(Email("a@example.com"), "Alice", None, Locale.EN, NOW)
    only_given.fill_in_from_provider(first_name="Alice", last_name=None, name=None)
    assert (only_given.first_name, only_given.last_name, only_given.name) == (
        "Alice",
        None,
        "Alice",
    )

    only_family = User.register(Email("b@example.com"), None, "Martin", Locale.EN, NOW)
    only_family.fill_in_from_provider(first_name=None, last_name="Martin", name=None)
    assert (only_family.first_name, only_family.last_name, only_family.name) == (
        None,
        "Martin",
        "Martin",
    )


def test_role_change_is_logged_with_the_admin():
    user = make_user()
    admin_id = UserId.new()
    change = user.change_role(Role.AGENT, changed_by=admin_id, now=NOW)
    assert user.role is Role.AGENT
    assert (change.old_role, change.new_role) == (Role.CLIENT, Role.AGENT)
    assert change.source == "admin_api"
    assert change.changed_by == admin_id


def test_role_change_by_the_command_has_no_author():
    change = make_user().change_role(Role.ADMIN, changed_by=None, now=NOW)
    assert change.source == "cmd_grant_role"
    assert change.changed_by is None


def test_nobody_changes_their_own_role():
    admin = make_user(role=Role.ADMIN)
    with pytest.raises(CannotChangeOwnRole):
        admin.change_role(Role.CLIENT, changed_by=admin.id, now=NOW)


def test_agent_and_admin_need_a_verified_email():
    user = make_user(verified=False)
    with pytest.raises(EmailNotVerified):
        user.change_role(Role.AGENT, changed_by=None, now=NOW)


def test_same_role_changes_nothing():
    assert make_user().change_role(Role.CLIENT, changed_by=None, now=NOW) is None


def open_session() -> AuthSession:
    return AuthSession.open(
        UserId.new(), "hash", NOW, timedelta(days=7), timedelta(days=30), user_agent=None
    )


def test_session_expires_after_idle_and_absolute_ttl():
    session = open_session()
    assert session.is_active(NOW + timedelta(days=6))
    assert not session.is_active(NOW + timedelta(days=7))
    assert session.touch(NOW + timedelta(days=6), timedelta(days=7))
    assert session.is_active(NOW + timedelta(days=12))
    assert not session.is_active(NOW + timedelta(days=30))


def test_touch_writes_at_most_every_five_minutes():
    session = open_session()
    assert not session.touch(NOW + timedelta(minutes=4), timedelta(days=7))
    assert session.touch(NOW + timedelta(minutes=6), timedelta(days=7))


def test_revoked_session_is_not_active():
    session = open_session()
    session.revoke(NOW)
    assert not session.is_active(NOW)


def test_one_time_token_works_once_and_expires():
    token = OneTimeToken.issue(UserId.new(), TokenPurpose.PASSWORD_RESET, "hash", NOW)
    token.consume(NOW)
    with pytest.raises(InvalidOrExpiredToken):
        token.consume(NOW)

    late = OneTimeToken.issue(UserId.new(), TokenPurpose.PASSWORD_RESET, "hash", NOW)
    with pytest.raises(InvalidOrExpiredToken):
        late.consume(NOW + timedelta(minutes=31))


def test_status_change_remembers_the_admin_and_the_time():
    user = make_user()
    admin_id = UserId.new()
    assert user.change_status(UserStatus.DISABLED, changed_by=admin_id, now=NOW) is True
    assert not user.is_active
    assert (user.status_changed_by, user.status_changed_at) == (admin_id, NOW)


def test_same_status_changes_nothing():
    user = make_user()
    assert user.change_status(UserStatus.ACTIVE, changed_by=UserId.new(), now=NOW) is False
    assert (user.status_changed_by, user.status_changed_at) == (None, None)


def test_nobody_changes_their_own_status():
    admin = make_user(role=Role.ADMIN)
    with pytest.raises(CannotChangeOwnStatus):
        admin.change_status(UserStatus.DISABLED, changed_by=admin.id, now=NOW)


def test_an_admin_does_not_change_another_admins_status():
    other_admin = make_user(role=Role.ADMIN)
    with pytest.raises(CannotChangeAdminStatus):
        other_admin.change_status(UserStatus.DISABLED, changed_by=UserId.new(), now=NOW)
    assert other_admin.is_active
