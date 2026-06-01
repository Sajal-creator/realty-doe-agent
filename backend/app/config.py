"""
Realty DOE Agent - Configuration
All settings loaded from .env via pydantic-settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────
    APP_NAME: str = "Realty DOE Agent"
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api/v1"

    # ── Meta WhatsApp Cloud API ───────────────────────────────────
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v19.0"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_WEBHOOK_PATH: str = "/webhook/whatsapp"

    # ── LLM Providers ─────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.3

    GOOGLE_API_KEY: str = ""
    GOOGLE_MODEL: str = "gemini-2.0-flash"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    LLM_PROVIDER: str = "openai"  # openai | google | anthropic

    # ── PostgreSQL ────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://realty:realty@postgres:5432/realty_db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_SESSION_TTL: int = 86400  # 24h
    REDIS_RATE_LIMIT_TTL: int = 60

    # ── Google Calendar ───────────────────────────────────────────
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # path to JSON key file
    CALENDAR_SLOT_DURATION_MIN: int = 30
    CALENDAR_TZ: str = "America/New_York"

    # ── Mapbox ────────────────────────────────────────────────────
    MAPBOX_ACCESS_TOKEN: str = ""
    MAPBOX_STYLE: str = "mapbox://styles/mapbox/streets-v12"

    # ── JWT / Auth ────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # ── Rate Limiting ─────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_WHATSAPP_PER_MIN: int = 20

    # ── Nurture Engine ────────────────────────────────────────────
    NURTURE_REENGAGE_HOURS: int = 48
    NURTURE_MAX_FOLLOWUPS: int = 5
    NURTURE_QUIET_START_HOUR: int = 21  # no messages after 9 PM
    NURTURE_QUIET_END_HOUR: int = 8    # no messages before 8 AM
    NURTURE_QUIET_TZ: str = "America/New_York"

    # ── Warmth Scoring ────────────────────────────────────────────
    WARMTH_COLD_THRESHOLD: int = 30
    WARMTH_WARM_THRESHOLD: int = 60
    WARMTH_HOT_THRESHOLD: int = 80
    WARMTH_DECAY_PER_DAY: float = 2.0
    WARMTH_MSG_BONUS: float = 5.0
    WARMTH_VIEWING_BONUS: float = 15.0
    WARMTH_CALL_BONUS: float = 20.0

    # ── WebSocket ─────────────────────────────────────────────────
    WS_PATH: str = "/ws"
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 100

    # ── Frontend ──────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Scheduler ─────────────────────────────────────────────────
    SCHEDULER_REENGAGE_CRON: str = "0 9 * * *"  # every day at 9 AM
    SCHEDULER_WARMTH_DECAY_CRON: str = "0 0 * * *"  # midnight


@lru_cache()
def get_settings() -> Settings:
    return Settings()
