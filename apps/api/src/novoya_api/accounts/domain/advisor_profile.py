import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from novoya_api.accounts.domain.errors import AdvisorConsentRequired, InvalidAdvisorProfile
from novoya_api.accounts.domain.value_objects import UserId

_HIDDEN = frozenset({"Cc", "Cf"})
NAME_MAX = 100
TITLE_MAX = 60
SUMMARY_MAX = 140  # a short line under the name: a longer one would stretch the card
SERVICE_MAX = 40
SERVICES_MAX = 6


def _clean(value: str | None, max_len: int, field: str) -> str | None:
    """Trimmed, without control or format characters; None when nothing is left."""
    if value is None:
        return None
    cleaned = "".join(ch for ch in value if unicodedata.category(ch) not in _HIDDEN).strip()
    if len(cleaned) > max_len:
        raise InvalidAdvisorProfile(f"{field} is longer than {max_len} characters")
    return cleaned or None


@dataclass(frozen=True, slots=True)
class AdvisorService:
    """Something the advisor handles, e.g. "Greece" or "Weekends for two". The admin types it
    in French, in English or both: the home page shows the visitor's language, else the other."""

    fr: str | None
    en: str | None

    @classmethod
    def of(cls, fr: str | None, en: str | None) -> "AdvisorService":
        service = cls(_clean(fr, SERVICE_MAX, "service"), _clean(en, SERVICE_MAX, "service"))
        if service.fr is None and service.en is None:
            raise InvalidAdvisorProfile("a service needs a French or an English label")
        return service


@dataclass(slots=True)
class AdvisorProfile:
    """What the home page shows of an agent (#167): a public name, a title, a short line and
    their services. Never the email or another account detail.

    It is shown only once the agent agreed to it: the admin records the agreement (who and
    when), and taking it back hides the profile at once.
    """

    id: UUID  # public: the home page never sees the account's id
    user_id: UserId
    public_name: str
    title: str | None
    summary: str | None
    services: tuple[AdvisorService, ...]
    shown: bool
    consent_at: datetime | None
    consent_by: UserId | None  # the admin who recorded the agreement; None once deleted
    updated_at: datetime

    @classmethod
    def new(cls, user_id: UserId, now: datetime) -> "AdvisorProfile":
        return cls(uuid4(), user_id, "", None, None, (), False, None, None, now)

    @property
    def has_consent(self) -> bool:
        return self.consent_at is not None

    def edit(
        self,
        *,
        public_name: str,
        title: str | None,
        summary: str | None,
        services: list[AdvisorService],
        consent: bool,
        shown: bool,
        by: UserId,
        now: datetime,
    ) -> None:
        """Replace the whole profile. The agreement keeps its first date while it holds."""
        name = _clean(public_name, NAME_MAX, "public_name")
        if name is None:
            raise InvalidAdvisorProfile("the public name is required")
        if len(services) > SERVICES_MAX:
            raise InvalidAdvisorProfile(f"at most {SERVICES_MAX} services")
        if shown and not consent:
            raise AdvisorConsentRequired("record the agent's agreement before showing them")

        self.public_name = name
        self.title = _clean(title, TITLE_MAX, "title")
        self.summary = _clean(summary, SUMMARY_MAX, "summary")
        self.services = tuple(services)
        if consent and self.consent_at is None:
            self.consent_at, self.consent_by = now, by
        elif not consent:
            self.consent_at = self.consent_by = None
        self.shown = shown
        self.updated_at = now
