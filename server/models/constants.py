"""Shared field constraints.

Single source of truth for enum values and string lengths that appear in
both the Pydantic schemas (`server/models/schemas.py`) and the SQLAlchemy
ORM models (`server/models_db.py`). Both layers import from here so the
two cannot drift apart.

Adding a new field:
1. Add the column/field declaration with the relevant `MAX_*` constant.
2. Add a matching pydantic field with the same constant.
3. The schema validator and the database column will then stay in sync.
"""
from __future__ import annotations

# ---- AI provider enum (Pydantic + DB) ----
ALLOWED_AI_PROVIDERS: tuple[str, ...] = ("openai", "claude", "gemini", "grok", "custom")
MAX_AI_PROVIDER_LEN = 24

# ---- Webhook types ----
ALLOWED_WEBHOOK_TYPES: tuple[str, ...] = ("generic", "dingtalk", "feishu")
MAX_WEBHOOK_TYPE_LEN = 16
MAX_WEBHOOK_URL_LEN = 500

# ---- UI preferences ----
ALLOWED_UI_THEMES: tuple[str, ...] = ("dark", "light", "auto")
MAX_UI_THEME_LEN = 20
ALLOWED_UI_DENSITIES: tuple[str, ...] = ("comfortable", "compact", "spacious")
MAX_UI_DENSITY_LEN = 20

# ---- Model / URL lengths ----
MAX_MODEL_LEN = 50
MAX_BASE_URL_LEN = 500
MAX_LLM_PROVIDER_LEN = 24

# ---- User / auth fields ----
MAX_USER_EMAIL_LEN = 320
MAX_USER_DISPLAY_NAME_LEN = 120
MAX_TOTP_SECRET_LEN = 64
MAX_BACKUP_CODE_HASH_LEN = 128
MAX_PASSWORD_HASH_LEN = 255
MAX_PROVIDER_USER_ID_LEN = 255
MAX_IP_ADDRESS_LEN = 64
MAX_USER_AGENT_LEN = 500
MAX_AUTH_PROVIDER_LEN = 32
MAX_ROLE_LEN = 16

# ---- Config / request fields ----
MAX_PASSWORD_LEN = 128
MIN_PASSWORD_LEN = 8
MAX_API_KEY_LEN = 512
MIN_TOTP_CODE_LEN = 6
MAX_TOTP_CODE_LEN = 10
MAX_OTP_CODE_LEN = 12
MIN_OTP_CODE_LEN = 4
MAX_OAUTH_ID_TOKEN_LEN = 8192
MAX_PROVIDER_USER_ID_INPUT_LEN = 255

# ---- Alert fields ----
MAX_ALERT_EVENT_LEN = 32
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 300

# ---- Audit / log fields ----
MAX_LOG_LEVEL_LEN = 16
MAX_LOG_ACTION_LEN = 80
MAX_LOG_DETAIL_LEN = 8000

# ---- Copilot fields ----
MAX_COPILOT_MESSAGE_LEN = 8000
MIN_COPILOT_MESSAGE_LEN = 1

# ---- Refresh token fields ----
MAX_REFRESH_TOKEN_SESSION_ID_LEN = 48
MAX_REFRESH_TOKEN_HASH_LEN = 128
