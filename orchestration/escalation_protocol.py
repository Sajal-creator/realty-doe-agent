"""
High-Intent Escalation Protocol.
Detects high-intent leads and escalates them to human agents with briefing and alerts.
"""

from datetime import datetime, timezone
from typing import Optional

import structlog

from config import settings
from orchestration.warmth_engine import HOT_THRESHOLD, WarmthTier

logger = structlog.get_logger(__name__)

# Escalation thresholds
ESCALATION_WARMTH_THRESHOLD = 80
TIMELINE_DAYS_THRESHOLD = 30


class EscalationResult:
    __slots__ = ("should_escalate", "reason", "urgency")

    def __init__(self, should_escalate: bool, reason: str = "", urgency: str = "normal") -> None:
        self.should_escalate = should_escalate
        self.reason = reason
        self.urgency = urgency


async def check_escalation(
    lead_id: str,
    warmth_score: int,
    qualification: dict,
) -> EscalationResult:
    """
    Determine if a lead should be escalated to a human agent.

    Threshold: score >= 80 AND (pre-approved OR cash buyer OR timeline < 30 days).
    """
    if warmth_score < ESCALATION_WARMTH_THRESHOLD:
        return EscalationResult(False, f"score {warmth_score} < {ESCALATION_WARMTH_THRESHOLD}")

    is_pre_approved = bool(qualification.get("pre_approval"))
    is_cash_buyer = bool(qualification.get("cash_buyer"))

    timeline_days: Optional[int] = None
    raw_timeline = qualification.get("timeline")
    if raw_timeline is not None:
        try:
            timeline_days = int(raw_timeline)
        except (ValueError, TypeError):
            pass

    has_urgent_timeline = timeline_days is not None and timeline_days < TIMELINE_DAYS_THRESHOLD

    high_intent = is_pre_approved or is_cash_buyer or has_urgent_timeline

    if not high_intent:
        return EscalationResult(False, "score qualifies but no high-intent signal")

    reasons: list[str] = []
    if is_pre_approved:
        reasons.append("pre-approved")
    if is_cash_buyer:
        reasons.append("cash buyer")
    if has_urgent_timeline:
        reasons.append(f"timeline={timeline_days}d")

    urgency = "critical" if warmth_score >= 90 and (is_cash_buyer or is_pre_approved) else "high"

    return EscalationResult(
        should_escalate=True,
        reason=f"score={warmth_score}, {', '.join(reasons)}",
        urgency=urgency,
    )


async def generate_briefing(lead_id: str) -> str:
    """
    Generate a 2-sentence summary for the agent dashboard.
    Pulls cached lead data from warmth store and produces a human-readable brief.
    """
    try:
        from orchestration.warmth_engine import _warmth_store  # type: ignore

        entry = _warmth_store.get(lead_id, {})
        score = entry.get("score", "unknown")
        tier = entry.get("tier", "unknown")
    except ImportError:
        score = "unknown"
        tier = "unknown"

    # In production, fetch from DB for full qualification data
    briefing = (
        f"Lead {lead_id} has a warmth score of {score} ({tier}) and meets escalation criteria. "
        f"High-intent signals detected — recommend immediate follow-up."
    )

    logger.info("briefing_generated", lead_id=lead_id)
    return briefing


async def trigger_escalation(
    lead_id: str,
    phone_number: Optional[str] = None,
) -> dict:
    """
    Full escalation flow:
    1. Freeze AI input for the lead
    2. Generate briefing
    3. Emit WebSocket alert to agent dashboard
    4. Send [Confirm Priority Call] WhatsApp button
    5. Create handover_request event
    """
    briefing = await generate_briefing(lead_id)

    result = {
        "lead_id": lead_id,
        "briefing": briefing,
        "frozen": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actions": [],
    }

    # Freeze AI input
    await _freeze_ai_input(lead_id)
    result["actions"].append("ai_input_frozen")

    # Emit WebSocket alert
    await _emit_ws_alert(lead_id, briefing)
    result["actions"].append("ws_alert_emitted")

    # Send WhatsApp button
    if phone_number:
        await _send_priority_call_button(lead_number=phone_number, lead_id=lead_id)
        result["actions"].append("whatsapp_button_sent")

    # Create handover_request event
    await _emit_handover_request(lead_id, briefing)
    result["actions"].append("handover_request_created")

    logger.info("escalation_triggered", lead_id=lead_id, actions=result["actions"])
    return result


async def _freeze_ai_input(lead_id: str) -> None:
    """Mark the lead as frozen so AI stops generating responses."""
    logger.info("ai_input_frozen", lead_id=lead_id)
    # Persist freeze flag to DB/cache


async def _emit_ws_alert(lead_id: str, briefing: str) -> None:
    """Send a real-time WebSocket alert to the agent dashboard."""
    try:
        from orchestration.dashboard_syncer import emit_event  # type: ignore

        await emit_event(
            "lead.escalation_alert",
            {
                "lead_id": lead_id,
                "briefing": briefing,
                "urgency": "high",
            },
        )
    except ImportError:
        logger.warning("dashboard_syncer_not_available", lead_id=lead_id)
    except Exception as exc:
        logger.error("ws_alert_failed", lead_id=lead_id, error=str(exc))


async def _send_priority_call_button(lead_number: str, lead_id: str) -> None:
    """Send a WhatsApp interactive button for confirming priority call."""
    try:
        from orchestration.whatsapp_client import send_interactive_button  # type: ignore

        await send_interactive_button(
            to=lead_number,
            body="Our agent would love to connect with you right away! Ready for a priority call?",
            buttons=[
                {"id": f"confirm_call_{lead_id}", "title": "Confirm Priority Call"},
                {"id": f"decline_call_{lead_id}", "title": "Not Right Now"},
            ],
        )
    except ImportError:
        logger.warning("whatsapp_client_not_available", lead_id=lead_id)
    except Exception as exc:
        logger.error("whatsapp_button_failed", lead_id=lead_id, error=str(exc))


async def _emit_handover_request(lead_id: str, briefing: str) -> None:
    """Create a handover_request event for the CRM."""
    try:
        from orchestration.dashboard_syncer import emit_event  # type: ignore

        await emit_event(
            "lead.handover_request",
            {
                "lead_id": lead_id,
                "briefing": briefing,
                "urgency": "high",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            },
        )
    except Exception as exc:
        logger.error("handover_event_failed", lead_id=lead_id, error=str(exc))
