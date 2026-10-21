"""add indicative offer prices, reviews and extras for the DÉTOUR import

Revision ID: d4f2a8c61e93
Revises: b7e4a91c2d08
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4f2a8c61e93"
down_revision: str | Sequence[str] | None = "b7e4a91c2d08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("partners", "contact_phone", existing_type=sa.String(length=32), nullable=True)
    op.add_column("partners", sa.Column("source", sa.String(length=16), nullable=True))

    op.add_column("offers", sa.Column("price_eur", sa.Integer(), nullable=True))
    op.add_column("offers", sa.Column("price_unit", sa.String(length=16), nullable=True))
    op.add_column(
        "offers",
        sa.Column(
            "opening_months",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("offers", sa.Column("conditions", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("restrictions", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("cancellation", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("confirmation_delay_hours", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "offers_price_with_unit",
        "offers",
        "(price_eur IS NULL) = (price_unit IS NULL) AND (price_eur IS NULL OR price_eur > 0)",
    )
    op.create_check_constraint(
        "offers_price_unit",
        "offers",
        "price_unit IN ('person/night', 'person/trip', 'person/activity')",
    )
    op.create_check_constraint(
        "offers_confirmation_delay",
        "offers",
        "confirmation_delay_hours IS NULL OR confirmation_delay_hours >= 0",
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("reviewed_on", sa.Date(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="reviews_rating"),
    )
    op.create_index("ix_reviews_place", "reviews", ["country", "city"], unique=False)
    op.create_table(
        "extras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("pricing", sa.String(length=16), nullable=False),
        sa.Column("supplement_eur", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column(
            "constraints",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "pricing IN ('included', 'supplement', 'on_quote')", name="extras_pricing"
        ),
        sa.CheckConstraint(
            "(pricing = 'supplement') = (supplement_eur IS NOT NULL)"
            " AND (supplement_eur IS NULL OR supplement_eur > 0)",
            name="extras_supplement",
        ),
    )


def downgrade() -> None:
    op.drop_table("extras")
    op.drop_index("ix_reviews_place", table_name="reviews")
    op.drop_table("reviews")

    op.drop_constraint("offers_confirmation_delay", "offers", type_="check")
    op.drop_constraint("offers_price_unit", "offers", type_="check")
    op.drop_constraint("offers_price_with_unit", "offers", type_="check")
    op.drop_column("offers", "confirmation_delay_hours")
    op.drop_column("offers", "cancellation")
    op.drop_column("offers", "restrictions")
    op.drop_column("offers", "conditions")
    op.drop_column("offers", "opening_months")
    op.drop_column("offers", "price_unit")
    op.drop_column("offers", "price_eur")

    op.drop_column("partners", "source")
    # Imported partners have no phone; the old schema and Partner need a non-empty one.
    op.execute("UPDATE partners SET contact_phone = '-' WHERE contact_phone IS NULL")
    op.alter_column("partners", "contact_phone", existing_type=sa.String(length=32), nullable=False)
