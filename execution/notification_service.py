"""Dashboard push notifications via DB records + WebSocket emission."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update, func

logger = structlog.get_logger(__name__)


def _get_session_factory():
    from database.session import async_session_factory
    return async_session_factory


def _get_models():
    from database.models import Notification
    return Notification


def _get_ws_manager():
    """Lazy import to avoid circular deps."""
    try:
        from websocket_manager import ws_manager
        return ws_manager
    except ImportError:
        return None


# ─── Core Notification ───────────────────────────────────────────────────────


async def send_notification(
    agent_id: str,
    notification_type: str,
    title: str,
    message: str,
    lead_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Create a notification record and emit via WebSocket."""
    Notification = _get_models()
    async with _get_session_factory()() as session:
        notif = Notification(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            type=notification_type,
            title=title,
            message=message,
            lead_id=lead_id,
            metadata=metadata or {},
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        session.add(notif)
        await session.commit()
        await session.refresh(notif)

        # Emit via WebSocket
        ws = _get_ws_manager()
        if ws:
            try:
                await ws.emit_to_user(agent_id, "notification", {
                    "id": notif.id,
                    "type": notification_type,
                    "title": title,
                    "message": message,
                    "lead_id": lead_id,
                    "created_at": notif.created_at.isoformat(),
                })
            except Exception as e:
                logger.warning("ws_emit_failed", error=str(e))

        logger.info("notification_sent", notif_id=notif.id, agent_id=agent_id, type=notification_type)
        return _notif_to_dict(notif)


# ─── Specialized Notifications ───────────────────────────────────────────────


async def notify_handover_request(
    agent_id: str, lead_id: str, urgency: str = "high"
) -> dict:
    """Send an urgent handover alert to an agent."""
    return await send_notification(
        agent_id=agent_id,
        notification_type="handover_request",
        title=f"🚨 Handover Request ({urgency.upper()})",
        message=f"Lead {lead_id} is requesting human assistance. Urgency: {urgency}.",
        lead_id=lead_id,
        metadata={"urgency": urgency},
    )


async def notify_new_hot_lead(agent_id: str, lead_id: str) -> dict:
    """Alert agent about a new hot lead."""
    return await send_notification(
        agent_id=agent_id,
        notification_type="hot_lead",
        title="🔥 New Hot Lead",
        message=f"A high-warmth lead ({lead_id}) has been identified and needs attention.",
        lead_id=lead_id,
    )


async def notify_appointment_booked(
    agent_id: str, lead_id: str, appointment: dict
) -> dict:
    """Notify agent of a booked appointment."""
    date_str = appointment.get("date", "TBD")
    time_str = appointment.get("time", "")
    return await send_notification(
        agent_id=agent_id,
        notification_type="appointment_booked",
        title="📅 Appointment Booked",
        message=f"Appointment with lead {lead_id} on {date_str} {time_str}.",
        lead_id=lead_id,
        metadata={"appointment": appointment},
    )


async def notify_ticket_created(agent_id: str, ticket: dict) -> dict:
    """Notify agent of a new support ticket."""
    return await send_notification(
        agent_id=agent_id,
        notification_type="ticket_created",
        title="🎫 New Support Ticket",
        message=f"Ticket #{ticket.get('id', 'N/A')}: {ticket.get('subject', 'No subject')}",
        lead_id=ticket.get("lead_id"),
        metadata={"ticket": ticket},
    )


# ─── Query Notifications ────────────────────────────────────────────────────


async def get_unread_notifications(agent_id: str) -> dict:
    """Fetch unread notification count and list."""
    Notification = _get_models()
    async with _get_session_factory()() as session:
        count_result = await session.execute(
            select(func.count(Notification.id))
            .where(Notification.agent_id == agent_id)
            .where(Notification.is_read == False)
        )
        count = count_result.scalar() or 0

        list_result = await session.execute(
            select(Notification)
            .where(Notification.agent_id == agent_id)
            .where(Notification.is_read == False)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        notifications = [_notif_to_dict(n) for n in list_result.scalars().all()]
        return {"count": count, "notifications": notifications}


async def mark_read(notification_id: str) -> bool:
    """Mark a notification as read."""
    Notification = _get_models()
    async with _get_session_factory()() as session:
        await session.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await session.commit()
        logger.info("notification_marked_read", notif_id=notification_id)
        return True


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _notif_to_dict(n) -> dict:
    return {
        "id": n.id,
        "agent_id": n.agent_id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "lead_id": n.lead_id,
        "metadata": n.metadata if hasattr(n, "metadata") else {},
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
