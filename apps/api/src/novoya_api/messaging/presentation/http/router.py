from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from novoya_api.messaging.application.use_cases.list_messages import ListMessages
from novoya_api.messaging.application.use_cases.post_message import PostMessage
from novoya_api.messaging.presentation.http.dependencies import (
    Participant,
    get_list_messages,
    get_participant,
    get_post_message,
)
from novoya_api.messaging.presentation.http.schemas import ChatMessage, PostMessageRequest
from novoya_api.shared.presentation.http.errors import ErrorResponse

ERRORS = {status_code: {"model": ErrorResponse} for status_code in (401, 404)}

router = APIRouter(prefix="/wishes", tags=["messaging"], responses=ERRORS)


@router.get("/{wish_id}/messages", operation_id="listWishMessages")
async def list_messages(
    wish_id: UUID,
    reader: Annotated[Participant, Depends(get_participant)],
    use_case: Annotated[ListMessages, Depends(get_list_messages)],
    response: Response,
) -> list[ChatMessage]:
    """The advisor chat of this wish, oldest first (the last 500). For the client who sent
    the wish, an agent or an admin; 404 for anyone else, so the id stays hidden. The pages
    poll it, and no cache keeps it."""
    found = await use_case(wish_id, reader.user_id, reader.staff)
    response.headers["Cache-Control"] = "private, no-store"
    return [ChatMessage.of(message, reader.user_id) for message in found]


@router.post(
    "/{wish_id}/messages",
    operation_id="postWishMessage",
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
async def post_message(
    wish_id: UUID,
    body: PostMessageRequest,
    author: Annotated[Participant, Depends(get_participant)],
    use_case: Annotated[PostMessage, Depends(get_post_message)],
) -> ChatMessage:
    """Write in the advisor chat of this wish: its client, an agent or an admin. 404 for
    anyone else. 422 invalid_message when it is empty or longer than 2000 characters."""
    message = await use_case(wish_id, author.user_id, author.staff, body.body)
    return ChatMessage.of(message, author.user_id)
