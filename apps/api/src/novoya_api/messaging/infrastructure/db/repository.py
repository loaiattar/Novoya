from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.messaging.application.ports.messages import CONVERSATION_CAP
from novoya_api.messaging.domain.message import Message
from novoya_api.messaging.infrastructure.db.models import MessageModel


class SqlMessageRepository:
    """MessageRepository on PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_wish(self, wish_id: UUID) -> list[Message]:
        rows = (
            await self._session.scalars(
                select(MessageModel)
                .where(MessageModel.wish_id == wish_id)
                .order_by(MessageModel.sent_at.desc(), MessageModel.id.desc())
                .limit(CONVERSATION_CAP)
            )
        ).all()
        return [
            Message(row.id, row.wish_id, row.author_id, row.from_agency, row.body, row.sent_at)
            for row in reversed(rows)
        ]

    async def add(self, message: Message) -> None:
        self._session.add(
            MessageModel(
                id=message.id,
                wish_id=message.wish_id,
                author_id=message.author_id,
                from_agency=message.from_agency,
                body=message.body,
                sent_at=message.sent_at,
            )
        )
