from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from novoya_api.quoting.domain.errors import InvalidQuote, QuoteAlreadyAnswered, QuoteExpired
from novoya_api.shared.domain.value_objects import Locale

# The client has a week to answer; the agent's negotiated prices hold that long.
VALIDITY = timedelta(days=7)
CURRENCY = "EUR"
# The client's optional comment with their answer.
COMMENT_MAX_LENGTH = 1000
# The agency works in Paris: the dates on a quote, and in its number, are Paris dates.
AGENCY_TIMEZONE = ZoneInfo("Europe/Paris")


class QuoteStatus(StrEnum):
    """Where a quote stands: open until the client answers or its validity ends."""

    OPEN = "open"
    EXPIRED = "expired"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(slots=True)
class Quote:
    """The final offer for one plan: its total in euros, in the client's language, valid a
    week. pdf holds the rendered file once the quote is sent; None means not rendered yet,
    or not read (QuoteRepository.get with with_pdf=False). answer, decided_at and
    client_comment are the client's answer, when they gave it and what they added; None
    until then."""

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
    pdf: bytes | None = None
    answer: QuoteStatus | None = None
    decided_at: datetime | None = None
    client_comment: str | None = None

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

    def record_answer(self, answer: QuoteStatus, comment: str | None, now: datetime) -> None:
        """The client accepts or rejects, once, before the validity day is over. A blank
        comment is no comment."""
        if answer not in (QuoteStatus.ACCEPTED, QuoteStatus.REJECTED):
            raise InvalidQuote("the answer is accepted or rejected")
        if self.answer is not None:
            raise QuoteAlreadyAnswered("the quote is already answered")
        if self.has_expired(now):
            raise QuoteExpired("the quote is no longer valid")
        comment = (comment or "").strip() or None
        if comment is not None and len(comment) > COMMENT_MAX_LENGTH:
            raise InvalidQuote(f"the comment is longer than {COMMENT_MAX_LENGTH} characters")
        self.answer = answer
        self.decided_at = now
        self.client_comment = comment

    def readable_by(self, reader_id: UUID, admin: bool) -> bool:
        """Its client, the agent who sent it and any admin may read it; nobody else. Another
        agent may not: agents see client data only for their own plans."""
        return admin or reader_id in (self.client_id, self.agent_id)

    def has_expired(self, now: datetime) -> bool:
        """True once the validity day is over in Paris: the PDF and the email show the client
        only that day ("valid until 29 October"), so the whole day counts."""
        return paris_day(now) > paris_day(self.valid_until)

    def status(self, now: datetime) -> QuoteStatus:
        """The client's answer once given, even after the validity ends; before it, open
        until the validity ends, then expired."""
        if self.answer is not None:
            return self.answer
        return QuoteStatus.EXPIRED if self.has_expired(now) else QuoteStatus.OPEN


def paris_day(moment: datetime) -> date:
    return moment.astimezone(AGENCY_TIMEZONE).date()
