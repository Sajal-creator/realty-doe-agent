"""
Realty DOE Agent - Execution Workers
Worker modules that perform actual labor in the DOE pipeline.
"""

# ── Path bootstrap: ensure backend/ is on sys.path so `app.config` resolves ──
import os
import sys

_backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Batch 1: Core communication & data workers ─────────────────────
from execution.whatsapp_gateway import WhatsAppGateway
from execution.whisper_processor import WhisperProcessor
from execution.matrix_analyzer import MatrixAnalyzer
from execution.vector_mls_matcher import VectorMLSMatcher
from execution.calendar_scheduler import CalendarScheduler

__all__ = [
    # Core workers
    "WhatsAppGateway",
    "WhisperProcessor",
    "MatrixAnalyzer",
    "VectorMLSMatcher",
    "CalendarScheduler",
]
