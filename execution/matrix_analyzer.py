"""
Matrix Analyzer - 4-D Lead Qualification data extraction.

Uses LLM function-calling to extract structured qualification data
(budget, timeline, financing, deal-breakers) from unstructured text.
Implements confidence scoring and safe merge with existing data.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── LLM function schema for structured extraction ──────────────────
EXTRACTION_FUNCTION = {
    "name": "extract_qualification_data",
    "description": (
        "Extract real-estate buyer/seller qualification data from the "
        "provided message text. Every field is optional — only extract "
        "what is explicitly or implicitly stated. Assign a confidence "
        "score (0.0–1.0) for each extracted field."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "budget_min": {
                "type": "number",
                "description": "Minimum budget mentioned (USD). Null if not stated.",
            },
            "budget_max": {
                "type": "number",
                "description": "Maximum budget mentioned (USD). Handles ranges and single values.",
            },
            "budget_confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0 in the budget extraction.",
            },
            "timeline_days": {
                "type": "integer",
                "description": "Estimated timeline in days. Map: 'ASAP'→14, 'soon'→30, 'few months'→90, 'flexible'→180, 'just browsing'→365.",
            },
            "timeline_confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0 in the timeline extraction.",
            },
            "financial_readiness": {
                "type": "string",
                "enum": ["pre_approved", "needs_pre_approval", "cash_buyer", "unsure", "not_applicable"],
                "description": "Financial readiness category.",
            },
            "financial_readiness_confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0 in financial readiness.",
            },
            "deal_breakers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of explicit deal-breakers (e.g. 'no HOA', 'must have garage', 'no busy roads').",
            },
            "deal_breakers_confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0 in deal-breakers extraction.",
            },
            "property_type": {
                "type": "string",
                "enum": ["single_family", "condo", "townhouse", "multi_family", "land", "commercial", "any"],
                "description": "Preferred property type.",
            },
            "property_type_confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0 in property type.",
            },
            "location_preferences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Preferred neighbourhoods, cities, or areas.",
            },
            "location_confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0 in location preferences.",
            },
            "bedrooms_min": {
                "type": "integer",
                "description": "Minimum bedrooms desired.",
            },
            "bathrooms_min": {
                "type": "number",
                "description": "Minimum bathrooms desired.",
            },
            "must_haves": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Explicit must-have features (pool, garage, etc.).",
            },
            "nice_to_haves": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Nice-to-have features mentioned but not essential.",
            },
            "raw_notes": {
                "type": "string",
                "description": "Any other relevant notes that don't fit the above categories.",
            },
        },
        "required": [],
    },
}

SYSTEM_PROMPT = """You are a real-estate lead qualification specialist.
Analyze the message text and extract buyer/seller qualification signals.

Rules:
- Only extract what is explicitly or clearly implied in the text.
- For ambiguous ranges ("around 400k"), set both budget_min and budget_max with the range.
- For single amounts ("400k budget"), set budget_min = budget_max.
- Map vague timelines to estimated days (see timeline field description).
- "maybe pre-approved" → needs_pre_approval with low confidence.
- "pre-approved for X" → pre_approved with high confidence.
- If nothing relevant is mentioned for a field, omit it entirely.
- Assign honest confidence scores: 1.0 = certain, 0.5 = guessing, 0.3 = very uncertain.
"""

# ── Minimum confidence threshold for overwriting existing data ──────
OVERWRITE_CONFIDENCE_THRESHOLD = 0.6


class MatrixAnalyzer:
    """Extracts 4-D qualification matrix from unstructured text via LLM."""

    def __init__(self) -> None:
        self._api_key = settings.OPENAI_API_KEY
        self._model = settings.OPENAI_MODEL
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── main extraction ─────────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def extract_qualification(
        self,
        message_text: str,
        existing_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract qualification data from a message, merging with existing data.

        Args:
            message_text: The raw message from the lead.
            existing_data: Previously confirmed qualification data.
                Fields with high confidence in existing_data won't be overwritten
                by lower-confidence extractions.

        Returns:
            Structured dict with all extracted fields + confidence scores.
        """
        if not self._api_key:
            logger.warning("matrix.no_api_key")
            return existing_data or {}

        # Build conversation context
        user_content = f"Message to analyze:\n\"\"\"{message_text}\"\"\""
        if existing_data:
            user_content += f"\n\nPreviously confirmed data (do NOT overwrite high-confidence fields with lower-confidence ones):\n```json\n{json.dumps(existing_data, indent=2)}\n```"

        client = await self._get_client()
        payload = {
            "model": self._model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "tools": [{"type": "function", "function": EXTRACTION_FUNCTION}],
            "tool_choice": {"type": "function", "function": {"name": "extract_qualification_data"}},
        }

        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if resp.status_code == 429:
            logger.warning("matrix.rate_limited")
            resp.raise_for_status()

        if resp.status_code >= 400:
            logger.error("matrix.api_error", status=resp.status_code, body=resp.text[:500])
            return existing_data or {}

        result = resp.json()
        extracted = self._parse_tool_calls(result)

        if not extracted:
            logger.info("matrix.no_extraction", text_preview=message_text[:80])
            return existing_data or {}

        # Merge with existing data
        merged = self._merge_data(existing_data or {}, extracted)

        logger.info(
            "matrix.extracted",
            fields=list(merged.keys()),
            budget=merged.get("budget_max"),
            timeline=merged.get("timeline_days"),
        )
        return merged

    # ── parsing ─────────────────────────────────────────────────────
    @staticmethod
    def _parse_tool_calls(result: dict[str, Any]) -> dict[str, Any] | None:
        """Extract the function call arguments from the LLM response."""
        try:
            choices = result.get("choices", [])
            if not choices:
                return None

            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            if not tool_calls:
                return None

            args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
            return json.loads(args_str)
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error("matrix.parse_error", error=str(exc))
            return None

    # ── merge logic ─────────────────────────────────────────────────
    @staticmethod
    def _merge_data(
        existing: dict[str, Any],
        extracted: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge extracted data with existing, respecting confidence thresholds.

        Rules:
        - New data wins if its confidence >= OVERWRITE_CONFIDENCE_THRESHOLD.
        - Existing confirmed data (no confidence score = assumed 1.0) is never overwritten
          by extractions below the threshold.
        - Lists (deal_breakers, location_preferences, etc.) are union-merged.
        - Fields not present in extracted are kept from existing.
        """
        merged = dict(existing)

        # Scalar fields and their confidence keys
        scalar_fields = {
            "budget_min": "budget_confidence",
            "budget_max": "budget_confidence",
            "timeline_days": "timeline_confidence",
            "financial_readiness": "financial_readiness_confidence",
            "property_type": "property_type_confidence",
            "bedrooms_min": None,
            "bathrooms_min": None,
            "raw_notes": None,
        }

        for field, conf_key in scalar_fields.items():
            if field not in extracted or extracted[field] is None:
                continue

            new_val = extracted[field]
            if conf_key:
                new_conf = extracted.get(conf_key, 0.5)
                # Check if existing value has a stored confidence
                existing_conf_key = f"{field}_confidence"
                old_conf = existing.get(existing_conf_key, 1.0)
                # Only overwrite if new confidence is high enough
                if new_conf < OVERWRITE_CONFIDENCE_THRESHOLD and field in merged:
                    logger.debug(
                        "matrix.skip_field",
                        field=field,
                        new_conf=new_conf,
                        old_conf=old_conf,
                    )
                    continue

                merged[field] = new_val
                merged[conf_key] = new_conf
            else:
                # No confidence tracking — just overwrite
                merged[field] = new_val

        # List fields — union merge (no overwrite, just add)
        list_fields = ["deal_breakers", "location_preferences", "must_haves", "nice_to_haves"]
        for field in list_fields:
            if field not in extracted or not extracted[field]:
                continue
            new_conf = extracted.get(f"{field}_confidence", 0.5)
            existing_list = merged.get(field, [])
            if isinstance(existing_list, list) and isinstance(extracted[field], list):
                # Deduplicate while preserving order
                seen = set()
                combined = []
                for item in existing_list + extracted[field]:
                    key = item.strip().lower()
                    if key not in seen:
                        seen.add(key)
                        combined.append(item)
                merged[field] = combined
                if f"{field}_confidence" in extracted:
                    merged[f"{field}_confidence"] = max(
                        new_conf,
                        merged.get(f"{field}_confidence", 0.0),
                    )

        return merged
