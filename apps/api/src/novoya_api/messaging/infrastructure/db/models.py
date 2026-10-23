"""ORM tables of the messaging module: messages."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from novoya_api.shared.infrastructure.db.base import Base


class MessageModel(Base):
    """One message of the advisor chat of a wish (#169). Personal data (ARCHITECTURE §9).

    ON DELETE CASCADE from the wish: DELETE /me erases the wishes, and their conversations
    go with them without a step of their own. An erased author leaves the line with no
    author, so an agent who leaves does not take the client's history away."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_wish_id_sent_at", "wish_id", "sent_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    wish_id: Mapped[UUID] = mapped_column(ForeignKey("wishes.id", ondelete="CASCADE"))
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    from_agency: Mapped[bool] = mapped_column(Boolean)
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
