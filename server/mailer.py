from __future__ import annotations

import os
from datetime import datetime

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def get_mail_config() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
        MAIL_FROM=os.getenv("MAIL_FROM", "noreply@ai-cybersentinel.local"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
        MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.example.com"),
        MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "AI-CyberSentinel"),
        MAIL_STARTTLS=_bool_env("MAIL_STARTTLS", True),
        MAIL_SSL_TLS=_bool_env("MAIL_SSL_TLS", False),
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=_bool_env("MAIL_VALIDATE_CERTS", True),
    )


async def send_otp_email(email: str, code: str) -> None:
    conf = get_mail_config()
    fm = FastMail(conf)
    message = MessageSchema(
        subject="AI-CyberSentinel 登录验证码",
        recipients=[email],
        body=(
            "<h3>你的登录验证码</h3>"
            f"<p style='font-size:22px;font-weight:700'>{code}</p>"
            "<p>验证码 10 分钟内有效。如非本人操作，请忽略。</p>"
        ),
        subtype=MessageType.html,
    )
    await fm.send_message(message)


async def send_reset_email(email: str, code: str) -> None:
    conf = get_mail_config()
    fm = FastMail(conf)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    message = MessageSchema(
        subject="AI-CyberSentinel 密码重置验证码",
        recipients=[email],
        body=(
            "<h3>密码重置请求</h3>"
            f"<p style='font-size:22px;font-weight:700'>{code}</p>"
            f"<p>请求时间：{now}</p>"
            "<p>验证码 10 分钟内有效。如非本人操作，请尽快修改邮箱密码。</p>"
        ),
        subtype=MessageType.html,
    )
    await fm.send_message(message)
