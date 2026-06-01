"""Main cognitive controller – the DOE orchestration brain."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog

from orchestration.config import settings
from execution.llm_client import LLMClient
from orchestration.intent_router import IntentResult, intent_router
from orchestration.memory_compressor import memory_compressor
from orchestration.state_manager import ConversationMode, state_manager

logger = structlog.get_logger(__name__)

DIRECTIVES_DIR = Path(getattr(settings, "DIRECTIVES_DIR", "/home/ubuntu/realty-doe-agent/directives"))
MAX_RETRIES = 2
HISTORY_WINDOW = 15  # last N messages pulled from DB


# ── Directive loader ─────────────────────────────────────────────────────

def load_directives(directory: Path = DIRECTIVES_DIR) -> str:
    """Read all .md files from the directives folder and concatenate."""
    if not directory.exists():
        logger.warning("directives.directory_missing", path=str(directory))
        return ""
    blocks: list[str] = []
    for md_file in sorted(directory.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8").strip()
            blocks.append(f"### {md_file.stem}\n{content}")
        except Exception as exc:
            logger.error("directives.load_failed", file=str(md_file), error=str(exc))
    logger.info("directives.loaded", count=len(blocks), files=[f.name for f in sorted(directory.glob("*.md"))])
    return "\n\n---\n\n".join(blocks)


# ── Database helpers (thin wrappers – real impl lives in db/ layer) ──────

async def fetch_conversation_history(
    phone: str, limit: int = HISTORY_WINDOW
) -> list[dict[str, str]]:
    """Pull the last N messages for this phone from the DB."""
    try:
        from db.message_repository import get_recent_messages  # deferred to avoid circular
    except ImportError:
        logger.debug("db.message_repository_unavailable", phone=phone)
        return []

    rows = await get_recent_messages(phone, limit=limit)
    messages: list[dict[str, str]] = []
    for row in rows:
        messages.append(
            {
                "role": "user" if row.get("direction") == "inbound" else "assistant",
                "content": row.get("body", ""),
            }
        )
    return list(reversed(messages))  # chronological order


async def fetch_qualification_matrix(phone: str) -> dict[str, Any]:
    """Pull lead qualification data from the DB."""
    try:
        from db.lead_repository import get_lead_by_phone  # deferred
    except ImportError:
        logger.debug("db.lead_repository_unavailable", phone=phone)
        return {}

    lead = await get_lead_by_phone(phone)
    if not lead:
        return {}
    return lead.get("qualification_data", {})


async def persist_message(
    phone: str, direction: str, body: str, metadata: Optional[dict] = None
) -> None:
    """Save a message to the DB."""
    try:
        from db.message_repository import save_message  # deferred
    except ImportError:
        logger.debug("db.persist_unavailable", phone=phone)
        return

    await save_message(phone=phone, direction=direction, body=body, metadata=metadata or {})


# ── WebSocket event emitter ─────────────────────────────────────────────

async def emit_ws_event(event_type: str, payload: dict[str, Any]) -> None:
    """Broadcast a state-change event to connected WebSocket clients."""
    try:
        from api.ws_manager import broadcast  # deferred
    except ImportError:
        logger.debug("ws.broadcast_unavailable", event=event_type)
        return

    await broadcast({"event": event_type, "payload": payload, "ts": datetime.utcnow().isoformat()})


# ── Orchestrator ─────────────────────────────────────────────────────────

class Orchestrator:
    """
    Cognitive controller that coordinates directives, intent routing,
    tool execution, and response generation.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm = llm_client or LLMClient()
        self._directives_cache: Optional[str] = None
        self._directives_mtime: float = 0.0

    # ── Directive management ─────────────────────────────────────────────

    def _get_directives(self) -> str:
        """Load directives with filesystem mtime-based cache invalidation."""
        try:
            current_mtime = DIRECTIVES_DIR.stat().st_mtime if DIRECTIVES_DIR.exists() else 0.0
        except OSError:
            current_mtime = 0.0

        if self._directives_cache is None or current_mtime != self._directives_mtime:
            self._directives_cache = load_directives()
            self._directives_mtime = current_mtime
        return self._directives_cache

    # ── System prompt construction ───────────────────────────────────────

    def _build_system_prompt(
        self,
        conversation_history: list[dict[str, str]],
        qualification: dict[str, Any],
        context_snapshot: Optional[dict[str, Any]],
        skills_description: str = "",
    ) -> str:
        directives = self._get_directives()
        sections = [
            "You are a professional real-estate AI assistant. Follow ALL directives strictly.",
            "",
            "## DIRECTIVES",
            directives or "(no directives loaded)",
            "",
            "## LEAD QUALIFICATION MATRIX",
            json.dumps(qualification, indent=2) if qualification else "(no data yet)",
            "",
        ]
        if context_snapshot:
            sections.extend([
                "## CONVERSATION CONTEXT SNAPSHOT (compressed memory)",
                json.dumps(context_snapshot, indent=2),
                "",
            ])
        if skills_description:
            sections.extend(["## AVAILABLE SKILLS / TOOLS", skills_description, ""])

        sections.append(
            "## RULES\n"
            "- Always be helpful, professional, and concise.\n"
            "- Never invent property listings – use real data from tools.\n"
            "- Escalate to human if explicitly requested or if confidence is low.\n"
            "- Respect the qualification flow defined in directives.\n"
        )
        return "\n".join(sections)

    # ── Agentic loop ────────────────────────────────────────────────────

    async def process_incoming_message(
        self, phone: str, message_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Main entry point: receive a WhatsApp message, process through the
        full agentic loop, and return the assistant response.
        """
        body = message_data.get("body", "").strip()
        if not body:
            logger.warning("orchestrator.empty_message", phone=phone)
            return {"status": "ignored", "reason": "empty"}

        logger.info("orchestrator.incoming", phone=phone, preview=body[:100])

        # 1. Check session state – is AI allowed to respond?
        await emit_ws_event("message.received", {"phone": phone, "body": body})

        ai_allowed = await state_manager.is_ai_allowed(phone)
        if not ai_allowed:
            logger.info("orchestrator.ai_blocked", phone=phone)
            await emit_ws_event("message.hijacked", {"phone": phone})
            return {"status": "blocked", "reason": "human_hijacked"}

        # 2. Persist inbound message
        await persist_message(phone, "inbound", body, message_data)

        # 3. Reconstitute session context
        session = await state_manager.get_session_state(phone)
        conversation_history = await fetch_conversation_history(phone, limit=HISTORY_WINDOW)
        qualification = await fetch_qualification_matrix(phone)
        context_snapshot = session.context_snapshot

        # 4. Memory compression check
        compressed = await memory_compressor.maybe_compress(conversation_history)
        if compressed:
            context_snapshot = compressed
            await state_manager.update_context_snapshot(phone, compressed)
            await emit_ws_event("memory.compressed", {"phone": phone, "turns": compressed.get("turns_compressed")})

        # 5. Classify intent
        await emit_ws_event("intent.classifying", {"phone": phone})
        intent_result: IntentResult = await intent_router.classify(
            message=body, conversation_history=conversation_history
        )
        await state_manager.append_intent(phone, intent_result.primary.value, intent_result.confidence)
        await emit_ws_event(
            "intent.classified",
            {
                "phone": phone,
                "primary": intent_result.primary.value,
                "confidence": intent_result.confidence,
                "secondary": [s[0].value for s in intent_result.secondary],
                "entities": intent_result.entities,
            },
        )

        # 6. Store extracted entities into qualification data
        if intent_result.entities:
            await state_manager.update_qualification_data(phone, intent_result.entities)
            qualification.update(intent_result.entities)

        # 7. Build system prompt & generate response (with tool-calling loop)
        system_prompt = self._build_system_prompt(
            conversation_history=conversation_history,
            qualification=qualification,
            context_snapshot=context_snapshot,
        )

        # Augment conversation with user message for LLM
        llm_messages = [{"role": "system", "content": system_prompt}]
        llm_messages.extend(conversation_history)
        llm_messages.append({"role": "user", "content": body})

        response_text = await self.generate_response(
            context={
                "phone": phone,
                "messages": llm_messages,
                "intent": intent_result,
                "session": session,
            }
        )

        # 8. Persist outbound message
        await persist_message(phone, "outbound", response_text, {"intent": intent_result.primary.value})

        await emit_ws_event("message.sent", {"phone": phone, "body": response_text})

        return {
            "status": "sent",
            "response": response_text,
            "intent": intent_result.primary.value,
            "confidence": intent_result.confidence,
        }

    async def generate_response(self, context: dict[str, Any]) -> str:
        """
        Generate an assistant response, handling tool calls iteratively.
        Implements the agentic loop: LLM → tool call → feed result back → repeat.
        """
        messages = context["messages"]
        intent: IntentResult = context.get("intent")

        # Register available tools from execution layer
        tools = self._get_available_tools()

        for iteration in range(MAX_RETRIES + 1):
            await emit_ws_event("llm.generating", {"phone": context["phone"], "iteration": iteration})

            try:
                response = await self._llm.function_call(
                    messages=messages,
                    tools=tools if tools else None,
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                )
            except Exception as exc:
                logger.error("llm.call_failed", iteration=iteration, error=str(exc))
                if iteration < MAX_RETRIES:
                    continue
                return "I'm sorry, I'm having trouble processing that right now. Let me connect you with our team."

            choice = response["choices"][0]
            message = choice["message"]

            # No tool call – return text
            if not message.get("tool_calls"):
                text = message.get("content", "")
                logger.info("orchestrator.response_generated", phone=context["phone"], chars=len(text))
                return text or "I'd be happy to help! Could you give me a bit more detail?"

            # Tool call(s) present – execute them
            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                fn_args = tool_call["function"].get("arguments", "{}")
                if isinstance(fn_args, str):
                    fn_args = json.loads(fn_args)

                await emit_ws_event("tool.executing", {
                    "phone": context["phone"],
                    "tool": fn_name,
                    "args": fn_args,
                })

                result = await self.handle_tool_call(fn_name, fn_args)

                # Feed tool result back into conversation
                messages.append(message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                })

            # Loop back for next LLM call with tool results

        return "I want to make sure I get this right. Let me have a team member follow up with you shortly."

    async def handle_tool_call(
        self, tool_name: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a tool call. Self-anneals: if the worker fails,
        logs the error and returns a graceful fallback.
        """
        logger.info("orchestrator.tool_call", tool=tool_name, params=params)

        try:
            from execution.worker_registry import execute_worker  # deferred

            result = await execute_worker(tool_name, params)
            await emit_ws_event("tool.completed", {"tool": tool_name, "success": True})
            return result
        except Exception as exc:
            logger.error(
                "orchestrator.tool_failed",
                tool=tool_name,
                error=str(exc),
                params=params,
            )
            await emit_ws_event("tool.failed", {"tool": tool_name, "error": str(exc)})

            # Self-annealing: try once more with adjusted params
            return await self._anneal_and_retry(tool_name, params, exc)

    async def _anneal_and_retry(
        self,
        tool_name: str,
        params: dict[str, Any],
        original_error: Exception,
    ) -> dict[str, Any]:
        """
        Self-annealing: intercept failure, adjust parameters, retry once.
        """
        logger.info("orchestrator.annealing", tool=tool_name, error=str(original_error))
        await emit_ws_event("tool.annealing", {"tool": tool_name})

        # Adjustments based on error type
        adjusted = dict(params)
        error_str = str(original_error).lower()

        if "timeout" in error_str:
            adjusted["_retry_with_longer_timeout"] = True
        elif "not found" in error_str:
            adjusted["_fuzzy_match"] = True
        elif "rate limit" in error_str:
            adjusted["_backoff_seconds"] = 5

        try:
            from execution.worker_registry import execute_worker

            result = await execute_worker(tool_name, adjusted)
            await emit_ws_event("tool.annealed", {"tool": tool_name, "success": True})
            return result
        except Exception as retry_exc:
            logger.error(
                "orchestrator.anneal_failed",
                tool=tool_name,
                error=str(retry_exc),
            )
            await emit_ws_event("tool.anneal_failed", {"tool": tool_name, "error": str(retry_exc)})
            return {
                "error": f"Tool '{tool_name}' failed after retry: {str(retry_exc)}",
                "fallback": True,
            }

    def _get_available_tools(self) -> list[dict]:
        """Load tool definitions from the execution worker registry."""
        try:
            from execution.worker_registry import get_tool_definitions  # deferred
            return get_tool_definitions()
        except (ImportError, Exception) as exc:
            logger.warning("orchestrator.tools_unavailable", error=str(exc))
            return []


# Singleton
orchestrator = Orchestrator()
