from typing import Any, Literal
from pydantic import BaseModel, EmailStr, Field


def _validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("密码长度至少8位")
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        raise ValueError("密码必须包含大写字母、小写字母和数字")
    return password


# ---------------------------------------------------------------------------
# 告警研判 (M3-02)
# ---------------------------------------------------------------------------

# 稳定的研判状态枚举,后端契约白名单。
TRIAGE_STATUS_VALUES = ("new", "investigating", "contained", "false_positive", "resolved")
AlertTriageStatus = Literal["new", "investigating", "contained", "false_positive", "resolved"]


class AlertTriageUpdateIn(BaseModel):
    """PATCH /alerts/{alert_id}/triage 请求体。

    - ``status`` 必须落在 ``TRIAGE_STATUS_VALUES`` 内,否则由 Pydantic 返回 422。
    - ``disposition`` 是可选的处置分类(自定义短码,如 ``blocked_at_waf``)。
    - ``analyst_note`` 上限 800 字符,由 Pydantic 强制。
    """

    status: AlertTriageStatus
    disposition: str | None = Field(default=None, max_length=64)
    analyst_note: str | None = Field(default=None, max_length=800)


class AlertTriageOut(BaseModel):
    """GET /alerts 与 PATCH 响应中的 triage 字段。"""

    status: AlertTriageStatus
    disposition: str | None = None
    analyst_note: str | None = None
    updated_at: float
    updated_by: int | None = None


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
    ai_provider: str | None = Field(default=None, max_length=24)
    api_key: str | None = Field(default=None, max_length=512)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=50)
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)


class ThreatConfirmIn(BaseModel):
    alert_id: str
    label: str = Field(default="user_confirmed_threat")


class UserRegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None

    def model_post_init(self, __context: object) -> None:
        _validate_password_strength(self.password)


class LoginPasswordIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    # TOTP 验证码（仅当用户已启用 2FA 时必填）。
    # 服务端在用户启用 TOTP 后，会要求登录时附带 6 位动态码。
    totp_code: str | None = Field(default=None, min_length=6, max_length=10)


class OTPRequestIn(BaseModel):
    email: EmailStr


class OTPVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    # 用户在已启用 2FA 时，OTP 登录后仍需再校验 TOTP。
    totp_code: str | None = Field(default=None, min_length=6, max_length=10)


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)

    def model_post_init(self, __context: object) -> None:
        _validate_password_strength(self.new_password)


class OAuthLoginIn(BaseModel):
    provider: str = Field(pattern="^(github|google)$")
    id_token: str = Field(min_length=1, max_length=8192)
    provider_user_id: str = Field(max_length=255)
    email: EmailStr
    display_name: str | None = None
    # OAuth 用户若已启用 TOTP，登录时也必须提供动态码。
    totp_code: str | None = Field(default=None, min_length=6, max_length=10)


class UserConfigIn(BaseModel):
    ai_provider: str | None = Field(default=None, pattern="^(openai|claude|gemini|grok|custom)$", max_length=24)
    model: str | None = Field(default=None, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    alert_email_enabled: bool | None = None
    alert_voice_enabled: bool | None = None
    webhook_url: str | None = Field(default=None, max_length=500)
    webhook_type: str | None = Field(default=None, pattern="^(generic|dingtalk|feishu)$", max_length=16)
    ui_theme: str | None = Field(default=None, pattern="^(dark|light|auto)$", max_length=20)
    ui_density: str | None = Field(default=None, pattern="^(comfortable|compact|spacious)$", max_length=20)
    api_key: str | None = Field(default=None, max_length=512)


class SiteTargetIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class CopilotMessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class CopilotStreamIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    alert_id: str | None = None
    # M3-05: 案件感知 Copilot 合约;后端负责 owner 隔离并构造受控 context_block。
    # 最多 64 字符,由 Pydantic 强制;incident_id 与 alert_id 可独立使用,二者同时
    # 存在时 incident 优先(见 server.services.copilot_service.copilot_stream)。
    incident_id: str | None = Field(default=None, max_length=64)
    history: list[CopilotMessageIn] = Field(default_factory=list)
