import asyncio
import os
import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from server.analyzer import AnalyzerConfig
from server.core.config import (
    load_dotenv_file,
    load_timeout_seconds,
    validate_cookie_config,
)
from server.core.database import init_db, ensure_user_config_columns
from server.core.state import app_state
from server.routers import (
    auth_router,
    user_router,
    logs_router,
    site_router,
    copilot_router,
    alerts_router,
    llm_router,
    waf_router,
)
from server.services.alert_service import alert_worker
from server.services.site_monitor_service import _ssl_monitor_loop

try:
    from models.train import FEATURE_COLUMNS
except ModuleNotFoundError:
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from models.train import FEATURE_COLUMNS

load_dotenv_file(Path(__file__).resolve().parents[1] / ".env")
validate_cookie_config()
init_db()
ensure_user_config_columns()

app = FastAPI(title="AI-IDS Alert Backend", version="0.2.0")

_cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://192.168.28.1:3000",
    ]
)
if os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"} and any(
    "localhost" in o or "127.0.0.1" in o for o in _cors_origins
):
    logger.warning("CORS allows localhost in production — set CORS_ORIGINS explicitly")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Alerts-Token", "X-LLM-Admin-Token"],
    max_age=600,
)

_llm_config = AnalyzerConfig(
    api_key=os.getenv("LLM_API_KEY", "").strip(),
    base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/"),
    model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
    timeout_seconds=load_timeout_seconds(),
)

app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(logs_router.router)
app.include_router(site_router.router)
app.include_router(copilot_router.router)
app.include_router(alerts_router.router)
app.include_router(llm_router.router)
app.include_router(waf_router.router)


@app.on_event("startup")
async def startup_event() -> None:
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
