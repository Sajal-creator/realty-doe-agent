"""
Notification model — alerts pushed to agents.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPrimaryKeyMixin


class NotificationType(str, enum.Enum):
    HANDOVER_REQUEST = "HANDOVER_REQUEST"
    NEW_HOT_LEAD = "NEW_HOT_LEAD"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    TICKET_CREATED = "TICKET_CREATED"
    LEAD_REPLY = "LEAD_REPLY"


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", create_constraint=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), index=True, nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="notifications", lazy="selectin")  # noqa: F821
    lead: Mapped["Lead | None"] = relationship("Lead", back_populates="notifications", lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Notification id={self.id} type={self.type.value} read={self.is_read}>"
