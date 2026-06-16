"""AI-CyberSentinel 环境与启动安全检查脚本。

检测项（按严重程度分类输出）：

- ``[BLOCK]``  生产模式缺关键 secret / 弱 secret / 明文占位值 / 危险 CORS → 退出码 1。
- ``[WARN]``   建议项：metrics / MCP 暴露边界 / trusted hosts / 邮件服务配置 → 退出码 0。
- ``[INFO]``   本地开发提醒。
- ``[PASS]``   通过。

运行：

    ./.venv/Scripts/python.exe scripts/check_env_security.py

退出码：

- 0 = 通过或仅有 INFO/WARN。
- 1 = 存在至少一条 ``[BLOCK]``。

脚本只读取 ``.env`` 和 ``.env.example``，从不在终端打印真实密钥；任何
``value`` 都会按 ``key[:4] + "***"`` 形式脱敏输出。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

# ---------------------------------------------------------------------------
# Sentinel patterns (secrets that should never appear in a clean .env).
# ---------------------------------------------------------------------------
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI/DeepSeek API Key"),
    (r"sk-proj-[A-Za-z0-9_-]+", "OpenAI Project Key"),
    (r"(?:AKIA|ASIA)[A-Z0-9]{16}", "AWS Access Key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Token"),
    (r"xox[baprs]-[A-Za-z0-9-]+", "Slack Token"),
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    (r"PRIVATE\s+KEY", "Private Key"),
)

PLACEHOLDER_TOKENS: tuple[str, ...] = (
    "change-me",
    "your-key-here",
    "replace-me",
    "your-password",
    "your-token",
    "your-api-key",
    "todo",
    "sk-your-",
    "sk-placeholder",
    "xxxx",
)

# Production minimum-viable secret catalogue.
PROD_REQUIRED_SECRETS: tuple[tuple[str, int], ...] = (
    # (env var, min length)
    ("APP_SECRET", 32),
    ("AUTH_SECRET", 32),
    ("ALERTS_INGEST_TOKEN", 32),
)

PROD_RECOMMENDED_SECRETS: tuple[str, ...] = (
    "GUARDRAILS_MCP_API_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
)

DANGEROUS_LOCALHOST_CORS: tuple[str, ...] = (
    "http://localhost",
    "http://127.0.0.1",
)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    level: str  # BLOCK / WARN / INFO / PASS
    category: str
    message: str


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return value[:4] + "***"


def _print(findings: list[Finding]) -> None:
    counts = {"BLOCK": 0, "WARN": 0, "INFO": 0, "PASS": 0}
    for f in findings:
        counts[f.level] = counts.get(f.level, 0) + 1
        prefix = f"[{f.level}]"
        print(f"{prefix} {f.category}: {f.message}")
    print("-" * 60)
    print(
        f"  BLOCK={counts['BLOCK']}  WARN={counts['WARN']}  "
        f"INFO={counts['INFO']}  PASS={counts['PASS']}"
    )


# ---------------------------------------------------------------------------
# .env parsing
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_value(env_values: dict[str, str], key: str) -> str:
    """Resolve a key with priority: process env > .env file."""
    return os.environ.get(key) or env_values.get(key) or ""


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_gitignore() -> list[Finding]:
    findings: list[Finding] = []
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        findings.append(Finding("BLOCK", "gitignore", ".gitignore 不存在！"))
        return findings
    content = gitignore.read_text(encoding="utf-8")
    if ".env" not in content:
        findings.append(Finding("BLOCK", "gitignore", ".gitignore 未排除 .env"))
    else:
        findings.append(Finding("PASS", "gitignore", ".gitignore 已排除 .env"))
    if "htmlcov" not in content:
        findings.append(Finding("WARN", "gitignore", "建议在 .gitignore 添加 htmlcov/"))
    if "data/" not in content and "*.db" not in content:
        findings.append(Finding("WARN", "gitignore", "建议在 .gitignore 添加 data/ 或 *.db"))
    return findings


def check_env_in_git() -> list[Finding]:
    result = subprocess.run(
        ["git", "ls-files", ".env"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.stdout.strip():
        return [Finding("BLOCK", "env_in_git", ".env 已被 Git 追踪！立即运行 git rm --cached .env")]
    return [Finding("PASS", "env_in_git", ".env 未被 Git 追踪")]


def check_leaked_secrets(env_values: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    if not env_values:
        return [Finding("INFO", "env_file", ".env 不存在（从 .env.example 复制一份）")]
    leaked = False
    placeholders = []
    for key, value in env_values.items():
        if not value:
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, value):
                findings.append(
                    Finding(
                        "BLOCK",
                        "leaked_secret",
                        f"{key} 命中 {label}（mask: {_mask(value)}）",
                    )
                )
                leaked = True
        lower = value.lower()
        for token in PLACEHOLDER_TOKENS:
            if token in lower:
                placeholders.append(key)
                break
    if not leaked:
        findings.append(Finding("PASS", "leaked_secret", "未检测到高置信明文密钥"))
    if placeholders:
        unique = sorted(set(placeholders))
        findings.append(
            Finding(
                "INFO",
                "placeholder",
                f"以下变量仍使用占位值（生产前必须替换）：{', '.join(unique)}",
            )
        )
    return findings


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    lower = value.lower()
    return any(tok in lower for tok in PLACEHOLDER_TOKENS) or len(value) < 8


def check_required_secrets(env_values: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for key, min_len in PROD_REQUIRED_SECRETS:
        value = _resolve_value(env_values, key)
        if not value:
            findings.append(
                Finding(
                    "BLOCK",
                    "required_secret",
                    f"{key} 未设置（生产模式必填，最小长度 {min_len}）",
                )
            )
            continue
        if _is_placeholder(value):
            findings.append(
                Finding(
                    "BLOCK",
                    "required_secret",
                    f"{key} 仍是占位值或长度过短（mask: {_mask(value)}）",
                )
            )
            continue
        if len(value) < min_len:
            findings.append(
                Finding(
                    "BLOCK",
                    "required_secret",
                    f"{key} 长度 {len(value)} < {min_len}（mask: {_mask(value)}）",
                )
            )
            continue
        findings.append(Finding("PASS", "required_secret", f"{key} 已设置（长度 {len(value)}）"))
    for key in PROD_RECOMMENDED_SECRETS:
        value = _resolve_value(env_values, key)
        if not value:
            findings.append(
                Finding(
                    "WARN",
                    "recommended_secret",
                    f"{key} 未设置（生产模式建议设置）",
                )
            )
        elif _is_placeholder(value):
            findings.append(
                Finding(
                    "WARN",
                    "recommended_secret",
                    f"{key} 仍为占位值（生产前请替换）",
                )
            )
        else:
            findings.append(Finding("PASS", "recommended_secret", f"{key} 已设置"))
    return findings


def check_app_env_specific(env_values: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    app_env = (_resolve_value(env_values, "APP_ENV") or "development").lower()
    is_prod = app_env in {"production", "prod"}

    cors = _resolve_value(env_values, "CORS_ORIGINS")
    if is_prod and cors:
        for dangerous in DANGEROUS_LOCALHOST_CORS:
            if dangerous in cors:
                findings.append(
                    Finding(
                        "BLOCK",
                        "cors",
                        f"APP_ENV=production 但 CORS_ORIGINS 含 {dangerous}（生产模式不允许 localhost）",
                    )
                )
                break
        else:
            findings.append(Finding("PASS", "cors", "CORS_ORIGINS 不含 localhost"))
    elif is_prod and not cors:
        findings.append(Finding("BLOCK", "cors", "APP_ENV=production 但 CORS_ORIGINS 未设置"))
    else:
        findings.append(Finding("INFO", "cors", f"APP_ENV={app_env}，CORS localhost 允许"))

    dev_mode = _resolve_value(env_values, "DEV_MODE")
    if is_prod and dev_mode.lower() in {"true", "1", "yes"}:
        findings.append(
            Finding(
                "BLOCK",
                "dev_mode",
                "APP_ENV=production 时 DEV_MODE 必须关闭（当前为 true）",
            )
        )

    bind_host = _resolve_value(env_values, "BIND_HOST")
    if is_prod and bind_host in {"0.0.0.0", ""}:
        findings.append(
            Finding(
                "WARN",
                "bind_host",
                "BIND_HOST=0.0.0.0 在生产模式需配合反向代理 / 防火墙；当前未限制",
            )
        )

    return findings


def check_observability(env_values: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    is_prod = (_resolve_value(env_values, "APP_ENV") or "development").lower() in {
        "production",
        "prod",
    }

    metrics_token = _resolve_value(env_values, "METRICS_TOKEN")
    if is_prod and not metrics_token:
        findings.append(
            Finding(
                "WARN",
                "metrics",
                "生产模式建议设置 METRICS_TOKEN，/metrics 不应公网裸奔",
            )
        )
    else:
        findings.append(Finding("INFO", "metrics", "metrics 暴露边界需在 nginx 中 allowlist（参考 nginx.conf）"))

    mcp_key = _resolve_value(env_values, "GUARDRAILS_MCP_API_KEY")
    if is_prod and not mcp_key:
        findings.append(
            Finding(
                "BLOCK",
                "mcp_auth",
                "GUARDRAILS_MCP_API_KEY 未设置；/mcp 端点将 401 拒绝所有调用",
            )
        )
    elif mcp_key and _is_placeholder(mcp_key):
        findings.append(
            Finding(
                "BLOCK",
                "mcp_auth",
                "GUARDRAILS_MCP_API_KEY 仍为占位值",
            )
        )
    return findings


def check_optional_modules(env_values: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    nemo = _resolve_value(env_values, "NEMO_GUARDRAILS_ENABLED")
    if nemo.lower() in {"true", "1", "yes"}:
        findings.append(
            Finding(
                "INFO",
                "nemo",
                "NeMo Guardrails 启用中；确保 NEMO_GUARDRAILS_CONFIG_PATH 可达",
            )
        )
    else:
        findings.append(Finding("INFO", "nemo", "NeMo Guardrails 关闭，使用 L1+L4 兜底"))

    mail_user = _resolve_value(env_values, "MAIL_USERNAME")
    if mail_user and mail_user != "your-email@qq.com":
        findings.append(Finding("PASS", "mail", "邮件服务已配置"))
    elif not _resolve_value(env_values, "APP_ENV", ).lower().startswith("prod"):
        findings.append(Finding("INFO", "mail", "邮件服务未配置，OTP 登录会降级到 dev 模式输出验证码"))
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 60)
    print("  AI-CyberSentinel 环境与启动安全检查")
    print("=" * 60)

    env_values = _load_env_file(ENV_FILE)
    findings: list[Finding] = []
    findings.extend(check_gitignore())
    findings.extend(check_env_in_git())
    findings.extend(check_leaked_secrets(env_values))
    findings.extend(check_required_secrets(env_values))
    findings.extend(check_app_env_specific(env_values))
    findings.extend(check_observability(env_values))
    findings.extend(check_optional_modules(env_values))

    _print(findings)
    has_block = any(f.level == "BLOCK" for f in findings)
    print("=" * 60)
    if has_block:
        print("  [FAIL] 存在阻塞项，请修复后再部署生产")
        return 1
    print("  [OK]   未发现阻塞项；WARN/INFO 可在生产前再处理")
    return 0


if __name__ == "__main__":
    sys.exit(main())
