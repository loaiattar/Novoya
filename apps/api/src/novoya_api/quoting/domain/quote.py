from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from novoya_api.quoting.domain.errors import InvalidQuote
from novoya_api.shared.domain.value_objects import Locale

# The client has a week to answer; the agent's negotiated prices hold that long.
VALIDITY = timedelta(days=7)
CURRENCY = "EUR"
# The agency works in Paris: the dates on a quote, and in its number, are Paris dates.
AGENCY_TIMEZONE = ZoneInfo("Europe/Paris")


@dataclass(slots=True)
class Quote:
    """The final offer for one plan: its total in euros, in the client's language, valid a
    week. pdf holds the rendered file once the quote is sent."""

    id: UUID
    number: str
    plan_id: UUID
    client_id: UUID
    agent_id: UUID
    total: Decimal
    currency: str
    locale: Locale
    sent_at: datetime
    valid_until: datetime
    pdf: bytes = b""

    @classmethod
    def issue(
        cls,
        plan_id: UUID,
        client_id: UUID,
        agent_id: UUID,
        total: Decimal,
        locale: Locale,
        sent_at: datetime,
    ) -> "Quote":
        """A new quote sent now. Its number reads well on the phone: NV-20261019-3FA2C1."""
        if total <= 0:
            raise InvalidQuote("the total must be more than 0")
        quote_id = uuid4()
        return cls(
            id=quote_id,
            number=f"NV-{sent_at.astimezone(AGENCY_TIMEZONE):%Y%m%d}-{quote_id.hex[:6].upper()}",
            plan_id=plan_id,
            client_id=client_id,
            agent_id=agent_id,
            total=total,
            currency=CURRENCY,
            locale=locale,
            sent_at=sent_at,
            valid_until=sent_at + VALIDITY,
        )

    def has_expired(self, now: datetime) -> bool:
        """True once the validity ends: the client can no longer answer."""
        return now > self.valid_until
