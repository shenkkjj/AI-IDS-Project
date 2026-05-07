# flake8: noqa: E501
from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from server.core.config import load_dotenv_file

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv_file(_ENV_PATH)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def get_mail_config() -> ConnectionConfig:
    mail_from = os.getenv("MAIL_FROM", "")
    if not mail_from:
        raise RuntimeError("MAIL_FROM must be configured in environment variables")
    try:
        mail_port = int(os.getenv("MAIL_PORT", "587"))
    except ValueError:
        mail_port = 587
    return ConnectionConfig(
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
        MAIL_FROM=mail_from,
        MAIL_PORT=mail_port,
        MAIL_SERVER=os.getenv("MAIL_SERVER", ""),
        MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "AI-CyberSentinel"),
        MAIL_STARTTLS=_bool_env("MAIL_STARTTLS", True),
        MAIL_SSL_TLS=_bool_env("MAIL_SSL_TLS", False),
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=_bool_env("MAIL_VALIDATE_CERTS", True),
    )


async def send_otp_email(email: str, code: str) -> None:
    conf = get_mail_config()
    fm = FastMail(conf)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录验证码</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f4f4f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
            <td align="center" style="padding:40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding:48px 40px 32px;text-align:center;background:linear-gradient(135deg,#3b82f6 0%,#8b5cf6 100%);border-radius:12px 12px 0 0;">
                            <h1 style="color:#ffffff;margin:0;font-size:28px;font-weight:700;letter-spacing:-0.5px;">AI-CyberSentinel</h1>
                            <p style="color:rgba(255,255,255,0.9);margin:8px 0 0 0;font-size:14px;">智能入侵检测系统</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:40px;">
                            <h2 style="color:#1f2937;margin:0 0 16px 0;font-size:22px;font-weight:600;">登录验证码</h2>
                            <p style="color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 24px 0;">您正在进行登录验证，请使用以下验证码完成操作。如果这不是您本人的操作，请忽略此邮件。</p>
                            <div style="background:#f3f4f6;border-radius:8px;padding:24px;text-align:center;margin:24px 0;border:2px dashed #d1d5db;">
                                <p style="color:#6b7280;font-size:13px;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:1px;">验证码</p>
                                <p style="color:#3b82f6;font-size:36px;font-weight:800;margin:0;letter-spacing:6px;font-family:'Courier New',monospace;">{html.escape(code)}</p>
                            </div>
                            <p style="color:#9ca3af;font-size:13px;margin:24px 0 0 0;">请求时间: {now}</p>
                            <p style="color:#9ca3af;font-size:13px;margin:4px 0 0 0;">验证码 10 分钟内有效，请勿泄露给他人</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:24px 40px;text-align:center;background:#f9fafb;border-radius:0 0 12px 12px;border-top:1px solid #e5e7eb;">
                            <p style="color:#9ca3af;font-size:12px;margin:0;">此邮件由 AI-CyberSentinel 系统自动发送</p>
                            <p style="color:#d1d5db;font-size:11px;margin:8px 0 0 0;">请勿回复此邮件</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""  # noqa: E501

    message = MessageSchema(
        subject="AI-CyberSentinel 登录验证码",
        recipients=[email],
        body=html_body,
        subtype=MessageType.html,
    )
    await fm.send_message(message)


async def send_reset_email(email: str, code: str) -> None:
    conf = get_mail_config()
    fm = FastMail(conf)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>密码重置验证码</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f4f4f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
            <td align="center" style="padding:40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding:48px 40px 32px;text-align:center;background:linear-gradient(135deg,#3b82f6 0%,#8b5cf6 100%);border-radius:12px 12px 0 0;">
                            <h1 style="color:#ffffff;margin:0;font-size:28px;font-weight:700;letter-spacing:-0.5px;">AI-CyberSentinel</h1>
                            <p style="color:rgba(255,255,255,0.9);margin:8px 0 0 0;font-size:14px;">智能入侵检测系统</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:40px;">
                            <h2 style="color:#1f2937;margin:0 0 16px 0;font-size:22px;font-weight:600;">密码重置请求</h2>
                            <p style="color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 24px 0;">您收到了这封邮件，是因为有人请求重置您的账户密码。如果这不是您本人的操作，请忽略此邮件。</p>
                            <div style="background:#f3f4f6;border-radius:8px;padding:24px;text-align:center;margin:24px 0;border:2px dashed #d1d5db;">
                                <p style="color:#6b7280;font-size:13px;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:1px;">验证码</p>
                                <p style="color:#3b82f6;font-size:36px;font-weight:800;margin:0;letter-spacing:6px;font-family:'Courier New',monospace;">{html.escape(code)}</p>
                            </div>
                            <p style="color:#9ca3af;font-size:13px;margin:24px 0 0 0;">请求时间: {now}</p>
                            <p style="color:#9ca3af;font-size:13px;margin:4px 0 0 0;">验证码 10 分钟内有效，请勿泄露给他人</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:24px 40px;text-align:center;background:#f9fafb;border-radius:0 0 12px 12px;border-top:1px solid #e5e7eb;">
                            <p style="color:#9ca3af;font-size:12px;margin:0;">此邮件由 AI-CyberSentinel 系统自动发送</p>
                            <p style="color:#d1d5db;font-size:11px;margin:8px 0 0 0;">请勿回复此邮件</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""  # noqa: E501

    message = MessageSchema(
        subject="AI-CyberSentinel 密码重置验证码",
        recipients=[email],
        body=html_body,
        subtype=MessageType.html,
    )
    await fm.send_message(message)


async def send_alert_email(
    email: str,
    alert_type: str,
    source_ip: str,
    destination: str,
    payload: str,
    risk_level: str = "high",
    blocked: bool = True,
) -> None:
    conf = get_mail_config()
    fm = FastMail(conf)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    risk_color = {"critical": "#dc2626", "high": "#ea580c", "medium": "#ca8a04", "low": "#16a34a"}.get(risk_level, "#ea580c")  # noqa: E501
    risk_label = {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危"}.get(risk_level, "高危")
    status_text = "已拦截" if blocked else "已检测"
    status_color = "#16a34a" if blocked else "#ca8a04"

    truncated_payload = html.escape(payload[:500]) if payload else "无"
    if len(payload) > 500:
        truncated_payload += "..."

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>安全警报</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#0a0a0a;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
            <td align="center" style="padding:40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:#111111;border-radius:12px;border:1px solid #333333;">
                    <tr>
                        <td style="padding:32px 40px;text-align:center;background:linear-gradient(135deg,#1a1a1a 0%,#0a0a0a 100%);border-radius:12px 12px 0 0;border-bottom:2px solid {risk_color};">
                            <h1 style="color:#00ff41;margin:0;font-size:24px;font-weight:700;font-family:'Courier New',monospace;">AI-CyberSentinel</h1>
                            <p style="color:#666666;margin:8px 0 0 0;font-size:12px;">智能入侵检测系统</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px 40px;">
                            <div style="background:#1a1a1a;border-radius:8px;padding:20px;margin-bottom:20px;border-left:4px solid {risk_color};">
                                <h2 style="color:{risk_color};margin:0 0 8px 0;font-size:18px;font-weight:700;">安全警报 - {risk_label}</h2>
                                <p style="color:#888888;margin:0;font-size:12px;font-family:'Courier New',monospace;">{now}</p>
                            </div>

                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:20px;">
                                <tr>
                                    <td style="padding:12px 0;border-bottom:1px solid #333333;color:#888888;font-size:13px;">事件类型</td>
                                    <td style="padding:12px 0;border-bottom:1px solid #333333;color:#e5e5e5;font-size:13px;text-align:right;font-family:'Courier New',monospace;">{html.escape(alert_type)}</td>
                                </tr>
                                <tr>
                                    <td style="padding:12px 0;border-bottom:1px solid #333333;color:#888888;font-size:13px;">源 IP</td>
                                    <td style="padding:12px 0;border-bottom:1px solid #333333;color:#e5e5e5;font-size:13px;text-align:right;font-family:'Courier New',monospace;">{html.escape(source_ip)}</td>
                                </tr>
                                <tr>
                                    <td style="padding:12px 0;border-bottom:1px solid #333333;color:#888888;font-size:13px;">目标</td>
                                    <td style="padding:12px 0;border-bottom:1px solid #333333;color:#e5e5e5;font-size:13px;text-align:right;font-family:'Courier New',monospace;">{html.escape(destination)}</td>
                                </tr>
                                <tr>
                                    <td style="padding:12px 0;color:#888888;font-size:13px;">处理状态</td>
                                    <td style="padding:12px 0;text-align:right;">
                                        <span style="background:{status_color};color:#ffffff;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:600;">{status_text}</span>
                                    </td>
                                </tr>
                            </table>

                            <div style="background:#0a0a0a;border-radius:8px;padding:16px;border:1px solid #333333;">
                                <p style="color:#888888;font-size:11px;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:1px;">攻击载荷</p>
                                <pre style="margin:0;color:#00ff41;font-size:12px;font-family:'Courier New',monospace;white-space:pre-wrap;word-break:break-all;line-height:1.5;">{truncated_payload}</pre>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:24px 40px;text-align:center;background:#0a0a0a;border-radius:0 0 12px 12px;border-top:1px solid #333333;">
                            <p style="color:#666666;font-size:12px;margin:0;">请登录系统查看详细信息并采取进一步措施</p>
                            <p style="color:#444444;font-size:11px;margin:8px 0 0 0;">此邮件由 AI-CyberSentinel 系统自动发送</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""  # noqa: E501

    message = MessageSchema(
        subject=f"【{risk_label}】AI-CyberSentinel 安全警报 - {status_text}",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )
    await fm.send_message(message)


async def send_login_notification(
    email: str,
    ip_address: str,
    user_agent: str,
    location: str = "未知位置",
    timestamp: str = "",
) -> None:
    conf = get_mail_config()
    fm = FastMail(conf)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>账户登录通知</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f4f4f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
            <td align="center" style="padding:40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding:48px 40px 32px;text-align:center;background:linear-gradient(135deg,#16a34a 0%,#15803d 100%);border-radius:12px 12px 0 0;">
                            <h1 style="color:#ffffff;margin:0;font-size:28px;font-weight:700;letter-spacing:-0.5px;">AI-CyberSentinel</h1>
                            <p style="color:rgba(255,255,255,0.9);margin:8px 0 0 0;font-size:14px;">智能入侵检测系统</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:40px;">
                            <div style="background:#fef2f2;border-radius:8px;padding:20px;margin-bottom:24px;border-left:4px solid #dc2626;">
                                <h2 style="color:#dc2626;margin:0 0 8px 0;font-size:18px;font-weight:700;">⚠️ 新设备登录提醒</h2>
                                <p style="color:#991b1b;font-size:14px;margin:0;">我们检测到您的账户在新设备上登录。如果这不是您本人的操作，请立即修改密码并联系管理员。</p>
                            </div>

                            <h3 style="color:#1f2937;margin:0 0 16px 0;font-size:16px;font-weight:600;">登录信息</h3>
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:24px;">
                                <tr>
                                    <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:14px;">登录时间</td>
                                    <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#1f2937;font-size:14px;text-align:right;font-family:'Courier New',monospace;">{timestamp or now}</td>
                                </tr>
                                <tr>
                                    <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:14px;">IP 地址</td>
                                    <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#1f2937;font-size:14px;text-align:right;font-family:'Courier New',monospace;">{html.escape(ip_address)}</td>
                                </tr>
                                <tr>
                                    <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:14px;">地理位置</td>
                                    <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;color:#1f2937;font-size:14px;text-align:right;">{html.escape(location)}</td>
                                </tr>
                                <tr>
                                    <td style="padding:12px 0;color:#6b7280;font-size:14px;">设备信息</td>
                                    <td style="padding:12px 0;color:#1f2937;font-size:14px;text-align:right;word-break:break-all;">{html.escape(user_agent[:100])}</td>
                                </tr>
                            </table>

                            <div style="background:#f9fafb;border-radius:8px;padding:16px;">
                                <p style="color:#374151;font-size:14px;margin:0 0 8px 0;font-weight:600;">建议操作：</p>
                                <ul style="margin:0;padding-left:20px;color:#6b7280;font-size:14px;line-height:1.8;">
                                    <li>如果不是您本人的操作，请立即修改密码</li>
                                    <li>启用双因素认证 (2FA) 提高账户安全</li>
                                    <li>检查最近的登录记录，确保没有异常活动</li>
                                </ul>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:24px 40px;text-align:center;background:#f9fafb;border-radius:0 0 12px 12px;border-top:1px solid #e5e7eb;">
                            <p style="color:#9ca3af;font-size:12px;margin:0;">此邮件由 AI-CyberSentinel 系统自动发送</p>
                            <p style="color:#d1d5db;font-size:11px;margin:8px 0 0 0;">请勿回复此邮件</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""  # noqa: E501

    message = MessageSchema(
        subject="【安全提醒】AI-CyberSentinel 账户新设备登录",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )
    await fm.send_message(message)
