"""Redis-based session state manager for conversation mode tracking."""

from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import Any, Optional

import redis.asyncio as redis
import structlog

from orchestration.config import settings

logger = structlog.get_logger(__name__)

DEFAULT_TTL = 86400  # 24 hours
LOCK_TTL = 3600  # 1 hour default lock


class ConversationMode(str, enum.Enum):
    AI_MANAGED = "AI_MANAGED"
    HUMAN_HIJACKED = "HUMAN_HIJACKED"


class SessionState:
    """In-memory representation of a phone session."""

    def __init__(
        self,
        phone: str,
        mode: ConversationMode = ConversationMode.AI_MANAGED,
        locked_by: Optional[str] = None,
        locked_at: Optional[str] = None,
        context_snapshot: Optional[dict] = None,
        last_active: Optional[str] = None,
        intent_history: Optional[list] = None,
        qualification_data: Optional[dict] = None,
    ):
        self.phone = phone
        self.mode = mode
        self.locked_by = locked_by
        self.locked_at = locked_at
        self.context_snapshot = context_snapshot or {}
        self.last_active = last_active or datetime.utcnow().isoformat()
        self.intent_history = intent_history or []
        self.qualification_data = qualification_data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "phone": self.phone,
            "mode": self.mode.value,
            "locked_by": self.locked_by,
            "locked_at": self.locked_at,
            "context_snapshot": self.context_snapshot,
            "last_active": self.last_active,
            "intent_history": self.intent_history,
            "qualification_data": self.qualification_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        data = dict(data)
        data["mode"] = ConversationMode(data.get("mode", "AI_MANAGED"))
        return cls(**data)


class StateManager:
    """Manages per-phone conversation state in Redis."""

    _KEY_PREFIX = "session:"
    _LOCK_SUFFIX = ":lock"

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or settings.REDIS_URL
        self._pool: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._pool is None:
            self._pool = redis.from_url(
                self._redis_url, decode_responses=True, max_connections=20
            )
        return self._pool

    def _session_key(self, phone: str) -> str:
        return f"{self._KEY_PREFIX}{phone}"

    def _lock_key(self, phone: str) -> str:
        return f"{self._KEY_PREFIX}{phone}{self._LOCK_SUFFIX}"

    # ── Core state operations ────────────────────────────────────────────

    async def get_session_state(self, phone: str) -> SessionState:
        """Retrieve full session state for a phone number."""
        client = await self._get_client()
        raw = await client.get(self._session_key(phone))
        if raw:
            data = json.loads(raw)
            logger.debug("session.loaded", phone=phone, mode=data.get("mode"))
            return SessionState.from_dict(data)
        logger.debug("session.new", phone=phone)
        return SessionState(phone=phone)

    async def _save_session(
        self, state: SessionState, ttl: int = DEFAULT_TTL
    ) -> None:
        client = await self._get_client()
        await client.set(
            self._session_key(state.phone),
            json.dumps(state.to_dict()),
            ex=ttl,
        )
        logger.debug("session.saved", phone=state.phone, ttl=ttl)

    async def set_session_mode(
        self, phone: str, mode: ConversationMode, actor: Optional[str] = None
    ) -> SessionState:
        """Switch a session between AI_MANAGED and HUMAN_HIJACKED."""
        state = await self.get_session_state(phone)
        old_mode = state.mode
        state.mode = mode
        state.last_active = datetime.utcnow().isoformat()
        await self._save_session(state)
        logger.info(
            "session.mode_changed",
            phone=phone,
            old_mode=old_mode.value,
            new_mode=mode.value,
            actor=actor,
        )
        return state

    # ── Lock mechanism ───────────────────────────────────────────────────

    async def lock_session(
        self, phone: str, agent_id: str, ttl: int = LOCK_TTL
    ) -> bool:
        """
        Lock a session so AI will not respond.
        Returns True if lock acquired, False if already locked by someone else.
        """
        client = await self._get_client()
        lock_key = self._lock_key(phone)
        acquired = await client.set(
            lock_key, agent_id, ex=ttl, nx=True
        )
        if acquired:
            state = await self.set_session_mode(
                phone, ConversationMode.HUMAN_HIJACKED, actor=agent_id
            )
            state.locked_by = agent_id
            state.locked_at = datetime.utcnow().isoformat()
            await self._save_session(state, ttl=ttl)
            logger.info("session.locked", phone=phone, agent=agent_id)
            return True

        existing = await client.get(lock_key)
        logger.warning(
            "session.lock_denied",
            phone=phone,
            requested_by=agent_id,
            held_by=existing,
        )
        return False

    async def unlock_session(self, phone: str, agent_id: str) -> bool:
        """Release lock and return session to AI_MANAGED."""
        client = await self._get_client()
        lock_key = self._lock_key(phone)
        holder = await client.get(lock_key)
        if holder and holder != agent_id:
            logger.warning(
                "session.unlock_denied",
                phone=phone,
                requested_by=agent_id,
                held_by=holder,
            )
            return False
        await client.delete(lock_key)
        state = await self.get_session_state(phone)
        state.locked_by = None
        state.locked_at = None
        await self._save_session(state)
        await self.set_session_mode(
            phone, ConversationMode.AI_MANAGED, actor=agent_id
        )
        logger.info("session.unlocked", phone=phone, agent=agent_id)
        return True

    async def is_ai_allowed(self, phone: str) -> bool:
        """Check whether the AI is currently allowed to respond on this session."""
        client = await self._get_client()
        lock_exists = await client.exists(self._lock_key(phone))
        if lock_exists:
            logger.debug("session.ai_blocked_by_lock", phone=phone)
            return False
        state = await self.get_session_state(phone)
        allowed = state.mode == ConversationMode.AI_MANAGED
        logger.debug("session.ai_check", phone=phone, allowed=allowed, mode=state.mode.value)
        return allowed

    # ── Context snapshot (used by memory_compressor) ─────────────────────

    async def update_context_snapshot(
        self, phone: str, snapshot: dict[str, Any]
    ) -> None:
        state = await self.get_session_state(phone)
        state.context_snapshot = snapshot
        state.last_active = datetime.utcnow().isoformat()
        await self._save_session(state)
        logger.info(
            "session.context_updated", phone=phone, keys=list(snapshot.keys())
        )

    async def get_context_snapshot(self, phone: str) -> dict[str, Any]:
        state = await self.get_session_state(phone)
        return state.context_snapshot

    # ── Intent history bookkeeping ───────────────────────────────────────

    async def append_intent(self, phone: str, intent: str, confidence: float) -> None:
        state = await self.get_session_state(phone)
        state.intent_history.append(
            {
                "intent": intent,
                "confidence": confidence,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        # keep last 50
        state.intent_history = state.intent_history[-50:]
        await self._save_session(state)

    async def update_qualification_data(
        self, phone: str, data: dict[str, Any]
    ) -> None:
        state = await self.get_session_state(phone)
        state.qualification_data.update(data)
        await self._save_session(state)

    # ── Housekeeping ─────────────────────────────────────────────────────

    async def delete_session(self, phone: str) -> None:
        client = await self._get_client()
        await client.delete(self._session_key(phone), self._lock_key(phone))
        logger.info("session.deleted", phone=phone)

    async def close(self) -> None:
        if self._pool:
            await self._pool.aclose()
            self._pool = None


# Singleton used by the rest of the app
state_manager = StateManager()
