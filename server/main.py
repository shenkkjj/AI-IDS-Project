import asyncio
import os
import sys
from pathlib import Path

from server.core.config import load_dotenv_file

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv_file(_ENV_PATH)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402
from loguru import logger  # noqa: E402

from server.analyzer import AnalyzerConfig  # noqa: E402
from server.core.config import (  # noqa: E402
    load_timeout_seconds,
    validate_cookie_config,
)
from server.core.database import init_db, ensure_user_config_columns  # noqa: E402
from server.core.state import app_state  # noqa: E402
from server.core.websocket import manager  # noqa: E402
from server.routers import (  # noqa: E402
    admin_router,
    auth_router,
    alerts_router,
    compliance_router,
    copilot_router,
    export_router,
    llm_router,
    logs_router,
    notify_router,
    site_router,
    threat_intel_router,
    user_router,
    waf_router,
)
from server.services.alert_service import alert_worker  # noqa: E402
from server.services.site_monitor_service import _ssl_monitor_loop  # noqa: E402

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
try:
    from models.train import FEATURE_COLUMNS
except ModuleNotFoundError:
    FEATURE_COLUMNS = []

_DEFAULT_SECRETS = {
    "dev-local-secret-not-for-production-use-12345678901234567890",
    "dev-insecure-secret-do-not-use-in-production",
    "change-me",
    "secret",
    "",
}

_app_secret = os.getenv("APP_SECRET", "").strip()
if _app_secret in _DEFAULT_SECRETS:
    logger.error("APP_SECRET is not set or uses a default/weak value. Refusing to start.")
    logger.error("Generate a secure secret with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    sys.exit(1)

_auth_secret = os.getenv("AUTH_SECRET", "").strip()
if _auth_secret in _DEFAULT_SECRETS:
    logger.error("AUTH_SECRET is not set or uses a default/weak value. Refusing to start.")
    logger.error("Generate a secure secret with: openssl rand -base64 32")
    sys.exit(1)

validate_cookie_config()
init_db()
ensure_user_config_columns()

app = FastAPI(title="AI-IDS Alert Backend", version="0.2.0")


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Enable XSS filter (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Permissions policy
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

_cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]
)
if os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"} and any(
    "localhost" in o or "127.0.0.1" in o for o in _cors_origins
):
    logger.error("CORS allows localhost in production — set CORS_ORIGINS explicitly")
    sys.exit(1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Alerts-Token", "X-LLM-Admin-Token"],
    max_age=600,
)

# Trusted host middleware (production only)
if os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}:
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "").strip()
    if allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[h.strip() for h in allowed_hosts.split(",") if h.strip()],
        )

_llm_config = AnalyzerConfig(
    api_key=os.getenv("LLM_API_KEY", "").strip(),
    base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/"),
    model=os.getenv("LLM_MODEL", "").strip(),
    timeout_seconds=load_timeout_seconds(),
)

app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(logs_router.router)
app.include_router(site_router.router)
app.include_router(copilot_router.router)
app.include_router(alerts_router.router)
app.include_router(llm_router.router)
app.include_router(waf_router.router)
app.include_router(notify_router.router)
app.include_router(export_router.router)
app.include_router(threat_intel_router.router)
app.include_router(compliance_router.router)


@app.on_event("startup")
async def startup_event() -> None:
    manager.start_heartbeat()
    app_state.rate_limit.start_cleanup()
    for worker_id in range(4):
        app_state.worker_tasks.append(asyncio.create_task(alert_worker(worker_id)))
    app_state.ssl_monitor_task = asyncio.create_task(_ssl_monitor_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for task in app_state.worker_tasks:
        task.cancel()
    if app_state.ssl_monitor_task is not None:
        app_state.ssl_monitor_task.cancel()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
