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


class CannotChangeOwnStatus(Conflict):
    code = "cannot_change_own_status"


class CannotChangeAdminStatus(PermissionDenied):
    """Only a super admin disables or enables an admin or a super admin."""

    code = "cannot_change_admin_status"


class CannotChangeAdminRole(PermissionDenied):
    """Only a super admin gives, takes or changes the admin and super admin roles."""

    code = "cannot_change_admin_role"


class SuperAdminServerOnly(PermissionDenied):
    """The super admin role is managed on the server only (grant-role): the API never gives
    or takes it, and never disables or enables a super admin's account."""

    code = "super_admin_server_only"


class CannotPromoteDisabled(Conflict):
    """A disabled account stays a client: enable it before giving it a staff role."""

    code = "cannot_promote_disabled"


class LastSuperAdminRequired(Conflict):
    """The last active super admin cannot lose the role: nobody could act on admins any more."""

    code = "last_super_admin_required"


class NotAnAgent(Conflict):
    """Only an agent has a public advisor profile: give the user the agent role first."""

    code = "not_an_agent"


class AdvisorConsentRequired(Conflict):
    """An advisor is shown on the home page only once the agent agreed to it."""

    code = "advisor_consent_required"


class InvalidAdvisorProfile(InvalidInput):
    """A field of the advisor profile is empty or too long, or there are too many services."""

    code = "invalid_advisor_profile"


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
