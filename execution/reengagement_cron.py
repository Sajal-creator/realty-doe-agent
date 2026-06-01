"""
Reengagement Cron - Anti-ghosting scheduler.

Scans for silent leads, generates personalized nurture messages,
and sends them via WhatsApp to re-engage cold leads.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class NurtureTier(IntEnum):
    """Nurture attempt tiers with increasing intervals."""
    TIER_1 = 1  # 72h silent → gentle check-in
    TIER_2 = 2  # 7 days → value drop (new listings)
    TIER_3 = 3  # 14 days → market insight
    MONTHLY = 4  # 30+ days → monthly digest


TIER_INTERVALS = {
    NurtureTier.TIER_1: timedelta(hours=72),
    NurtureTier.TIER_2: timedelta(days=7),
    NurtureTier.TIER_3: timedelta(days=14),
    NurtureTier.MONTHLY: timedelta(days=30),
}


class ReengagementCron:
    """
    Anti-ghosting scheduler that finds silent leads and sends
    personalized nurture messages to re-engage them.
    """

    def __init__(
        self,
        redis_client=None,
        db_session_factory=None,
        llm_client=None,
        whatsapp_gateway=None,
        vector_mls_matcher=None,
    ):
        self._redis = redis_client
        self._db_factory = db_session_factory
        self._llm = llm_client
        self._whatsapp = whatsapp_gateway
        self._mls_matcher = vector_mls_matcher

    # -- Main cron entry point --

    async def execute_nurture_sequence(self) -> dict[str, Any]:
        """
        Main cron job: scan → filter → generate → send.
        Run this on a schedule (e.g., every hour).
        """
        logger.info("nurture_sequence_started")
        results = {"scanned": 0, "sent": 0, "skipped": 0, "errors": 0}

        # 1. Scan for silent leads
        silent_leads = await self.scan_silent_leads()
        results["scanned"] = len(silent_leads)

        for lead in silent_leads:
            try:
                # 2. Respect opt-outs
                if not await self.respect_opt_outs(lead["lead_id"]):
                    results["skipped"] += 1
                    continue

                # 3. Determine nurture tier
                tier = await self._determine_tier(lead)

                # 4. Generate personalized message
                message = await self.generate_nurture_message(lead["lead_id"], tier)
                if not message:
                    results["skipped"] += 1
                    continue

                # 5. Send via WhatsApp
                success = await self._send_nurture(lead, message, tier)
                if success:
                    results["sent"] += 1
                    await self.track_nurture_attempts(lead["lead_id"])
                else:
                    results["errors"] += 1

            except Exception as exc:
                logger.error("nurture_error", lead_id=lead["lead_id"], error=str(exc))
                results["errors"] += 1

        logger.info("nurture_sequence_completed", **results)
        return results

    # -- Scanning --

    async def scan_silent_leads(self) -> list[dict[str, Any]]:
        """
        Find leads with no inbound or outbound activity in the last 72 hours.
        Excludes leads already in active nurture sequences.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)

        # Query leads with last_activity < cutoff
        # and not opted out and not currently in human takeover
        leads = await self._db_query_silent_leads(cutoff)

        logger.info("silent_leads_found", count=len(leads))
        return leads

    # -- Message generation --

    async def generate_nurture_message(self, lead_id: str, tier: NurtureTier) -> dict[str, Any] | None:
        """
        Generate a personalized nurture message using LLM + MLS data.
        Returns message dict or None if generation fails.
        """
        lead_info = await self._db_get_lead_info(lead_id)
        if not lead_info:
            return None

        # Get matching MLS listings for value-drop messages
        matching_listings = []
        if tier in (NurtureTier.TIER_2, NurtureTier.MONTHLY) and self._mls_matcher:
            matching_listings = await self._mls_matcher.find_matches(
                lead_id=lead_id,
                limit=3,
            )

        # Build prompt based on tier
        prompt = self._build_nurture_prompt(lead_info, tier, matching_listings)

        if not self._llm:
            return self._fallback_message(lead_info, tier)

        try:
            response = await self._llm.generate(prompt)
            return {
                "lead_id": lead_id,
                "tier": tier.value,
                "message": response,
                "listings": matching_listings,
                "generated_at": time.time(),
            }
        except Exception as exc:
            logger.error("nurture_llm_failed", lead_id=lead_id, error=str(exc))
            return self._fallback_message(lead_info, tier)

    def _build_nurture_prompt(
        self, lead_info: dict, tier: NurtureTier, listings: list,
    ) -> str:
        """Build LLM prompt for nurture message generation."""
        base = (
            "You are a friendly real estate assistant. Write a short WhatsApp message "
            "(max 3 sentences) to re-engage a lead who has gone quiet.\n\n"
            f"Lead: {lead_info.get('name', 'there')}\n"
            f"Looking for: {lead_info.get('property_preferences', 'N/A')}\n"
            f"Budget: {lead_info.get('budget', 'N/A')}\n"
        )

        if tier == NurtureTier.TIER_1:
            base += "\nGoal: Gentle check-in. Ask if they're still interested."
        elif tier == NurtureTier.TIER_2:
            base += "\nGoal: Share new listings that match their criteria."
            if listings:
                base += f"\nMatching listings: {json.dumps(listings[:2])}"
        elif tier == NurtureTier.TIER_3:
            base += "\nGoal: Share a market insight relevant to their area."
        elif tier == NurtureTier.MONTHLY:
            base += "\nGoal: Monthly market update with any new listings."
            if listings:
                base += f"\nNew listings: {json.dumps(listings[:3])}"

        base += "\n\nKeep it casual, not salesy. No emojis overload."
        return base

    def _fallback_message(self, lead_info: dict, tier: NurtureTier) -> dict[str, Any]:
        """Fallback message when LLM is unavailable."""
        name = lead_info.get("name", "there")
        messages = {
            NurtureTier.TIER_1: f"Hi {name}! Just checking in — still looking for a property? Let me know if I can help.",
            NurtureTier.TIER_2: f"Hi {name}! Some new properties just came on the market that match what you're looking for. Want me to send you the details?",
            NurtureTier.TIER_3: f"Hi {name}! The market's been moving — wanted to share some insights that might be relevant to your search.",
            NurtureTier.MONTHLY: f"Hi {name}! Here's your monthly market update with new listings in your area.",
        }
        return {
            "lead_id": lead_info.get("lead_id"),
            "tier": tier.value,
            "message": messages.get(tier, messages[NurtureTier.TIER_1]),
            "listings": [],
            "generated_at": time.time(),
            "fallback": True,
        }

    # -- Sending --

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _send_nurture(self, lead: dict, message: dict, tier: NurtureTier) -> bool:
        """Send nurture message via WhatsApp gateway."""
        if not self._whatsapp:
            logger.warning("no_whatsapp_gateway")
            return False

        try:
            result = await self._whatsapp.send_message(
                to=lead["phone"],
                message=message["message"],
                message_type="nurture",
                metadata={
                    "lead_id": lead["lead_id"],
                    "tier": tier.value,
                },
            )
            logger.info("nurture_sent", lead_id=lead["lead_id"], tier=tier.value)
            return True
        except Exception as exc:
            logger.error("nurture_send_failed", lead_id=lead["lead_id"], error=str(exc))
            raise

    # -- Tracking --

    async def track_nurture_attempts(self, lead_id: str) -> None:
        """
        Record a nurture attempt and manage tier progression.
        Tier 1 → 2 → 3 → monthly after that.
        """
        key = f"nurture:attempts:{lead_id}"

        if self._redis:
            data = await self._redis.get(key)
            attempts = json.loads(data) if data else {"count": 0, "tier": 1, "timestamps": []}

            attempts["count"] += 1
            attempts["timestamps"].append(time.time())

            # Progress tier
            if attempts["count"] >= 4:
                attempts["tier"] = NurtureTier.MONTHLY
            elif attempts["count"] == 3:
                attempts["tier"] = NurtureTier.TIER_3
            elif attempts["count"] == 2:
                attempts["tier"] = NurtureTier.TIER_2

            await self._redis.set(key, json.dumps(attempts), ex=86400 * 90)
        else:
            await self._db_track_nurture(lead_id)

        logger.debug("nurture_tracked", lead_id=lead_id)

    async def _determine_tier(self, lead: dict) -> NurtureTier:
        """Determine which nurture tier a lead should receive."""
        if not self._redis:
            return NurtureTier.TIER_1

        data = await self._redis.get(f"nurture:attempts:{lead['lead_id']}")
        if not data:
            return NurtureTier.TIER_1

        attempts = json.loads(data)
        tier_value = attempts.get("tier", 1)
        return NurtureTier(min(tier_value, 4))

    # -- Opt-out handling --

    async def respect_opt_outs(self, lead_id: str) -> bool:
        """
        Check if lead has opted out of nurture messages.
        Returns True if OK to send, False if opted out.
        """
        # Check DO_NOT_CONTACT flag
        opted_out = await self._db_check_opt_out(lead_id)
        if opted_out:
            logger.info("nurture_opted_out", lead_id=lead_id)
            return False

        # Check Redis quick-flag
        if self._redis:
            blocked = await self._redis.get(f"opt_out:{lead_id}")
            if blocked:
                return False

        return True

    # -- DB stubs --

    async def _db_query_silent_leads(self, cutoff: datetime) -> list[dict[str, Any]]:
        """Query leads with no activity since cutoff."""
        return []  # Implement with SQLAlchemy

    async def _db_get_lead_info(self, lead_id: str) -> dict[str, Any] | None:
        """Get lead details for message personalization."""
        return None  # Implement with SQLAlchemy

    async def _db_check_opt_out(self, lead_id: str) -> bool:
        """Check if lead has DO_NOT_CONTACT flag."""
        return False  # Implement with SQLAlchemy

    async def _db_track_nurture(self, lead_id: str) -> None:
        """Record nurture attempt in DB (fallback when no Redis)."""
        pass  # Implement with SQLAlchemy
