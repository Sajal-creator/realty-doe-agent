"""
Agent model — represents a human real-estate agent in the system.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPrimaryKeyMixin


class AgentStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class Agent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_status", create_constraint=True),
        default=AgentStatus.OFFLINE,
        nullable=False,
    )
    max_concurrent_sessions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    current_session_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agency_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        "Lead", back_populates="assigned_agent", lazy="selectin"
    )
    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        "Session", back_populates="agent", lazy="selectin"
    )
    tickets: Mapped[list["SupportTicket"]] = relationship(  # noqa: F821
        "SupportTicket", back_populates="agent", lazy="selectin"
    )
    appointments: Mapped[list["Appointment"]] = relationship(  # noqa: F821
        "Appointment", back_populates="agent", lazy="selectin"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification", back_populates="agent", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Agent {self.name!r} status={self.status.value}>"
