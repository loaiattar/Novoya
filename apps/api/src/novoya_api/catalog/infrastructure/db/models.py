"""ORM tables of the catalog module: partners, offers, reviews, extras."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    false,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from novoya_api.shared.infrastructure.db.base import Base

# partners.source of the rows the DÉTOUR import owns.
DETOUR_SOURCE = "detour"


class PartnerRow(Base):
    __tablename__ = "partners"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The agent's switch in Novoya; the DÉTOUR import never writes it (ADR 0014).
    hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # "detour" for rows the DÉTOUR import owns (their offers too); NULL for the seed and
    # hand-added partners. An imported row only changes hidden (and featured) in Novoya.
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OfferRow(Base):
    __tablename__ = "offers"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    partner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("partners.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    min_persons: Mapped[int] = mapped_column(Integer, nullable=False)
    max_persons: Mapped[int] = mapped_column(Integer, nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    available_to: Mapped[date] = mapped_column(Date, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The agent's switch in Novoya; the DÉTOUR import never writes it (ADR 0014).
    hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Indicative only (ADR 0014): the agent still negotiates the price of each trip.
    price_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    opening_months: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_delay_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "min_persons >= 1 AND max_persons >= min_persons",
            name="offers_person_limits",
        ),
        CheckConstraint("available_from <= available_to", name="offers_availability_dates"),
        CheckConstraint(
            "(price_eur IS NULL) = (price_unit IS NULL) AND (price_eur IS NULL OR price_eur > 0)",
            name="offers_price_with_unit",
        ),
        CheckConstraint(
            "price_unit IN ('person/night', 'person/trip', 'person/activity')",
            name="offers_price_unit",
        ),
        CheckConstraint(
            "confirmation_delay_hours IS NULL OR confirmation_delay_hours >= 0",
            name="offers_confirmation_delay",
        ),
    )


class ReviewRow(Base):
    """A published review from DÉTOUR's avis_diffusables: consented and pseudonymised (ADR 0014).
    The import deletes a row as soon as it leaves that view."""

    __tablename__ = "reviews"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reviewed_on: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="reviews_rating"),
        Index("ix_reviews_place", "country", "city"),
    )


class ExtraRow(Base):
    """An option a client can add to a plan, from DÉTOUR's preferences."""

    __tablename__ = "extras"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    pricing: Mapped[str] = mapped_column(String(16), nullable=False)
    supplement_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    constraints: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The agent's switch in Novoya; the DÉTOUR import never writes it (ADR 0014).
    hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    __table_args__ = (
        CheckConstraint("pricing IN ('included', 'supplement', 'on_quote')", name="extras_pricing"),
        CheckConstraint(
            "(pricing = 'supplement') = (supplement_eur IS NOT NULL)"
            " AND (supplement_eur IS NULL OR supplement_eur > 0)",
            name="extras_supplement",
        ),
    )
