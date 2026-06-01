"""
Agent Router - Multi-agent load balancer for lead assignment.

Distributes leads across human agents using round-robin with
workload-aware balancing. Tracks online/offline status via Redis.
"""

import asyncio
import time
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class AgentStatus:
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    AWAY = "away"


class AgentRouter:
    """
    Routes leads to available agents within an agency.
    Uses round-robin with workload awareness.
    """

    REDIS_AGENTS_KEY = "router:agents:{agency_id}"
    REDIS_WORKLOAD_KEY = "router:workload:{agent_id}"
    REDIS_STATUS_KEY = "router:status:{agent_id}"
    REDIS_ROUND_ROBIN_KEY = "router:round_robin:{agency_id}"
    MAX_CONCURRENT_LEADS = 20  # per agent

    def __init__(self, redis_client=None, db_session_factory=None):
        self._redis = redis_client
        self._db_factory = db_session_factory

    # -- Agent discovery --

    async def find_available_agent(self, agency_id: str) -> dict[str, Any] | None:
        """
        Find the best available agent using round-robin with workload balancing.
        Returns agent info dict or None if no agents available.
        """
        agents = await self._get_agency_agents(agency_id)
        if not agents:
            logger.warning("no_agents_in_agency", agency_id=agency_id)
            return None

        # Filter to online agents only
        available = []
        for agent in agents:
            status = await self.get_agent_status(agent["agent_id"])
            if status == AgentStatus.ONLINE:
                workload = await self.get_agent_workload(agent["agent_id"])
                if workload < self.MAX_CONCURRENT_LEADS:
                    available.append({**agent, "workload": workload})

        if not available:
            logger.warning("no_available_agents", agency_id=agency_id)
            return None

        # Sort by workload (ascending), then round-robin tiebreaker
        available.sort(key=lambda a: a["workload"])
        min_workload = available[0]["workload"]
        candidates = [a for a in available if a["workload"] == min_workload]

        # Round-robin among candidates with equal workload
        idx = await self._next_round_robin(agency_id, len(candidates))
        selected = candidates[idx]

        logger.info(
            "agent_selected",
            agent_id=selected["agent_id"],
            agency_id=agency_id,
            workload=selected["workload"],
        )
        return selected

    async def get_agent_workload(self, agent_id: str) -> int:
        """Count active AI_MANAGED + HUMAN_HIJACKED sessions for an agent."""
        if self._redis:
            count = await self._redis.get(self.REDIS_WORKLOAD_KEY.format(agent_id=agent_id))
            return int(count) if count else 0
        return await self._db_get_workload(agent_id)

    async def get_agent_status(self, agent_id: str) -> str:
        """Get agent's current status from Redis."""
        if self._redis:
            status = await self._redis.get(self.REDIS_STATUS_KEY.format(agent_id=agent_id))
            return status or AgentStatus.OFFLINE
        return AgentStatus.OFFLINE

    # -- Assignment --

    async def assign_lead_to_agent(self, lead_id: str, agent_id: str) -> dict[str, Any]:
        """Assign a lead to a specific agent and update workload."""
        await self._db_assign_lead(lead_id, agent_id)
        await self._increment_workload(agent_id)
        logger.info("lead_assigned", lead_id=lead_id, agent_id=agent_id)
        return {"lead_id": lead_id, "agent_id": agent_id, "status": "assigned"}

    async def reassign_lead(self, lead_id: str, new_agent_id: str) -> dict[str, Any]:
        """Transfer a lead from one agent to another."""
        old_agent_id = await self._db_get_lead_agent(lead_id)
        if old_agent_id:
            await self._decrement_workload(old_agent_id)

        await self._db_assign_lead(lead_id, new_agent_id)
        await self._increment_workload(new_agent_id)

        logger.info(
            "lead_reassigned",
            lead_id=lead_id,
            from_agent=old_agent_id,
            to_agent=new_agent_id,
        )
        return {
            "lead_id": lead_id,
            "old_agent_id": old_agent_id,
            "new_agent_id": new_agent_id,
            "status": "reassigned",
        }

    # -- Status tracking --

    async def set_agent_online(self, agent_id: str, agency_id: str) -> None:
        """Mark agent as online."""
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.set(self.REDIS_STATUS_KEY.format(agent_id=agent_id), AgentStatus.ONLINE, ex=300)
            pipe.sadd(self.REDIS_AGENTS_KEY.format(agency_id=agency_id), agent_id)
            await pipe.execute()
        logger.info("agent_online", agent_id=agent_id)

    async def set_agent_offline(self, agent_id: str, agency_id: str) -> None:
        """Mark agent as offline."""
        if self._redis:
            await self._redis.set(
                self.REDIS_STATUS_KEY.format(agent_id=agent_id),
                AgentStatus.OFFLINE,
                ex=300,
            )
        logger.info("agent_offline", agent_id=agent_id)

    async def refresh_agent_heartbeat(self, agent_id: str) -> None:
        """Refresh agent's online status TTL (call periodically)."""
        if self._redis:
            status = await self._redis.get(self.REDIS_STATUS_KEY.format(agent_id=agent_id))
            if status and status != AgentStatus.OFFLINE:
                await self._redis.expire(
                    self.REDIS_STATUS_KEY.format(agent_id=agent_id), 300,
                )

    # -- Internal helpers --

    async def _get_agency_agents(self, agency_id: str) -> list[dict[str, Any]]:
        """Get all registered agents for an agency."""
        if self._redis:
            agent_ids = await self._redis.smembers(
                self.REDIS_AGENTS_KEY.format(agency_id=agency_id)
            )
            return [{"agent_id": aid, "agency_id": agency_id} for aid in agent_ids]
        return await self._db_get_agency_agents(agency_id)

    async def _next_round_robin(self, agency_id: str, pool_size: int) -> int:
        """Get next round-robin index for an agency."""
        if self._redis:
            idx = await self._redis.incr(self.REDIS_ROUND_ROBIN_KEY.format(agency_id=agency_id))
            return idx % pool_size
        return 0

    async def _increment_workload(self, agent_id: str) -> None:
        if self._redis:
            await self._redis.incr(self.REDIS_WORKLOAD_KEY.format(agent_id=agent_id))

    async def _decrement_workload(self, agent_id: str) -> None:
        if self._redis:
            key = self.REDIS_WORKLOAD_KEY.format(agent_id=agent_id)
            current = await self._redis.get(key)
            if current and int(current) > 0:
                await self._redis.decr(key)

    # -- DB stubs --

    async def _db_assign_lead(self, lead_id: str, agent_id: str) -> None:
        """Update lead assignment in database."""
        pass  # Implement with SQLAlchemy

    async def _db_get_lead_agent(self, lead_id: str) -> str | None:
        """Get currently assigned agent for a lead."""
        return None  # Implement with SQLAlchemy

    async def _db_get_workload(self, agent_id: str) -> int:
        return 0  # Implement with SQLAlchemy

    async def _db_get_agency_agents(self, agency_id: str) -> list[dict[str, Any]]:
        return []  # Implement with SQLAlchemy
