# CyberSentinel .env 安全检测脚本
# 用法: python scripts/check_env_security.py

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

KEY_PATTERNS = [
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI/DeepSeek API Key"),
    (r"(?:AKIA|ASIA)[A-Z0-9]{16}", "AWS Access Key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Token"),
    (r"xox[baprs]-[A-Za-z0-9-]+", "Slack Token"),
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    (r"s3cr3t|password\s*=\s*(?![!\s]*$).+", "疑似明文密码"),
]

DEFAULT_PLACEHOLDERS = [
    "change-me", "your-key-here", "replace-me", "xxxx", "todo",
    "sk-your-", "sk-placeholder",
]


def check_gitignore() -> bool:
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        print("[FAIL] .gitignore 不存在!")
        return False
    content = gitignore.read_text(encoding="utf-8")
    if ".env" not in content:
        print("[FAIL] .gitignore 未排除 .env!")
        return False
    print("[PASS] .gitignore 已排除 .env")
    return True


def check_env_in_git() -> bool:
    import subprocess
    result = subprocess.run(
        ["git", "ls-files", ".env"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if result.stdout.strip():
        print("[FAIL] .env 已被 Git 追踪! 立即运行: git rm --cached .env")
        return False
    print("[PASS] .env 未被 Git 追踪")
    return True


def check_leaked_keys() -> bool:
    if not ENV_FILE.exists():
        print("[WARN] .env 文件不存在，从 .env.example 创建...")
        if ENV_EXAMPLE.exists():
            ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
            print("[INFO] .env 已创建，请编辑填入真实密钥")
        return True

    content = ENV_FILE.read_text(encoding="utf-8")
    found_any = False

    for line_no, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for pattern, label in KEY_PATTERNS:
            if re.search(pattern, line):
                masked = line[:20] + "***" if len(line) > 20 else line
                print(f"[SECRET] 第{line_no}行 检测到 {label}: {masked}")
                found_any = True

    if found_any:
        print("[WARN] 以上密钥已从 .env 读取，请确认它们不会被提交到 Git")
        print("[TIP]  .env 已被 .gitignore 排除，git 不会追踪此文件")
    else:
        print("[PASS] 未检测到明文密钥")

    for line_no, line in enumerate(content.splitlines(), 1):
        line_lower = line.lower()
        for placeholder in DEFAULT_PLACEHOLDERS:
            if placeholder in line_lower and "=" in line:
                key = line.split("=")[0].strip()
                print(f"[TODO] 第{line_no}行 {key} 使用占位值，需替换为真实密钥")

    return True


def main():
    print("=" * 50)
    print("  CyberSentinel .env 安全检测")
    print("=" * 50)
    ok = all([check_gitignore(), check_env_in_git(), check_leaked_keys()])
    print("=" * 50)
    if ok:
        print("  安全检测通过 ✅")
    else:
        print("  发现问题，请修复后重试 ❌")
    print("=" * 50)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
