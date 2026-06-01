"""LLM-based semantic intent router with multi-intent detection."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from orchestration.config import settings
from execution.llm_client import LLMClient

logger = structlog.get_logger(__name__)


class Intent(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    SUPPORT = "SUPPORT"
    SCHEDULE = "SCHEDULE"
    FAQ = "FAQ"
    CHITCHAT = "CHITCHAT"
    HANDOVER = "HANDOVER"
    DATA_DROP = "DATA_DROP"
    COMPLAINT = "COMPLAINT"


@dataclass
class IntentResult:
    primary: Intent
    confidence: float
    secondary: list[tuple[Intent, float]] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)
    raw_llm_response: Optional[dict] = None


CLASSIFICATION_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_message",
        "description": (
            "Classify the user's real-estate WhatsApp message into one or more intents. "
            "Extract any structured entities present (budget, property address, "
            "bedrooms, timeline, contact info, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "primary_intent": {
                    "type": "string",
                    "enum": [i.value for i in Intent],
                    "description": "The dominant intent of the message.",
                },
                "primary_confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence score for the primary intent.",
                },
                "secondary_intents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "string",
                                "enum": [i.value for i in Intent],
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": ["intent", "confidence"],
                    },
                    "description": (
                        "Additional intents detected in the same message (e.g., user "
                        "drops a budget AND asks about HOA fees)."
                    ),
                },
                "entities": {
                    "type": "object",
                    "description": (
                        "Extracted structured data. Possible keys: budget_min, budget_max, "
                        "bedrooms, bathrooms, sqft, property_address, city, zip_code, "
                        "timeline, full_name, email, phone_alt, hoa_question, etc."
                    ),
                    "additionalProperties": True,
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief chain-of-thought on why this classification was chosen.",
                },
            },
            "required": ["primary_intent", "primary_confidence", "entities"],
        },
    },
}

CLASSIFIER_SYSTEM_PROMPT = """\
You are an intent classification engine for a real-estate assistant.

Given the conversation history and the latest user message, classify the message.

INTENTS:
- BUY: user wants to purchase / browse / get alerts for properties
- SELL: user wants to list / value / sell their property
- SUPPORT: general real-estate question or service request
- SCHEDULE: user wants to book a showing, call, or meeting
- FAQ: factual question (HOA rules, school zones, taxes, etc.)
- CHITCHAT: greetings, thanks, small-talk, off-topic
- HANDOVER: user explicitly asks for a human agent
- DATA_DROP: user volunteers personal or property data (budget, address, email)
- COMPLAINT: dissatisfaction, frustration, or negative feedback

RULES:
1. A single message CAN carry multiple intents (e.g. "I'm John, budget 450k, what are the HOA fees on 123 Main?")
2. Extract ALL structured entities you can find.
3. Provide a confidence 0-1 for each intent.
4. Be conservative with HANDOVER/COMPLAINT – only if the user is explicit.
"""


class IntentRouter:
    """Semantic intent classifier backed by LLM function calling."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm = llm_client or LLMClient()

    def _build_messages(
        self, message: str, conversation_history: list[dict[str, str]] | None = None
    ) -> list[dict]:
        messages: list[dict] = [
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT}
        ]
        # Include last few turns for context (but keep it lean)
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": message})
        return messages

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def classify(
        self,
        message: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> IntentResult:
        """
        Classify a user message into intents + extracted entities.

        Uses LLM function-calling to get structured output, falling back
        to CHITCHAT on failure.
        """
        messages = self._build_messages(message, conversation_history)
        try:
            response = await self._llm.function_call(
                messages=messages,
                tools=[CLASSIFICATION_TOOL],
                tool_choice={"type": "function", "function": {"name": "classify_message"}},
                model=settings.INTENT_MODEL or settings.LLM_MODEL,
                temperature=0.0,
                max_tokens=800,
            )
            args = response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            parsed = json.loads(args) if isinstance(args, str) else args
        except Exception as exc:
            logger.error("intent.classification_failed", error=str(exc), message_preview=message[:120])
            return IntentResult(
                primary=Intent.CHITCHAT,
                confidence=0.3,
                entities={},
                raw_llm_response={"error": str(exc)},
            )

        try:
            primary = Intent(parsed["primary_intent"])
        except (KeyError, ValueError) as exc:
            logger.error("intent.parse_failed", error=str(exc), raw=parsed)
            return IntentResult(primary=Intent.CHITCHAT, confidence=0.3, entities={})

        secondary: list[tuple[Intent, float]] = []
        for sec in parsed.get("secondary_intents", []):
            try:
                secondary.append((Intent(sec["intent"]), float(sec["confidence"])))
            except (KeyError, ValueError):
                continue

        result = IntentResult(
            primary=primary,
            confidence=float(parsed.get("primary_confidence", 0.5)),
            secondary=secondary,
            entities=parsed.get("entities", {}),
            raw_llm_response=parsed,
        )
        logger.info(
            "intent.classified",
            primary=primary.value,
            confidence=result.confidence,
            secondary=[s[0].value for s in secondary],
            entity_keys=list(result.entities.keys()),
        )
        return result


# Singleton
intent_router = IntentRouter()
