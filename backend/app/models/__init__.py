"""
Models package — import all ORM models here so Alembic & the rest of the app
can do ``from app.models import Lead, Agent, ...``.
"""

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .agent import Agent, AgentStatus
from .lead import Lead, LeadSource, LeadStage, LeadRole, WarmthTier
from .session import Session, SessionStatus, ConversationMode
from .message import Message, SenderType, MessageType
from .ticket import SupportTicket, TicketCategory, TicketPriority, TicketStatus
from .appointment import Appointment, AppointmentType, AppointmentStatus
from .notification import Notification, NotificationType
from .property_listing import PropertyListing, PropertyStatus

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # Agent
    "Agent",
    "AgentStatus",
    # Lead
    "Lead",
    "LeadSource",
    "LeadStage",
    "LeadRole",
    "WarmthTier",
    # Session
    "Session",
    "SessionStatus",
    "ConversationMode",
    # Message
    "Message",
    "SenderType",
    "MessageType",
    # Ticket
    "SupportTicket",
    "TicketCategory",
    "TicketPriority",
    "TicketStatus",
    # Appointment
    "Appointment",
    "AppointmentType",
    "AppointmentStatus",
    # Notification
    "Notification",
    "NotificationType",
    # Property Listing
    "PropertyListing",
    "PropertyStatus",
]
