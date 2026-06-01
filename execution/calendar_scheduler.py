"""
Calendar Scheduler - Google Calendar integration.

Handles appointment booking, availability checks, conflict detection,
and ICS file generation. Uses Google service-account auth.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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

GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class CalendarError(Exception):
    """Raised when a calendar operation fails."""


class SlotConflictError(CalendarError):
    """Raised when the requested slot conflicts with existing events."""


class CalendarScheduler:
    """Google Calendar integration for appointment management."""

    def __init__(self, whatsapp_gateway=None) -> None:
        self._calendar_id = settings.GOOGLE_CALENDAR_ID
        self._sa_json_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON
        self._slot_duration = settings.CALENDAR_SLOT_DURATION_MIN
        self._tz = ZoneInfo(settings.CALENDAR_TZ)
        self._gateway = whatsapp_gateway  # optional, for reminders

        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expires: datetime | None = None

    # ── lifecycle ───────────────────────────────────────────────────
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── auth ────────────────────────────────────────────────────────
    async def _ensure_token(self) -> str:
        """Get a valid OAuth2 access token via service-account JWT grant."""
        if self._access_token and self._token_expires:
            if datetime.now(ZoneInfo("UTC")) < self._token_expires:
                return self._access_token

        if not self._sa_json_path:
            raise CalendarError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")

        try:
            # Read service account key
            with open(self._sa_json_path) as f:
                sa_key = json.load(f)

            client_email = sa_key["client_email"]
            private_key = sa_key["private_key"]
            token_uri = sa_key.get("token_uri", GOOGLE_TOKEN_URL)

            # Build JWT assertion
            import jwt  # PyJWT

            now = datetime.now(ZoneInfo("UTC"))
            payload = {
                "iss": client_email,
                "scope": "https://www.googleapis.com/auth/calendar",
                "aud": token_uri,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
            assertion = jwt.encode(payload, private_key, algorithm="RS256")

            # Exchange for access token
            client = await self._get_client()
            resp = await client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            self._access_token = data["access_token"]
            self._token_expires = now + timedelta(seconds=data.get("expires_in", 3600) - 60)

            logger.info("calendar.token_refreshed")
            return self._access_token

        except FileNotFoundError:
            raise CalendarError(f"Service account key not found: {self._sa_json_path}")
        except Exception as exc:
            logger.error("calendar.auth_failed", error=str(exc))
            raise CalendarError(f"Authentication failed: {exc}") from exc

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated Google Calendar API request."""
        token = await self._ensure_token()
        client = await self._get_client()

        url = f"{GOOGLE_CALENDAR_API}{path}"
        resp = await client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=json_body,
            params=params,
        )

        if resp.status_code == 429:
            logger.warning("calendar.rate_limited")
            resp.raise_for_status()

        if resp.status_code >= 400:
            logger.error("calendar.api_error", status=resp.status_code, body=resp.text[:300])
            raise CalendarError(f"Calendar API {resp.status_code}: {resp.text[:200]}")

        return resp.json() if resp.text else {}

    # ── availability ────────────────────────────────────────────────
    async def get_available_slots(
        self,
        agent_id: str,
        date_range: tuple[datetime, datetime],
        slot_duration_min: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch available time slots for an agent within a date range.

        Args:
            agent_id: Agent identifier (used as calendarId or email).
            date_range: (start, end) datetime tuple.
            slot_duration_min: Override default slot duration.

        Returns:
            List of {"start": str, "end": str} available slots in ISO format.
        """
        start, end = date_range
        duration = slot_duration_min or self._slot_duration

        # Ensure timezone-aware
        if start.tzinfo is None:
            start = start.replace(tzinfo=self._tz)
        if end.tzinfo is None:
            end = end.replace(tzinfo=self._tz)

        # Fetch busy times from Google
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": str(self._tz),
            "items": [{"id": agent_id or self._calendar_id}],
        }

        data = await self._api_request(
            "POST",
            "/freeBusy",
            json_body=body,
        )

        busy_slots = []
        calendars = data.get("calendars", {})
        for cal_data in calendars.values():
            for busy in cal_data.get("busy", []):
                busy_slots.append({
                    "start": datetime.fromisoformat(busy["start"]),
                    "end": datetime.fromisoformat(busy["end"]),
                })

        # Generate available slots by splitting around busy times
        available = []
        current = start
        slot_delta = timedelta(minutes=duration)

        while current + slot_delta <= end:
            slot_end = current + slot_delta

            # Check for conflicts
            conflict = False
            for busy in busy_slots:
                if current < busy["end"] and slot_end > busy["start"]:
                    conflict = True
                    break

            if not conflict:
                available.append({
                    "start": current.isoformat(),
                    "end": slot_end.isoformat(),
                })

            current += slot_delta

        logger.info(
            "calendar.available_slots",
            agent_id=agent_id,
            date_range=f"{start.date()} to {end.date()}",
            slots=len(available),
        )
        return available

    # ── booking ─────────────────────────────────────────────────────
    async def book_appointment(
        self,
        agent_id: str,
        lead_id: str,
        slot: dict[str, str],
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a calendar event for an appointment.

        Args:
            agent_id: Agent's calendar ID or email.
            lead_id: Lead identifier for reference.
            slot: {"start": ISO datetime, "end": ISO datetime}.
            details: Optional dict with title, description, location, lead_name, lead_phone.

        Returns:
            Created event dict with event_id, htmlLink, etc.
        """
        details = details or {}

        # Check for conflicts first
        start = datetime.fromisoformat(slot["start"])
        end = datetime.fromisoformat(slot["end"])

        existing = await self.get_available_slots(
            agent_id=agent_id,
            date_range=(start, end),
        )

        if not existing:
            raise SlotConflictError(
                f"Slot {slot['start']} – {slot['end']} is not available"
            )

        # Build event body
        event_body = {
            "summary": details.get("title", f"Property Showing – Lead {lead_id}"),
            "description": self._build_description(lead_id, details),
            "start": {
                "dateTime": slot["start"],
                "timeZone": str(self._tz),
            },
            "end": {
                "dateTime": slot["end"],
                "timeZone": str(self._tz),
            },
            "attendees": [],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 15},
                ],
            },
        }

        if details.get("location"):
            event_body["location"] = details["location"]

        # Add agent as attendee if it's an email
        if "@" in str(agent_id):
            event_body["attendees"].append({"email": agent_id})

        calendar_id = agent_id if "@" in str(agent_id) else self._calendar_id
        result = await self._api_request(
            "POST",
            f"/calendars/{calendar_id}/events",
            json_body=event_body,
        )

        event_id = result.get("id", "")
        logger.info(
            "calendar.event_created",
            event_id=event_id,
            lead_id=lead_id,
            start=slot["start"],
        )

        # Store in database for reference
        await self._persist_appointment(event_id, lead_id, slot, details)

        return {
            "event_id": event_id,
            "html_link": result.get("htmlLink", ""),
            "start": slot["start"],
            "end": slot["end"],
            "status": "confirmed",
        }

    # ── cancellation ────────────────────────────────────────────────
    async def cancel_appointment(
        self,
        event_id: str,
        agent_id: str | None = None,
    ) -> bool:
        """Cancel (delete) a calendar event.

        Args:
            event_id: The Google Calendar event ID.
            agent_id: Agent's calendar ID. Falls back to default.

        Returns:
            True if cancelled successfully.
        """
        calendar_id = agent_id if agent_id and "@" in str(agent_id) else self._calendar_id

        try:
            await self._api_request(
                "DELETE",
                f"/calendars/{calendar_id}/events/{event_id}",
            )
            logger.info("calendar.event_cancelled", event_id=event_id)
            return True
        except CalendarError as exc:
            logger.error("calendar.cancel_failed", event_id=event_id, error=str(exc))
            return False

    # ── reminders ───────────────────────────────────────────────────
    async def send_reminder(
        self,
        lead_id: str,
        appointment_id: str,
        message: str | None = None,
    ) -> bool:
        """Send a WhatsApp reminder for an upcoming appointment.

        Args:
            lead_id: Lead identifier.
            appointment_id: The calendar event ID.
            message: Optional custom reminder message.

        Returns:
            True if the reminder was sent successfully.
        """
        if not self._gateway:
            logger.warning("calendar.no_gateway", msg="WhatsApp gateway not configured")
            return False

        try:
            # Look up appointment details from DB
            appt = await self._get_appointment(appointment_id)
            if not appt:
                logger.warning("calendar.appointment_not_found", appointment_id=appointment_id)
                return False

            lead_phone = appt.get("lead_phone")
            if not lead_phone:
                logger.warning("calendar.no_phone", lead_id=lead_id)
                return False

            # Format reminder
            if not message:
                start_dt = datetime.fromisoformat(appt["start"])
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=self._tz)
                local_dt = start_dt.astimezone(self._tz)

                message = (
                    f"🏠 Reminder: You have a property showing scheduled!\n\n"
                    f"📅 Date: {local_dt.strftime('%A, %B %d')}\n"
                    f"🕐 Time: {local_dt.strftime('%I:%M %p')}\n"
                )
                if appt.get("location"):
                    message += f"📍 Location: {appt['location']}\n"
                message += "\nReply CONFIRM to confirm or RESCHEDULE to change the time."

            await self._gateway.send_text_message(lead_phone, message)
            logger.info("calendar.reminder_sent", lead_id=lead_id, appointment_id=appointment_id)
            return True

        except Exception as exc:
            logger.error("calendar.reminder_failed", error=str(exc))
            return False

    # ── ICS generation ──────────────────────────────────────────────
    @staticmethod
    def generate_ics(event_details: dict[str, Any]) -> str:
        """Generate an ICS (iCalendar) file content for an event.

        Args:
            event_details: Dict with:
                - uid: Event unique ID
                - summary: Event title
                - description: Event description
                - location: Event location
                - start: ISO datetime string
                - end: ISO datetime string
                - organizer_email: Organizer email (optional)
                - attendee_email: Attendee email (optional)

        Returns:
            ICS file content as a string.
        """
        uid = event_details.get("uid", "unknown")
        summary = event_details.get("summary", "Appointment")
        description = event_details.get("description", "").replace("\n", "\\n")
        location = event_details.get("location", "")

        start = event_details.get("start", "")
        end = event_details.get("end", "")

        # Format datetimes for ICS (YYYYMMDDTHHMMSSZ)
        def _fmt_ics(iso_str: str) -> str:
            try:
                dt = datetime.fromisoformat(iso_str)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(ZoneInfo("UTC"))
                return dt.strftime("%Y%m%dT%H%M%SZ")
            except (ValueError, TypeError):
                return "20250101T120000Z"

        now = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//RealtyDOE//Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART:{_fmt_ics(start)}",
            f"DTEND:{_fmt_ics(end)}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
        ]

        if location:
            lines.append(f"LOCATION:{location}")

        if event_details.get("organizer_email"):
            lines.append(f"ORGANIZER:mailto:{event_details['organizer_email']}")

        if event_details.get("attendee_email"):
            lines.append(f"ATTENDEE:mailto:{event_details['attendee_email']}")

        lines.extend([
            "STATUS:CONFIRMED",
            "BEGIN:VALARM",
            "TRIGGER:-PT60M",
            "ACTION:DISPLAY",
            "DESCRIPTION:Reminder",
            "END:VALARM",
            "END:VEVENT",
            "END:VCALENDAR",
        ])

        return "\r\n".join(lines)

    # ── helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _build_description(lead_id: str, details: dict[str, Any]) -> str:
        """Build event description from lead and appointment details."""
        parts = [f"Lead ID: {lead_id}"]
        if details.get("lead_name"):
            parts.append(f"Lead: {details['lead_name']}")
        if details.get("lead_phone"):
            parts.append(f"Phone: {details['lead_phone']}")
        if details.get("property_address"):
            parts.append(f"Property: {details['property_address']}")
        if details.get("notes"):
            parts.append(f"\nNotes: {details['notes']}")
        return "\n".join(parts)

    async def _persist_appointment(
        self,
        event_id: str,
        lead_id: str,
        slot: dict[str, str],
        details: dict[str, Any],
    ) -> None:
        """Store appointment record in the database."""
        try:
            import asyncpg
            pool = await asyncpg.create_pool(
                settings.DATABASE_URL.replace("+asyncpg", ""),
                min_size=1,
                max_size=2,
            )
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO appointments
                        (event_id, lead_id, start_time, end_time, location, notes, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'confirmed')
                    ON CONFLICT (event_id) DO UPDATE
                    SET start_time = $3, end_time = $4, location = $5, notes = $6
                    """,
                    event_id,
                    lead_id,
                    datetime.fromisoformat(slot["start"]),
                    datetime.fromisoformat(slot["end"]),
                    details.get("location", ""),
                    details.get("notes", ""),
                )
            await pool.close()
        except Exception as exc:
            logger.warning("calendar.persist_failed", error=str(exc))

    async def _get_appointment(self, appointment_id: str) -> dict[str, Any] | None:
        """Fetch appointment details from the database."""
        try:
            import asyncpg
            pool = await asyncpg.create_pool(
                settings.DATABASE_URL.replace("+asyncpg", ""),
                min_size=1,
                max_size=2,
            )
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT a.*, l.phone as lead_phone, l.name as lead_name
                    FROM appointments a
                    LEFT JOIN leads l ON l.id = a.lead_id
                    WHERE a.event_id = $1
                    """,
                    appointment_id,
                )
            await pool.close()
            if row:
                return dict(row)
            return None
        except Exception as exc:
            logger.warning("calendar.fetch_failed", error=str(exc))
            return None
