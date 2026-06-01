"""
Vector MLS Matcher - Semantic property search using pgvector.

Creates OpenAI embeddings for property listings and lead queries,
then performs cosine similarity search via PostgreSQL pgvector.
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

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class VectorSearchError(Exception):
    """Raised when vector search fails."""


class VectorMLSMatcher:
    """Semantic property search powered by pgvector and OpenAI embeddings."""

    def __init__(self, db_pool=None) -> None:
        """Args:
            db_pool: An asyncpg connection pool. If None, will be lazy-initialised.
        """
        self._api_key = settings.OPENAI_API_KEY
        self._pool = db_pool
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                settings.DATABASE_URL.replace("+asyncpg", ""),
                min_size=2,
                max_size=settings.DB_POOL_SIZE,
            )
        return self._pool

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        if self._pool:
            await self._pool.close()

    # ── embeddings ──────────────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get_embedding(self, text: str) -> list[float]:
        """Get an OpenAI embedding vector for the given text."""
        client = await self._get_client()
        resp = await client.post(
            OPENAI_EMBEDDINGS_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": text,
                "dimensions": EMBEDDING_DIMENSIONS,
            },
        )

        if resp.status_code == 429:
            logger.warning("vector.rate_limited")
            resp.raise_for_status()

        if resp.status_code >= 400:
            logger.error("vector.embedding_error", status=resp.status_code, body=resp.text[:300])
            raise VectorSearchError(f"Embedding API error {resp.status_code}")

        data = resp.json()
        return data["data"][0]["embedding"]

    async def _get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts in one API call (up to 100)."""
        client = await self._get_client()
        resp = await client.post(
            OPENAI_EMBEDDINGS_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": texts,
                "dimensions": EMBEDDING_DIMENSIONS,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to maintain order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    # ── property text builder ───────────────────────────────────────
    @staticmethod
    def _build_property_text(property_data: dict[str, Any]) -> str:
        """Build a rich text representation of a property for embedding."""
        parts = []

        if property_data.get("address"):
            parts.append(f"Address: {property_data['address']}")
        if property_data.get("city"):
            parts.append(f"City: {property_data['city']}")
        if property_data.get("state"):
            parts.append(f"State: {property_data['state']}")
        if property_data.get("zip_code"):
            parts.append(f"ZIP: {property_data['zip_code']}")

        if property_data.get("price"):
            parts.append(f"Price: ${property_data['price']:,.0f}")
        if property_data.get("property_type"):
            parts.append(f"Type: {property_data['property_type']}")
        if property_data.get("bedrooms"):
            parts.append(f"Bedrooms: {property_data['bedrooms']}")
        if property_data.get("bathrooms"):
            parts.append(f"Bathrooms: {property_data['bathrooms']}")
        if property_data.get("sqft"):
            parts.append(f"Square feet: {property_data['sqft']:,}")
        if property_data.get("year_built"):
            parts.append(f"Year built: {property_data['year_built']}")
        if property_data.get("lot_size"):
            parts.append(f"Lot size: {property_data['lot_size']} acres")

        if property_data.get("features"):
            features = property_data["features"]
            if isinstance(features, list):
                parts.append(f"Features: {', '.join(features)}")
            else:
                parts.append(f"Features: {features}")

        if property_data.get("description"):
            parts.append(f"Description: {property_data['description']}")

        if property_data.get("neighborhood"):
            parts.append(f"Neighborhood: {property_data['neighborhood']}")
        if property_data.get("school_district"):
            parts.append(f"School district: {property_data['school_district']}")

        return ". ".join(parts)

    # ── indexing ────────────────────────────────────────────────────
    async def index_property(self, property_data: dict[str, Any]) -> str:
        """Create or update a vector embedding for a property listing.

        Args:
            property_data: Dict with property fields (address, price, bedrooms, etc.)
                           Must include 'id' or 'mls_number' for upsert.

        Returns:
            The property ID that was indexed.

        Raises:
            VectorSearchError: on embedding or DB failure.
        """
        prop_id = property_data.get("id") or property_data.get("mls_number")
        if not prop_id:
            raise VectorSearchError("Property must have 'id' or 'mls_number'")

        text = self._build_property_text(property_data)
        embedding = await self._get_embedding(text)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO property_embeddings (property_id, embedding, metadata, updated_at)
                VALUES ($1, $2::vector, $3, NOW())
                ON CONFLICT (property_id) DO UPDATE
                SET embedding = $2::vector,
                    metadata = $3,
                    updated_at = NOW()
                """,
                prop_id,
                str(embedding),
                json.dumps(property_data),
            )

        logger.info("vector.property_indexed", property_id=prop_id)
        return prop_id

    # ── search ──────────────────────────────────────────────────────
    async def search_properties(
        self,
        query_text: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Semantic search for properties using cosine similarity.

        Args:
            query_text: Natural language search query.
            filters: Optional SQL filters (price_min, price_max, property_type, city, etc.).
            limit: Max results to return.
            similarity_threshold: Minimum cosine similarity (0-1).

        Returns:
            List of property dicts with similarity scores.
        """
        embedding = await self._get_embedding(query_text)

        # Build optional WHERE clause from filters
        where_clauses: list[str] = []
        params: list[Any] = [str(embedding), similarity_threshold]
        param_idx = 3

        if filters:
            if filters.get("price_min"):
                where_clauses.append(f"(metadata->>'price')::numeric >= ${param_idx}")
                params.append(filters["price_min"])
                param_idx += 1
            if filters.get("price_max"):
                where_clauses.append(f"(metadata->>'price')::numeric <= ${param_idx}")
                params.append(filters["price_max"])
                param_idx += 1
            if filters.get("property_type"):
                where_clauses.append(f"metadata->>'property_type' = ${param_idx}")
                params.append(filters["property_type"])
                param_idx += 1
            if filters.get("city"):
                where_clauses.append(f"LOWER(metadata->>'city') = LOWER(${param_idx})")
                params.append(filters["city"])
                param_idx += 1
            if filters.get("bedrooms_min"):
                where_clauses.append(f"(metadata->>'bedrooms')::int >= ${param_idx}")
                params.append(filters["bedrooms_min"])
                param_idx += 1
            if filters.get("bathrooms_min"):
                where_clauses.append(f"(metadata->>'bathrooms')::numeric >= ${param_idx}")
                params.append(filters["bathrooms_min"])
                param_idx += 1

        where_sql = ""
        if where_clauses:
            where_sql = "AND " + " AND ".join(where_clauses)

        params.append(limit)

        query = f"""
            SELECT
                property_id,
                metadata,
                1 - (embedding <=> $1::vector) AS similarity
            FROM property_embeddings
            WHERE 1 - (embedding <=> $1::vector) >= $2
            {where_sql}
            ORDER BY embedding <=> $1::vector
            LIMIT ${param_idx}
        """

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
            meta["similarity"] = round(float(row["similarity"]), 4)
            meta["property_id"] = row["property_id"]
            results.append(meta)

        logger.info("vector.search_complete", query=query_text[:60], results=len(results))
        return results

    # ── match by lead preferences ───────────────────────────────────
    async def match_lead_preferences(
        self,
        lead_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find properties matching a lead's stored qualification data.

        Reads the lead's 4-D matrix data and constructs a semantic query.

        Args:
            lead_id: The lead's UUID.
            limit: Max results.

        Returns:
            List of matched property dicts.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    l.budget_min, l.budget_max, l.property_type,
                    l.bedrooms_min, l.bathrooms_min,
                    l.location_preferences, l.must_haves, l.nice_to_haves,
                    l.deal_breakers
                FROM leads l
                WHERE l.id = $1
                """,
                lead_id,
            )

        if not row:
            logger.warning("vector.lead_not_found", lead_id=lead_id)
            return []

        # Build a natural language query from the lead's preferences
        query_parts = []
        if row["property_type"]:
            query_parts.append(f"{row['property_type']} property")
        if row["budget_max"]:
            query_parts.append(f"under ${row['budget_max']:,.0f}")
        if row["bedrooms_min"]:
            query_parts.append(f"{row['bedrooms_min']}+ bedrooms")
        if row["bathrooms_min"]:
            query_parts.append(f"{row['bathrooms_min']}+ bathrooms")

        locations = row["location_preferences"]
        if locations:
            if isinstance(locations, str):
                locations = json.loads(locations)
            if isinstance(locations, list):
                query_parts.append(f"in {', '.join(locations)}")

        must_haves = row["must_haves"]
        if must_haves:
            if isinstance(must_haves, str):
                must_haves = json.loads(must_haves)
            if isinstance(must_haves, list):
                query_parts.append(f"with {', '.join(must_haves)}")

        if not query_parts:
            logger.info("vector.no_preferences", lead_id=lead_id)
            return []

        query_text = "Looking for " + ", ".join(query_parts)

        # Build filters from structured data
        filters: dict[str, Any] = {}
        if row["budget_max"]:
            filters["price_max"] = row["budget_max"]
        if row["budget_min"]:
            filters["price_min"] = row["budget_min"]
        if row["property_type"] and row["property_type"] != "any":
            filters["property_type"] = row["property_type"]

        results = await self.search_properties(
            query_text=query_text,
            filters=filters,
            limit=limit,
        )

        # Filter out properties that match deal-breakers
        deal_breakers = row.get("deal_breakers")
        if deal_breakers:
            if isinstance(deal_breakers, str):
                deal_breakers = json.loads(deal_breakers)
            if isinstance(deal_breakers, list) and deal_breakers:
                results = self._filter_deal_breakers(results, deal_breakers)

        logger.info("vector.lead_match", lead_id=lead_id, results=len(results))
        return results

    # ── find similar ────────────────────────────────────────────────
    async def find_similar(
        self,
        property_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find properties similar to a given one.

        Args:
            property_id: The reference property ID.
            limit: Max results (excluding the reference property).

        Returns:
            List of similar property dicts with similarity scores.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT embedding FROM property_embeddings WHERE property_id = $1",
                property_id,
            )

        if not row:
            logger.warning("vector.property_not_found", property_id=property_id)
            return []

        embedding_str = row["embedding"]

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    property_id,
                    metadata,
                    1 - (embedding <=> $1::vector) AS similarity
                FROM property_embeddings
                WHERE property_id != $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_str,
                property_id,
                limit,
            )

        results = []
        for row in rows:
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
            meta["similarity"] = round(float(row["similarity"]), 4)
            meta["property_id"] = row["property_id"]
            results.append(meta)

        logger.info("vector.similar_found", property_id=property_id, results=len(results))
        return results

    # ── deal-breaker filter ─────────────────────────────────────────
    @staticmethod
    def _filter_deal_breakers(
        properties: list[dict[str, Any]],
        deal_breakers: list[str],
    ) -> list[dict[str, Any]]:
        """Remove properties whose metadata mentions a deal-breaker.

        Simple keyword matching — for production, consider LLM-based filtering.
        """
        filtered = []
        for prop in properties:
            prop_text = json.dumps(prop).lower()
            has_breaker = False
            for breaker in deal_breakers:
                if breaker.lower() in prop_text:
                    logger.debug(
                        "vector.deal_breaker_hit",
                        property_id=prop.get("property_id"),
                        breaker=breaker,
                    )
                    has_breaker = True
                    break
            if not has_breaker:
                filtered.append(prop)
        return filtered
