"""ORM tables of the wishes module: wishes."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novoya_api.shared.infrastructure.db.base import Base


class WishModel(Base):
    """The whole request: the text, the panel shown, the tags picked, budget, travellers and
    dates. Uncovered wishes stay here so the team sees which destinations are asked for."""

    __tablename__ = "wishes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'not_covered', 'panel_shown', 'answered', 'planned')",
            name="ck_wishes_status",
        ),
        Index("ix_wishes_user_id", "user_id"),
        Index("ix_wishes_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    # No cascade: DELETE /me erases wishes first (#46), so a forgotten step fails loudly.
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    destination_country: Mapped[str | None] = mapped_column(String(100))
    destination_city: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    panel_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    # Filled by #28 (answers): the picked tags, budget, travellers and dates.
    selected_tags: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    persons: Mapped[int | None]
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
