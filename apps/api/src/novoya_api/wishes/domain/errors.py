from novoya_api.shared.domain.errors import Conflict, InvalidInput, NotFound


class InvalidWish(InvalidInput):  # 422
    """The wish cannot be used, for example an empty text."""

    code = "invalid_wish"


class InvalidAnswers(InvalidInput):  # 422
    """The panel answers break a rule, for example a tag the panel did not show."""

    code = "invalid_answers"


class WishNotFound(NotFound):  # 404
    """No such wish, or it belongs to someone else: the client cannot tell which."""

    code = "wish_not_found"


class PreferenceLocked(Conflict):  # 409
    """Every wish carrying this tag is with the agency (a plan requested,
    negotiating, quoted, accepted or rejected): the brief
    behind that plan does not change."""

    code = "preference_locked"


class AnswerInProgress(Conflict):  # 409
    """Another request is answering this wish and building its plan right now."""

    code = "answer_in_progress"
