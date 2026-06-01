"""
Hijack Controller - AI kill-switch for human agent takeover.

Allows human agents to take over a conversation from the AI,
and hand back control with a generated context summary.
"""

import asyncio
import time
from enum import Enum
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class SessionControl(str, Enum):
    AI_MANAGED = "AI_MANAGED"
    HUMAN_HIJACKED = "HUMAN_HIJACKED"
    HUMAN_PENDING = "HUMAN_PENDING"
    TRANSITIONING = "TRANSITIONING"


class TakeoverConflict(Exception):
    """Raised when another agent already controls the session."""

    def __init__(self, controlling_agent_id: str):
        self.controlling_agent_id = controlling_agent_id
        super().__init__(f"Session already controlled by agent {controlling_agent_id}")


class HijackController:
    """
    Manages session control between AI and human agents.
    Uses Redis for distributed state so multiple API servers stay in sync.
    """

    REDIS_PREFIX = "hijack:"
    CONTEXT_PREFIX = "handover_ctx:"
    LOCK_TTL = 300  # 5 min lock for takeover

    def __init__(self, redis_client=None, db_session_factory=None, llm_client=None):
        self._redis = redis_client
        self._db_factory = db_session_factory
        self._llm = llm_client

    # -- Core operations --

    async def takeover_session(self, lead_id: str, agent_id: str) -> dict[str, Any]:
        """
        Human agent requests control of a conversation.
        Flips session to HUMAN_HIJACKED and disconnects AI.

        Raises TakeoverConflict if another agent already controls it.
        """
        current = await self.get_session_control_status(lead_id)

        if current["status"] == SessionControl.HUMAN_HIJACKED:
            if current["agent_id"] != agent_id:
                raise TakeoverConflict(current["agent_id"])
            # Already controlling
            return {"status": "already_controlled", "agent_id": agent_id}

        # Attempt atomic lock acquisition
        lock_key = f"{self.REDIS_PREFIX}{lead_id}"
        acquired = await self._acquire_lock(lock_key, agent_id)
        if not acquired:
            existing = await self._get_lock_owner(lock_key)
            raise TakeoverConflict(existing)

        # Update session control in DB
        await self._update_session_control(lead_id, SessionControl.HUMAN_HIJACKED, agent_id)

        # Disconnect AI processing for this lead
        await self._disconnect_ai(lead_id)

        # Generate context summary for the human agent
        context = await self._build_takeover_context(lead_id)

        logger.info("session_hijacked", lead_id=lead_id, agent_id=agent_id)

        return {
            "status": "hijacked",
            "lead_id": lead_id,
            "agent_id": agent_id,
            "context_summary": context,
        }

    async def handback_to_ai(self, lead_id: str, agent_id: str) -> dict[str, Any]:
        """
        Return conversation control to AI with a handover context summary.
        """
        current = await self.get_session_control_status(lead_id)

        if current["status"] != SessionControl.HUMAN_HIJACKED:
            return {"status": "not_hijacked", "message": "Session is not under human control"}

        if current["agent_id"] != agent_id:
            return {"status": "not_owner", "message": f"Controlled by {current['agent_id']}"}

        # Build handover summary from human conversation
        summary = await self._build_handover_summary(lead_id, agent_id)

        # Update session control
        await self._update_session_control(lead_id, SessionControl.AI_MANAGED, None)

        # Release lock
        lock_key = f"{self.REDIS_PREFIX}{lead_id}"
        await self._release_lock(lock_key)

        # Store handover context for AI to consume
        await self._store_handover_context(lead_id, summary)

        # Re-engage AI processing
        await self._reconnect_ai(lead_id)

        logger.info("session_handed_back", lead_id=lead_id, agent_id=agent_id)

        return {
            "status": "handed_back",
            "lead_id": lead_id,
            "handover_summary": summary,
        }

    async def get_session_control_status(self, lead_id: str) -> dict[str, Any]:
        """Check who currently controls the conversation."""
        # Try Redis first for speed
        if self._redis:
            data = await self._redis.hgetall(f"{self.REDIS_PREFIX}status:{lead_id}")
            if data:
                return {
                    "lead_id": lead_id,
                    "status": SessionControl(data.get("status", "AI_MANAGED")),
                    "agent_id": data.get("agent_id"),
                    "since": float(data.get("since", 0)),
                }

        # Fallback to DB
        db_status = await self._query_session_control(lead_id)
        return db_status or {
            "lead_id": lead_id,
            "status": SessionControl.AI_MANAGED,
            "agent_id": None,
            "since": None,
        }

    async def warn_pending_takeover(self, lead_id: str, agent_id: str) -> dict[str, Any]:
        """
        When a second agent tries to take over, send them a warning
        without granting control.
        """
        current = await self.get_session_control_status(lead_id)
        logger.warning(
            "takeover_conflict",
            lead_id=lead_id,
            requesting_agent=agent_id,
            controlling_agent=current["agent_id"],
        )
        return {
            "status": "conflict",
            "message": f"Session is already controlled by agent {current['agent_id']}",
            "controlling_agent": current["agent_id"],
        }

    # -- Context building --

    async def _build_takeover_context(self, lead_id: str) -> dict[str, Any]:
        """Build context summary when human takes over from AI."""
        # Fetch recent conversation history
        messages = await self._fetch_recent_messages(lead_id, limit=50)
        lead_info = await self._fetch_lead_info(lead_id)

        if not self._llm:
            return {"messages": messages, "lead": lead_info}

        prompt = (
            "Summarize this real estate conversation for a human agent taking over. "
            "Include: lead's property preferences, budget, timeline, concerns, "
            "and what the AI has discussed so far.\n\n"
            f"Lead info: {lead_info}\n\n"
            f"Recent messages: {messages[-20:]}"
        )

        summary = await self._llm.generate(prompt)
        return {
            "summary": summary,
            "lead": lead_info,
            "message_count": len(messages),
            "last_messages": messages[-5:],
        }

    async def _build_handover_summary(self, lead_id: str, agent_id: str) -> dict[str, Any]:
        """Build summary of human conversation to hand back to AI."""
        messages = await self._fetch_messages_since_hijack(lead_id)

        if not self._llm:
            return {"messages": messages}

        prompt = (
            "Summarize this human agent conversation with a real estate lead. "
            "The AI will resume, so include: decisions made, commitments given, "
            "next steps agreed upon, and any updated preferences.\n\n"
            f"Messages: {messages[-30:]}"
        )

        summary = await self._llm.generate(prompt)
        return {
            "summary": summary,
            "agent_id": agent_id,
            "message_count": len(messages),
        }

    # -- Redis helpers --

    async def _acquire_lock(self, key: str, agent_id: str) -> bool:
        if not self._redis:
            return True
        result = await self._redis.set(
            key, agent_id, nx=True, ex=self.LOCK_TTL,
        )
        return bool(result)

    async def _release_lock(self, key: str) -> None:
        if self._redis:
            await self._redis.delete(key)

    async def _get_lock_owner(self, key: str) -> str:
        if self._redis:
            owner = await self._redis.get(key)
            return owner if owner else "unknown"
        return "unknown"

    # -- DB / external stubs (integrate with your models) --

    async def _update_session_control(
        self, lead_id: str, status: SessionControl, agent_id: str | None,
    ) -> None:
        if self._redis:
            await self._redis.hset(
                f"{self.REDIS_PREFIX}status:{lead_id}",
                mapping={"status": status.value, "agent_id": agent_id or "", "since": str(time.time())},
            )
        logger.debug("session_control_updated", lead_id=lead_id, status=status.value)

    async def _query_session_control(self, lead_id: str) -> dict[str, Any] | None:
        return None  # Implement with DB query

    async def _disconnect_ai(self, lead_id: str) -> None:
        """Signal the AI conversation engine to stop processing for this lead."""
        if self._redis:
            await self._redis.publish(f"ai_control:{lead_id}", "disconnect")
        logger.debug("ai_disconnected", lead_id=lead_id)

    async def _reconnect_ai(self, lead_id: str) -> None:
        """Signal the AI to resume processing."""
        if self._redis:
            await self._redis.publish(f"ai_control:{lead_id}", "reconnect")
        logger.debug("ai_reconnected", lead_id=lead_id)

    async def _fetch_recent_messages(self, lead_id: str, limit: int = 50) -> list[dict]:
        return []  # Implement with DB query

    async def _fetch_messages_since_hijack(self, lead_id: str) -> list[dict]:
        return []  # Implement with DB query

    async def _fetch_lead_info(self, lead_id: str) -> dict[str, Any]:
        return {}  # Implement with DB query

    async def _store_handover_context(self, lead_id: str, summary: dict) -> None:
        if self._redis:
            import json
            await self._redis.set(
                f"{self.CONTEXT_PREFIX}{lead_id}",
                json.dumps(summary),
                ex=86400,
            )
