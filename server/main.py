import asyncio
import csv
import hashlib
import hmac
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urlparse
from uuid import uuid4

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from models.train import FEATURE_COLUMNS
except ModuleNotFoundError:
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from models.train import FEATURE_COLUMNS
from server.analyzer import AnalyzerConfig, LLMAnalyzer, build_chat_completions_url
from server.db import SessionLocal, engine
from server.mailer import send_otp_email, send_reset_email
from server.models_db import AuthChallenge, Base, Log, User, UserConfig
from server.security_utils import (
    DecryptionError,
    decode_access_token,
    decrypt_api_key,
    encrypt_api_key,
    hash_password,
    issue_access_token,
    random_otp,
    verify_password,
)


ALERT_QUEUE_MAX_SIZE = 256
ALERT_WORKER_COUNT = 4
ALERT_BACKLOG_SIZE = 200
OTP_EXPIRES_MINUTES = 10
PASSWORD_RESET_EXPIRES_MINUTES = 10
SSL_CHECK_INTERVAL_SECONDS = 60
SITE_MONITOR_HTTP_TIMEOUT_SECONDS = 8.0
LOGIN_RATE_LIMIT_WINDOW = 300
LOGIN_RATE_LIMIT_MAX = 10
OTP_RATE_LIMIT_WINDOW = 600
OTP_RATE_LIMIT_MAX = 5
REGISTER_RATE_LIMIT_WINDOW = 3600
REGISTER_RATE_LIMIT_MAX = 5
LLM_RATE_LIMIT_WINDOW = 60
LLM_RATE_LIMIT_MAX = 10
COPILOT_RATE_LIMIT_WINDOW = 60
COPILOT_RATE_LIMIT_MAX = 20
OTP_VERIFY_MAX_ATTEMPTS = 5

INTERNAL_ALERT_TOKEN_HEADER = "x-alerts-token"
INTERNAL_ALERT_TOKEN_ENV = "ALERTS_INGEST_TOKEN"
LLM_ADMIN_TOKEN_HEADER = "x-llm-admin-token"
LLM_ADMIN_TOKEN_ENV = "LLM_ADMIN_TOKEN"

WAF_BLOCK_PATTERNS = [
    re.compile(r"(?i)(?:\bor\b\s+1=1|\bunion\b\s+\bselect\b|sleep\s*\(|benchmark\s*\(|information_schema)"),
    re.compile(r"(?i)(?:<script\b|onerror\s*=|onload\s*=|javascript:)"),
    re.compile(r"(?i)(?:\.\./|%2e%2e%2f|/etc/passwd|\\x00)"),
]
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
PROXY_STRIP_HEADERS = {
    "authorization",
    "cookie",
}
UPSTREAM_STRIP_RESPONSE_HEADERS = {
    "server",
    "x-powered-by",
    "x-aspnet-version",
    "set-cookie",
}


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _get_client_ip(request: Request) -> str:
    trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT", "0").strip())
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and trusted_proxy_count > 0:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        # SECURITY: Validate each IP in the chain to prevent IP spoofing
        valid_parts = []
        for p in parts:
            try:
                ipaddress.ip_address(p)
                valid_parts.append(p)
            except ValueError:
                continue
        if len(valid_parts) >= trusted_proxy_count:
            idx = len(valid_parts) - trusted_proxy_count
            ip = valid_parts[idx]
            if ip:
                return ip
    elif forwarded and trusted_proxy_count == 0:
        # SECURITY: When TRUSTED_PROXY_COUNT=0, X-Forwarded-For is untrusted and ignored
        pass
    client = request.client
    return str(client.host) if client else "unknown"


def _get_direct_client_ip(request: Request) -> str:
    client = request.client
    return str(client.host) if client else ""


def _is_private_or_loopback_ip(ip_text: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved


def _is_url_pointing_to_internal(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _type, _proto, _canonname, sockaddr in addr_info:
                ip_text = sockaddr[0]
                if _is_private_or_loopback_ip(ip_text):
                    return True
        except socket.gaierror:
            return True
        return False
    except Exception:
        return True


def _is_allowed_alert_ingest_source(request: Request) -> bool:
    source_ip = _get_direct_client_ip(request)
    if not source_ip:
        return False

    cidr_text = os.getenv("ALERTS_INGEST_ALLOWED_CIDRS", "").strip()
    if not cidr_text:
        return _is_private_or_loopback_ip(source_ip)

    try:
        source = ipaddress.ip_address(source_ip)
    except ValueError:
        return False

    for raw_item in cidr_text.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError:
            continue
        if source in network:
            return True
    return False


def _payload_has_attack_signature(text: str) -> bool:
    if not text:
        return False
    for pattern in WAF_BLOCK_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _build_proxy_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP_HEADERS or lower in PROXY_STRIP_HEADERS:
            continue
        out[key] = value
    return out


def _sanitize_for_log(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
        .replace("\n", " ")
        .replace("\r", "")
    )


def _build_attack_alert(source_ip: str, destination_host: str, payload: str, user_id: int) -> "AlertIn":
    return AlertIn(
        event="waf_block",
        source_ip=_sanitize_for_log(source_ip),
        destination_ip=_sanitize_for_log(destination_host),
        payload=payload[:4000],
        alert_user_id=user_id,
        timestamp=time.time(),
        blocked=True,
        block_expires_at=None,
    )


def load_timeout_seconds() -> int:
    raw = os.getenv("LLM_TIMEOUT_SECONDS", "20").strip()
    try:
        timeout = int(raw)
    except ValueError:
        return 20
    if timeout < 1:
        return 1
    if timeout > 300:
        return 300
    return timeout


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def cookie_secure() -> bool:
    env = os.getenv("APP_ENV", "development").strip().lower()
    if env in {"dev", "development"}:
        return False
    return True


def cookie_samesite() -> str:
    value = os.getenv("APP_COOKIE_SAMESITE", "lax").strip().lower()
    if value in {"lax", "strict", "none"}:
        return value
    return "lax"


def validate_cookie_config() -> None:
    secure = cookie_secure()
    same_site = cookie_samesite()
    env = os.getenv("APP_ENV", "development").strip().lower()
    is_production = env in {"prod", "production"}

    if same_site == "none" and not secure:
        raise RuntimeError("APP_COOKIE_SAMESITE=none requires APP_COOKIE_SECURE=true")

    if is_production and not secure:
        raise RuntimeError("APP_COOKIE_SECURE must be true when APP_ENV=production")


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite=cookie_samesite(),
        secure=cookie_secure(),
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        "access_token",
        httponly=True,
        samesite=cookie_samesite(),
        secure=cookie_secure(),
    )


class AlertIn(BaseModel):
    event: str = Field(default="anomaly", pattern="^(anomaly|waf_block|site_down|ssl_warning|ssl_critical)$")
    source_ip: str
    destination_ip: str
    payload: str = Field(default="")
    alert_user_id: int | None = None
    timestamp: float | None = None
    feature_values: dict[str, Any] | None = None
    model_probability: float | None = None
    blocked: bool = False
    block_expires_at: float | None = None


class LLMConfigIn(BaseModel):
    ai_provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)


class ThreatConfirmIn(BaseModel):
    alert_id: str
    label: str = Field(default="user_confirmed_threat")


class UserRegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None

    @staticmethod
    def validate_password_strength(password: str) -> str:
        if len(password) < 8:
            raise ValueError("密码长度至少8位")
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        if not (has_upper and has_lower and has_digit):
            raise ValueError("密码必须包含大写字母、小写字母和数字")
        return password

    def model_post_init(self, __context: object) -> None:
        UserRegisterIn.validate_password_strength(self.password)


class LoginPasswordIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class OTPRequestIn(BaseModel):
    email: EmailStr


class OTPVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)

    def model_post_init(self, __context: object) -> None:
        UserRegisterIn.validate_password_strength(self.new_password)


class OAuthLoginIn(BaseModel):
    provider: str = Field(pattern="^(github|google)$")
    id_token: str = Field(min_length=1, max_length=8192)
    provider_user_id: str = Field(max_length=255)
    email: EmailStr
    display_name: str | None = None


class UserConfigIn(BaseModel):
    ai_provider: str | None = Field(default=None, pattern="^(openai|claude|gemini|grok|custom)$")
    model: str | None = None
    base_url: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    alert_email_enabled: bool | None = None
    alert_voice_enabled: bool | None = None
    ui_theme: str | None = Field(default=None, pattern="^(dark|light|auto)$")
    ui_density: str | None = Field(default=None, pattern="^(comfortable|compact|spacious)$")
    api_key: str | None = None


class SiteTargetIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class CopilotMessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class CopilotStreamIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    alert_id: str | None = None
    history: list[CopilotMessageIn] = Field(default_factory=list)


ALLOWED_AI_PROVIDERS = {"openai", "claude", "gemini", "grok", "custom"}
PROVIDER_MODEL_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-3-mini",
    "custom": "gpt-4o-mini",
}
PROVIDER_BASE_URL_DEFAULTS = {
    "openai": "https://api.openai.com",
    "claude": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "grok": "https://api.x.ai",
    "custom": "",
}


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            user_connections = self.active_connections.setdefault(user_id, set())
            user_connections.add(websocket)
            total = sum(len(items) for items in self.active_connections.values())
        logger.info("WebSocket connected. user_id={} total={}", user_id, total)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            user_connections = self.active_connections.get(user_id)
            if user_connections is not None:
                user_connections.discard(websocket)
                if not user_connections:
                    self.active_connections.pop(user_id, None)
            total = sum(len(items) for items in self.active_connections.values())
        logger.info("WebSocket disconnected. user_id={} total={}", user_id, total)

    async def snapshot_connections(self, user_id: int) -> list[WebSocket]:
        async with self._lock:
            return list(self.active_connections.get(user_id, set()))

    async def broadcast_json(self, user_id: int, message: dict[str, Any]) -> None:
        targets = await self.snapshot_connections(user_id)
        if not targets:
            return

        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                user_connections = self.active_connections.get(user_id)
                if user_connections is not None:
                    for websocket in stale:
                        user_connections.discard(websocket)
                    if not user_connections:
                        self.active_connections.pop(user_id, None)


load_dotenv_file(Path(__file__).resolve().parents[1] / ".env")
validate_cookie_config()
Base.metadata.create_all(bind=engine)

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

manager = ConnectionManager()
_llm_config_lock = asyncio.Lock()
_llm_config = AnalyzerConfig(
    api_key=os.getenv("LLM_API_KEY", "").strip(),
    base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/"),
    model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
    timeout_seconds=load_timeout_seconds(),
)
_alert_queue: asyncio.Queue[AlertIn] = asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE)
_alert_backlog: deque[dict[str, Any]] = deque(maxlen=ALERT_BACKLOG_SIZE)
_alert_backlog_lock = asyncio.Lock()
_login_attempts: dict[str, list[float]] = {}
_login_lock = asyncio.Lock()
_otp_attempts: dict[str, list[float]] = {}
_otp_lock = asyncio.Lock()
_register_attempts: dict[str, list[float]] = {}
_register_lock = asyncio.Lock()
_llm_attempts: dict[str, list[float]] = {}
_llm_lock = asyncio.Lock()
_copilot_attempts: dict[str, list[float]] = {}
_copilot_lock = asyncio.Lock()
_otp_verify_failures: dict[str, int] = {}
_otp_verify_lock = asyncio.Lock()
_new_threats_lock = asyncio.Lock()
_worker_tasks: list[asyncio.Task[None]] = []
_ssl_monitor_task: asyncio.Task[None] | None = None
_new_threats_csv_path = Path(__file__).resolve().parents[1] / "data" / "new_threats.csv"
site_targets: dict[int, str] = {}
site_health_status: dict[int, dict[str, Any]] = {}


def ensure_user_config_columns() -> None:
    statements = [
        "ALTER TABLE user_configs ADD COLUMN ai_provider VARCHAR(24) NOT NULL DEFAULT 'openai'",
        "ALTER TABLE users ADD COLUMN password_changed_at DATETIME NULL",
    ]
    with engine.begin() as conn:
        for sql in statements:
            try:
                conn.execute(text(sql))
            except Exception as exc:
                err_msg = str(exc).lower()
                if "already exists" not in err_msg and "duplicate" not in err_msg:
                    logger.warning("ALTER failed: {} err={}", sql.strip(), exc)


ensure_user_config_columns()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_log(db: Session, *, user_id: int | None, level: str, action: str, detail: str, ip_address: str | None = None) -> None:
    db.add(Log(user_id=user_id, level=level, action=action, detail=detail, ip_address=ip_address))
    db.commit()


def record_site_monitor_log(*, user_id: int, level: str, action: str, detail: str) -> None:
    db = SessionLocal()
    try:
        create_log(db, user_id=user_id, level=level, action=action, detail=detail)
    except Exception as exc:
        logger.warning("site monitor log write failed user_id={} action={} err={}", user_id, action, exc)
    finally:
        db.close()


def build_default_config(user_id: int) -> UserConfig:
    return UserConfig(
        user_id=user_id,
        ai_provider="openai",
        model="gpt-4o-mini",
        base_url=_llm_config.base_url,
        timeout_seconds=_llm_config.timeout_seconds,
        alert_email_enabled=True,
        alert_voice_enabled=False,
        ui_theme="dark",
        ui_density="comfortable",
    )


def get_or_create_user_config(db: Session, user_id: int) -> UserConfig:
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    if config:
        return config
    config = build_default_config(user_id)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config




def normalize_ai_provider(value: str | None) -> str:
    provider = str(value or "").strip().lower()
    if provider not in ALLOWED_AI_PROVIDERS:
        return "custom"
    return provider


def infer_provider_from_base_url(base_url: str) -> str:
    normalized = str(base_url or "").strip().lower()
    if "anthropic.com" in normalized:
        return "claude"
    if "generativelanguage.googleapis.com" in normalized:
        return "gemini"
    if "x.ai" in normalized:
        return "grok"
    if "openai.com" in normalized:
        return "openai"
    return "custom"


def infer_provider_from_model(model_name: str) -> str:
    model = str(model_name or "").strip().lower()
    if model.startswith("claude"):
        return "claude"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("grok"):
        return "grok"
    if model.startswith("gpt") or model.startswith("o"):
        return "openai"
    return "custom"


def choose_provider(preferred: str | None, model_name: str, base_url: str) -> str:
    normalized = normalize_ai_provider(preferred)
    if normalized != "custom":
        return normalized

    by_url = infer_provider_from_base_url(base_url)
    if by_url != "custom":
        return by_url

    by_model = infer_provider_from_model(model_name)
    if by_model != "custom":
        return by_model

    return "openai"


def user_config_to_llm_runtime(config: UserConfig, user: User) -> tuple[AnalyzerConfig, str]:
    try:
        api_key = decrypt_api_key(user.encrypted_api_key) or ""
    except DecryptionError:
        api_key = ""
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    model = (config.model or "").strip() or PROVIDER_MODEL_DEFAULTS[provider]
    base_url = (config.base_url or "").strip().rstrip("/") or PROVIDER_BASE_URL_DEFAULTS[provider]

    runtime = AnalyzerConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=config.timeout_seconds,
    )
    return runtime, provider


COPILOT_SYSTEM_PROMPT = (
    "你是企业级 Security Copilot。回答要专业、可执行、简洁，先给结论，再给证据与处置步骤。"
)


def _provider_headers(provider: str, api_key: str) -> dict[str, str]:
    if provider == "claude":
        return {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    if provider == "gemini":
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


def _test_request_body(provider: str, model: str) -> dict[str, Any]:
    if provider == "claude":
        return {
            "model": model,
            "system": "You are a network security assistant.",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "reply with pong"}]}],
            "max_tokens": 8,
            "temperature": 0,
        }
    if provider == "gemini":
        return {
            "contents": [{"role": "user", "parts": [{"text": "reply with pong"}]}],
            "generationConfig": {"temperature": 0},
        }
    return {
        "model": model,
        "messages": [{"role": "user", "content": "reply with pong"}],
        "temperature": 0,
        "max_tokens": 8,
    }


def _provider_test_endpoint(provider: str, runtime: AnalyzerConfig) -> str:
    normalized_base = runtime.base_url.rstrip("/")
    if provider == "claude":
        return f"{normalized_base}/v1/messages"
    if provider == "gemini":
        return f"{normalized_base}/v1beta/models/{runtime.model}:generateContent"
    return build_chat_completions_url(runtime.base_url)


def _resolve_test_api_key(update: dict[str, Any], runtime: AnalyzerConfig) -> str:
    candidate = str(update.get("api_key", "")).strip()
    if candidate:
        return candidate

    if "api_key" in update:
        raise HTTPException(status_code=400, detail="api_key cannot be empty")

    return str(runtime.api_key).strip()


def _extract_test_reply(provider: str, payload: dict[str, Any]) -> str:
    if provider == "claude":
        content_items = payload.get("content") or []
        if not content_items:
            return ""
        return str((content_items[0] or {}).get("text", "") or "").strip()
    if provider == "gemini":
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        if not parts:
            return ""
        return str((parts[0] or {}).get("text", "") or "").strip()
    return str((payload.get("choices", [{}])[0] or {}).get("message", {}).get("content", "") or "").strip()


async def test_llm_connection_by_provider(config: AnalyzerConfig, provider: str) -> dict[str, Any]:
    if not config.api_key or not config.base_url:
        raise ValueError("缺少 API Key 或 Base URL")

    if config.timeout_seconds < 1 or config.timeout_seconds > 300:
        raise ValueError("timeout_seconds 必须在 1-300 之间")

    endpoint = _provider_test_endpoint(provider, config)
    request_body = _test_request_body(provider, config.model)
    headers = _provider_headers(provider, config.api_key)

    started_at = time.time()
    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.post(endpoint, headers=headers, json=request_body)
    response.raise_for_status()

    response_json = response.json()
    content = _extract_test_reply(provider, response_json)
    latency_ms = int((time.time() - started_at) * 1000)

    return {
        "ok": True,
        "latency_ms": latency_ms,
        "reply": content,
        "model": config.model,
        "base_url": config.base_url,
    }


def _build_openai_messages(user_message: str, context_block: str, history: list[CopilotMessageIn]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": COPILOT_SYSTEM_PROMPT}]
    for item in history:
        messages.append({"role": item.role, "content": item.content})

    user_content = user_message
    if context_block:
        user_content = f"{user_message}\n\n{context_block}"
    messages.append({"role": "user", "content": user_content})
    return messages


def _build_gemini_contents(user_message: str, context_block: str, history: list[CopilotMessageIn]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for item in history:
        role = "model" if item.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item.content}]})

    user_content = user_message
    if context_block:
        user_content = f"{user_message}\n\n{context_block}"
    contents.append({"role": "user", "parts": [{"text": user_content}]})
    return contents


def _extract_openai_delta(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not choices:
        return ""
    return str((choices[0] or {}).get("delta", {}).get("content", "") or "")


def _extract_claude_delta(payload: dict[str, Any]) -> str:
    if payload.get("type") != "content_block_delta":
        return ""
    return str(payload.get("delta", {}).get("text", "") or "")


def _extract_gemini_delta(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return ""
    return str((parts[0] or {}).get("text", "") or "")


async def stream_user_chat_completion(
    *,
    runtime: AnalyzerConfig,
    provider: str,
    user_message: str,
    context_block: str,
    history: list[CopilotMessageIn],
) -> AsyncIterator[str]:
    if not runtime.api_key or not runtime.base_url:
        yield _sse_error("请先在配置页设置可用的 API Key 与 Base URL")
        return

    timeout = httpx.Timeout(connect=8.0, read=120.0, write=30.0, pool=20.0)

    try:
        if provider == "claude":
            endpoint = f"{runtime.base_url.rstrip('/')}/v1/messages"
            request_body = {
                "model": runtime.model,
                "system": COPILOT_SYSTEM_PROMPT,
                "messages": _build_openai_messages(user_message, context_block, history)[1:],
                "max_tokens": 2048,
                "temperature": 0.2,
                "stream": True,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", endpoint, headers=_provider_headers(provider, runtime.api_key), json=request_body) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = str(raw_line or "").strip()
                        if not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            payload = json.loads(payload_text)
                        except Exception:
                            continue
                        token = _extract_claude_delta(payload)
                        if token:
                            yield _sse_pack(token)

        elif provider == "gemini":
            # SECURITY: Gemini API key is passed via x-goog-api-key header, not URL query params
            endpoint = (
                f"{runtime.base_url.rstrip('/')}/v1beta/models/{runtime.model}:streamGenerateContent"
                f"?alt=sse"
            )
            request_body = {
                "system_instruction": {"parts": [{"text": COPILOT_SYSTEM_PROMPT}]},
                "contents": _build_gemini_contents(user_message, context_block, history),
                "generationConfig": {"temperature": 0.2},
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", endpoint, headers=_provider_headers(provider, runtime.api_key), json=request_body) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = str(raw_line or "").strip()
                        if not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            payload = json.loads(payload_text)
                        except Exception:
                            continue
                        token = _extract_gemini_delta(payload)
                        if token:
                            yield _sse_pack(token)

        else:
            endpoint = build_chat_completions_url(runtime.base_url)
            request_body = {
                "model": runtime.model,
                "messages": _build_openai_messages(user_message, context_block, history),
                "temperature": 0.2,
                "stream": True,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", endpoint, headers=_provider_headers(provider, runtime.api_key), json=request_body) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = str(raw_line or "").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            payload = json.loads(payload_text)
                        except Exception:
                            continue
                        token = _extract_openai_delta(payload)
                        if token:
                            yield _sse_pack(token)

        yield _sse_done(provider, runtime.model)
    except Exception as exc:
        logger.exception("copilot stream failed provider={} model={} err_type={}", provider, runtime.model, type(exc).__name__)
        # SECURITY: Never leak internal exception details to the client
        yield _sse_error("AI 服务暂时不可用，请稍后重试")


def _build_context_from_alert(alert: dict[str, Any] | None) -> str:
    if not alert:
        return ""

    raw_alert = alert.get("raw_alert") or {}
    llm_analysis = alert.get("llm_analysis") or {}
    lines = [
        "[当前选中告警上下文]",
        f"alert_id: {alert.get('alert_id', '')}",
        f"source_ip: {raw_alert.get('source_ip', '')}",
        f"destination_ip: {raw_alert.get('destination_ip', '')}",
        f"timestamp: {raw_alert.get('timestamp', '')}",
        f"model_probability: {raw_alert.get('model_probability', '')}",
        f"blocked: {raw_alert.get('blocked', False)}",
        f"payload: {raw_alert.get('payload', '')}",
        f"existing_risk_level: {llm_analysis.get('risk_level', '')}",
        f"existing_summary: {llm_analysis.get('summary', '')}",
        "请基于这条告警给出专业安全分析和可执行防御建议，优先给出立即动作。",
    ]
    return "\n".join(lines)


def _sse_pack(text: str) -> str:
    return f"data: {json.dumps({'token': text}, ensure_ascii=False)}\n\n"


def _sse_error(text: str) -> str:
    return f"event: error\ndata: {json.dumps({'message': text}, ensure_ascii=False)}\n\n"


def _sse_done(provider: str, model_name: str) -> str:
    payload = {"provider": provider, "model": model_name}
    return f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    text = authorization.strip()
    if not text.lower().startswith("bearer "):
        return None
    return text[7:].strip() or None


def resolve_token(access_token_cookie: str | None, authorization: str | None) -> str:
    bearer = _extract_bearer_token(authorization)
    token = access_token_cookie or bearer
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def _issue_token_for_user(user: User) -> str:
    pwd_ts = user.password_changed_at.replace(tzinfo=timezone.utc).timestamp() if user.password_changed_at else None
    return issue_access_token(str(user.id), password_changed_at=pwd_ts)


def _safe_decrypt(encrypted: str | None) -> str | None:
    try:
        return decrypt_api_key(encrypted)
    except DecryptionError:
        return None


def get_current_user(
    db: Session,
    access_token_cookie: str | None,
    authorization: str | None,
) -> User:
    token = resolve_token(access_token_cookie, authorization)
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", "0"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token_pwd_iat = payload.get("pwd_iat")
    if user.password_changed_at is not None:
        if token_pwd_iat is None:
            raise HTTPException(status_code=401, detail="密码已更改，请重新登录")
        changed_ts = user.password_changed_at.replace(tzinfo=timezone.utc).timestamp()
        if changed_ts > token_pwd_iat:
            raise HTTPException(status_code=401, detail="密码已更改，请重新登录")

    return user


def require_auth_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> User:
    return get_current_user(db, access_token_cookie, authorization)


def require_llm_admin_token(token: str | None = Header(default=None, alias=LLM_ADMIN_TOKEN_HEADER)) -> None:
    expected = os.getenv(LLM_ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"{LLM_ADMIN_TOKEN_ENV} not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def require_alert_ingest_token(token: str | None = Header(default=None, alias=INTERNAL_ALERT_TOKEN_HEADER)) -> None:
    expected = os.getenv(INTERNAL_ALERT_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"{INTERNAL_ALERT_TOKEN_ENV} not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid alerts token")


def config_to_payload(config: AnalyzerConfig, ai_provider: str = "custom") -> dict[str, Any]:
    provider = choose_provider(ai_provider, config.model, config.base_url)
    return {
        "ai_provider": provider,
        "base_url": config.base_url,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "has_api_key": bool(config.api_key),
    }


async def get_runtime_llm_config() -> AnalyzerConfig:
    async with _llm_config_lock:
        return _llm_config


async def update_runtime_llm_config(data: LLMConfigIn) -> AnalyzerConfig:
    global _llm_config

    update = data.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="No config fields provided")

    async with _llm_config_lock:
        current = _llm_config

        api_key = current.api_key
        if "api_key" in update:
            api_key = str(update["api_key"]).strip()

        base_url = current.base_url
        if "base_url" in update:
            base_url = str(update["base_url"]).strip().rstrip("/")

        model = current.model
        if "model" in update:
            model = str(update["model"]).strip() or current.model

        timeout_seconds = current.timeout_seconds
        if "timeout_seconds" in update:
            timeout_seconds = int(update["timeout_seconds"])

        provider = choose_provider(str(update.get("ai_provider", "custom")), model, base_url)
        if not base_url:
            base_url = PROVIDER_BASE_URL_DEFAULTS[provider]
        if not model:
            model = PROVIDER_MODEL_DEFAULTS[provider]

        if timeout_seconds < 1 or timeout_seconds > 300:
            raise HTTPException(status_code=422, detail="timeout_seconds must be in 1..300")

        new_config = AnalyzerConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )

        _llm_config = new_config
        return new_config


async def append_backlog(payload: dict[str, Any]) -> None:
    async with _alert_backlog_lock:
        _alert_backlog.append(payload)


async def get_backlog_snapshot() -> list[dict[str, Any]]:
    async with _alert_backlog_lock:
        return list(_alert_backlog)


def enqueue_alert(alert: AlertIn) -> tuple[bool, bool]:
    try:
        _alert_queue.put_nowait(alert)
        return True, False
    except asyncio.QueueFull:
        try:
            _alert_queue.get_nowait()
            _alert_queue.task_done()
        except asyncio.QueueEmpty:
            return False, False

        try:
            _alert_queue.put_nowait(alert)
            return True, True
        except asyncio.QueueFull:
            return False, True


def _feature_value(raw: dict[str, Any], key: str) -> Any:
    feature_values = raw.get("feature_values") or {}
    if key in feature_values:
        return feature_values.get(key)
    return ""


async def append_new_threat_csv(payload: dict[str, Any], label: str) -> None:
    raw = payload.get("raw_alert") or {}
    _new_threats_csv_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "alert_id",
        "label",
        "confirmed_at",
        "source_ip",
        "destination_ip",
        "payload",
        "model_probability",
        "blocked",
        "block_expires_at",
        *FEATURE_COLUMNS,
    ]

    row = {
        "alert_id": payload.get("alert_id", ""),
        "label": label,
        "confirmed_at": time.time(),
        "source_ip": raw.get("source_ip", ""),
        "destination_ip": raw.get("destination_ip", ""),
        "payload": raw.get("payload", ""),
        "model_probability": raw.get("model_probability"),
        "blocked": raw.get("blocked", False),
        "block_expires_at": raw.get("block_expires_at"),
    }

    for feature_name in FEATURE_COLUMNS:
        row[feature_name] = _feature_value(raw, feature_name)

    async with _new_threats_lock:
        exists = _new_threats_csv_path.exists()
        with _new_threats_csv_path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=header)
            if not exists:
                writer.writeheader()
            writer.writerow(row)


def find_alert_by_id(alert_id: str, *, user_id: int | None = None) -> dict[str, Any] | None:
    for item in _alert_backlog:
        if str(item.get("alert_id", "")) != alert_id:
            continue
        if user_id is None:
            return item
        raw_alert = item.get("raw_alert") or {}
        if raw_alert.get("alert_user_id") == user_id:
            return item
    return None


def _check_rate_limit(attempts: dict[str, list[float]], key: str, window: int, max_attempts: int) -> bool:
    now = time.time()
    if key in attempts:
        attempts[key] = [t for t in attempts[key] if now - t < window]
    if key not in attempts or len(attempts[key]) < max_attempts:
        if key not in attempts:
            attempts[key] = []
        attempts[key].append(now)
        return True
    return False


def _check_login_rate_limit(email: str) -> bool:
    return _check_rate_limit(_login_attempts, email.lower(), LOGIN_RATE_LIMIT_WINDOW, LOGIN_RATE_LIMIT_MAX)


def _check_otp_rate_limit(email: str) -> bool:
    return _check_rate_limit(_otp_attempts, email.lower(), OTP_RATE_LIMIT_WINDOW, OTP_RATE_LIMIT_MAX)


def _mask_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


def _challenge_hash_material(email: str, challenge_type: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{challenge_type}:{code}".encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _issue_challenge(db: Session, email: str, challenge_type: str, user_id: int | None) -> str:
    code = random_otp(6)
    code_hash = _challenge_hash_material(email, challenge_type, code)
    expires_at = _now() + timedelta(minutes=OTP_EXPIRES_MINUTES if challenge_type == "otp" else PASSWORD_RESET_EXPIRES_MINUTES)
    challenge = AuthChallenge(
        user_id=user_id,
        email=email.lower(),
        challenge_type=challenge_type,
        code_hash=code_hash,
        expires_at=expires_at,
        consumed_at=None,
        metadata_json=None,
    )
    db.add(challenge)
    db.commit()
    return code


def _consume_valid_challenge(db: Session, email: str, challenge_type: str, code: str) -> AuthChallenge:
    challenge = (
        db.query(AuthChallenge)
        .filter(
            AuthChallenge.email == email.lower(),
            AuthChallenge.challenge_type == challenge_type,
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=400, detail="验证码不存在，请先获取验证码")
    if challenge.expires_at < _now():
        raise HTTPException(status_code=400, detail="验证码已过期")

    expected = _challenge_hash_material(email, challenge_type, code)
    if not hmac.compare_digest(expected, challenge.code_hash):
        raise HTTPException(status_code=400, detail="验证码错误")

    challenge.consumed_at = _now()
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def _auth_payload(user: User, config: UserConfig, access_token: str | None = None) -> dict[str, Any]:
    try:
        api_key_plain = decrypt_api_key(user.encrypted_api_key)
    except DecryptionError:
        api_key_plain = None
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    payload = {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(api_key_plain),
            "api_key_masked": _mask_key(api_key_plain),
        },
    }
    if access_token:
        payload["access_token"] = access_token
    return payload



async def process_alert(alert: AlertIn) -> dict[str, Any]:
    analysis: dict[str, Any] | None = None
    analysis_error: str | None = None

    try:
        config = await get_runtime_llm_config()
        if not config.api_key or not config.base_url:
            raise ValueError("Missing LLM_API_KEY or LLM_BASE_URL environment variables.")

        analyzer = LLMAnalyzer(config=config)
        analysis = await run_in_threadpool(
            analyzer.analyze_alert,
            alert.source_ip,
            alert.destination_ip,
            alert.payload,
        )
    except Exception as exc:
        analysis_error = str(exc)
        logger.exception("LLM analysis failed: {}", exc)

    return {
        "alert_id": uuid4().hex,
        "raw_alert": alert.model_dump(),
        "llm_analysis": analysis,
        "analysis_error": analysis_error,
        "processed_at": time.time(),
    }


def _build_site_monitor_alert(user_id: int, target_url: str, reason: str, detail: str = "") -> "AlertIn":
    return AlertIn(
        event="site_down",
        source_ip="system:site-monitor",
        destination_ip=target_url,
        payload=(f"reason={reason};detail={detail}" if detail else f"reason={reason}")[:4000],
        alert_user_id=user_id,
        timestamp=time.time(),
        blocked=False,
        block_expires_at=None,
    )


def _enqueue_site_monitor_alert(user_id: int, target_url: str, reason: str, detail: str = "") -> None:
    alert = _build_site_monitor_alert(user_id, target_url, reason, detail)
    accepted, replaced_oldest = enqueue_alert(alert)
    if not accepted:
        logger.warning("site monitor alert queue full, drop user_id={} reason={}", user_id, reason)
        return
    if replaced_oldest:
        logger.warning("site monitor alert queue full, evict oldest user_id={} reason={}", user_id, reason)


def _check_target_uptime(url: str) -> dict[str, Any]:
    try:
        response = httpx.get(
            url,
            timeout=SITE_MONITOR_HTTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        status_code = int(response.status_code)
        if status_code >= 500:
            return {
                "uptime_status": "down",
                "uptime_http_status": status_code,
                "uptime_detail": f"upstream returned {status_code}",
            }
        return {
            "uptime_status": "up",
            "uptime_http_status": status_code,
            "uptime_detail": "ok",
        }
    except Exception as exc:
        return {
            "uptime_status": "down",
            "uptime_http_status": None,
            "uptime_detail": str(exc),
        }


def _check_target_ssl(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return {"status": "invalid", "detail": "invalid host"}
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if parsed.scheme != "https":
        return {"status": "no_ssl", "detail": "target is not https"}

    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=5) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            not_after = cert.get("notAfter")
            if not not_after:
                return {"status": "unknown", "detail": "certificate has no expiry"}
            expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            days_left = (expires_at - _now()).days
            tone = "ok"
            if days_left <= 14:
                tone = "critical"
            elif days_left <= 30:
                tone = "warning"
            return {
                "status": "ok",
                "ssl_expires_at": expires_at.isoformat(),
                "ssl_days_left": days_left,
                "ssl_tone": tone,
            }


def _normalize_ssl_tone(status: str | None, ssl_tone: str | None) -> str:
    normalized_status = str(status or "").strip().lower()
    normalized_tone = str(ssl_tone or "").strip().lower()
    if normalized_status != "ok":
        return "none"
    if normalized_tone in {"warning", "critical", "ok"}:
        return normalized_tone
    return "ok"


async def _ssl_monitor_loop() -> None:
    while True:
        try:
            for user_id, url in list(site_targets.items()):
                health = {"checked_at": _now().isoformat(), "url": url}
                previous = site_health_status.get(user_id) or {}

                uptime_info = await run_in_threadpool(_check_target_uptime, url)
                health.update(uptime_info)

                was_down = str(previous.get("uptime_status", "")).lower() == "down"
                is_down = str(uptime_info.get("uptime_status", "")).lower() == "down"

                if is_down:
                    detail = str(uptime_info.get("uptime_detail", "target unreachable"))
                    health.update({"status": "error", "detail": detail, "alert_tone": "critical"})
                    if not was_down:
                        _enqueue_site_monitor_alert(
                            user_id=user_id,
                            target_url=url,
                            reason="uptime_down",
                            detail=detail,
                        )
                        record_site_monitor_log(
                            user_id=user_id,
                            level="error",
                            action="site_target_down",
                            detail=f"url={url};detail={detail}",
                        )
                else:
                    try:
                        ssl_info = await run_in_threadpool(_check_target_ssl, url)
                        health.update(ssl_info)

                        current_ssl_tone = _normalize_ssl_tone(ssl_info.get("status"), ssl_info.get("ssl_tone"))
                        previous_ssl_tone = _normalize_ssl_tone(previous.get("status"), previous.get("ssl_tone"))

                        if current_ssl_tone in {"warning", "critical"} and current_ssl_tone != previous_ssl_tone:
                            days_left = ssl_info.get("ssl_days_left")
                            detail = f"ssl_tone={current_ssl_tone};days_left={days_left}"
                            _enqueue_site_monitor_alert(
                                user_id=user_id,
                                target_url=url,
                                reason=f"ssl_{current_ssl_tone}",
                                detail=detail,
                            )
                            record_site_monitor_log(
                                user_id=user_id,
                                level="warning" if current_ssl_tone == "warning" else "error",
                                action="site_ssl_expiring",
                                detail=f"url={url};{detail}",
                            )
                    except Exception as exc:
                        health.update({"status": "error", "detail": str(exc), "alert_tone": "critical"})

                site_health_status[user_id] = health
        except Exception as exc:
            logger.warning("ssl monitor loop error: {}", exc)
        await asyncio.sleep(SSL_CHECK_INTERVAL_SECONDS)


@app.post("/auth/register")
async def auth_register(data: UserRegisterIn, response: Response, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    client_ip = _get_client_ip(request)
    async with _register_lock:
        if not _check_rate_limit(_register_attempts, client_ip, REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="注册尝试过于频繁，请1小时后再试")

    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="邮箱已注册")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        auth_provider="password",
        provider_user_id=None,
        encrypted_api_key=None,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="register", detail="password register")
    return _auth_payload(user, config, token)


@app.post("/auth/login/password")
async def auth_login_password(data: LoginPasswordIn, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    async with _login_lock:
        if not _check_login_rate_limit(data.email):
            raise HTTPException(status_code=429, detail="登录尝试过于频繁，请5分钟后再试")

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_password", detail="password login")
    return _auth_payload(user, config, token)


async def _verify_google_token(id_token: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("email_verified") != "true" and data.get("email_verified") is not True:
                return None
            return {"email": data.get("email", "").lower(), "sub": data.get("sub", ""), "name": data.get("name")}
    except Exception:
        return None


async def _verify_github_token(access_token: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "AI-CyberSentinel"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            email = data.get("email") or ""
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "AI-CyberSentinel"},
            )
            if emails_resp.status_code == 200:
                for e in emails_resp.json():
                    if e.get("primary") and e.get("verified"):
                        email = e.get("email", email)
            return {"email": email.lower(), "sub": str(data.get("id", "")), "name": data.get("name") or data.get("login")}
    except Exception:
        return None


@app.post("/auth/login/oauth")
async def auth_login_oauth(data: OAuthLoginIn, response: Response, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    client_ip = _get_client_ip(request)
    async with _register_lock:
        if not _check_rate_limit(_register_attempts, client_ip, REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="注册尝试过于频繁，请稍后再试")

    if not data.provider_user_id or len(data.provider_user_id) < 2:
        raise HTTPException(status_code=400, detail="OAuth 身份验证信息无效")

    verified: dict[str, Any] | None = None
    if data.provider == "google":
        verified = await _verify_google_token(data.id_token)
    elif data.provider == "github":
        verified = await _verify_github_token(data.id_token)

    if not verified:
        raise HTTPException(status_code=401, detail="OAuth 身份验证失败，请重新登录")

    if verified["email"].lower() != data.email.lower():
        raise HTTPException(status_code=401, detail="OAuth 邮箱与请求不匹配")

    if str(verified["sub"]) != str(data.provider_user_id):
        raise HTTPException(status_code=401, detail="OAuth 用户标识与请求不匹配")

    user = db.query(User).filter(User.email == data.email.lower()).first()
    if user is None:
        logger.warning(
            "OAuth auto-register: provider={} email={} ip={} — "
            "ensure OAuth callback verification is enabled on the frontend",
            data.provider, _sanitize_for_log(data.email), client_ip,
        )
        user = User(
            email=data.email.lower(),
            password_hash=None,
            display_name=data.display_name,
            auth_provider=data.provider,
            provider_user_id=data.provider_user_id,
            encrypted_api_key=None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user.auth_provider and user.auth_provider != data.provider:
            raise HTTPException(status_code=409, detail="该邮箱已使用其他方式注册")
        user.auth_provider = data.provider
        user.provider_user_id = data.provider_user_id
        if data.display_name:
            user.display_name = data.display_name
        db.add(user)
        db.commit()
        db.refresh(user)

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_oauth", detail=f"oauth login {data.provider}")
    return _auth_payload(user, config, token)


@app.post("/auth/login/otp/request")
async def auth_login_otp_request(data: OTPRequestIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    async with _otp_lock:
        if not _check_otp_rate_limit(data.email):
            raise HTTPException(status_code=429, detail="验证码请求过于频繁，请10分钟后再试")

    async with _otp_verify_lock:
        _otp_verify_failures.pop(data.email.lower(), None)

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    code = _issue_challenge(db, data.email.lower(), "otp", user.id if user else None)
    try:
        await send_otp_email(data.email.lower(), code)
    except Exception as exc:
        logger.warning("send otp email failed: {}", exc)
        raise HTTPException(status_code=500, detail="邮件发送失败，请检查 SMTP 配置") from exc
    create_log(db, user_id=user.id if user else None, level="info", action="otp_request", detail="otp requested")
    return {"status": "ok", "message": "验证码已发送"}


@app.post("/auth/login/otp/verify")
async def auth_login_otp_verify(data: OTPVerifyIn, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    email_key = data.email.lower()
    async with _otp_verify_lock:
        failures = _otp_verify_failures.get(email_key, 0)
        if failures >= OTP_VERIFY_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="验证码错误次数过多，请重新获取验证码")

    user = db.query(User).filter(User.email == email_key, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在，请先注册")

    try:
        _consume_valid_challenge(db, email_key, "otp", data.code)
    except HTTPException:
        async with _otp_verify_lock:
            _otp_verify_failures[email_key] = _otp_verify_failures.get(email_key, 0) + 1
        raise

    async with _otp_verify_lock:
        _otp_verify_failures.pop(email_key, None)

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_otp", detail="otp login")
    return _auth_payload(user, config, token)


@app.post("/auth/password/reset/request")
async def auth_password_reset_request(data: PasswordResetRequestIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    async with _otp_lock:
        if not _check_otp_rate_limit(data.email):
            raise HTTPException(status_code=429, detail="请求过于频繁，请10分钟后再试")

    async with _otp_verify_lock:
        _otp_verify_failures.pop(data.email.lower(), None)

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    if not user:
        return {"status": "ok", "message": "如果邮箱存在，验证码已发送"}

    code = _issue_challenge(db, data.email.lower(), "reset", user.id)
    try:
        await send_reset_email(data.email.lower(), code)
    except Exception as exc:
        logger.warning("send reset email failed: {}", exc)
        raise HTTPException(status_code=500, detail="邮件发送失败，请检查 SMTP 配置") from exc

    create_log(db, user_id=user.id, level="info", action="password_reset_request", detail="reset requested")
    return {"status": "ok", "message": "如果邮箱存在，验证码已发送"}


@app.post("/auth/password/reset/confirm")
async def auth_password_reset_confirm(data: PasswordResetConfirmIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    async with _otp_lock:
        if not _check_otp_rate_limit(data.email):
            raise HTTPException(status_code=429, detail="请求过于频繁，请10分钟后再试")

    email_key = data.email.lower()
    async with _otp_verify_lock:
        failures = _otp_verify_failures.get(email_key, 0)
        if failures >= OTP_VERIFY_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="验证码错误次数过多，请重新获取验证码")

    user = db.query(User).filter(User.email == email_key, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    try:
        _consume_valid_challenge(db, email_key, "reset", data.code)
    except HTTPException:
        async with _otp_verify_lock:
            _otp_verify_failures[email_key] = _otp_verify_failures.get(email_key, 0) + 1
        raise

    async with _otp_verify_lock:
        _otp_verify_failures.pop(email_key, None)

    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = _now()
    db.add(user)
    db.commit()
    create_log(db, user_id=user.id, level="info", action="password_reset_confirm", detail="password reset")
    return {"status": "ok", "message": "密码已更新"}


@app.post("/auth/logout")
async def auth_logout(response: Response) -> dict[str, Any]:
    clear_access_cookie(response)
    return {"status": "ok"}


@app.get("/auth/session")
async def auth_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    config = get_or_create_user_config(db, user.id)
    return _auth_payload(user, config)


@app.get("/user/config")
async def get_user_config(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    config = get_or_create_user_config(db, user.id)

    try:
        api_key_plain = decrypt_api_key(user.encrypted_api_key)
    except DecryptionError:
        api_key_plain = None
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    return {
        "ai_provider": provider,
        "model": config.model,
        "base_url": config.base_url,
        "timeout_seconds": config.timeout_seconds,
        "alert_email_enabled": config.alert_email_enabled,
        "alert_voice_enabled": config.alert_voice_enabled,
        "ui_theme": config.ui_theme,
        "ui_density": config.ui_density,
        "has_api_key": bool(api_key_plain),
        "api_key_masked": _mask_key(api_key_plain),
    }


@app.put("/user/config")
async def put_user_config(
    data: UserConfigIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    config = get_or_create_user_config(db, user.id)

    payload = data.model_dump(exclude_none=True)
    log_payload = payload.copy()
    if "api_key" in log_payload:
        log_payload["api_key"] = "***"
    if "ai_provider" in payload:
        config.ai_provider = normalize_ai_provider(payload["ai_provider"])
    if "model" in payload:
        config.model = str(payload["model"]).strip() or config.model
    if "base_url" in payload:
        config.base_url = str(payload["base_url"]).strip().rstrip("/")
    if "timeout_seconds" in payload:
        config.timeout_seconds = int(payload["timeout_seconds"])
    if "alert_email_enabled" in payload:
        config.alert_email_enabled = bool(payload["alert_email_enabled"])
    if "alert_voice_enabled" in payload:
        config.alert_voice_enabled = bool(payload["alert_voice_enabled"])
    if "ui_theme" in payload:
        config.ui_theme = str(payload["ui_theme"]).strip() or config.ui_theme
    if "ui_density" in payload:
        config.ui_density = str(payload["ui_density"]).strip() or config.ui_density

    if "api_key" in payload:
        key_text = str(payload["api_key"]).strip()
        user.encrypted_api_key = encrypt_api_key(key_text) if key_text else user.encrypted_api_key

    provider = choose_provider(config.ai_provider, config.model, config.base_url)
    config.ai_provider = provider
    if not config.base_url:
        config.base_url = PROVIDER_BASE_URL_DEFAULTS[provider]
    if not config.model:
        config.model = PROVIDER_MODEL_DEFAULTS[provider]

    db.add(config)
    db.add(user)
    db.commit()
    db.refresh(config)

    create_log(db, user_id=user.id, level="info", action="user_config_update", detail=json.dumps(log_payload, ensure_ascii=False))
    return {
        "status": "updated",
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(user.encrypted_api_key),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }


@app.get("/logs")
async def get_logs(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    logs = (
        db.query(Log)
        .filter((Log.user_id == user.id) | (Log.user_id.is_(None)))
        .order_by(Log.created_at.desc())
        .limit(200)
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "level": item.level,
                "action": item.action,
                "detail": item.detail,
                "created_at": item.created_at.isoformat(),
            }
            for item in logs
        ]
    }


@app.post("/site/target")
async def set_site_target(
    data: SiteTargetIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    normalized = data.url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="site target must be valid http(s) url")

    if _is_url_pointing_to_internal(normalized):
        raise HTTPException(status_code=422, detail="不允许监控内网地址")

    site_targets[user.id] = normalized

    initial_health: dict[str, Any] = {"checked_at": _now().isoformat(), "url": normalized}
    uptime_info = await run_in_threadpool(_check_target_uptime, normalized)
    initial_health.update(uptime_info)

    if str(uptime_info.get("uptime_status", "")).lower() == "down":
        detail = str(uptime_info.get("uptime_detail", "target unreachable"))
        initial_health.update({"status": "error", "detail": detail, "alert_tone": "critical"})
        _enqueue_site_monitor_alert(
            user_id=user.id,
            target_url=normalized,
            reason="uptime_down",
            detail=detail,
        )
        record_site_monitor_log(
            user_id=user.id,
            level="error",
            action="site_target_down",
            detail=f"url={normalized};detail={detail}",
        )
    else:
        try:
            ssl_info = await run_in_threadpool(_check_target_ssl, normalized)
            initial_health.update(ssl_info)
        except Exception as exc:
            initial_health.update({"status": "error", "detail": str(exc), "alert_tone": "critical"})

    site_health_status[user.id] = initial_health

    create_log(db, user_id=user.id, level="info", action="site_target_set", detail=normalized)
    return {"status": "ok", "target": normalized}


@app.get("/site/health")
async def get_site_health(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    item = site_health_status.get(user.id)
    if item is None:
        return {"status": "idle", "detail": "尚未设置监测站点"}
    return item


@app.post("/copilot/stream")
async def copilot_stream(
    data: CopilotStreamIn,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    user = get_current_user(db, access_token_cookie, authorization)
    client_ip = _get_client_ip(request)
    async with _copilot_lock:
        if not _check_rate_limit(_copilot_attempts, client_ip, COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="Copilot请求过于频繁，请1分钟后再试")
    config = get_or_create_user_config(db, user.id)
    runtime, provider = user_config_to_llm_runtime(config, user)

    alert: dict[str, Any] | None = None
    if data.alert_id:
        alert = find_alert_by_id(str(data.alert_id).strip(), user_id=user.id)

    context_block = _build_context_from_alert(alert)
    stream = stream_user_chat_completion(
        runtime=runtime,
        provider=provider,
        user_message=str(data.message).strip(),
        context_block=context_block,
        history=data.history,
    )

    create_log(
        db,
        user_id=user.id,
        level="info",
        action="copilot_stream",
        detail=f"provider={provider};model={runtime.model};alert_id={data.alert_id or ''}",
    )

    return StreamingResponse(stream, media_type="text/event-stream")


@app.post("/threats/confirm")
async def post_threat_confirm(
    data: ThreatConfirmIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)

    alert = find_alert_by_id(data.alert_id, user_id=user.id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_id not found")

    await append_new_threat_csv(alert, data.label)
    create_log(db, user_id=user.id, level="info", action="threat_confirm", detail=f"{data.alert_id}:{_sanitize_for_log(data.label)}")
    return {
        "status": "ok",
        "saved_to": _new_threats_csv_path.name,
        "alert_id": data.alert_id,
        "label": data.label,
    }


async def alert_worker(worker_id: int) -> None:
    logger.info("Alert worker started id={}", worker_id)
    while True:
        alert = await _alert_queue.get()
        try:
            payload = await process_alert(alert)
            await append_backlog(payload)
            alert_user_id = int((payload.get("raw_alert") or {}).get("alert_user_id") or 0)
            if alert_user_id > 0:
                await manager.broadcast_json(alert_user_id, payload)
        except Exception as exc:
            logger.exception("Alert worker failed id={} err={}", worker_id, exc)
        finally:
            _alert_queue.task_done()


@app.on_event("startup")
async def startup_event() -> None:
    global _ssl_monitor_task
    for worker_id in range(ALERT_WORKER_COUNT):
        _worker_tasks.append(asyncio.create_task(alert_worker(worker_id)))
    _ssl_monitor_task = asyncio.create_task(_ssl_monitor_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for task in _worker_tasks:
        task.cancel()
    if _ssl_monitor_task is not None:
        _ssl_monitor_task.cancel()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/llm/config")
async def get_llm_config(
    _: None = Depends(require_llm_admin_token),
) -> dict[str, Any]:
    config = await get_runtime_llm_config()
    provider = choose_provider("custom", config.model, config.base_url)
    return config_to_payload(config, provider)


@app.put("/llm/config")
async def put_llm_config(
    data: LLMConfigIn,
    _: None = Depends(require_llm_admin_token),
) -> dict[str, Any]:
    config = await update_runtime_llm_config(data)
    provider = choose_provider(data.ai_provider, config.model, config.base_url)
    return {"status": "updated", "config": config_to_payload(config, provider)}


@app.post("/llm/test")
async def post_llm_test(
    data: LLMConfigIn,
    request: Request,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client_ip = _get_client_ip(request)
    async with _llm_lock:
        if not _check_rate_limit(_llm_attempts, client_ip, LLM_RATE_LIMIT_WINDOW, LLM_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="LLM测试请求过于频繁，请1分钟后再试")

    update = data.model_dump(exclude_none=True)
    config = get_or_create_user_config(db, user.id)
    decrypted_key = _safe_decrypt(user.encrypted_api_key) or ""

    provider = choose_provider(
        str(update.get("ai_provider", config.ai_provider)),
        str(update.get("model", config.model)),
        str(update.get("base_url", config.base_url)),
    )

    model = str(update.get("model", config.model)).strip() or config.model
    base_url = str(update.get("base_url", config.base_url)).strip() or config.base_url
    timeout_seconds = int(update.get("timeout_seconds", config.timeout_seconds))

    api_key = decrypted_key
    if "api_key" in update:
        api_key = str(update["api_key"] or "").strip() or decrypted_key

    test_config = AnalyzerConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    logger.info(
        "[LLM_TEST] user_id={} provider={} model={} base_url={} has_api_key={}",
        user.id, provider, test_config.model,
        test_config.base_url[:30] + "..." if len(test_config.base_url) > 30 else test_config.base_url,
        bool(test_config.api_key),
    )

    if not test_config.api_key or not test_config.base_url:
        raise HTTPException(status_code=400, detail="API Key 和 Base URL 不能为空")

    if test_config.timeout_seconds < 1 or test_config.timeout_seconds > 300:
        raise HTTPException(status_code=422, detail="timeout_seconds 必须在 1-300 之间")

    parsed_base = urlparse(test_config.base_url)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise HTTPException(status_code=422, detail="Base URL 格式无效")

    try:
        result = await test_llm_connection_by_provider(test_config, provider)
        logger.info("[LLM_TEST] success user_id={} result={}", user.id, result)
        create_log(
            db,
            user_id=user.id,
            level="info",
            action="llm_test",
            detail=f"provider={provider};model={test_config.model}",
        )
        return {"status": "ok", "provider": provider, "result": result}
    except httpx.TimeoutException as exc:
        logger.warning("[LLM_TEST] timeout user_id={} base_url={} exc={}", user.id, test_config.base_url, exc)
        raise HTTPException(status_code=400, detail="连接超时，请检查网络或 Base URL 是否可达，或增加超时时间") from exc
    except httpx.ConnectError as exc:
        logger.warning("[LLM_TEST] connect_error user_id={} base_url={} exc={}", user.id, test_config.base_url, exc)
        raise HTTPException(status_code=400, detail="无法连接到服务器，请检查 Base URL") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("[LLM_TEST] http_error user_id={} status={} body={}", user.id, exc.response.status_code, exc.response.text[:200])
        raise HTTPException(status_code=400, detail=f"服务器返回错误 ({exc.response.status_code})，请检查 API Key 和模型名称") from exc
    except Exception as exc:
        logger.warning("[LLM_TEST] failure user_id={} exc_type={} exc={}", user.id, type(exc).__name__, exc)
        raise HTTPException(status_code=400, detail="LLM 连接测试失败，请检查配置") from exc

async def site_proxy(
    path: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> Response:
    user = get_current_user(db, access_token_cookie, authorization)
    target_base = site_targets.get(user.id, "").strip()
    if not target_base:
        raise HTTPException(status_code=400, detail="请先设置受保护站点")

    parsed = urlparse(target_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="受保护站点配置无效")

    if _is_url_pointing_to_internal(target_base):
        raise HTTPException(status_code=400, detail="受保护站点不允许指向内网地址")

    # SECURITY: Multi-layer path traversal protection
    decoded_path = path
    # Decode up to 3 times to catch double/triple encoding
    for _ in range(3):
        new_decoded = unquote(decoded_path)
        if new_decoded == decoded_path:
            break
        decoded_path = new_decoded

    if ".." in decoded_path or ".." in path or "%2e" in path.lower() or "%2f" in path.lower() or "\\" in path or "\0" in decoded_path:
        return JSONResponse(status_code=400, content={"detail": "无效的路径格式"})

    # Validate path segments don't contain traversal after decoding
    segments = [s for s in decoded_path.split("/") if s]
    for seg in segments:
        if seg == ".." or seg.startswith("..") or "/" in seg or "\\" in seg:
            return JSONResponse(status_code=400, content={"detail": "无效的路径格式"})

    target_url = f"{target_base.rstrip('/')}/{path.lstrip('/')}"
    resolved = urlparse(target_url)
    if resolved.scheme not in {"http", "https"} or not resolved.netloc:
        return JSONResponse(status_code=400, content={"detail": "无效的目标URL"})

    # SECURITY: Ensure resolved URL doesn't escape the target base
    resolved_target = urlparse(target_base)
    target_path = (resolved_target.path or "/").rstrip("/")
    path_ok = resolved.path == target_path or resolved.path == target_path + "/" or resolved.path.startswith(target_path + "/")
    if resolved.hostname != resolved_target.hostname or not path_ok:
        return JSONResponse(status_code=400, content={"detail": "无效的目标URL"})

    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="ignore") if body_bytes else ""
    inspect_text = "\n".join([path, request.url.query, body_text])

    if _payload_has_attack_signature(inspect_text):
        source_ip = _get_client_ip(request)
        destination = parsed.hostname or "unknown"
        attack_payload = body_text or path
        accepted, replaced_oldest = enqueue_alert(_build_attack_alert(source_ip, destination, attack_payload, user.id))
        if not accepted:
            logger.warning("waf alert queue full, drop block alert source_ip={}", source_ip)
        elif replaced_oldest:
            logger.warning("waf alert queue full, evict oldest block alert source_ip={}", source_ip)
        create_log(db, user_id=user.id, level="warning", action="waf_block", detail=f"ip={_sanitize_for_log(source_ip)}")
        return JSONResponse(status_code=403, content={"status": "blocked", "reason": "Security policy violation"})

    headers = _build_proxy_headers(request)
    headers["X-Forwarded-For"] = _get_client_ip(request)

    timeout = httpx.Timeout(connect=8.0, read=60.0, write=30.0, pool=20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body_bytes if body_bytes else None,
            )
    except httpx.HTTPError as exc:
        logger.warning("site_proxy upstream error: {}", exc)
        raise HTTPException(status_code=502, detail="上游服务不可用") from exc

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() not in UPSTREAM_STRIP_RESPONSE_HEADERS
    }
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)



@app.post("/alerts")
async def receive_alert(
    alert: AlertIn,
    request: Request,
    _: None = Depends(require_alert_ingest_token),
) -> dict[str, Any]:
    if not _is_allowed_alert_ingest_source(request):
        raise HTTPException(status_code=403, detail="Alert ingest source is not allowed")

    accepted, replaced_oldest = enqueue_alert(alert)
    if not accepted:
        raise HTTPException(status_code=503, detail="Alert queue is full")

    return {
        "status": "accepted",
        "queued": True,
        "received_at": time.time(),
        "replaced_oldest": replaced_oldest,
    }


@app.get("/alerts")
async def get_alerts(
    limit: int = 100,
    user: User = Depends(require_auth_user),
) -> dict[str, Any]:
    backlog = await get_backlog_snapshot()
    user_items = [item for item in backlog if (item.get("raw_alert") or {}).get("alert_user_id") == user.id]
    bounded = max(1, min(limit, ALERT_BACKLOG_SIZE))
    return {
        "items": user_items[-bounded:],
        "count": len(user_items),
    }


@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket) -> None:
    token = websocket.headers.get("authorization")
    cookie_text = websocket.headers.get("cookie", "")
    access_token_cookie: str | None = None

    # SECURITY: Use SimpleCookie for robust cookie parsing with proper decoding
    try:
        from http.cookies import SimpleCookie
        cookie = SimpleCookie()
        cookie.load(cookie_text)
        if "access_token" in cookie:
            access_token_cookie = cookie["access_token"].value or None
    except Exception:
        # Fallback only for malformed cookie strings, not for parsing logic errors
        access_token_cookie = None

    with SessionLocal() as db:
        user: User | None = None
        try:
            user = get_current_user(db, access_token_cookie, token)
        except HTTPException:
            await websocket.close(code=1008)
            return

    if user is None:
        await websocket.close(code=1008)
        return
    await manager.connect(user.id, websocket)
    try:
        backlog = await get_backlog_snapshot()
        for item in backlog:
            if (item.get("raw_alert") or {}).get("alert_user_id") == user.id:
                await websocket.send_json(item)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user.id, websocket)
    except Exception as exc:
        await manager.disconnect(user.id, websocket)
        logger.warning("WebSocket closed with error: {}", exc)
