import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from novoya_api.accounts.application.dto import AccountView, AgentAdvisorView
from novoya_api.accounts.domain.advisor_profile import (
    NAME_MAX,
    SERVICE_MAX,
    SERVICES_MAX,
    SUMMARY_MAX,
    TITLE_MAX,
    AdvisorProfile,
    AdvisorService,
)
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User

RoleName = Literal["client", "agent", "admin", "super_admin"]


def _visible_person_name(value: str) -> str:
    if any(unicodedata.category(ch) in {"Cc", "Cf"} for ch in value):
        raise ValueError("must not contain control or format characters")
    if not any(unicodedata.category(ch).startswith("L") for ch in value):
        raise ValueError("must contain at least one letter")
    return value


PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_visible_person_name),
]


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: SecretStr
    first_name: PersonName
    last_name: PersonName
    locale: Literal["en", "fr"] | None = None  # defaults to the browser language


class SignInRequest(BaseModel):
    email: str = Field(max_length=254)
    password: SecretStr


class TokenRequest(BaseModel):
    token: str = Field(max_length=200)


class EmailRequest(BaseModel):
    email: str = Field(max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(max_length=200)
    new_password: SecretStr


class ChangePasswordRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr


class ChangeRoleRequest(BaseModel):
    role: RoleName


class ChangeStatusRequest(BaseModel):
    status: Literal["active", "disabled"]


class UpdateMeRequest(BaseModel):
    """Send only what changes, at least one field. A field sent as null is refused, and so is
    any other field: the email, the sign-in identity, cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    first_name: PersonName | None = None
    last_name: PersonName | None = None
    locale: Literal["en", "fr"] | None = None

    @field_validator("first_name", "last_name", "locale", mode="before")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @model_validator(mode="after")
    def _something_given(self) -> "UpdateMeRequest":
        if not self.model_fields_set:
            raise ValueError("send first_name, last_name or locale")
        return self


class AccountResponse(BaseModel):
    """What every account shows, its owner included."""

    id: UUID
    email: str
    name: str | None
    first_name: str | None
    last_name: str | None
    role: RoleName
    locale: Literal["en", "fr"]
    status: Literal["active", "disabled"]
    email_verified: bool
    created_at: datetime

    @staticmethod
    def fields_of(user: User) -> dict[str, object]:
        return {
            "id": user.id.value,
            "email": user.email.value,
            "name": user.name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "locale": user.locale.value,
            "status": user.status.value,
            "email_verified": user.is_email_verified,
            "created_at": user.created_at,
        }


class UserResponse(AccountResponse):
    """A user as an admin sees them."""

    # The last status change: the admin who made it and when. None if it never changed.
    # Kept out of MeResponse: a user does not learn which admin disabled them.
    status_changed_by: UUID | None
    status_changed_at: datetime | None

    @classmethod
    def of(cls, user: User) -> "UserResponse":
        return cls.model_validate(
            {
                **cls.fields_of(user),
                "status_changed_by": user.status_changed_by.value
                if user.status_changed_by
                else None,
                "status_changed_at": user.status_changed_at,
            }
        )


def _sign_in_methods(account: AccountView) -> list[Literal["password", "google"]]:
    methods: list[Literal["password", "google"]] = []
    if account.has_password:
        methods.append("password")
    if account.has_google:
        methods.append("google")
    return methods


class MeResponse(AccountResponse):
    sign_in_methods: list[Literal["password", "google"]]

    @classmethod
    def of_account(cls, account: AccountView) -> "MeResponse":
        return cls.model_validate(
            {**cls.fields_of(account.user), "sign_in_methods": _sign_in_methods(account)}
        )


class UserDetailResponse(UserResponse):
    """One user for an admin: with their sign-in methods."""

    sign_in_methods: list[Literal["password", "google"]]

    @classmethod
    def of_account(cls, account: AccountView) -> "UserDetailResponse":
        return cls.model_validate(
            {
                **UserResponse.of(account.user).model_dump(),
                "sign_in_methods": _sign_in_methods(account),
            }
        )


# The advisors on the home page (#167)

ServiceLabel = Annotated[str, StringConstraints(strip_whitespace=True, max_length=SERVICE_MAX)]


class AdvisorServiceBody(BaseModel):
    """A service in French, in English or both: one of the two at least."""

    model_config = ConfigDict(extra="forbid")

    fr: ServiceLabel | None = None
    en: ServiceLabel | None = None

    @model_validator(mode="after")
    def _one_language_at_least(self) -> "AdvisorServiceBody":
        if not self.fr and not self.en:
            raise ValueError("give the service in French, in English or both")
        return self


class UpdateAdvisorProfileRequest(BaseModel):
    """The whole profile. `shown` needs `consent`: the agent agreed to appear on the site."""

    model_config = ConfigDict(extra="forbid")

    public_name: PersonName
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=TITLE_MAX)] | None = (
        None
    )
    summary: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=SUMMARY_MAX)] | None
    ) = None
    services: list[AdvisorServiceBody] = Field(default_factory=list, max_length=SERVICES_MAX)
    consent: bool
    shown: bool


class AdvisorServiceResponse(BaseModel):
    fr: str | None
    en: str | None

    @classmethod
    def of(cls, service: AdvisorService) -> "AdvisorServiceResponse":
        return cls(fr=service.fr, en=service.en)


class AdvisorResponse(BaseModel):
    """An advisor as the home page shows them: public fields only, never an account detail.
    The id is the profile's, not the account's."""

    id: UUID
    name: str = Field(max_length=NAME_MAX)
    title: str | None
    summary: str | None
    services: list[AdvisorServiceResponse]

    @classmethod
    def of(cls, profile: AdvisorProfile) -> "AdvisorResponse":
        return cls(
            id=profile.id,
            name=profile.public_name,
            title=profile.title,
            summary=profile.summary,
            services=[AdvisorServiceResponse.of(s) for s in profile.services],
        )


class AdvisorProfileResponse(BaseModel):
    public_name: str
    title: str | None
    summary: str | None
    services: list[AdvisorServiceResponse]
    consent: bool
    consent_at: datetime | None
    shown: bool
    updated_at: datetime

    @classmethod
    def of(cls, profile: AdvisorProfile) -> "AdvisorProfileResponse":
        return cls(
            public_name=profile.public_name,
            title=profile.title,
            summary=profile.summary,
            services=[AdvisorServiceResponse.of(s) for s in profile.services],
            consent=profile.has_consent,
            consent_at=profile.consent_at,
            shown=profile.shown,
            updated_at=profile.updated_at,
        )


class AgentAdvisorResponse(BaseModel):
    """An agent for the back office: their account, and their public profile if filled in."""

    user_id: UUID
    email: str
    name: str | None
    status: Literal["active", "disabled"]
    profile: AdvisorProfileResponse | None

    @classmethod
    def of(cls, view: AgentAdvisorView) -> "AgentAdvisorResponse":
        return cls(
            user_id=view.user.id.value,
            email=view.user.email.value,
            name=view.user.name,
            status=view.user.status.value,
            profile=AdvisorProfileResponse.of(view.profile) if view.profile else None,
        )


def role_of(name: RoleName | None) -> Role | None:
    return Role(name) if name else None
