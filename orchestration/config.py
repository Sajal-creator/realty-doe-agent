"""Configuration shim for orchestration layer.

Re-exports settings from the main app config, adding orchestration-specific
field aliases (LLM_MODEL → OPENAI_MODEL, etc.).
"""

import sys
from pathlib import Path

# Ensure the backend app is importable
_backend_path = str(Path(__file__).resolve().parent.parent / "backend" / "app")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from config import get_settings as _get_settings  # noqa: E402

_raw = _get_settings()


class _OrchSettings:
    """Thin proxy that maps orchestration field names to the real config."""

    # Direct pass-through
    REDIS_URL: str = _raw.REDIS_URL
    DIRECTIVES_DIR: str = str(Path(__file__).resolve().parent.parent / "directives")

    # LLM aliases
    LLM_MODEL: str = _raw.OPENAI_MODEL
    LLM_TEMPERATURE: float = _raw.OPENAI_TEMPERATURE
    LLM_MAX_TOKENS: int = 2048
    LLM_PROVIDER: str = _raw.LLM_PROVIDER

    # Optional: dedicated model for intent classification (falls back to main)
    INTENT_MODEL: str = _raw.OPENAI_MODEL

    # Memory compressor threshold override
    MEMORY_TOKEN_THRESHOLD: int = 4000

    # Expose raw settings for anything else
    _raw = _raw


settings = _OrchSettings()
