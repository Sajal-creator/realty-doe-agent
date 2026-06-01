"""
Lead model — represents a prospective buyer or seller.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LeadSource(str, enum.Enum):
    FACEBOOK = "FACEBOOK"
    ZILLOW = "ZILLOW"
    QR = "QR"
    ORGANIC = "ORGANIC"
    REFERRAL = "REFERRAL"


class LeadStage(str, enum.Enum):
    DISCOVERY = "DISCOVERY"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    BROWSING = "BROWSING"
    SELLER_DISCOVERY = "SELLER_DISCOVERY"
    SELLER_QUALIFIED = "SELLER_QUALIFIED"
    VIEWING_SCHEDULED = "VIEWING_SCHEDULED"
    ESCALATED = "ESCALATED"
    HUMAN_HIJACKED = "HUMAN_HIJACKED"
    COLD = "COLD"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"


class WarmthTier(str, enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class LeadRole(str, enum.Enum):
    BUYER = "buyer"
    SELLER = "seller"
    CLIENT = "client"


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource, name="lead_source", create_constraint=True),
        nullable=False,
    )
    lead_stage: Mapped[LeadStage] = mapped_column(
        Enum(LeadStage, name="lead_stage", create_constraint=True),
        default=LeadStage.DISCOVERY,
        nullable=False,
    )
    warmth_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warmth_tier: Mapped[WarmthTier] = mapped_column(
        Enum(WarmthTier, name="warmth_tier", create_constraint=True),
        default=WarmthTier.COLD,
        nullable=False,
    )
    # 4-D qualification matrix stored as JSON
    qualification: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), index=True, nullable=True
    )
    role: Mapped[LeadRole] = mapped_column(
        Enum(LeadRole, name="lead_role", create_constraint=True),
        default=LeadRole.BUYER,
        nullable=False,
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    assigned_agent: Mapped["Agent | None"] = relationship(  # noqa: F821
        "Agent", back_populates="leads", lazy="selectin"
    )
    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        "Session", back_populates="lead", lazy="selectin"
    )
    tickets: Mapped[list["SupportTicket"]] = relationship(  # noqa: F821
        "SupportTicket", back_populates="lead", lazy="selectin"
    )
    appointments: Mapped[list["Appointment"]] = relationship(  # noqa: F821
        "Appointment", back_populates="lead", lazy="selectin"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification", back_populates="lead", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Lead {self.name!r} phone={self.phone} stage={self.lead_stage.value}>"
