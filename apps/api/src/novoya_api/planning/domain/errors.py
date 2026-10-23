from novoya_api.shared.domain.errors import InvalidInput, NotFound


class InvalidPlan(InvalidInput):  # 422
    """The plan breaks a rule, for example an item on a day outside the trip."""

    code = "invalid_plan"


class NoOfferFits(InvalidInput):  # 422
    """No listed offer fits the travellers and the dates: there is nothing to plan with."""

    code = "no_offer_fits"


class PlanNotReady(InvalidInput):  # 422
    """A kept item or an on_quote extra has no price, or a supplement is not confirmed: the
    quote cannot be sent yet."""

    code = "plan_not_ready"


class PlanNotFound(NotFound):  # 404
    """No plan with this id, or it is not the caller's. Same code so the id stays hidden."""
