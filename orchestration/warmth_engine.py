"""
Warmth Score Calculator - Lead temperature scoring engine.
Scores leads 0-100 based on engagement signals and assigns HOT/WARM/COLD tiers.
"""

import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import structlog

from config import settings

logger = structlog.get_logger(__name__)

# --- Constants ---

HOT_THRESHOLD = 80
WARM_THRESHOLD = 50

# Scoring weights
RESPONSE_SPEED_POINTS = (10, 20)       # min, max
SENTIMENT_POSITIVITY_POINTS = (10, 15)
CONCRETE_ANSWERS_POINTS = (15, 20)
BUYING_SIGNALS_POINTS = (20, 30)
ENGAGEMENT_FREQUENCY_POINTS = (5, 10)

# Cold signals (negative)
VAGUE_ANSWERS_PENALTY = (5, 10)
LONG_PAUSES_PENALTY = (10, 20)
ONE_WORD_REPLIES_PENALTY = 10

# Decay schedule: (days_inactive, points_lost)
DECAY_SCHEDULE: list[tuple[int, int]] = [
    (7, -10),
    (14, -20),
    (30, -35),
]


class WarmthTier(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class WarmthResult:
    __slots__ = ("score", "tier", "breakdown")

    def __init__(self, score: int, tier: WarmthTier, breakdown: dict) -> None:
        self.score = score
        self.tier = tier
        self.breakdown = breakdown


# --- In-memory warmth store (replace with DB/Redis in production) ---
_warmth_store: dict[str, dict] = {}


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def _score_response_speed(messages: list[dict]) -> tuple[int, str]:
    """Faster response times yield higher points."""
    if len(messages) < 2:
        return RESPONSE_SPEED_POINTS[0], "insufficient_data"

    gaps: list[float] = []
    for i in range(1, len(messages)):
        prev_ts = messages[i - 1].get("timestamp", 0)
        curr_ts = messages[i].get("timestamp", 0)
        if prev_ts and curr_ts:
            gaps.append(curr_ts - prev_ts)

    if not gaps:
        return RESPONSE_SPEED_POINTS[0], "no_timestamps"

    avg_gap_s = sum(gaps) / len(gaps)
    # Map avg gap: <60s -> max, >3600s -> min
    if avg_gap_s <= 60:
        points = RESPONSE_SPEED_POINTS[1]
    elif avg_gap_s >= 3600:
        points = RESPONSE_SPEED_POINTS[0]
    else:
        ratio = 1 - (avg_gap_s - 60) / 3540
        points = int(RESPONSE_SPEED_POINTS[0] + ratio * (RESPONSE_SPEED_POINTS[1] - RESPONSE_SPEED_POINTS[0]))

    return points, f"avg_gap={avg_gap_s:.0f}s"


def _score_sentiment(messages: list[dict]) -> tuple[int, str]:
    """Check for positive sentiment keywords in messages."""
    positive_words = {
        "yes", "great", "perfect", "love", "interested", "definitely",
        "absolutely", "excited", "ready", "approved", "pre-approved",
        "budget", "approved", "down payment", "mortgage",
    }
    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return SENTIMENT_POSITIVITY_POINTS[0], "no_user_msgs"

    hits = sum(
        1 for m in user_msgs
        for word in positive_words
        if word in m.get("text", "").lower()
    )
    ratio = min(hits / max(len(user_msgs), 1), 1.0)
    points = int(SENTIMENT_POSITIVITY_POINTS[0] + ratio * (SENTIMENT_POSITIVITY_POINTS[1] - SENTIMENT_POSITIVITY_POINTS[0]))
    return points, f"positive_hits={hits}"


def _score_concrete_answers(qualification: dict) -> tuple[int, str]:
    """Concrete qualification answers (budget, timeline, location) score higher."""
    concrete_fields = ["budget", "timeline", "location", "pre_approval", "property_type"]
    filled = sum(1 for f in concrete_fields if qualification.get(f))
    ratio = filled / len(concrete_fields)
    points = int(CONCRETE_ANSWERS_POINTS[0] + ratio * (CONCRETE_ANSWERS_POINTS[1] - CONCRETE_ANSWERS_POINTS[0]))
    return points, f"filled={filled}/{len(concrete_fields)}"


def _score_buying_signals(messages: list[dict], qualification: dict) -> tuple[int, str]:
    """Detect strong buying signals."""
    signals = 0
    # Check qualification data
    if qualification.get("pre_approval"):
        signals += 2
    if qualification.get("timeline") and "30" in str(qualification["timeline"]):
        signals += 2
    if qualification.get("cash_buyer"):
        signals += 2

    buying_keywords = [
        "pre-approved", "pre approved", "cash buyer", "down payment",
        "ready to buy", "closing", "offer", "mortgage", "lender",
        "when can i see", "schedule a showing", "put in an offer",
    ]
    for m in messages:
        text = m.get("text", "").lower()
        if any(kw in text for kw in buying_keywords):
            signals += 1

    signals = min(signals, 6)
    ratio = signals / 6
    points = int(BUYING_SIGNALS_POINTS[0] + ratio * (BUYING_SIGNALS_POINTS[1] - BUYING_SIGNALS_POINTS[0]))
    return points, f"signals={signals}"


def _score_engagement_frequency(messages: list[dict]) -> tuple[int, str]:
    """Higher message count in recent window = higher engagement."""
    recent = [m for m in messages if m.get("timestamp", 0) > time.time() - 86400 * 3]
    count = len(recent)
    if count >= 10:
        points = ENGAGEMENT_FREQUENCY_POINTS[1]
    elif count >= 3:
        ratio = (count - 3) / 7
        points = int(ENGAGEMENT_FREQUENCY_POINTS[0] + ratio * (ENGAGEMENT_FREQUENCY_POINTS[1] - ENGAGEMENT_FREQUENCY_POINTS[0]))
    else:
        points = ENGAGEMENT_FREQUENCY_POINTS[0]
    return points, f"recent_msgs={count}"


def _score_cold_signals(messages: list[dict]) -> tuple[int, str]:
    """Calculate negative cold-signal deductions."""
    deduction = 0
    details: list[str] = []

    # Vague answers
    vague_phrases = ["i don't know", "not sure", "maybe", "idk", "hmm", "nah"]
    vague_count = sum(
        1 for m in messages
        if m.get("role") == "user" and any(p in m.get("text", "").lower() for p in vague_phrases)
    )
    if vague_count >= 3:
        deduction += VAGUE_ANSWERS_PENALTY[1]
        details.append(f"vague={vague_count}(max)")
    elif vague_count >= 1:
        deduction += VAGUE_ANSWERS_PENALTY[0]
        details.append(f"vague={vague_count}")

    # One-word replies
    one_word = sum(
        1 for m in messages
        if m.get("role") == "user" and len(m.get("text", "").strip().split()) <= 1
    )
    if one_word >= 3:
        deduction += ONE_WORD_REPLIES_PENALTY
        details.append(f"oneword={one_word}")

    # Long pauses (>24h gaps)
    long_pauses = 0
    for i in range(1, len(messages)):
        gap = messages[i].get("timestamp", 0) - messages[i - 1].get("timestamp", 0)
        if gap > 86400:
            long_pauses += 1
    if long_pauses >= 3:
        deduction += LONG_PAUSES_PENALTY[1]
        details.append(f"pauses={long_pauses}(max)")
    elif long_pauses >= 1:
        deduction += LONG_PAUSES_PENALTY[0]
        details.append(f"pauses={long_pauses}")

    return deduction, ", ".join(details) if details else "none"


async def calculate_warmth(
    lead_id: str,
    messages: list[dict],
    qualification: dict,
) -> WarmthResult:
    """
    Calculate a warmth score (0-100) and tier for a lead.

    Args:
        lead_id: Unique lead identifier.
        messages: List of message dicts with keys: role, text, timestamp.
        qualification: Dict of qualification answers.

    Returns:
        WarmthResult with score, tier, and per-factor breakdown.
    """
    breakdown: dict[str, int] = {}

    p, detail = _score_response_speed(messages)
    breakdown[f"response_speed({detail})"] = p

    p, detail = _score_sentiment(messages)
    breakdown[f"sentiment({detail})"] = p

    p, detail = _score_concrete_answers(qualification)
    breakdown[f"concrete_answers({detail})"] = p

    p, detail = _score_buying_signals(messages, qualification)
    breakdown[f"buying_signals({detail})"] = p

    p, detail = _score_engagement_frequency(messages)
    breakdown[f"engagement({detail})"] = p

    cold_penalty, cold_detail = _score_cold_signals(messages)
    breakdown[f"cold_signals({cold_detail})"] = -cold_penalty

    raw_score = sum(v for v in breakdown.values()) - cold_penalty
    # Fix: breakdown already includes negative values, so just sum
    raw_score = sum(breakdown.values())
    score = _clamp(raw_score)

    # Apply time decay
    decay = _compute_decay(lead_id)
    score = _clamp(score + decay)
    if decay != 0:
        breakdown[f"decay({decay:+d})"] = decay

    if score >= HOT_THRESHOLD:
        tier = WarmthTier.HOT
    elif score >= WARM_THRESHOLD:
        tier = WarmthTier.WARM
    else:
        tier = WarmthTier.COLD

    result = WarmthResult(score=score, tier=tier, breakdown=breakdown)

    # Cache for decay tracking
    _warmth_store[lead_id] = {
        "score": score,
        "tier": tier.value,
        "last_activity": time.time(),
    }

    logger.info("warmth_calculated", lead_id=lead_id, score=score, tier=tier.value)

    # Emit event
    await _emit_warmth_event(lead_id, result)

    return result


def _compute_decay(lead_id: str) -> int:
    """Compute time-decay penalty based on last activity."""
    entry = _warmth_store.get(lead_id)
    if not entry:
        return 0

    last_activity = entry.get("last_activity", 0)
    if not last_activity:
        return 0

    days_inactive = (time.time() - last_activity) / 86400
    decay = 0
    for threshold_days, penalty in DECAY_SCHEDULE:
        if days_inactive >= threshold_days:
            decay = penalty  # Take the worst applicable penalty
    return decay


async def apply_time_decay(lead_id: str) -> Optional[int]:
    """
    Apply and return the time-decay penalty for a lead.
    Returns the decay amount (negative) or None if no entry exists.
    """
    decay = _compute_decay(lead_id)
    if decay == 0:
        return None

    entry = _warmth_store.get(lead_id, {})
    current_score = entry.get("score", 50)
    new_score = _clamp(current_score + decay)
    entry["score"] = new_score
    _warmth_store[lead_id] = entry

    logger.info("warmth_decay_applied", lead_id=lead_id, decay=decay, new_score=new_score)
    return decay


async def _emit_warmth_event(lead_id: str, result: WarmthResult) -> None:
    """Emit lead.warmth_updated event via dashboard_syncer."""
    try:
        from orchestration.dashboard_syncer import emit_event  # type: ignore

        await emit_event(
            "lead.warmth_updated",
            {
                "lead_id": lead_id,
                "score": result.score,
                "tier": result.tier.value,
                "breakdown": result.breakdown,
            },
        )
    except ImportError:
        logger.warning("dashboard_syncer_not_available", lead_id=lead_id)
    except Exception as exc:
        logger.error("warmth_event_emit_failed", lead_id=lead_id, error=str(exc))
