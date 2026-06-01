"""
Session model — tracks a conversation between a lead and the AI/agent.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPrimaryKeyMixin


class SessionStatus(str, enum.Enum):
    AI_MANAGED = "AI_MANAGED"
    AGENT_ACTIVE = "AGENT_ACTIVE"
    HUMAN_HIJACKED = "HUMAN_HIJACKED"
    CLOSED = "CLOSED"


class ConversationMode(str, enum.Enum):
    AI = "AI"
    AGENT = "AGENT"


class Session(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sessions"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", create_constraint=True),
        default=SessionStatus.AI_MANAGED,
        nullable=False,
    )
    conversation_mode: Mapped[ConversationMode] = mapped_column(
        Enum(ConversationMode, name="conversation_mode", create_constraint=True),
        default=ConversationMode.AI,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="sessions", lazy="selectin")  # noqa: F821
    agent: Mapped["Agent | None"] = relationship("Agent", back_populates="sessions", lazy="selectin")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="session", lazy="selectin", order_by="Message.timestamp"
    )

    def __repr__(self) -> str:
        return f"<Session id={self.id} status={self.status.value}>"
