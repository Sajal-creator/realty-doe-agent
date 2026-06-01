"""Token-density monitor and conversation history compressor."""

from __future__ import annotations

import json
from typing import Any, Optional

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from orchestration.config import settings
from execution.llm_client import LLMClient

logger = structlog.get_logger(__name__)

# Thresholds
DEFAULT_TOKEN_THRESHOLD = 4000
TARGET_TOKEN_RATIO = 0.35  # compress down to ~35% of threshold

COMPRESSION_SYSTEM_PROMPT = """\
You are a conversation state compressor for a real-estate AI assistant.

Given a conversation history, produce a HIGH-DENSITY state summary matrix in JSON.

PRESERVE (priority order):
1. Key decisions made (offer amounts, accepted/rejected, preferences locked in)
2. All extracted data points (budget, bedrooms, location, timeline, contact info)
3. Unresolved questions or pending items
4. Lead qualification status / score signals
5. Emotional state and rapport indicators
6. Property-specific details discussed

DISCARD:
- Redundant pleasantries / greetings repeated across turns
- Information that was superseded by later corrections
- Verbose assistant explanations that can be regenerated
- Generic filler messages

OUTPUT FORMAT (JSON):
{
  "decision_log": ["..."],
  "extracted_data": { ... },
  "qualification_status": { ... },
  "open_questions": ["..."],
  "emotional_state": "...",
  "property_context": [ ... ],
  "turns_compressed": N,
  "original_token_count": N,
  "summary_text": "A 2-3 sentence narrative summary of the conversation so far."
}
"""


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English)."""
    return max(1, len(text) // 4)


def _messages_token_count(messages: list[dict[str, str]]) -> int:
    total = 0
    for m in messages:
        total += _estimate_tokens(m.get("content", "") or "")
        total += _estimate_tokens(m.get("role", "user"))
    return total


class MemoryCompressor:
    """Monitors conversation token count and triggers LLM-based compression."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm = llm_client or LLMClient()
        self._threshold = getattr(
            settings, "MEMORY_TOKEN_THRESHOLD", DEFAULT_TOKEN_THRESHOLD
        )

    @property
    def token_threshold(self) -> int:
        return self._threshold

    def needs_compression(self, messages: list[dict[str, str]]) -> bool:
        """Check if conversation history exceeds the token threshold."""
        count = _messages_token_count(messages)
        logger.debug("memory.token_check", count=count, threshold=self._threshold)
        return count > self._threshold

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
    async def compress(
        self, messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        """
        Compress conversation history into a dense state summary.

        Returns a dict suitable for the session's context_snapshot field.
        The summary preserves all critical information for downstream use.
        """
        token_count = _messages_token_count(messages)
        logger.info("memory.compressing", token_count=token_count, message_count=len(messages))

        # Build compression prompt
        # Serialise conversation for the compressor
        conversation_text = "\n".join(
            f"[{m.get('role', 'user').upper()}]: {m.get('content', '')}"
            for m in messages
            if m.get("content")
        )

        llm_messages = [
            {"role": "system", "content": COMPRESSION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Compress the following conversation ({token_count} estimated tokens, "
                    f"{len(messages)} messages).\n\n---\n{conversation_text}\n---"
                ),
            },
        ]

        try:
            response = await self._llm.chat(
                messages=llm_messages,
                model=settings.LLM_MODEL,
                temperature=0.0,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            content = response["choices"][0]["message"]["content"]
            summary = json.loads(content) if isinstance(content, str) else content
        except Exception as exc:
            logger.error("memory.compression_failed", error=str(exc))
            # Fallback: keep last 5 messages verbatim
            summary = self._fallback_summary(messages, token_count)

        # Attach metadata
        summary.setdefault("original_token_count", token_count)
        summary.setdefault("turns_compressed", len(messages))
        summary.setdefault("compression_ratio", "llm")

        compressed_tokens = _estimate_tokens(json.dumps(summary))
        logger.info(
            "memory.compressed",
            original_tokens=token_count,
            compressed_tokens=compressed_tokens,
            ratio=f"{compressed_tokens / max(token_count, 1):.2%}",
        )
        return summary

    def _fallback_summary(
        self, messages: list[dict[str, str]], token_count: int
    ) -> dict[str, Any]:
        """Produce a minimal summary when LLM compression fails."""
        recent = messages[-5:] if len(messages) > 5 else messages
        return {
            "decision_log": [],
            "extracted_data": {},
            "qualification_status": {},
            "open_questions": [],
            "emotional_state": "unknown",
            "property_context": [],
            "turns_compressed": len(messages),
            "original_token_count": token_count,
            "summary_text": (
                f"Compression failed. Preserving last {len(recent)} messages verbatim. "
                f"Original history was {len(messages)} messages (~{token_count} tokens)."
            ),
            "fallback_messages": recent,
            "compression_ratio": "fallback",
        }

    async def maybe_compress(
        self, messages: list[dict[str, str]]
    ) -> Optional[dict[str, Any]]:
        """Convenience: compress only if threshold is exceeded, otherwise return None."""
        if not self.needs_compression(messages):
            return None
        return await self.compress(messages)


# Singleton
memory_compressor = MemoryCompressor()
