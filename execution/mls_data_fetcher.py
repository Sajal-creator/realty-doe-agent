"""Property listing sync: fetch from MLS API, store, and match to leads."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import openai
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# Rate limit: max requests per minute to MLS API
RATE_LIMIT_RPM = 60
PAGE_SIZE = 100


def _get_session_factory():
    from app.database.session import async_session_factory
    return async_session_factory


def _get_models():
    from app.models.property_listing import PropertyListing
    return PropertyListing


def _get_lead_model():
    from app.models.lead import Lead
    return Lead


def _get_mls_config():
    """Load MLS API configuration."""
    import os
    return {
        "base_url": os.getenv("MLS_API_BASE_URL", "https://api.mls.example.com/v1"),
        "api_key": os.getenv("MLS_API_KEY", ""),
    }


# ─── Data Fetching ───────────────────────────────────────────────────────────


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def fetch_new_listings(since_timestamp: str) -> list[dict]:
    """Fetch newly listed properties since a given timestamp.

    Handles pagination and rate limits.
    """
    config = _get_mls_config()
    all_listings = []
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                response = await client.get(
                    f"{config['base_url']}/listings",
                    headers={"Authorization": f"Bearer {config['api_key']}"},
                    params={
                        "listed_since": since_timestamp,
                        "page": page,
                        "per_page": PAGE_SIZE,
                        "status": "active",
                    },
                )
                response.raise_for_status()
                data = response.json()

                listings = data.get("listings", [])
                if not listings:
                    break

                all_listings.extend(_normalize_listings(listings))
                logger.info("fetched_listings_page", page=page, count=len(listings))

                if len(listings) < PAGE_SIZE:
                    break
                page += 1

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("rate_limited", page=page)
                    import asyncio
                    await asyncio.sleep(60)
                    continue
                raise
            except Exception as e:
                logger.error("fetch_listings_failed", page=page, error=str(e))
                raise

    logger.info("fetch_new_listings_complete", total=len(all_listings))
    return all_listings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def fetch_price_changes(since_timestamp: str) -> list[dict]:
    """Fetch price drops and increases since a timestamp."""
    config = _get_mls_config()
    all_changes = []
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                response = await client.get(
                    f"{config['base_url']}/price-changes",
                    headers={"Authorization": f"Bearer {config['api_key']}"},
                    params={
                        "changed_since": since_timestamp,
                        "page": page,
                        "per_page": PAGE_SIZE,
                    },
                )
                response.raise_for_status()
                data = response.json()

                changes = data.get("changes", [])
                if not changes:
                    break

                all_changes.extend(changes)
                logger.info("fetched_price_changes_page", page=page, count=len(changes))

                if len(changes) < PAGE_SIZE:
                    break
                page += 1

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("rate_limited_price_changes", page=page)
                    import asyncio
                    await asyncio.sleep(60)
                    continue
                raise

    logger.info("fetch_price_changes_complete", total=len(all_changes))
    return all_changes


# ─── Sync & Embed ───────────────────────────────────────────────────────────


async def _get_listing_embedding(listing: dict) -> list[float]:
    """Generate embedding text for a listing."""
    text = (
        f"{listing.get('address', '')} "
        f"{listing.get('city', '')} "
        f"{listing.get('property_type', '')} "
        f"{listing.get('bedrooms', '')}bd {listing.get('bathrooms', '')}ba "
        f"${listing.get('price', 0):,.0f} "
        f"{listing.get('description', '')}"
    )
    try:
        client = openai.AsyncOpenAI()
        response = await client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("listing_embedding_failed", error=str(e))
        return []


async def sync_listings_to_db(listings: list[dict]) -> dict:
    """Upsert listings to database with vector embeddings."""
    PropertyListing = _get_models()
    created = 0
    updated = 0
    errors = 0

    async with _get_session_factory()() as session:
        from sqlalchemy import select

        for listing in listings:
            mls_id = listing.get("mls_id")
            if not mls_id:
                errors += 1
                continue

            embedding = await _get_listing_embedding(listing)

            result = await session.execute(
                select(PropertyListing).where(PropertyListing.mls_id == mls_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                for key in ("price", "status", "description", "days_on_market"):
                    if key in listing:
                        setattr(existing, key, listing[key])
                if embedding:
                    existing.embedding = embedding
                existing.updated_at = datetime.now(timezone.utc)
                updated += 1
            else:
                pl = PropertyListing(
                    id=str(uuid.uuid4()),
                    mls_id=mls_id,
                    address=listing.get("address"),
                    city=listing.get("city"),
                    state=listing.get("state"),
                    zip_code=listing.get("zip_code"),
                    price=listing.get("price"),
                    bedrooms=listing.get("bedrooms"),
                    bathrooms=listing.get("bathrooms"),
                    sqft=listing.get("sqft"),
                    property_type=listing.get("property_type"),
                    description=listing.get("description"),
                    status=listing.get("status", "active"),
                    embedding=embedding,
                    raw_data=listing,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(pl)
                created += 1

        await session.commit()

    result = {"created": created, "updated": updated, "errors": errors}
    logger.info("listings_synced", **result)
    return result


# ─── Lead Matching ───────────────────────────────────────────────────────────


async def match_listings_to_leads(listing: dict) -> list[dict]:
    """Find leads whose preferences match a new listing."""
    PropertyListing = _get_models()
    Lead = _get_lead_model()

    listing_embedding = await _get_listing_embedding(listing)
    if not listing_embedding:
        return []

    async with _get_session_factory()() as session:
        from sqlalchemy import text

        # Match via vector similarity on lead preferences embedding
        cosine_op = "<=>"
        sql = text(f"""
            SELECT id, name, phone, preferences, warmth_score,
                   1 - (preferences_embedding {cosine_op} :listing_vec) AS match_score
            FROM leads
            WHERE status IN ('new', 'contacted', 'qualified')
              AND preferences_embedding IS NOT NULL
            ORDER BY preferences_embedding {cosine_op} :listing_vec
            LIMIT 10
        """)

        result = await session.execute(sql, {"listing_vec": str(listing_embedding)})
        rows = result.fetchall()

    matches = []
    for row in rows:
        score = float(row.match_score)
        if score >= 0.65:
            matches.append({
                "lead_id": row.id,
                "name": row.name,
                "phone": row.phone,
                "match_score": round(score, 4),
                "warmth_score": float(row.warmth_score) if row.warmth_score else 0,
            })

    logger.info(
        "listings_matched_to_leads",
        listing_mls_id=listing.get("mls_id"),
        match_count=len(matches),
    )
    return matches


# ─── Normalization ───────────────────────────────────────────────────────────


def _normalize_listings(raw_listings: list[dict]) -> list[dict]:
    """Normalize raw MLS API response to standard format."""
    normalized = []
    for raw in raw_listings:
        normalized.append({
            "mls_id": raw.get("ListingId") or raw.get("mls_id", ""),
            "address": raw.get("UnparsedAddress") or raw.get("address", ""),
            "city": raw.get("City") or raw.get("city", ""),
            "state": raw.get("StateOrProvince") or raw.get("state", ""),
            "zip_code": raw.get("PostalCode") or raw.get("zip_code", ""),
            "price": _safe_float(raw.get("ListPrice") or raw.get("price", 0)),
            "bedrooms": _safe_int(raw.get("BedroomsTotal") or raw.get("bedrooms")),
            "bathrooms": _safe_float(raw.get("BathroomsTotalInteger") or raw.get("bathrooms")),
            "sqft": _safe_int(raw.get("LivingArea") or raw.get("sqft")),
            "property_type": raw.get("PropertyType") or raw.get("property_type", ""),
            "description": raw.get("PublicRemarks") or raw.get("description", ""),
            "status": raw.get("StandardStatus") or raw.get("status", "active"),
            "days_on_market": _safe_int(raw.get("DaysOnMarket")),
            "listed_at": raw.get("ListingContractDate") or raw.get("listed_at"),
            "photos": raw.get("Media", []),
        })
    return normalized


def _safe_float(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0
