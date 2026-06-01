"""
Realty DOE Agent - Execution Workers
Worker modules that perform actual labor in the DOE pipeline.
"""

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
