import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from novoya_api.accounts.domain.errors import (
    AccountDisabled,
    CannotChangeAdminRole,
    CannotChangeAdminStatus,
    CannotChangeOwnRole,
    CannotChangeOwnStatus,
    CannotPromoteDisabled,
    EmailNotVerified,
)
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.role_change import RoleChange
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.shared.domain.value_objects import Locale

_HIDDEN = frozenset({"Cc", "Cf"})
_NAME_MAX = 200
_PART_MAX = 100


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


def _clip(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    visible = "".join(ch for ch in value.strip() if unicodedata.category(ch) not in _HIDDEN)
    cleaned = visible.strip()[:max_len]
    return cleaned or None


def _display_name(first_name: str | None, last_name: str | None) -> str | None:
    parts = [part for part in (first_name, last_name) if part]
    joined = " ".join(parts)
    return joined[:_NAME_MAX] or None


def _names_from_display(name: str | None) -> tuple[str | None, str | None]:
    cleaned = _clip(name, _NAME_MAX)
    if not cleaned:
        return None, None
    given, _, family = cleaned.partition(" ")
    return _clip(given, _PART_MAX), _clip(family, _PART_MAX)


@dataclass(slots=True)
class User:
    """A person with an account. Ways to sign in (password, Google) are kept apart."""

    id: UserId
    email: Email
    name: str | None
    first_name: str | None
    last_name: str | None
    role: Role
    locale: Locale
    status: UserStatus
    email_verified_at: datetime | None
    created_at: datetime
    # The last status change: the admin who made it (None once that admin is deleted) and when.
    status_changed_by: UserId | None = None
    status_changed_at: datetime | None = None

    @classmethod
    def register(
        cls,
        email: Email,
        first_name: str | None,
        last_name: str | None,
        locale: Locale,
        now: datetime,
    ) -> "User":
        """A new account is always a client. Only an admin can change the role afterwards."""
        given = _clip(first_name, _PART_MAX)
        family = _clip(last_name, _PART_MAX)
        return cls(
            UserId.new(),
            email,
            _display_name(given, family),
            given,
            family,
            Role.CLIENT,
            locale,
            UserStatus.ACTIVE,
            None,
            now,
        )

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    def fill_in_name(self, name: str | None) -> None:
        """Take the provider's name only when we have none: a name chosen at sign-up wins."""
        if self.name is None:
            self.name = _clip(name, _NAME_MAX)

    def fill_in_from_provider(
        self,
        *,
        first_name: str | None,
        last_name: str | None,
        name: str | None,
    ) -> None:
        """Take the provider's names only when we have none. An existing display name
        keeps first and last in sync with it, so Google cannot rename an old account."""
        if self.name is not None and self.first_name is None and self.last_name is None:
            self.first_name, self.last_name = _names_from_display(self.name)
            return

        if self.first_name is None:
            self.first_name = _clip(first_name, _PART_MAX)
        if self.last_name is None:
            self.last_name = _clip(last_name, _PART_MAX)
        if self.name is None:
            self.name = _display_name(self.first_name, self.last_name)
        self.fill_in_name(name)
        if self.name is not None and self.first_name is None and self.last_name is None:
            self.first_name, self.last_name = _names_from_display(self.name)

    def change_locale(self, locale: Locale) -> None:
        """The language of the interface, the emails and the quote PDF."""
        self.locale = locale

    def verify_email(self, now: datetime) -> None:
        if self.email_verified_at is None:
            self.email_verified_at = now

    def ensure_can_sign_in(self, *, require_verified_email: bool) -> None:
        if not self.is_active:
            raise AccountDisabled("this account is disabled")
        if require_verified_email and not self.is_email_verified:
            raise EmailNotVerified("verify your email address before signing in")

    def change_role(
        self, new_role: Role, *, changed_by: "UserId | None", now: datetime
    ) -> RoleChange | None:
        """Change the role and return the log line, or None if the role is the same.

        changed_by: the admin making the change, or None for the grant-role command.
        Whether the caller may change roles is checked before (require_admin, or server access).
        An admin never takes the role of another admin: otherwise demoting them would open
        their account to change_status. Only the grant-role command does it, until a super
        admin exists.
        """
        if changed_by == self.id:
            raise CannotChangeOwnRole("an admin cannot change their own role")
        if changed_by is not None and self.role is Role.ADMIN and new_role is not Role.ADMIN:
            raise CannotChangeAdminRole("an admin cannot change another admin's role")
        if new_role is not Role.CLIENT and not self.is_active:
            # Nobody could enable a disabled admin again, nor demote them.
            raise CannotPromoteDisabled("a disabled account cannot get the agent or admin role")
        if new_role is not Role.CLIENT and not self.is_email_verified:
            raise EmailNotVerified("only a verified email address can get the agent or admin role")
        if new_role is self.role:
            return None
        change = RoleChange.record(self.id, self.role, new_role, changed_by, now)
        self.role = new_role
        return change

    def change_status(self, new_status: UserStatus, *, changed_by: UserId, now: datetime) -> bool:
        """Disable or enable the account and remember who did it and when. False if the
        status is the same. A disabled account cannot sign in and its sessions stop working.

        Whether the caller is an admin is checked before (require_admin). An admin never
        changes their own status nor another admin's.
        """
        if changed_by == self.id:
            raise CannotChangeOwnStatus("an admin cannot disable or enable their own account")
        if self.role is Role.ADMIN:
            raise CannotChangeAdminStatus("an admin cannot disable or enable another admin")
        if new_status is self.status:
            return False
        self.status = new_status
        self.status_changed_by = changed_by
        self.status_changed_at = now
        return True
