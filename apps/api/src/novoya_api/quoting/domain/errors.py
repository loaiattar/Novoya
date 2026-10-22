from novoya_api.shared.domain.errors import InvalidInput, NotFound


class InvalidQuote(InvalidInput):  # 422
    """The quote breaks a rule, for example a total of 0."""

    code = "invalid_quote"


class QuoteNotFound(NotFound):  # 404
    """No quote with this id, or it is not the caller's. Same code so the id stays hidden."""
