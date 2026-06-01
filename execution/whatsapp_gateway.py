"""
Meta WhatsApp Cloud API Gateway.

Handles all outbound WhatsApp messaging and webhook verification.
Uses async httpx with exponential backoff for rate-limit resilience.
"""

from __future__ import annotations

import hashlib
import hmac
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

# ── Retryable 429 exception ────────────────────────────────────────
class RateLimitedError(Exception):
    """Raised when the Meta API returns 429."""


class WhatsAppAPIError(Exception):
    """Raised for non-retryable Meta API errors."""

    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body
        super().__init__(f"WhatsApp API {status}: {body}")


# ── Gateway ────────────────────────────────────────────────────────
class WhatsAppGateway:
    """Async interface to the Meta Cloud API for WhatsApp Business."""

    def __init__(self) -> None:
        self._base = settings.WHATSAPP_API_URL.rstrip("/")
        self._token = settings.WHATSAPP_ACCESS_TOKEN
        self._phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self._app_secret = settings.WHATSAPP_APP_SECRET
        self._client: httpx.AsyncClient | None = None

    # ── lifecycle ───────────────────────────────────────────────────
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── internal send helper ────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type(RateLimitedError),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _send_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a message payload to the Messages endpoint with retry."""
        client = await self._get_client()
        url = f"{self._base}/{self._phone_id}/messages"

        logger.debug("wa.send", payload=payload)
        resp = await client.post(url, json=payload)

        if resp.status_code == 429:
            logger.warning("wa.rate_limited", retry_after=resp.headers.get("Retry-After"))
            raise RateLimitedError()

        if resp.status_code >= 400:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
            raise WhatsAppAPIError(resp.status_code, body)

        data = resp.json()
        logger.info("wa.message_sent", message_id=data.get("messages", [{}])[0].get("id"))
        return data

    # ── public API ──────────────────────────────────────────────────
    async def send_text_message(self, phone: str, text: str) -> dict[str, Any]:
        """Send a plain text message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return await self._send_message(payload)

    async def send_interactive_buttons(
        self,
        phone: str,
        body: str,
        buttons: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send interactive button message.

        Each button: {"id": str, "title": str}
        Max 3 buttons per Meta spec.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": b["id"], "title": b["title"]},
                        }
                        for b in buttons[:3]
                    ]
                },
            },
        }
        return await self._send_message(payload)

    async def send_interactive_list(
        self,
        phone: str,
        body: str,
        sections: list[dict[str, Any]],
        button_text: str = "Choose an option",
    ) -> dict[str, Any]:
        """Send interactive list/menu message.

        Each section: {"title": str, "rows": [{"id": str, "title": str, "description": str}]}
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {
                    "button": button_text,
                    "sections": sections,
                },
            },
        }
        return await self._send_message(payload)

    async def send_template_message(
        self,
        phone: str,
        template_name: str,
        params: list[str] | None = None,
        language: str = "en_US",
    ) -> dict[str, Any]:
        """Send a pre-approved template message."""
        components: list[dict] = []
        if params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in params],
            })

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }
        if components:
            payload["template"]["components"] = components

        return await self._send_message(payload)

    async def send_media_message(
        self,
        phone: str,
        media_type: str,
        url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send an image, document, or audio message.

        media_type: "image" | "document" | "audio" | "video"
        """
        media_obj: dict[str, Any] = {"link": url}
        if caption and media_type in ("image", "document", "video"):
            media_obj["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": media_type,
            media_type: media_obj,
        }
        return await self._send_message(payload)

    async def send_flow_message(
        self,
        phone: str,
        flow_id: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a WhatsApp Flow interactive message."""
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "action": {
                    "name": "flow",
                    "parameters": {
                        "flow_id": flow_id,
                        "flow_cta": "Get Started",
                        "flow_action": "navigate",
                    },
                },
            },
        }
        if data:
            payload["interactive"]["action"]["parameters"]["flow_data"] = data
        return await self._send_message(payload)

    # ── media download ──────────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type(RateLimitedError),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Download incoming media from Meta by media_id.

        Returns (content_bytes, mime_type).
        """
        client = await self._get_client()

        # Step 1: get the download URL
        meta_resp = await client.get(f"{self._base}/{media_id}")
        if meta_resp.status_code == 429:
            raise RateLimitedError()
        if meta_resp.status_code >= 400:
            body = meta_resp.json() if "json" in meta_resp.headers.get("content-type", "") else {}
            raise WhatsAppAPIError(meta_resp.status_code, body)

        meta = meta_resp.json()
        download_url = meta["url"]
        mime_type = meta.get("mime_type", "application/octet-stream")

        # Step 2: download the binary
        bin_resp = await client.get(download_url)
        if bin_resp.status_code == 429:
            raise RateLimitedError()
        bin_resp.raise_for_status()

        logger.info("wa.media_downloaded", media_id=media_id, size=len(bin_resp.content))
        return bin_resp.content, mime_type

    # ── webhook helpers ─────────────────────────────────────────────
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify X-Hub-Signature-256 header against the app secret.

        signature format: sha256=<hex digest>
        """
        if not self._app_secret:
            logger.warning("wa.no_app_secret – skipping signature verification")
            return True

        expected = hmac.new(
            self._app_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        expected_full = f"sha256={expected}"
        return hmac.compare_digest(expected_full, signature)

    @staticmethod
    def parse_webhook_event(body: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse an incoming WhatsApp webhook JSON body.

        Returns a list of normalised event dicts:
        [
            {
                "type": "text" | "image" | "audio" | "video" | "document" | "interactive" | "button" | "status" | ...,
                "from": str,          # sender phone (E.164)
                "timestamp": str,
                "message_id": str,
                "data": dict,         # type-specific payload
            }
        ]
        """
        events: list[dict[str, Any]] = []

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Status updates (delivery, read, sent)
                for status in value.get("statuses", []):
                    events.append({
                        "type": "status",
                        "from": status.get("recipient_id", ""),
                        "timestamp": status.get("timestamp", ""),
                        "message_id": status.get("id", ""),
                        "data": {
                            "status": status.get("status"),
                            "errors": status.get("errors", []),
                        },
                    })

                # Incoming messages
                for msg in value.get("messages", []):
                    msg_type = msg.get("type", "unknown")
                    data: dict[str, Any] = {}

                    if msg_type == "text":
                        data["text"] = msg.get("text", {}).get("body", "")
                    elif msg_type == "image":
                        data["media_id"] = msg.get("image", {}).get("id")
                        data["mime_type"] = msg.get("image", {}).get("mime_type")
                        data["caption"] = msg.get("image", {}).get("caption")
                    elif msg_type == "audio":
                        data["media_id"] = msg.get("audio", {}).get("id")
                        data["mime_type"] = msg.get("audio", {}).get("mime_type")
                        data["voice"] = msg.get("audio", {}).get("voice", False)
                    elif msg_type == "video":
                        data["media_id"] = msg.get("video", {}).get("id")
                        data["caption"] = msg.get("video", {}).get("caption")
                    elif msg_type == "document":
                        data["media_id"] = msg.get("document", {}).get("id")
                        data["filename"] = msg.get("document", {}).get("filename")
                        data["mime_type"] = msg.get("document", {}).get("mime_type")
                    elif msg_type == "interactive":
                        interactive = msg.get("interactive", {})
                        data["interactive_type"] = interactive.get("type")
                        if interactive.get("type") == "button_reply":
                            data["button_id"] = interactive["button_reply"]["id"]
                            data["button_title"] = interactive["button_reply"]["title"]
                        elif interactive.get("type") == "list_reply":
                            data["list_id"] = interactive["list_reply"]["id"]
                            data["list_title"] = interactive["list_reply"]["title"]
                    elif msg_type == "button":
                        data["button_payload"] = msg.get("button", {}).get("payload")
                        data["button_text"] = msg.get("button", {}).get("text")
                    elif msg_type == "location":
                        data["latitude"] = msg.get("location", {}).get("latitude")
                        data["longitude"] = msg.get("location", {}).get("longitude")
                        data["address"] = msg.get("location", {}).get("address")
                    elif msg_type == "contacts":
                        data["contacts"] = msg.get("contacts", [])
                    else:
                        data["raw"] = msg

                    # Extract contact name if available
                    contacts_map = {
                        c["wa_id"]: c.get("profile", {}).get("name", "")
                        for c in value.get("contacts", [])
                    }

                    events.append({
                        "type": msg_type,
                        "from": msg.get("from", ""),
                        "timestamp": msg.get("timestamp", ""),
                        "message_id": msg.get("id", ""),
                        "contact_name": contacts_map.get(msg.get("from", ""), ""),
                        "data": data,
                    })

        return events
