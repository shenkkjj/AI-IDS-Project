import os
import re
from pathlib import Path


ALERT_QUEUE_MAX_SIZE = 256
ALERT_WORKER_COUNT = 4
ALERT_BACKLOG_SIZE = 200
ALERT_EMAIL_COOLDOWN_SECONDS = 300
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

BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1").strip()
TARGET_URL = os.getenv("TARGET_URL", "http://127.0.0.1:8000").strip().rstrip("/")

HONEYPOT_ENABLED = os.getenv("HONEYPOT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
HONEYPOT_PORT = int(os.getenv("HONEYPOT_PORT", "8888").strip())

GATEWAY_RATE_LIMIT_WINDOW = int(os.getenv("GATEWAY_RATE_LIMIT_WINDOW", "60").strip())
GATEWAY_RATE_LIMIT_MAX = int(os.getenv("GATEWAY_RATE_LIMIT_MAX", "120").strip())
GATEWAY_RATE_LIMIT_BURST = int(os.getenv("GATEWAY_RATE_LIMIT_BURST", "30").strip())

THREAT_INTEL_ENABLED = os.getenv("THREAT_INTEL_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY", "").strip()
THREAT_INTEL_SCORE_THRESHOLD = int(os.getenv("THREAT_INTEL_SCORE_THRESHOLD", "50").strip())

ALLOWED_AI_PROVIDERS = {"openai", "claude", "gemini", "grok", "custom"}
PROVIDER_MODEL_DEFAULTS = {
    "openai": "",
    "claude": "",
    "gemini": "",
    "grok": "",
    "custom": "",
}
PROVIDER_BASE_URL_DEFAULTS = {
    "openai": "https://api.openai.com",
    "claude": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "grok": "https://api.x.ai",
    "custom": "",
}

WAF_BLOCK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(\bunion\b\s*\bselect\b)"),
    re.compile(r"(?i)(\bunion\b\s+/\*[\s\S]*?\*/\s*\bselect\b)"),
    re.compile(r"(?i)(\b(or|and)\b\s+\d+\s*=\s*\d+)"),
    re.compile(r"(?i)(<\s*script\b)"),
    re.compile(r"(?i)(\bjavascript\s*:)"),
    re.compile(r"(?i)(\bexec\b\s*\()"),
    re.compile(r"(?i)(\beval\b\s*\()"),
    re.compile(r"(?i)(\bdrop\b\s+\btable\b)"),
    re.compile(r"(?i)(\binsert\b\s+\binto\b)"),
    re.compile(r"(?i)(\bdelete\b\s+\bfrom\b)"),
    re.compile(r"(?i)(\bon\w+\s*=)"),
    re.compile(r"(?i)'\s*\|\|?\s*\w+\s*\|\|?\s*'"),
    re.compile(r"(?i)(\bur[li]\b\s*\(['\"])"),
]

HOP_BY_HOP_HEADERS: set[str] = {
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade",
}

PROXY_STRIP_HEADERS: set[str] = {
    "cookie", "set-cookie", "authorization",
    "proxy-authorization", "www-authenticate",
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
