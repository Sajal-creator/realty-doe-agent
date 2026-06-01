"""Knowledge base RAG: embed FAQ Q&A pairs and perform semantic search."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import openai
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

ESCALATION_THRESHOLD = 0.70

# Supported knowledge domains
DOMAINS = ("buying", "selling", "neighborhoods", "legal", "general")


def _get_session_factory():
    from database.session import async_session_factory
    return async_session_factory


def _get_faq_model():
    from database.models import FAQEntry
    return FAQEntry


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _get_embedding(text: str) -> list[float]:
    """Get OpenAI embedding for text."""
    client = openai.AsyncOpenAI()
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


async def index_faq(qa_pairs: list[dict[str, Any]]) -> list[dict]:
    """Embed and store FAQ Q&A pairs.

    Args:
        qa_pairs: List of dicts with 'question', 'answer', and optional 'domain'.
    """
    FAQEntry = _get_faq_model()
    results = []

    async with _get_session_factory()() as session:
        for pair in qa_pairs:
            question = pair.get("question", "").strip()
            answer = pair.get("answer", "").strip()
            domain = pair.get("domain", "general")
            if domain not in DOMAINS:
                domain = "general"

            if not question or not answer:
                logger.warning("skipping_invalid_faq", pair=pair)
                continue

            try:
                embedding = await _get_embedding(f"{question} {answer}")
            except Exception as e:
                logger.error("faq_embedding_failed", question=question, error=str(e))
                continue

            entry = FAQEntry(
                id=str(uuid.uuid4()),
                question=question,
                answer=answer,
                domain=domain,
                embedding=embedding,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(entry)
            results.append({"id": entry.id, "question": question, "domain": domain})

        await session.commit()

    logger.info("faq_indexed", count=len(results))
    return results


async def search_faq(
    query: str, top_k: int = 3, domain: Optional[str] = None
) -> dict:
    """Semantic search for relevant FAQ answers.

    Returns results with confidence scores. If best match confidence < 0.70,
    recommends escalation.
    """
    if not query or not query.strip():
        return {"results": [], "recommend_escalation": True, "reason": "empty_query"}

    try:
        query_embedding = await _get_embedding(query)
    except Exception as e:
        logger.error("faq_search_embedding_failed", error=str(e))
        return {"results": [], "recommend_escalation": True, "reason": "embedding_failed"}

    FAQEntry = _get_faq_model()
    async with _get_session_factory()() as session:
        # Use pgvector cosine distance for similarity search
        from sqlalchemy import text
        cosine_op = "<=>"

        sql = text(f"""
            SELECT id, question, answer, domain,
                   1 - (embedding {cosine_op} :query_vec) AS confidence
            FROM faq_entries
            {"WHERE domain = :domain" if domain else ""}
            ORDER BY embedding {cosine_op} :query_vec
            LIMIT :top_k
        """)

        params = {
            "query_vec": str(query_embedding),
            "top_k": top_k,
        }
        if domain:
            params["domain"] = domain

        result = await session.execute(sql, params)
        rows = result.fetchall()

    results = []
    for row in rows:
        confidence = max(0.0, min(1.0, float(row.confidence)))
        results.append({
            "id": row.id,
            "question": row.question,
            "answer": row.answer,
            "domain": row.domain,
            "confidence": round(confidence, 4),
        })

    best_confidence = results[0]["confidence"] if results else 0.0
    recommend_escalation = best_confidence < ESCALATION_THRESHOLD

    logger.info(
        "faq_search_completed",
        query_len=len(query),
        results=len(results),
        best_confidence=best_confidence,
        recommend_escalation=recommend_escalation,
    )

    return {
        "results": results,
        "recommend_escalation": recommend_escalation,
        "best_confidence": round(best_confidence, 4),
        "reason": "low_confidence" if recommend_escalation else None,
    }
