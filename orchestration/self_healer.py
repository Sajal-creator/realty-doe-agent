"""
Self-annealing Error Recovery Engine.
Detects worker errors, analyzes root causes, and attempts automated recovery
with escalating strategies. Falls back to human escalation after repeated failures.
"""

import asyncio
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings

logger = structlog.get_logger(__name__)

MAX_RECOVERY_ATTEMPTS = 3


class ErrorType(str, Enum):
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_INVALID_RESPONSE = "llm_invalid_response"
    WHATSAPP_API_ERROR = "whatsapp_api_error"
    SEARCH_NO_RESULTS = "search_no_results"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    RETRY_SAME = "retry_same"
    RETRY_ADJUSTED = "retry_adjusted"
    SKIP = "skip"
    ESCALATE_HUMAN = "escalate_human"
    USE_FALLBACK = "use_fallback"


@dataclass
class RecoveryAttempt:
    timestamp: str
    error_type: ErrorType
    action: RecoveryAction
    adjusted_params: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    result: Any = None
    error_message: str = ""


@dataclass
class RecoveryResult:
    success: bool
    action: RecoveryAction
    result: Any = None
    attempts: list[RecoveryAttempt] = field(default_factory=list)
    escalated: bool = False


# Per-worker recovery history
_recovery_history: dict[str, list[RecoveryAttempt]] = {}


def _classify_error(error: Exception) -> ErrorType:
    """Map an exception to an ErrorType."""
    err_str = str(error).lower()
    err_type = type(error).__name__.lower()

    if "timeout" in err_str or "timeout" in err_type:
        return ErrorType.LLM_TIMEOUT
    if "rate" in err_str and "limit" in err_str:
        return ErrorType.LLM_RATE_LIMIT
    if "invalid" in err_str and ("json" in err_str or "response" in err_str):
        return ErrorType.LLM_INVALID_RESPONSE
    if "whatsapp" in err_str or "twilio" in err_str:
        return ErrorType.WHATSAPP_API_ERROR
    if "no results" in err_str or "not found" in err_str:
        return ErrorType.SEARCH_NO_RESULTS
    if "database" in err_str or "connection" in err_str or "sql" in err_str:
        return ErrorType.DATABASE_ERROR
    if "validation" in err_str or "value" in err_type:
        return ErrorType.VALIDATION_ERROR

    return ErrorType.UNKNOWN


def _suggest_fix(error_type: ErrorType, context: dict) -> dict[str, Any]:
    """Suggest parameter adjustments based on error type."""
    fixes: dict[ErrorType, dict[str, Any]] = {
        ErrorType.LLM_TIMEOUT: {
            "strategy": "shorten_prompt",
            "max_tokens_multiplier": 0.75,
            "description": "Shortened prompt and reduced max tokens",
        },
        ErrorType.LLM_RATE_LIMIT: {
            "strategy": "backoff_and_retry",
            "wait_seconds": 30,
            "description": "Waiting before retry due to rate limit",
        },
        ErrorType.LLM_INVALID_RESPONSE: {
            "strategy": "simplify_prompt",
            "add_json_instruction": True,
            "temperature": 0.1,
            "description": "Simplified prompt with stricter output format",
        },
        ErrorType.WHATSAPP_API_ERROR: {
            "strategy": "retry_with_backoff",
            "description": "Retrying WhatsApp API call with backoff",
        },
        ErrorType.SEARCH_NO_RESULTS: {
            "strategy": "widen_search",
            "radius_multiplier": 1.5,
            "relax_filters": True,
            "description": "Widened search radius and relaxed filters",
        },
        ErrorType.DATABASE_ERROR: {
            "strategy": "retry_connection",
            "description": "Retrying database operation",
        },
        ErrorType.VALIDATION_ERROR: {
            "strategy": "relax_validation",
            "description": "Relaxed validation constraints",
        },
        ErrorType.UNKNOWN: {
            "strategy": "retry_same",
            "description": "Retrying with same parameters",
        },
    }
    return fixes.get(error_type, fixes[ErrorType.UNKNOWN])


async def catch_worker_error(
    error: Exception,
    worker_name: str,
    context: Optional[dict] = None,
) -> RecoveryAction:
    """
    Catch a worker error and determine the recovery action.

    This is the main entry point when a worker encounters an error.
    It logs, classifies, and returns the recommended recovery action.
    """
    context = context or {}
    error_type = _classify_error(error)

    logger.error(
        "worker_error_caught",
        worker_name=worker_name,
        error_type=error_type.value,
        error=str(error),
        context=context,
    )

    # Track attempt count
    attempts = _recovery_history.get(worker_name, [])
    recent_failures = sum(1 for a in attempts if not a.success and a.timestamp > _five_min_ago())

    if recent_failures >= MAX_RECOVERY_ATTEMPTS:
        logger.warning(
            "max_recovery_attempts_reached",
            worker_name=worker_name,
            failures=recent_failures,
        )
        return RecoveryAction.ESCALATE_HUMAN

    return RecoveryAction.RETRY_ADJUSTED


async def analyze_error(
    error_logs: list[dict],
) -> tuple[ErrorType, str, dict[str, Any]]:
    """
    Analyze a batch of error logs to determine root cause and suggested fix.

    Returns:
        (error_type, root_cause_description, suggested_fix_params)
    """
    if not error_logs:
        return ErrorType.UNKNOWN, "no error logs provided", {}

    # Count error types
    type_counts: dict[str, int] = {}
    for log in error_logs:
        err_type = log.get("error_type", "unknown")
        type_counts[err_type] = type_counts.get(err_type, 0) + 1

    # Most common error type
    dominant_type_str = max(type_counts, key=type_counts.get)  # type: ignore
    try:
        dominant_type = ErrorType(dominant_type_str)
    except ValueError:
        dominant_type = ErrorType.UNKNOWN

    root_cause = f"Dominant error: {dominant_type.value} ({type_counts[dominant_type_str]}/{len(error_logs)} occurrences)"
    fix = _suggest_fix(dominant_type, {})

    logger.info("error_analysis_complete", dominant_type=dominant_type.value, count=type_counts[dominant_type_str])
    return dominant_type, root_cause, fix


async def attempt_recovery(
    worker_name: str,
    error: Exception,
    suggested_fix: Optional[dict[str, Any]] = None,
    retry_fn: Optional[Any] = None,
    **retry_kwargs: Any,
) -> RecoveryResult:
    """
    Attempt to recover from a worker error.

    If retry_fn is provided, it will be called with adjusted parameters.
    Otherwise, returns the recommended action.
    """
    error_type = _classify_error(error)
    fix = suggested_fix or _suggest_fix(error_type, {})

    attempt = RecoveryAttempt(
        timestamp=datetime.now(timezone.utc).isoformat(),
        error_type=error_type,
        action=RecoveryAction.RETRY_ADJUSTED,
        adjusted_params=fix,
    )

    # Record attempt
    if worker_name not in _recovery_history:
        _recovery_history[worker_name] = []
    _recovery_history[worker_name].append(attempt)

    # If no retry function, just return the action
    if retry_fn is None:
        attempt.success = False
        attempt.error_message = "no retry function provided"
        return RecoveryResult(
            success=False,
            action=RecoveryAction.RETRY_ADJUSTED,
            attempts=[attempt],
        )

    # Attempt retry with adjusted parameters using tenacity
    try:
        async for attemper in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(type(error)),
            reraise=True,
        ):
            with attemper:
                result = await retry_fn(**retry_kwargs, **fix)
                attempt.success = True
                attempt.result = result

                logger.info(
                    "recovery_succeeded",
                    worker_name=worker_name,
                    error_type=error_type.value,
                    attempt=attemper.retry_state.attempt_number,
                )

                return RecoveryResult(
                    success=True,
                    action=RecoveryAction.RETRY_ADJUSTED,
                    result=result,
                    attempts=[attempt],
                )
    except RetryError as retry_err:
        attempt.success = False
        attempt.error_message = str(retry_err)

        logger.warning(
            "recovery_failed_after_retries",
            worker_name=worker_name,
            error_type=error_type.value,
        )

        # Check if we should escalate
        total_failures = sum(1 for a in _recovery_history.get(worker_name, []) if not a.success)
        if total_failures >= MAX_RECOVERY_ATTEMPTS:
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ESCALATE_HUMAN,
                attempts=[attempt],
                escalated=True,
            )

        return RecoveryResult(
            success=False,
            action=RecoveryAction.USE_FALLBACK,
            attempts=[attempt],
        )
    except Exception as exc:
        attempt.success = False
        attempt.error_message = str(exc)

        logger.error(
            "recovery_unexpected_error",
            worker_name=worker_name,
            error=str(exc),
        )

        return RecoveryResult(
            success=False,
            action=RecoveryAction.ESCALATE_HUMAN,
            attempts=[attempt],
            escalated=True,
        )

    return RecoveryResult(success=False, action=RecoveryAction.SKIP, attempts=[attempt])


async def escalate_to_human(
    worker_name: str,
    error: Exception,
    context: Optional[dict] = None,
) -> dict:
    """Escalate a persistent error to a human operator."""
    context = context or {}
    attempts = _recovery_history.get(worker_name, [])

    escalation = {
        "worker_name": worker_name,
        "error": str(error),
        "error_type": _classify_error(error).value,
        "total_recovery_attempts": len(attempts),
        "failed_attempts": sum(1 for a in attempts if not a.success),
        "context": context,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.critical("human_escalation", **escalation)

    # Emit escalation event
    try:
        from orchestration.dashboard_syncer import emit_event  # type: ignore

        await emit_event("system.worker_escalation", escalation)
    except (ImportError, Exception) as exc:
        logger.error("escalation_emit_failed", error=str(exc))

    return escalation


def get_recovery_history(worker_name: str) -> list[RecoveryAttempt]:
    """Return recovery attempt history for a worker."""
    return _recovery_history.get(worker_name, [])


def clear_recovery_history(worker_name: str) -> None:
    """Clear recovery history for a worker (e.g., after successful deployment)."""
    _recovery_history.pop(worker_name, None)
    logger.info("recovery_history_cleared", worker_name=worker_name)


def _five_min_ago() -> str:
    """Return an ISO timestamp from 5 minutes ago."""
    from datetime import timedelta

    return (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
