from pydantic import BaseModel

from novoya_api.dashboard.application.dto import AdminStats, RowCounts


class StatsRows(BaseModel):
    """active: clients may see it; hidden: an admin hid it; inactive: it left the DÉTOUR
    export. An offer counts with its partner: hidden or inactive when its partner is."""

    active: int
    hidden: int
    inactive: int

    @classmethod
    def of(cls, counts: RowCounts) -> "StatsRows":
        return cls(active=counts.active, hidden=counts.hidden, inactive=counts.inactive)


class StatsReviews(BaseModel):
    published: int
    hidden: int


class StatsUsers(BaseModel):
    """Every account by role, disabled ones too."""

    client: int
    agent: int
    admin: int
    super_admin: int


class StatsPlans(BaseModel):
    """requested: waiting for an agent to take it and send the quote."""

    proposed: int
    requested: int
    negotiating: int
    quoted: int
    accepted: int
    rejected: int


class StatsQuotes(BaseModel):
    """As GET /quotes/{id} gives them: open until the end of the validity day in Paris."""

    open: int
    expired: int
    accepted: int
    rejected: int


class AdminStatsResponse(BaseModel):
    """The admin home's numbers. Counts only."""

    partners: StatsRows
    offers: StatsRows
    extras: StatsRows
    reviews: StatsReviews
    users: StatsUsers
    plans: StatsPlans
    quotes: StatsQuotes

    @classmethod
    def of(cls, stats: AdminStats) -> "AdminStatsResponse":
        catalog = stats.catalog
        return cls(
            partners=StatsRows.of(catalog.partners),
            offers=StatsRows.of(catalog.offers),
            extras=StatsRows.of(catalog.extras),
            reviews=StatsReviews(
                published=catalog.reviews_published, hidden=catalog.reviews_hidden
            ),
            users=StatsUsers.model_validate(stats.users),
            plans=StatsPlans.model_validate(stats.plans),
            quotes=StatsQuotes.model_validate(stats.quotes),
        )
