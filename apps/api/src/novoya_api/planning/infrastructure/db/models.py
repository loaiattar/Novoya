"""ORM tables of the planning module: plans, plan_items, plan_extras."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from novoya_api.shared.infrastructure.db.base import Base


class PlanModel(Base):
    """The plan built from a wish, and its status until it is quoted."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'requested', 'negotiating', 'quoted', 'accepted', 'rejected')",
            name="ck_plans_status",
        ),
        Index("ix_plans_wish_id", "wish_id"),
        Index("ix_plans_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    # No cascade: DELETE /me erases plans before wishes (#46), so a forgotten step fails loudly.
    wish_id: Mapped[UUID] = mapped_column(ForeignKey("wishes.id"))
    status: Mapped[str] = mapped_column(String(20))
    based_on_preferences: Mapped[bool] = mapped_column(Boolean)
    summary: Mapped[str] = mapped_column(Text)
    assigned_agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanItemModel(Base):
    """One offer on one day. negotiated_price stays empty until an agent fills it (#51)."""

    __tablename__ = "plan_items"
    __table_args__ = (
        CheckConstraint("day >= 1", name="ck_plan_items_day"),
        CheckConstraint("quantity >= 1", name="ck_plan_items_quantity"),
        Index("ix_plan_items_plan_id", "plan_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id"))
    day: Mapped[int]
    quantity: Mapped[int]
    note: Mapped[str | None] = mapped_column(Text)
    negotiated_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class PlanExtraModel(Base):
    """An extra the client chose when asking for the quote. price_eur: the supplement as it
    was then, or what the agent set for an on_quote extra; NULL until then."""

    __tablename__ = "plan_extras"
    __table_args__ = (
        CheckConstraint(
            "pricing IN ('included', 'supplement', 'on_quote')", name="ck_plan_extras_pricing"
        ),
        CheckConstraint("price_eur IS NULL OR price_eur > 0", name="ck_plan_extras_price"),
    )

    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    extra_id: Mapped[UUID] = mapped_column(ForeignKey("extras.id"), primary_key=True)
    pricing: Mapped[str] = mapped_column(String(16))
    price_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # Copied from the extra when the quote is requested, so the agent sees what was asked.
    label: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(64))
    # True once the assigned agent set its price (a supplement per person or night needs it).
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
