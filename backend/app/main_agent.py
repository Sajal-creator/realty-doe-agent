"""
Realty DOE Agent - System Bootstrapper
Initialises FastAPI, Redis, WebSocket, Orchestrator, and background scheduler.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings

# ── Logging ───────────────────────────────────────────────────────
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("realty-doe")

# ── Scheduler ─────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()

# ── Shared state (set during lifespan) ────────────────────────────
redis_pool: aioredis.Redis | None = None
orchestrator = None


# ── Background tasks (placeholder callbacks) ──────────────────────
async def re_engage_job():
    """Run the nurture re-engagement sweep."""
    logger.info("⏰ Running re-engagement cron …")
    if orchestrator:
        try:
            await orchestrator.run_re_engagement()
        except Exception as exc:
            logger.error("Re-engagement error: %s", exc)


async def warmth_decay_job():
    """Decay warmth scores daily."""
    logger.info("🌡️  Running warmth-decay cron …")
    if orchestrator:
        try:
            await orchestrator.decay_warmth_scores()
        except Exception as exc:
            logger.error("Warmth-decay error: %s", exc)


# ── Lifespan (startup / shutdown) ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool, orchestrator

    logger.info("🚀 Starting %s (%s)", settings.APP_NAME, settings.APP_ENV)

    # Redis
    logger.info("Connecting to Redis …")
    redis_pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis_pool.ping()
        logger.info("✅ Redis connected")
    except Exception as exc:
        logger.warning("⚠️  Redis unavailable (%s) – continuing without cache", exc)
        redis_pool = None

    # Orchestrator (lazy import to avoid circular deps)
    try:
        from app.orchestrator import Orchestrator
        orchestrator = Orchestrator(redis=redis_pool, settings=settings)
        await orchestrator.initialise()
        logger.info("✅ Orchestrator initialised")
    except ImportError:
        logger.warning("⚠️  Orchestrator module not found – skipping")
    except Exception as exc:
        logger.error("❌ Orchestrator init failed: %s", exc)

    # Scheduler
    scheduler.add_job(re_engage_job, "cron",
                      **_parse_cron(settings.SCHEDULER_REENGAGE_CRON),
                      id="re_engage", replace_existing=True)
    scheduler.add_job(warmth_decay_job, "cron",
                      **_parse_cron(settings.SCHEDULER_WARMTH_DECAY_CRON),
                      id="warmth_decay", replace_existing=True)
    scheduler.start()
    logger.info("✅ Scheduler started")

    yield  # ── app is running ──

    # Shutdown
    logger.info("🛑 Shutting down …")
    scheduler.shutdown(wait=False)
    if orchestrator:
        await orchestrator.shutdown()
    if redis_pool:
        await redis_pool.close()
    logger.info("👋 Bye")


def _parse_cron(expr: str) -> dict:
    """Parse a 5-field cron expression into APScheduler kwargs."""
    parts = expr.split()
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


# ── FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ─────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    logger.info(
        "%s %s → %d (%.1f ms)",
        request.method, request.url.path, response.status_code, elapsed,
    )
    return response


# ── Health check ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    checks = {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    # Redis
    if redis_pool:
        try:
            await redis_pool.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
            checks["status"] = "degraded"
    else:
        checks["redis"] = "not configured"
    return checks


# ── Register routers (import-safe) ────────────────────────────────
def _include_routers():
    """Import and mount all API routers."""
    router_modules = [
        ("app.routers.webhook",   "/api/v1/webhook",    "webhook"),
        ("app.routers.dashboard", "/api/v1/dashboard",  "dashboard"),
        ("app.routers.auth",      "/api/v1/auth",       "auth"),
        ("app.routers.leads",     "/api/v1/leads",      "leads"),
        ("app.routers.sessions",  "/api/v1/sessions",   "sessions"),
    ]
    for module_path, prefix, tag in router_modules:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            router = getattr(mod, "router")
            app.include_router(router, prefix=prefix, tags=[tag])
            logger.info("  ↳ router registered: %s → %s", tag, prefix)
        except ImportError:
            logger.warning("  ⚠ router not found: %s (skipping)", module_path)
        except Exception as exc:
            logger.error("  ❌ router %s failed: %s", tag, exc)


_include_routers()


# ── WebSocket endpoint (Socket.IO compatible) ─────────────────────
@app.on_event("startup")
async def _setup_websocket():
    """Attach Socket.IO or raw WS handler if available."""
    try:
        import socketio
        sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
        sio_app = socketio.ASGIApp(sio, socketio_path=settings.WS_PATH.lstrip("/"))

        @sio.event
        async def connect(sid, environ):
            logger.info("WS client connected: %s", sid)

        @sio.event
        async def disconnect(sid):
            logger.info("WS client disconnected: %s", sid)

        # Mount as sub-application
        app.mount(settings.WS_PATH, sio_app)
        logger.info("✅ WebSocket server mounted at %s", settings.WS_PATH)
    except ImportError:
        logger.info("ℹ️  python-socketio not installed – WebSocket disabled")
    except Exception as exc:
        logger.error("❌ WebSocket setup failed: %s", exc)


# ── Graceful signal handling ──────────────────────────────────────
def _handle_signal(sig):
    logger.info("Received signal %s – shutting down", sig.name)
    scheduler.shutdown(wait=False)
    sys.exit(0)


for _sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(_sig, _handle_signal)


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main_agent:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        ws_ping_interval=settings.WS_HEARTBEAT_INTERVAL,
    )
