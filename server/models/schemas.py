from typing import Any
from pydantic import BaseModel, EmailStr, Field


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
