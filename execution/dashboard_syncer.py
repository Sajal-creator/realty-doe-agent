"""
Dashboard Syncer - Real-time WebSocket server for live dashboard updates.

Manages WebSocket connections, rooms per agency, authentication,
and broadcasts events to connected dashboard clients.
"""

import asyncio
import json
import time
from enum import Enum
from typing import Any

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class EventType(str, Enum):
    LEAD_NEW = "lead.new"
    LEAD_QUALIFIED = "lead.qualified"
    LEAD_WARMTH_UPDATED = "lead.warmth_updated"
    LEAD_STAGE_CHANGED = "lead.stage_changed"
    CONVERSATION_MESSAGE = "conversation.message"
    CONVERSATION_TYPING = "conversation.typing"
    AGENT_TAKEOVER = "agent.takeover"
    HANDOVER_REQUEST = "handover.request"
    APPOINTMENT_BOOKED = "appointment.booked"
    TICKET_CREATED = "ticket.created"
    NURTURE_SENT = "nurture.sent"
    CONNECTION_STATUS = "connection.status"


class ConnectionInfo:
    """Metadata for a single WebSocket connection."""

    def __init__(self, websocket: WebSocket, agent_id: str, agency_id: str):
        self.websocket = websocket
        self.agent_id = agent_id
        self.agency_id = agency_id
        self.connected_at = time.time()
        self.last_heartbeat = time.time()
        self.is_alive = True


class DashboardConnectionManager:
    """
    Manages WebSocket connections grouped into agency rooms.
    Provides authentication, heartbeat monitoring, and event broadcasting.
    """

    def __init__(self):
        # room_name -> {agent_id: ConnectionInfo}
        self._rooms: dict[str, dict[str, ConnectionInfo]] = {}
        # agent_id -> ConnectionInfo (quick lookup)
        self._connections: dict[str, ConnectionInfo] = {}
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_timeout = 90   # seconds
        self._heartbeat_task: asyncio.Task | None = None

    async def start_heartbeat_monitor(self) -> None:
        """Start background task that pings clients and cleans dead connections."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("heartbeat_monitor_started", interval=self._heartbeat_interval)

    async def stop(self) -> None:
        """Gracefully shut down the manager."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        for agent_id in list(self._connections.keys()):
            await self.disconnect(agent_id)
        logger.info("dashboard_manager_stopped")

    # -- Connection lifecycle --

    async def connect(self, websocket: WebSocket, agent_id: str, agency_id: str) -> bool:
        """
        Accept a WebSocket connection, authenticate, and join the agency room.
        Returns True on success.
        """
        await websocket.accept()

        # Authenticate via first message
        try:
            auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            token = auth_msg.get("token", "")
            if not await self._validate_token(agent_id, agency_id, token):
                await websocket.send_json({"error": "authentication_failed"})
                await websocket.close(code=4001)
                return False
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("auth_failed", agent_id=agent_id, error=str(exc))
            await websocket.close(code=4001)
            return False

        # Disconnect existing connection for this agent (single session)
        if agent_id in self._connections:
            await self.disconnect(agent_id)

        conn = ConnectionInfo(websocket, agent_id, agency_id)
        self._connections[agent_id] = conn

        room = self._room_name(agency_id)
        self._rooms.setdefault(room, {})[agent_id] = conn

        await websocket.send_json({
            "type": "connection.established",
            "agent_id": agent_id,
            "agency_id": agency_id,
            "server_time": time.time(),
        })

        await self.emit_event(room, EventType.CONNECTION_STATUS, {
            "agent_id": agent_id,
            "status": "online",
        })

        logger.info("ws_connected", agent_id=agent_id, agency_id=agency_id)
        return True

    async def disconnect(self, agent_id: str) -> None:
        """Remove an agent's connection and clean up rooms."""
        conn = self._connections.pop(agent_id, None)
        if not conn:
            return

        conn.is_alive = False
        room = self._room_name(conn.agency_id)
        room_members = self._rooms.get(room, {})
        room_members.pop(agent_id, None)
        if not room_members:
            self._rooms.pop(room, None)

        try:
            await conn.websocket.close()
        except Exception:
            pass

        await self.emit_event(room, EventType.CONNECTION_STATUS, {
            "agent_id": agent_id,
            "status": "offline",
        })

        logger.info("ws_disconnected", agent_id=agent_id)

    # -- Room management --

    async def join_agency_room(self, agent_id: str, agency_id: str) -> None:
        """Move an existing connection to a different room (rare edge case)."""
        conn = self._connections.get(agent_id)
        if not conn:
            return

        old_room = self._room_name(conn.agency_id)
        old_members = self._rooms.get(old_room, {})
        old_members.pop(agent_id, None)
        if not old_members:
            self._rooms.pop(old_room, None)

        conn.agency_id = agency_id
        new_room = self._room_name(agency_id)
        self._rooms.setdefault(new_room, {})[agent_id] = conn
        logger.info("room_joined", agent_id=agent_id, room=new_room)

    async def leave_room(self, agent_id: str) -> None:
        """Remove agent from their current room without full disconnect."""
        conn = self._connections.get(agent_id)
        if not conn:
            return
        room = self._room_name(conn.agency_id)
        room_members = self._rooms.get(room, {})
        room_members.pop(agent_id, None)
        if not room_members:
            self._rooms.pop(room, None)

    # -- Event broadcasting --

    async def emit_event(
        self,
        room: str,
        event_type: EventType | str,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast an event to all connections in a room."""
        message = {
            "type": str(event_type) if isinstance(event_type, EventType) else event_type,
            "payload": payload,
            "timestamp": time.time(),
        }
        data = json.dumps(message)
        room_members = self._rooms.get(room, {})
        dead_agents: list[str] = []

        for agent_id, conn in room_members.items():
            if not conn.is_alive:
                dead_agents.append(agent_id)
                continue
            try:
                await conn.websocket.send_text(data)
            except Exception:
                dead_agents.append(agent_id)

        for agent_id in dead_agents:
            await self.disconnect(agent_id)

    async def emit_to_agent(self, agent_id: str, event_type: EventType | str, payload: dict[str, Any]) -> None:
        """Send an event to a specific agent."""
        conn = self._connections.get(agent_id)
        if not conn or not conn.is_alive:
            return
        message = {
            "type": str(event_type) if isinstance(event_type, EventType) else event_type,
            "payload": payload,
            "timestamp": time.time(),
        }
        try:
            await conn.websocket.send_json(message)
        except Exception:
            await self.disconnect(agent_id)

    # -- Heartbeat --

    async def _heartbeat_loop(self) -> None:
        """Ping clients periodically; evict unresponsive ones."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            now = time.time()
            dead: list[str] = []
            for agent_id, conn in self._connections.items():
                if not conn.is_alive:
                    dead.append(agent_id)
                    continue
                if now - conn.last_heartbeat > self._heartbeat_timeout:
                    logger.warning("heartbeat_timeout", agent_id=agent_id)
                    dead.append(agent_id)
                    continue
                try:
                    await conn.websocket.send_json({"type": "ping", "ts": now})
                except Exception:
                    dead.append(agent_id)
            for agent_id in dead:
                await self.disconnect(agent_id)

    async def handle_message(self, agent_id: str, message: dict) -> None:
        """Process an incoming message from a connected agent."""
        msg_type = message.get("type", "")
        if msg_type == "pong":
            conn = self._connections.get(agent_id)
            if conn:
                conn.last_heartbeat = time.time()
        elif msg_type == "subscribe":
            # Future: allow subscribing to specific lead channels
            pass

    # -- Internal helpers --

    @staticmethod
    def _room_name(agency_id: str) -> str:
        return f"agency:{agency_id}"

    async def _validate_token(self, agent_id: str, agency_id: str, token: str) -> bool:
        """Validate auth token against stored credentials (Redis/DB)."""
        # Placeholder - integrate with auth service
        return bool(token)

    def get_room_agents(self, agency_id: str) -> list[str]:
        """Return list of connected agent IDs for an agency."""
        room = self._room_name(agency_id)
        return list(self._rooms.get(room, {}).keys())

    def get_connection_count(self) -> int:
        return len(self._connections)


# Singleton instance
manager = DashboardConnectionManager()


async def listen_for_messages(agent_id: str, websocket: WebSocket) -> None:
    """Message loop for a single WebSocket connection."""
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(agent_id, data)
    except WebSocketDisconnect:
        await manager.disconnect(agent_id)
    except Exception as exc:
        logger.error("ws_error", agent_id=agent_id, error=str(exc))
        await manager.disconnect(agent_id)
