from novoya_api.shared.domain.errors import InvalidInput, NotFound


class InvalidMessage(InvalidInput):  # 422
    """The message is empty once trimmed, or longer than MAX_LENGTH."""

    code = "invalid_message"


class ConversationNotFound(NotFound):  # 404
    """No wish with this id, or the caller is neither its client nor staff. Same code so the
    id stays hidden."""
