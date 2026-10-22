"""ORM tables of the quoting module: quotes."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from novoya_api.shared.infrastructure.db.base import Base


class QuoteModel(Base):
    """The offer sent to the client: its total, its validity and the PDF itself.

    The PDF bytes live here, not in a file: the demo host wipes its disk on every deploy
    (ADR 0013). One quote per plan."""

    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint("total_price > 0", name="ck_quotes_total_price"),
        CheckConstraint("locale IN ('en', 'fr')", name="ck_quotes_locale"),
        UniqueConstraint("number", name="uq_quotes_number"),
        UniqueConstraint("plan_id", name="uq_quotes_plan_id"),
        Index("ix_quotes_client_id", "client_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32))
    # No cascade: DELETE /me erases quotes before plans (#46), so a forgotten step fails loudly.
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"))
    client_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    locale: Mapped[str] = mapped_column(String(2))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pdf: Mapped[bytes] = mapped_column(LargeBinary)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_comment: Mapped[str | None] = mapped_column(Text)
