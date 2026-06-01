"""Real-time sentiment scoring for lead messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import openai
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# Cached OpenAI client (avoids re-creating per call)
_openai_client: openai.AsyncOpenAI | None = None


def _get_openai_client() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI()
    return _openai_client

URGENCY_PATTERNS = [
    r"\bpre[- ]?approved\b",
    r"\bcash\s*(ready|buyer|on hand)\b",
    r"\brelocating\b",
    r"\bmust\s+sell\b",
    r"\bneed\s+(to|a)\s+(move|buy|sell)\b",
    r"\btime[- ]?sensitive\b",
    r"\burgent\b",
    r"\basap\b",
    r"\bright\s+away\b",
    r"\bimmediately\b",
    r"\bdeadline\b",
    r"\boffer\s+deadline\b",
]

FRUSTRATION_PATTERNS = [
    r"\bannoyed\b",
    r"\bwaiting\b",
    r"\bfrustrated\b",
    r"\bunresponsive\b",
    r"\bdidn'?t\s+hear\b",
    r"\bno\s+response\b",
    r"\bghost(ed|ing)?\b",
    r"\bwaste\s+of\s+time\b",
    r"\bdisappointed\b",
    r"\bupset\b",
    r"\bangry\b",
    r"\bterrible\b",
    r"\bhorrible\b",
    r"\bnever\s+again\b",
    r"\bworst\b",
    r"\bcomplain\b",
]

WARMTH_PATTERNS = [
    r"\bthank(s|you)\b",
    r"\bappreciate\b",
    r"\bgreat\b",
    r"\bawesome\b",
    r"\blove\b",
    r"\bperfect\b",
    r"\bexcellent\b",
    r"\bwonderful\b",
    r"\bhappy\b",
    r"\bpleased\b",
    r"\bexcited\b",
    r"\blooking\s+forward\b",
    r"\bcan'?t\s+wait\b",
    r"\bdefinitely\b",
    r"\babsolutely\b",
]


@dataclass
class SentimentResult:
    score: float  # -1.0 to +1.0
    label: Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]
    confidence: float


@dataclass
class WarmthSignals:
    warmth_score: float  # 0.0 to 1.0
    positive_count: int
    negative_count: int
    urgency_detected: bool
    frustration_detected: bool
    indicators: list[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def analyze_sentiment(text: str) -> SentimentResult:
    """Analyze sentiment of a single text message using OpenAI."""
    if not text or not text.strip():
        return SentimentResult(score=0.0, label="NEUTRAL", confidence=1.0)

    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analyze the sentiment of the message. "
                        "Respond with JSON: {\"score\": <float -1.0 to 1.0>, "
                        "\"label\": \"POSITIVE|NEGATIVE|NEUTRAL\", "
                        "\"confidence\": <float 0.0 to 1.0>}"
                    ),
                },
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
        )
        import json
        result = json.loads(response.choices[0].message.content)
        score = max(-1.0, min(1.0, float(result.get("score", 0.0))))
        label = result.get("label", "NEUTRAL")
        if label not in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
            label = "NEUTRAL"
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        logger.info("sentiment_analyzed", score=score, label=label, text_len=len(text))
        return SentimentResult(score=score, label=label, confidence=confidence)
    except Exception as e:
        logger.error("sentiment_analysis_failed", error=str(e))
        return _fallback_sentiment(text)


def _fallback_sentiment(text: str) -> SentimentResult:
    """Simple regex-based fallback when API is unavailable."""
    text_lower = text.lower()
    pos = sum(1 for p in WARMTH_PATTERNS if re.search(p, text_lower))
    neg = sum(1 for p in FRUSTRATION_PATTERNS if re.search(p, text_lower))
    total = pos + neg
    if total == 0:
        return SentimentResult(score=0.0, label="NEUTRAL", confidence=0.3)
    score = (pos - neg) / max(total, 1)
    score = max(-1.0, min(1.0, score))
    label = "POSITIVE" if score > 0.2 else "NEGATIVE" if score < -0.2 else "NEUTRAL"
    return SentimentResult(score=score, label=label, confidence=0.4)


def detect_urgency(text: str) -> dict:
    """Detect high-intent urgency phrases in text."""
    text_lower = text.lower()
    matches = []
    for pattern in URGENCY_PATTERNS:
        found = re.findall(pattern, text_lower)
        if found:
            matches.append(pattern.strip(r"\b"))
    is_urgent = len(matches) >= 1
    logger.info("urgency_detected", is_urgent=is_urgent, match_count=len(matches))
    return {"is_urgent": is_urgent, "match_count": len(matches), "patterns": matches}


def detect_frustration(text: str) -> dict:
    """Detect frustration markers in text."""
    text_lower = text.lower()
    matches = []
    for pattern in FRUSTRATION_PATTERNS:
        if re.search(pattern, text_lower):
            matches.append(pattern.strip(r"\b"))
    is_frustrated = len(matches) >= 1
    severity = min(1.0, len(matches) * 0.3)
    logger.info("frustration_detected", is_frustrated=is_frustrated, severity=severity)
    return {
        "is_frustrated": is_frustrated,
        "severity": round(severity, 2),
        "match_count": len(matches),
        "patterns": matches,
    }


async def calculate_warmth_signals(messages: list[dict]) -> WarmthSignals:
    """Analyze conversation history for warmth indicators.

    Args:
        messages: List of dicts with 'content' and optionally 'sender_type'.
    """
    if not messages:
        return WarmthSignals(
            warmth_score=0.5, positive_count=0, negative_count=0,
            urgency_detected=False, frustration_detected=False, indicators=[],
        )

    positive_count = 0
    negative_count = 0
    urgency_found = False
    frustration_found = False
    indicators: list[str] = []

    for msg in messages:
        content = msg.get("content", "")
        content_lower = content.lower()

        for pattern in WARMTH_PATTERNS:
            if re.search(pattern, content_lower):
                positive_count += 1
                break

        for pattern in FRUSTRATION_PATTERNS:
            if re.search(pattern, content_lower):
                negative_count += 1
                break

        urgency = detect_urgency(content)
        if urgency["is_urgent"]:
            urgency_found = True
            indicators.append(f"urgency: {', '.join(urgency['patterns'][:3])}")

        frustration = detect_frustration(content)
        if frustration["is_frustrated"]:
            frustration_found = True
            indicators.append(f"frustration: {', '.join(frustration['patterns'][:3])}")

    total = positive_count + negative_count
    if total == 0:
        warmth_score = 0.5
    else:
        warmth_score = positive_count / total
        warmth_score = max(0.0, min(1.0, warmth_score))

    # Frustration reduces warmth
    if frustration_found:
        warmth_score = max(0.0, warmth_score - 0.2)

    signals = WarmthSignals(
        warmth_score=round(warmth_score, 3),
        positive_count=positive_count,
        negative_count=negative_count,
        urgency_detected=urgency_found,
        frustration_detected=frustration_found,
        indicators=indicators,
    )
    logger.info("warmth_calculated", warmth_score=warmth_score, messages=len(messages))
    return signals
