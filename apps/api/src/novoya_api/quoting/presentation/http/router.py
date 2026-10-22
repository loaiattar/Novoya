from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Response, status

from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.presentation.http.dependencies import (
    Reader,
    get_current_agent_id,
    get_get_quote_pdf,
    get_reader,
    get_send_quote,
)
from novoya_api.quoting.presentation.http.schemas import Quote, SendQuoteRequest
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.presentation.http.errors import ErrorResponse

ERRORS = {status_code: {"model": ErrorResponse} for status_code in (401, 403, 404)}

agent_router = APIRouter(prefix="/agent/plans", tags=["agent"], responses=ERRORS)


@agent_router.post(
    "/{plan_id}/quote",
    operation_id="sendQuote",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def send_quote(
    plan_id: UUID,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[SendQuote, Depends(get_send_quote)],
    body: Annotated[SendQuoteRequest | None, Body()] = None,
) -> Quote:
    """Send the quote: the total of the priced items and extras, valid 7 days, rendered as a
    PDF in the language the agent chose (en or fr; the client's language without a body).
    The plan becomes quoted. Only the assigned agent (403).
    409 if the plan is not negotiating (a second click too). 422 plan_not_ready while a kept
    item or an on_quote extra has no price, or a supplement is not confirmed."""
    locale = Locale(body.locale) if body is not None and body.locale is not None else None
    return Quote.of(await use_case(plan_id, agent_id, locale))


router = APIRouter(prefix="/quotes", tags=["quoting"], responses=ERRORS)


@router.get(
    "/{quote_id}/pdf",
    operation_id="getQuotePdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The quote PDF"}},
)
async def get_quote_pdf(
    quote_id: UUID,
    reader: Annotated[Reader, Depends(get_reader)],
    use_case: Annotated[GetQuotePdf, Depends(get_get_quote_pdf)],
) -> Response:
    """The quote as a PDF, for its client or an agent. 404 for anyone else, so the id stays
    hidden."""
    pdf = await use_case(quote_id, reader.user_id, reader.staff)
    return Response(
        content=pdf.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf.filename}"',
            "Cache-Control": "private, no-store",
        },
    )
