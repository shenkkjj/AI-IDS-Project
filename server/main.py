import asyncio
import os
import sys
from pathlib import Path

from server.core.config import load_dotenv_file

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv_file(_ENV_PATH)

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402
from loguru import logger  # noqa: E402

from server.analyzer import AnalyzerConfig  # noqa: E402
from server.core.config import (  # noqa: E402
    load_timeout_seconds,
    validate_cookie_config,
)
from server.core.logging_setup import configure_logging  # noqa: E402

configure_logging()
from server.core.database import (  # noqa: E402
    get_db,
    init_db,
    ensure_user_config_columns,
    start_log_flusher,
    stop_log_flusher,
)
from server.core.exceptions import DomainException  # noqa: E402
from server.core.state import app_state  # noqa: E402
from server.core.websocket import manager  # noqa: E402
from server.middleware.waf import WAFMiddleware  # noqa: E402
from server.routers import (  # noqa: E402
    admin_router,
    auth_router,
    alerts_router,
    compliance_router,
    copilot_router,
    export_router,
    incidents_router,
    llm_router,
    logs_router,
    metrics_router,
    notify_router,
    site_router,
    threat_intel_router,
    user_router,
    waf_router,
)
from server.services.alert_service import alert_worker  # noqa: E402
from server.services.site_monitor_service import _ssl_monitor_loop  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from typing import Any  # noqa: E402

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
# M2-01 schema bootstrap: ``init_db()`` 仍负责"无 migration 状态时建空表"，对全新
# 库或没被 Alembic stamp 的旧开发库作为快速回退；``ensure_user_config_columns()``
# 是 legacy 兼容层，专门补旧 ``data/app.db`` 上 ``init_db()`` 创建时缺失的列。
# 新 schema 变更必须通过 Alembic revision（``alembic upgrade head``），不要往
# ``ensure_user_config_columns`` 加新 ALTER。详见 docs/ALEMBIC_MIGRATION.md。
init_db()
ensure_user_config_columns()

app = FastAPI(title="AI-IDS Alert Backend", version="0.2.0")


@app.exception_handler(DomainException)
async def _domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """Convert business exceptions raised by services into HTTP responses.

    Service layer code raises `DomainException` subclasses (AuthException,
    NotFoundException, etc.) without importing fastapi. This handler is the
    single point that turns them into HTTP responses with consistent shape.
    """
    headers = {}
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, **({"extra": exc.extra} if exc.extra else {})},
        headers=headers,
    )


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
    # CSP for backend API responses (frontend at :3000 has its own via nginx).
    # API responses are JSON, so a tight default-src 'none' is appropriate —
    # any resource the client loads must come from the explicit connect-src
    # allowlist.
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    return response


# Optional authentication middleware: extracts the JWT from the request and
# attaches the User object to `request.state.user` (or `None` if not
# authenticated). This lets routes use `Depends(get_optional_user)` and
# avoid the duplicate work of resolving the user twice (once in the
# middleware, once in a Depends). The existing `Depends(require_auth_user)`
# pattern continues to work; new routes should prefer this fast path.
_PUBLIC_API_PATH_PREFIXES: tuple[str, ...] = (
    "/auth/login",
    "/auth/register",
    "/auth/login/oauth",
    "/auth/login/otp",
    "/auth/password/reset",
    "/auth/refresh",
    "/alerts/receive",  # alerts ingest — gated by ALERTS_INGEST_TOKEN
    "/llm/test",  # gated by LLM_ADMIN_TOKEN
    "/health",
    "/ready",
    "/waf",
    "/threat-intel",
    "/openapi.json",
    "/docs",
    "/redoc",
)


@app.middleware("http")
async def attach_user_to_request(request: Request, call_next):
    """Resolve the current user (if any) once per request and stash it on
    `request.state.user`. Routes that need the user can then use
    `Depends(get_request_user)` and avoid re-parsing the JWT.
    """
    request.state.user = None
    path = request.url.path
    if not any(path.startswith(p) for p in _PUBLIC_API_PATH_PREFIXES):
        try:
            from server.core.database import SessionLocal
            from server.core.security import (
                _extract_bearer_token,
                decode_access_token,
            )
            access_cookie = request.cookies.get("access_token")
            bearer = _extract_bearer_token(request.headers.get("authorization"))
            token = bearer or access_cookie
            if token:
                payload = decode_access_token(token)
                user_id = int(payload.get("sub", "0"))
                if user_id > 0:
                    from server.core.refresh_tokens import is_session_active
                    from server.models_db import User
                    db = SessionLocal()
                    try:
                        user = (
                            db.query(User)
                            .filter(User.id == user_id, User.is_active.is_(True))
                            .first()
                        )
                        if user is not None and user.token_version == payload.get("tv", 0):
                            sid = payload.get("sid")
                            if sid is None or is_session_active(db, sid):
                                request.state.user = user
                    finally:
                        db.close()
        except Exception:
            # Any error resolving the user is treated as "not authenticated";
            # the route's own dependency will raise 401 if it requires auth.
            request.state.user = None
    return await call_next(request)


def get_request_user(request: Request):
    """FastAPI dependency that returns the user attached by the middleware.

    Raises 401 if the route requires authentication. Use this in new code;
    `require_auth_user` continues to work for backward compatibility.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

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

app.add_middleware(WAFMiddleware)
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
app.include_router(incidents_router.router)
app.include_router(llm_router.router)
app.include_router(waf_router.router)
app.include_router(notify_router.router)
app.include_router(export_router.router)
app.include_router(threat_intel_router.router)
app.include_router(compliance_router.router)
app.include_router(metrics_router.router)

# --- LLM Guardrails MCP endpoint ---
# Mount the FastMCP server (NeMoGuardrails) at /mcp so external agents
# (Claude Code, Cursor, custom internal agents) can call
# `guardrail.scan_text` / `guardrail.get_stats` over the Model Context
# Protocol. Falls back to a no-op stub if the `mcp` SDK is not installed.
#
# AUTH (security review SC-1 / C-4): The /mcp endpoint is gated by an
# API key passed in the `X-Guardrails-Key` header. The expected key
# comes from `GUARDRAILS_MCP_API_KEY` env var; if unset, the endpoint
# refuses all requests with 401 (fail-closed). Set the env var in any
# environment that exposes /mcp.
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse as StarletteJSONResponse


_MCP_API_KEY = os.getenv("GUARDRAILS_MCP_API_KEY", "").strip()
if not _MCP_API_KEY:
    logger.warning(
        "GUARDRAILS_MCP_API_KEY not set — /mcp endpoint will reject all "
        "requests with 401. Set the env var to enable MCP access."
    )


class _MCPAuthMiddleware(BaseHTTPMiddleware):
    """Reject any /mcp request that doesn't carry the configured key.

    Without this, an unauthenticated attacker can enumerate L1 regex via
    the `scan_text` tool (Guardrail Oracle attack) and call `get_stats`
    for traffic analysis. See security review SC-1.
    """

    async def dispatch(self, request: StarletteRequest, call_next):  # type: ignore[override]
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)
        if not _MCP_API_KEY:
            return StarletteJSONResponse(
                {"detail": "MCP endpoint disabled: GUARDRAILS_MCP_API_KEY not configured"},
                status_code=401,
            )
        provided = request.headers.get("x-guardrails-key", "")
        if not provided or provided != _MCP_API_KEY:
            return StarletteJSONResponse(
                {"detail": "Missing or invalid X-Guardrails-Key header"},
                status_code=401,
            )
        return await call_next(request)


app.add_middleware(_MCPAuthMiddleware)

try:
    from server.security.llm_guardrails.mcp_server import mcp as guardrails_mcp

    app.mount("/mcp", guardrails_mcp.streamable_http_app())
    logger.info("MCP guardrails endpoint mounted at /mcp (auth: X-Guardrails-Key)")
except Exception as exc:  # noqa: BLE001
    logger.warning("MCP guardrails endpoint not mounted: {}", exc)


@app.on_event("startup")
async def startup_event() -> None:
    # Eagerly instantiate the LLM guardrail engine so the first
    # request doesn't pay the (multi-second) NeMo / Colang load.
    try:
        from server.security.llm_guardrails.core import GuardrailEngine

        GuardrailEngine.instance()
    except Exception as exc:  # noqa: BLE001
        logger.warning("guardrail engine eager init failed: {}", exc)

    manager.start_heartbeat()
    app_state.rate_limit.start_cleanup()
    start_log_flusher()

    # P2-C: GDPR / PCI retention. Opt-in via env var; default 0 = disabled
    # so dev environments don't accidentally nuke recent rows.
    cleanup_days = int(os.getenv("GUARDRAIL_AUDIT_CLEANUP_DAYS", "0"))
    if cleanup_days > 0:
        try:
            from server.security.llm_guardrails.audit import cleanup_old_audit_logs
            cleanup_old_audit_logs(days=cleanup_days)
        except Exception as exc:  # noqa: BLE001
            logger.warning("audit cleanup skipped: {}", exc)
    for worker_id in range(4):
        app_state.worker_tasks.append(asyncio.create_task(alert_worker(worker_id)))
    app_state.ssl_monitor_task = asyncio.create_task(_ssl_monitor_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for task in app_state.worker_tasks:
        task.cancel()
    if app_state.ssl_monitor_task is not None:
        app_state.ssl_monitor_task.cancel()
    stop_log_flusher()


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Returns 200 as long as the process is responsive.

    Suitable for `livenessProbe` in Kubernetes — failing this means the
    process is stuck and should be restarted.
    """
    return {"status": "ok"}


@app.get("/ready")
async def ready(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe. Returns 200 only when the process can serve traffic.

    Checks:
    - Database connectivity (SELECT 1 against the configured engine)
    - Alert worker pool is alive
    - Log flusher is running

    Suitable for `readinessProbe` in Kubernetes — failing this should take
    the pod out of the load-balancer rotation, not kill it.
    """
    from sqlalchemy import text as sql_text

    checks: dict[str, str] = {}
    try:
        db.execute(sql_text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"fail: {type(exc).__name__}"

    checks["alert_workers"] = (
        "ok" if app_state.worker_tasks and not all(t.done() for t in app_state.worker_tasks)
        else "fail"
    )

    overall = "ok" if all(v == "ok" for v in checks.values()) else "fail"
    payload: dict[str, Any] = {"status": overall, "checks": checks}
    if overall != "ok":
        return JSONResponse(status_code=503, content=payload)
    return payload
