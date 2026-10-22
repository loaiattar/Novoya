from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Response, status

from novoya_api.quoting.application.use_cases.answer_quote import AnswerQuote
from novoya_api.quoting.application.use_cases.get_quote import GetQuote
from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.resend_quote_email import ResendQuoteEmail
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.domain.quote import QuoteStatus
from novoya_api.quoting.presentation.http.dependencies import (
    Reader,
    Staff,
    get_answer_quote,
    get_current_agent_id,
    get_get_quote,
    get_get_quote_pdf,
    get_reader,
    get_resend_quote_email,
    get_send_quote,
    get_staff,
)
from novoya_api.quoting.presentation.http.schemas import (
    AnswerQuoteRequest,
    Quote,
    QuoteDetail,
    SendQuoteRequest,
)
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
    The plan becomes quoted and the client gets an email that leads to the quote; email_sent
    is false if it did not go out (the quote is saved anyway). Only the assigned agent (403).
    409 if the plan is not negotiating (a second click too). 422 plan_not_ready while a kept
    item or an on_quote extra has no price, or a supplement is not confirmed."""
    locale = Locale(body.locale) if body is not None and body.locale is not None else None
    return Quote.of(await use_case(plan_id, agent_id, locale))


agent_quotes_router = APIRouter(prefix="/agent/quotes", tags=["agent"], responses=ERRORS)


@agent_quotes_router.post(
    "/{quote_id}/email",
    operation_id="resendQuoteEmail",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def resend_quote_email(
    quote_id: UUID,
    staff: Annotated[Staff, Depends(get_staff)],
    use_case: Annotated[ResendQuoteEmail, Depends(get_resend_quote_email)],
) -> None:
    """Send the client's "your quote is ready" email again. Only the agent who sent the quote,
    or an admin (403). At most 3 times an hour per quote: 429 too_many_requests after that,
    with Retry-After. 503 email_not_sent if the email server did not take it."""
    await use_case(quote_id, staff.user_id, staff.admin)


router = APIRouter(prefix="/quotes", tags=["quoting"], responses=ERRORS)


@router.get("/{quote_id}", operation_id="getQuote")
async def get_quote(
    quote_id: UUID,
    reader: Annotated[Reader, Depends(get_reader)],
    use_case: Annotated[GetQuote, Depends(get_get_quote)],
    response: Response,
) -> QuoteDetail:
    """The quote and where it stands (open, expired after its validity date, accepted or
    rejected), for its client or staff (agents, admins). 404 for anyone else, so the id
    stays hidden."""
    detail = QuoteDetail.of(await use_case(quote_id, reader.user_id, reader.staff))
    # The client's negotiated price: no shared or browser cache keeps it, as for the PDF.
    response.headers["Cache-Control"] = "private, no-store"
    return detail


@router.post(
    "/{quote_id}/accept",
    operation_id="acceptQuote",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": ErrorResponse}},
)
async def accept_quote(
    quote_id: UUID,
    reader: Annotated[Reader, Depends(get_reader)],
    use_case: Annotated[AnswerQuote, Depends(get_answer_quote)],
    body: Annotated[AnswerQuoteRequest | None, Body()] = None,
) -> None:
    """The client accepts their quote, with an optional comment for the agent. The plan
    becomes accepted. 409 quote_expired after the validity day, 409 quote_answered when it
    is answered already; 403 for staff, 404 for anyone else."""
    comment = body.comment if body else None
    await use_case(quote_id, reader.user_id, reader.staff, QuoteStatus.ACCEPTED, comment)


@router.post(
    "/{quote_id}/reject",
    operation_id="rejectQuote",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": ErrorResponse}},
)
async def reject_quote(
    quote_id: UUID,
    reader: Annotated[Reader, Depends(get_reader)],
    use_case: Annotated[AnswerQuote, Depends(get_answer_quote)],
    body: Annotated[AnswerQuoteRequest | None, Body()] = None,
) -> None:
    """The client rejects their quote, with an optional comment for the agent. The plan
    becomes rejected, and the client can start a new wish. Same errors as accept."""
    comment = body.comment if body else None
    await use_case(quote_id, reader.user_id, reader.staff, QuoteStatus.REJECTED, comment)


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
