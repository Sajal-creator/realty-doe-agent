"""
Async SQLAlchemy engine and session factory.

Usage:
    from app.database.session import async_session_factory, init_db

    # On startup:
    await init_db()  # creates tables if they don't exist

    # In your code:
    async with async_session_factory() as session:
        result = await session.execute(select(Lead))
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

# ── Engine ───────────────────────────────────────────────────────────────────
_engine = None


def get_engine():
    """Get or create the async SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            echo=settings.DB_ECHO,
            pool_pre_ping=True,
        )
    return _engine


# ── Session factory ─────────────────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=None,  # set dynamically on init
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Initialization ──────────────────────────────────────────────────────────
async def init_db() -> None:
    """
    Initialize the database engine and create all tables if they don't exist.
    Call this once during application startup.
    """
    global async_session_factory

    engine = get_engine()
    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import all models so Base.metadata knows about them
    from app.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Also create pgvector extension if using PostgreSQL
    try:
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
    except Exception:
        pass  # pgvector not available — vector search will fail gracefully
