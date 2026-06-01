"""
Organic Inbound Handler.
Classifies first-contact messages from organic leads (QR signs, website, referrals)
and generates personalized discovery greetings.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

from config import settings

logger = structlog.get_logger(__name__)


class LeadType(str, Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    NEIGHBOR = "NEIGHBOR"
    UNKNOWN = "UNKNOWN"


class TrackingSource(str, Enum):
    QR_SIGN = "QR_SIGN"
    WEBSITE = "WEBSITE"
    REFERRAL = "REFERRAL"
    DIRECT = "DIRECT"


@dataclass
class FirstContactResult:
    lead_type: LeadType
    initial_intent: str
    source: TrackingSource
    raw_message: str
    greeting: str


# --- QR / tracking keywords used on signs ---
_QR_KEYWORDS: list[str] = [
    "property123", "dreamhome", "listing", "forsale",
    "openhouse", "tour", "scanme", "realtor",
]

_BUYER_SIGNALS = [
    "looking to buy", "want to buy", "buying a home", "purchase",
    "first time buyer", "pre-approved", "house hunt", "property search",
    "interested in buying", "show me homes",
]
_SELLER_SIGNALS = [
    "want to sell", "selling my", "list my home", "how much is my",
    "property value", "market value", "selling price", "list my property",
    "considering selling", "thinking of selling",
]
_NEIGHBOR_SIGNALS = [
    "neighbor", "neighbour", "live nearby", "live on", "next door",
    "across the street", "in the area", "local resident",
]


async def classify_first_contact(
    message_text: str,
    metadata: Optional[dict] = None,
) -> tuple[LeadType, str]:
    """
    Classify an organic inbound message into a lead type and initial intent.

    Returns:
        (LeadType, initial_intent_description)
    """
    lower = message_text.lower().strip()
    metadata = metadata or {}

    # Check QR keywords first (message may contain tracking keyword)
    source = await extract_tracking_source(message_text)
    if source == TrackingSource.QR_SIGN:
        # Strip QR keyword and classify remaining text
        cleaned = _strip_qr_keyword(lower)
        if not cleaned.strip():
            return LeadType.UNKNOWN, "qr_scan_no_message"

    # Buyer signals
    if any(sig in lower for sig in _BUYER_SIGNALS):
        return LeadType.BUYER, f"buyer_intent: {_match_signal(lower, _BUYER_SIGNALS)}"

    # Seller signals
    if any(sig in lower for sig in _SELLER_SIGNALS):
        return LeadType.SELLER, f"seller_intent: {_match_signal(lower, _SELLER_SIGNALS)}"

    # Neighbor signals
    if any(sig in lower for sig in _NEIGHBOR_SIGNALS):
        return LeadType.NEIGHBOR, f"neighbor_intent: {_match_signal(lower, _NEIGHBOR_SIGNALS)}"

    # Fallback heuristics
    if any(w in lower for w in ["buy", "buying", "purchase", "afford"]):
        return LeadType.BUYER, "inferred_buyer"
    if any(w in lower for w in ["sell", "selling", "value", "worth"]):
        return LeadType.SELLER, "inferred_seller"

    return LeadType.UNKNOWN, "unclassified"


async def extract_tracking_source(message_text: str) -> TrackingSource:
    """Determine how the lead found us based on message content or metadata."""
    lower = message_text.lower().strip()

    # QR sign keyword detection
    for kw in _QR_KEYWORDS:
        if kw in lower:
            return TrackingSource.QR_SIGN

    # URL/website detection
    if re.search(r"https?://|www\.", lower):
        return TrackingSource.WEBSITE

    # Referral phrases
    referral_phrases = ["referred by", "my friend", "someone told me", "recommended by"]
    if any(p in lower for p in referral_phrases):
        return TrackingSource.REFERRAL

    return TrackingSource.DIRECT


def _strip_qr_keyword(text: str) -> str:
    """Remove known QR tracking keywords from the message."""
    cleaned = text
    for kw in _QR_KEYWORDS:
        cleaned = cleaned.replace(kw, "")
    return cleaned.strip()


def _match_signal(text: str, signals: list[str]) -> str:
    """Return the first matching signal phrase."""
    for sig in signals:
        if sig in text:
            return sig
    return ""


async def generate_discovery_greeting(
    lead_type: LeadType,
    source: TrackingSource,
) -> str:
    """
    Generate a personalized first-message greeting based on lead type and source.

    Uses WhatsApp quick-reply buttons where supported.
    """
    if lead_type == LeadType.BUYER:
        if source == TrackingSource.QR_SIGN:
            return (
                "Welcome! 🏠 Saw you scanned the sign — exciting! "
                "Are you currently looking to buy a home in the area?"
            )
        if source == TrackingSource.REFERRAL:
            return (
                "Welcome! 😊 Great to hear from you. "
                "Are you looking to buy a property?"
            )
        return (
            "Hi there! 👋 Welcome! "
            "Are you looking to buy a home in the area?"
        )

    if lead_type == LeadType.SELLER:
        return (
            "Hi! 👋 Thanks for reaching out. "
            "Are you thinking about selling your property?"
        )

    if lead_type == LeadType.NEIGHBOR:
        return (
            "Hi neighbor! 👋 Thanks for getting in touch. "
            "Are you curious about the local market, or is there something I can help with?"
        )

    # UNKNOWN / generic
    if source == TrackingSource.QR_SIGN:
        return (
            "Welcome! 👋 Thanks for scanning! "
            "How can I help you today?"
        )
    return (
        "Hi there! 👋 Welcome! How can I help you today?"
    )


async def handle_qr_code_message(
    tracking_keyword: str,
    full_message: str = "",
) -> FirstContactResult:
    """
    Handle a message triggered by scanning a QR code on a property sign.
    Strips the tracking keyword, logs the source, and starts discovery.
    """
    # Log the QR scan source
    logger.info(
        "qr_scan_received",
        tracking_keyword=tracking_keyword,
        full_message=full_message,
    )

    # Strip keyword from message
    cleaned_message = _strip_qr_keyword(full_message.lower()).strip()

    # Classify using cleaned message (or empty = generic greeting)
    if cleaned_message:
        lead_type, intent = await classify_first_contact(cleaned_message)
    else:
        lead_type, intent = LeadType.UNKNOWN, "qr_scan_no_message"

    # Generate greeting
    greeting = await generate_discovery_greeting(lead_type, TrackingSource.QR_SIGN)

    return FirstContactResult(
        lead_type=lead_type,
        initial_intent=intent,
        source=TrackingSource.QR_SIGN,
        raw_message=full_message,
        greeting=greeting,
    )


async def build_quick_reply_buttons(lead_type: LeadType) -> list[dict]:
    """
    Build WhatsApp quick-reply button options based on lead type.

    Returns a list of button dicts suitable for WhatsApp interactive message API.
    """
    if lead_type == LeadType.UNKNOWN:
        return [
            {"id": "btn_buying", "title": "Buying"},
            {"id": "btn_selling", "title": "Selling"},
            {"id": "btn_address", "title": "Asking About Address"},
        ]
    if lead_type == LeadType.BUYER:
        return [
            {"id": "btn_buying", "title": "Yes, Buying"},
            {"id": "btn_just_looking", "title": "Just Looking"},
        ]
    if lead_type == LeadType.SELLER:
        return [
            {"id": "btn_selling", "title": "Yes, Selling"},
            {"id": "btn_just_curious", "title": "Just Curious"},
        ]
    # NEIGHBOR
    return [
        {"id": "btn_market_info", "title": "Market Info"},
        {"id": "btn_address", "title": "About This Listing"},
        {"id": "btn_general", "title": "Just Saying Hi"},
    ]
