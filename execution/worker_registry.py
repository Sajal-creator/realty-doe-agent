"""Worker registry – maps tool names to execution functions.

This is a stub that will be expanded as execution workers are built out.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

# Type alias for async worker functions
WorkerFn = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]

# Registry: tool_name → worker function
_WORKERS: dict[str, WorkerFn] = {}

# Tool definitions for LLM function calling
_TOOL_DEFS: list[dict] = []


def register_worker(
    name: str,
    description: str,
    parameters: dict,
    fn: WorkerFn,
) -> None:
    """Register a worker function with its tool schema."""
    _WORKERS[name] = fn
    _TOOL_DEFS.append(
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
    )
    logger.info("worker.registered", name=name)


def get_tool_definitions() -> list[dict]:
    """Return all registered tool schemas for LLM function calling."""
    return list(_TOOL_DEFS)


async def execute_worker(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Execute a registered worker by name."""
    if name not in _WORKERS:
        raise ValueError(f"Unknown worker: {name}")
    logger.info("worker.executing", name=name, params=params)
    return await _WORKERS[name](params)


# ── Built-in stub workers (replace with real implementations) ────────────

async def _search_properties_stub(params: dict) -> dict:
    return {"results": [], "note": "stub – real MLS search not yet wired"}


async def _schedule_showing_stub(params: dict) -> dict:
    return {"status": "pending", "note": "stub – calendar integration not yet wired"}


async def _send_message_stub(params: dict) -> dict:
    return {"status": "sent", "note": "stub – WhatsApp gateway not yet wired"}


async def _get_lead_info_stub(params: dict) -> dict:
    return {"lead": None, "note": "stub – DB lookup not yet wired"}


register_worker(
    name="search_properties",
    description="Search MLS listings by criteria (bedrooms, budget, location, etc.)",
    parameters={
        "type": "object",
        "properties": {
            "bedrooms": {"type": "integer"},
            "bathrooms": {"type": "integer"},
            "budget_min": {"type": "number"},
            "budget_max": {"type": "number"},
            "city": {"type": "string"},
            "zip_code": {"type": "string"},
        },
    },
    fn=_search_properties_stub,
)

register_worker(
    name="schedule_showing",
    description="Schedule a property showing or call appointment",
    parameters={
        "type": "object",
        "properties": {
            "property_address": {"type": "string"},
            "preferred_date": {"type": "string"},
            "preferred_time": {"type": "string"},
            "phone": {"type": "string"},
        },
        "required": ["phone"],
    },
    fn=_schedule_showing_stub,
)

register_worker(
    name="send_whatsapp_message",
    description="Send a WhatsApp message to a phone number",
    parameters={
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["phone", "message"],
    },
    fn=_send_message_stub,
)

register_worker(
    name="get_lead_info",
    description="Retrieve lead information and qualification data",
    parameters={
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
        },
        "required": ["phone"],
    },
    fn=_get_lead_info_stub,
)
