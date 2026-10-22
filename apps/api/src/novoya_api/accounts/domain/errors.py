"""Errors of the accounts module. Each one extends a shared error, which sets its HTTP status."""

from novoya_api.shared.domain.errors import (
    Conflict,
    InvalidInput,
    NotFound,
    PermissionDenied,
    TooManyRequests,
    Unauthenticated,
)


class SessionInvalid(Unauthenticated):
    """No session cookie, or the session is expired, revoked or its account disabled."""

    code = "unauthenticated"


class OAuthStateInvalid(Unauthenticated):
    """The sign-in came back with a state we did not issue, used already or too old."""

    code = "oauth_state_invalid"


class OAuthProviderError(Unauthenticated):
    """The provider refused the code, could not be reached, or sent an invalid ID token."""

    code = "oauth_failed"


class InvalidCredentials(Unauthenticated):
    """Wrong email or password. Same error whether the email exists or not."""

    code = "invalid_credentials"


class NotAllowed(PermissionDenied):
    """The user's role may not use this route."""

    code = "forbidden"


class StaffAccountDeletion(PermissionDenied):
    """Only a client deletes their own account: plans and quotes keep pointing to the agent
    or admin who handled them."""

    code = "staff_account"


class EmailNotVerified(PermissionDenied):
    code = "email_not_verified"


class OAuthEmailNotVerified(PermissionDenied):
    """The provider does not vouch for the email address: we cannot link or create on it."""

    code = "oauth_email_not_verified"


class AccountDisabled(PermissionDenied):
    code = "account_disabled"


class UserNotFound(NotFound):
    code = "user_not_found"


class UnknownIdentityProvider(NotFound):
    """No such sign-in provider, or it is not configured (no client ID and secret)."""

    code = "unknown_provider"


class IdentityAlreadyLinked(Conflict):
    """This provider account is already linked to another user."""

    code = "identity_already_linked"


class EmailAlreadyUsed(Conflict):
    code = "email_already_used"


class OAuthLinkNotAllowed(Conflict):
    """An account exists with this email, but the provider cannot prove who owns the address
    today (not Gmail or a Workspace domain), or the account has another provider account
    linked already. The person signs in with their password instead."""

    code = "oauth_link_not_allowed"


class CannotChangeOwnRole(Conflict):
    code = "cannot_change_own_role"


class LastAdminRequired(Conflict):
    """The last admin cannot lose the admin role: nobody could manage roles any more."""

    code = "last_admin_required"


class InvalidEmail(InvalidInput):
    code = "invalid_email"


class WeakPassword(InvalidInput):
    code = "weak_password"


class InvalidOrExpiredToken(InvalidInput):
    code = "invalid_token"


class NoPasswordSet(InvalidInput):
    """The account has no password, for example a Google-only account."""

    code = "no_password_set"


class TooManyAttempts(TooManyRequests):
    code = "too_many_attempts"
