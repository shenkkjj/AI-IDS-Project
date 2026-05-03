import json
import os
import time
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

CLOUD_METADATA_HOSTS = frozenset({"metadata.google.internal", "169.254.169.254"})


def _is_ssrf_safe(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname.lower() in CLOUD_METADATA_HOSTS:
            return False
        try:
            addr = ip_address(hostname)
            if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_multicast:
                return False
            return True
        except ValueError:
            pass
        from server.core.utils import _is_url_pointing_to_internal
        return not _is_url_pointing_to_internal(url)
    except Exception:
        return False


SOC_SYSTEM_PROMPT = """
你是一名拥有15年以上实战经验的资深SOC（Security Operations Center）首席分析师，专长于网络入侵检测、威胁狩猎、溯源分析、ATT&CK战术映射和高压事件响应。

你的任务：对输入的可疑网络载荷（Payload）进行深入、可执行、可审计的安全分析，并输出结构化结论，支持一线分析员快速处置。

分析要求（必须覆盖）：
1) 攻击意图识别：判断这是扫描、凭据窃取、命令执行、漏洞利用、横向移动、数据渗漏、C2回连还是噪声误报。
2) IOC与可疑模式：提取IP、域名、URL路径、可疑参数、命令片段、编码痕迹（base64/hex/混淆）、凭据痕迹。
3) 技术与战术映射：尽可能映射MITRE ATT&CK战术/技术（例如 T1190、T1071、T1059 等），并给出置信度理由。
4) 危害评估：给出风险等级（low/medium/high/critical）与理由，描述潜在影响面。
5) 溯源线索：给出后续追踪方向（同源IP、同UA、同会话特征、时间窗口关联、资产关联）。
6) 处置建议：提供立即动作（分钟级）与短期动作（小时级）和长期加固建议。
7) 误报评估：若可能为正常业务流量，也要明确说明并给出验证办法。

输出格式要求：
- 只输出一个JSON对象，不要输出Markdown，不要输出额外解释。
- JSON字段必须包含：
  - summary: string
  - risk_level: "low" | "medium" | "high" | "critical"
  - confidence: number (0~1)
  - attack_intent: string
  - iocs: { ips: string[], domains: string[], urls: string[], commands: string[], keywords: string[] }
  - mitre_attack: [{ tactic: string, technique_id: string, technique_name: string, confidence: number }]
  - evidence: string[]
  - false_positive_analysis: string
  - immediate_actions: string[]
  - short_term_actions: string[]
  - long_term_hardening: string[]

质量标准：
- 结论必须与输入内容可追溯。
- 不允许编造无法从输入推出的确定性事实。
- 若证据不足，明确标注不确定性并给出下一步采集建议。
""".strip()


@dataclass(frozen=True)
class AnalyzerConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int


def build_chat_completions_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("Missing base URL.")

    if not _is_ssrf_safe(normalized):
        raise ValueError("Base URL resolves to an internal or restricted address.")

    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")

    if path.endswith("/chat/completions"):
        final_path = path
    elif path.endswith("/v1"):
        final_path = f"{path}/chat/completions"
    else:
        final_path = f"{path}/v1/chat/completions"

    return urlunsplit((parsed.scheme, parsed.netloc, final_path, parsed.query, parsed.fragment))


class LLMAnalyzer:
    def __init__(self, config: AnalyzerConfig | None = None) -> None:
        self.config = config or self._load_config()

    @staticmethod
    def _load_config() -> AnalyzerConfig:
        api_key = os.getenv("LLM_API_KEY", "").strip()
        base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
        model = os.getenv("LLM_MODEL", "").strip()
        timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))

        if not api_key or not base_url:
            raise ValueError("Missing LLM_API_KEY or LLM_BASE_URL environment variables.")

        return AnalyzerConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    def analyze_alert(self, source_ip: str, destination_ip: str, payload: str) -> dict[str, Any]:
        user_prompt = {
            "source_ip": source_ip,
            "destination_ip": destination_ip,
            "payload": payload,
        }

        request_body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SOC_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(user_prompt, ensure_ascii=False),
                },
            ],
            "temperature": 0.1,
        }

        response = requests.post(
            build_chat_completions_url(self.config.base_url),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()

        response_json = response.json()
        content = (
            response_json.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not content:
            raise ValueError("LLM response content is empty.")

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "summary": content,
                "risk_level": "medium",
                "confidence": 0.3,
                "attack_intent": "unknown",
                "iocs": {
                    "ips": [],
                    "domains": [],
                    "urls": [],
                    "commands": [],
                    "keywords": [],
                },
                "mitre_attack": [],
                "evidence": ["LLM returned non-JSON content, fallback applied."],
                "false_positive_analysis": "Need manual validation due to malformed LLM output.",
                "immediate_actions": ["Escalate to analyst for manual review."],
                "short_term_actions": ["Adjust prompt or model settings for JSON compliance."],
                "long_term_hardening": ["Enforce structured output with schema validation."],
            }

def test_llm_connection(config: AnalyzerConfig) -> dict[str, Any]:
    if not config.api_key or not config.base_url:
        raise ValueError("Missing API Key or Base URL.")

    started_at = time.time()
    response = requests.post(
        build_chat_completions_url(config.base_url),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.model,
            "messages": [{"role": "user", "content": "reply with pong"}],
            "temperature": 0,
            "max_tokens": 8,
        },
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()

    response_json = response.json()
    content = (
        response_json.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    latency_ms = int((time.time() - started_at) * 1000)

    return {
        "ok": True,
        "latency_ms": latency_ms,
        "reply": content,
        "model": config.model,
        "base_url": config.base_url,
    }

