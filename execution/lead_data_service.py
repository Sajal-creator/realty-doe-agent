"""Database CRUD operations for leads, sessions, messages, and qualifications."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Import models - these will be defined in the models layer
# Using string references to avoid circular imports at module level
def _get_session_factory():
    from database.session import async_session_factory
    return async_session_factory


def _get_models():
    from database.models import (
        Lead, ConversationSession, Message, QualificationMatrix, Notification,
    )
    return Lead, ConversationSession, Message, QualificationMatrix, Notification


# ─── Lead CRUD ───────────────────────────────────────────────────────────────


async def create_lead(data: dict[str, Any]) -> dict:
    """Create a new lead record."""
    Lead, *_ = _get_models()
    async with _get_session_factory()() as session:
        lead = Lead(
            id=str(uuid.uuid4()),
            name=data.get("name"),
            phone=data.get("phone"),
            email=data.get("email"),
            source=data.get("source", "whatsapp"),
            status=data.get("status", "new"),
            agent_id=data.get("agent_id"),
            preferences=data.get("preferences", {}),
            metadata=data.get("metadata", {}),
            warmth_score=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        logger.info("lead_created", lead_id=lead.id, phone=data.get("phone"))
        return _lead_to_dict(lead)


async def get_lead(lead_id: str) -> Optional[dict]:
    """Get a lead by ID."""
    Lead, *_ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        return _lead_to_dict(lead) if lead else None


async def get_lead_by_phone(phone: str) -> Optional[dict]:
    """Get a lead by phone number."""
    Lead, *_ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(select(Lead).where(Lead.phone == phone))
        lead = result.scalar_one_or_none()
        return _lead_to_dict(lead) if lead else None


async def update_lead(lead_id: str, data: dict[str, Any]) -> Optional[dict]:
    """Update lead fields."""
    Lead, *_ = _get_models()
    data["updated_at"] = datetime.now(timezone.utc)
    async with _get_session_factory()() as session:
        await session.execute(
            update(Lead).where(Lead.id == lead_id).values(**data)
        )
        await session.commit()
        return await get_lead(lead_id)


# ─── Session CRUD ────────────────────────────────────────────────────────────


async def create_session(lead_id: str) -> dict:
    """Create a new conversation session for a lead."""
    _, ConversationSession, *_ = _get_models()
    async with _get_session_factory()() as session:
        cs = ConversationSession(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            status="active",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        session.add(cs)
        await session.commit()
        await session.refresh(cs)
        logger.info("session_created", session_id=cs.id, lead_id=lead_id)
        return _session_to_dict(cs)


async def get_active_session(lead_id: str) -> Optional[dict]:
    """Get the active session for a lead."""
    _, ConversationSession, *_ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(
            select(ConversationSession)
            .where(ConversationSession.lead_id == lead_id)
            .where(ConversationSession.status == "active")
            .order_by(ConversationSession.started_at.desc())
            .limit(1)
        )
        cs = result.scalar_one_or_none()
        return _session_to_dict(cs) if cs else None


async def close_session(session_id: str) -> bool:
    """Close a conversation session."""
    _, ConversationSession, *_ = _get_models()
    async with _get_session_factory()() as session:
        await session.execute(
            update(ConversationSession)
            .where(ConversationSession.id == session_id)
            .values(status="closed", ended_at=datetime.now(timezone.utc))
        )
        await session.commit()
        logger.info("session_closed", session_id=session_id)
        return True


# ─── Message CRUD ────────────────────────────────────────────────────────────


async def add_message(
    session_id: str,
    sender_type: str,
    content: str,
    message_type: str = "text",
) -> dict:
    """Add a message to a conversation session."""
    _, _, Message, *_ = _get_models()
    async with _get_session_factory()() as session:
        msg = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            sender_type=sender_type,
            content=content,
            message_type=message_type,
            created_at=datetime.now(timezone.utc),
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return _message_to_dict(msg)


async def get_messages(session_id: str, limit: int = 50) -> list[dict]:
    """Get messages for a session, newest first."""
    _, _, Message, *_ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return [_message_to_dict(m) for m in result.scalars().all()]


# ─── Qualification CRUD ─────────────────────────────────────────────────────


async def update_qualification(lead_id: str, matrix_data: dict) -> dict:
    """Create or update qualification matrix for a lead."""
    _, _, _, QualificationMatrix, _ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(
            select(QualificationMatrix).where(QualificationMatrix.lead_id == lead_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in matrix_data.items():
                setattr(existing, k, v)
            existing.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(existing)
            return _qual_to_dict(existing)
        else:
            qm = QualificationMatrix(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                **matrix_data,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(qm)
            await session.commit()
            await session.refresh(qm)
            return _qual_to_dict(qm)


async def get_qualification(lead_id: str) -> Optional[dict]:
    """Get qualification matrix for a lead."""
    _, _, _, QualificationMatrix, _ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(
            select(QualificationMatrix).where(QualificationMatrix.lead_id == lead_id)
        )
        qm = result.scalar_one_or_none()
        return _qual_to_dict(qm) if qm else None


# ─── Warmth & Timeline ──────────────────────────────────────────────────────


async def update_warmth_score(lead_id: str, score: float) -> bool:
    """Update the warmth score for a lead."""
    return (await update_lead(lead_id, {"warmth_score": score})) is not None


async def get_lead_timeline(lead_id: str) -> list[dict]:
    """Get full timeline of lead interactions (sessions + messages)."""
    _, ConversationSession, Message, _, _ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(
            select(ConversationSession)
            .where(ConversationSession.lead_id == lead_id)
            .order_by(ConversationSession.started_at.asc())
        )
        sessions = result.scalars().all()
        timeline = []
        for cs in sessions:
            msg_result = await session.execute(
                select(Message)
                .where(Message.session_id == cs.id)
                .order_by(Message.created_at.asc())
            )
            messages = [_message_to_dict(m) for m in msg_result.scalars().all()]
            timeline.append({
                "type": "session",
                "session": _session_to_dict(cs),
                "messages": messages,
            })
        return timeline


# ─── Search & Pipeline ──────────────────────────────────────────────────────


async def search_leads(
    query: str, filters: Optional[dict] = None
) -> list[dict]:
    """Search leads by name, phone, or email with optional filters."""
    Lead, *_ = _get_models()
    async with _get_session_factory()() as session:
        stmt = select(Lead)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Lead.name.ilike(pattern),
                    Lead.phone.ilike(pattern),
                    Lead.email.ilike(pattern),
                )
            )
        if filters:
            if "status" in filters:
                stmt = stmt.where(Lead.status == filters["status"])
            if "agent_id" in filters:
                stmt = stmt.where(Lead.agent_id == filters["agent_id"])
            if "min_warmth" in filters:
                stmt = stmt.where(Lead.warmth_score >= filters["min_warmth"])
        stmt = stmt.order_by(Lead.updated_at.desc()).limit(filters.get("limit", 50) if filters else 50)
        result = await session.execute(stmt)
        return [_lead_to_dict(l) for l in result.scalars().all()]


async def get_pipeline_leads(agent_id: str) -> list[dict]:
    """Get all active leads in an agent's pipeline."""
    Lead, *_ = _get_models()
    async with _get_session_factory()() as session:
        result = await session.execute(
            select(Lead)
            .where(Lead.agent_id == agent_id)
            .where(Lead.status.in_(["new", "contacted", "qualified", "negotiating"]))
            .order_by(Lead.warmth_score.desc())
        )
        return [_lead_to_dict(l) for l in result.scalars().all()]


# ─── Dict Converters ────────────────────────────────────────────────────────


def _lead_to_dict(lead) -> dict:
    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "source": lead.source,
        "status": lead.status,
        "agent_id": lead.agent_id,
        "preferences": lead.preferences if hasattr(lead, "preferences") else {},
        "metadata": lead.metadata if hasattr(lead, "metadata") else {},
        "warmth_score": float(lead.warmth_score) if lead.warmth_score else 0.0,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def _session_to_dict(cs) -> dict:
    return {
        "id": cs.id,
        "lead_id": cs.lead_id,
        "status": cs.status,
        "started_at": cs.started_at.isoformat() if cs.started_at else None,
        "ended_at": cs.ended_at.isoformat() if hasattr(cs, "ended_at") and cs.ended_at else None,
    }


def _message_to_dict(msg) -> dict:
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "sender_type": msg.sender_type,
        "content": msg.content,
        "message_type": msg.message_type,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _qual_to_dict(qm) -> dict:
    return {
        "id": qm.id,
        "lead_id": qm.lead_id,
        "created_at": qm.created_at.isoformat() if qm.created_at else None,
        "updated_at": qm.updated_at.isoformat() if qm.updated_at else None,
    }
