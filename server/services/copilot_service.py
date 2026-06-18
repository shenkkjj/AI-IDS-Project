import json
from typing import Any, AsyncIterator

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from server.analyzer import AnalyzerConfig
from server.core.config import COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX
from server.core.database import create_log
from server.core.llm_utils import user_config_to_llm_runtime
from server.core.state import app_state
from server.models.schemas import CopilotMessageIn, CopilotStreamIn
from server.models_db import User
from server.security.llm_guardrails import guard_input, guard_output
from server.security.llm_guardrails.audit import log_guardrail_event
from server.security.llm_guardrails.exceptions import GuardrailViolation
from server.services import incident_service
from server.services.llm_providers import (
    resolve_provider,
    sse_done,
    sse_error,
    stream_completion,
)


# ---------------------------------------------------------------------------
# context builder 常量
# ---------------------------------------------------------------------------

# M3-05: incident context 截断与限制。
_INCIDENT_SUMMARY_MAX = 500
_ALERT_SUMMARY_MAX = 160
_INCIDENT_CONTEXT_ALERT_LIMIT = 5
_INCIDENT_CONTEXT_EVENT_LIMIT = 5
# user-visible 错误:不区分"不存在"和"非 owner",不暴露 incident_id。
_INCIDENT_NOT_FOUND_SSE_ERROR = "案件上下文不可用或不存在"


def _truncate_context_value(value: Any, max_chars: int) -> str:
    """截断 context value;``None`` 返回空串。供 ``_build_context_from_incident`` 使用。"""
    if value is None:
        return ""
    text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


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


def _build_context_from_incident(
    detail: dict[str, Any] | None,
    *,
    selected_alert_id: str | None = None,
) -> str:
    """从 ``incident_service.get_incident_detail`` 返回值构造受控 context_block。

    设计要点(``docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md`` §4.2):

    - 最多 5 条 linked_alerts + 5 条 events。
    - incident summary 截断 500 字符;alert summary 截断 160 字符。
    - event note **不**进 context,只放 ``note_length``。
    - alert payload **不**进 context,只放 ``payload_length``。
    - 不放 secret / system prompt / stack trace / regex。
    - 不放完整 note / title 全文(由 audit log / owner API 私有返回)。
    """
    if not detail:
        return ""

    inc = detail.get("incident") or {}
    linked_alerts = (detail.get("linked_alerts") or [])[:_INCIDENT_CONTEXT_ALERT_LIMIT]
    events = (detail.get("events") or [])[:_INCIDENT_CONTEXT_EVENT_LIMIT]

    lines: list[str] = ["[当前安全案件上下文]"]
    lines.append(f"incident_id: {inc.get('incident_id', '')}")
    title = _truncate_context_value(inc.get('title'), _INCIDENT_SUMMARY_MAX)
    if title:
        lines.append(f"title: {title}")
    lines.append(f"severity: {inc.get('severity', '')}")
    lines.append(f"status: {inc.get('status', '')}")
    lines.append(f"alert_count: {inc.get('alert_count', 0)}")
    if selected_alert_id:
        # alert_id + incident_id 同时存在时,只把 alert_id 视为 selected 标记;
        # 不重复读 alert payload。
        lines.append(f"selected_alert_id: {selected_alert_id}")
    summary = _truncate_context_value(inc.get('summary'), _INCIDENT_SUMMARY_MAX)
    if summary:
        lines.append(f"summary: {summary}")

    lines.append("")
    lines.append("[关联告警摘要]")
    if not linked_alerts:
        lines.append("- (无)")
    else:
        for a in linked_alerts:
            alert_id = a.get("alert_id", "")
            raw = a.get("raw_alert") or {}
            llm = a.get("llm_analysis") or {}
            src = raw.get("source_ip", "?")
            dst = raw.get("destination_ip", "?")
            risk = llm.get("risk_level", "unknown")
            blocked = raw.get("blocked", False)
            payload_length = len(str(raw.get("payload", "") or ""))
            alert_summary = _truncate_context_value(llm.get("summary"), _ALERT_SUMMARY_MAX)
            lines.append(
                f"- alert_id={alert_id} source={src} destination={dst} "
                f"risk={risk} blocked={blocked} payload_length={payload_length} "
                f"summary={alert_summary}"
            )

    lines.append("")
    lines.append("[案件事件摘要]")
    if not events:
        lines.append("- (无)")
    else:
        for e in events:
            event_type = e.get("event_type", "")
            from_status = e.get("from_status") or ""
            to_status = e.get("to_status") or ""
            note = e.get("note")
            note_length = len(note) if note else 0
            detail_text = _truncate_context_value(
                e.get("detail"), _ALERT_SUMMARY_MAX
            )
            created_at = e.get("created_at", 0)
            # 注意:不放 note 全文;detail 仅限事件元数据(状态切换 / severity 等
            # 短摘要),并走 160 字符截断。secret / 完整 payload / stack trace
            # 不应进入 detail(由 incident_service.update_incident 写入时约束)。
            lines.append(
                f"- event_type={event_type} from={from_status} to={to_status} "
                f"note_length={note_length} detail={detail_text} "
                f"created_at={created_at}"
            )

    lines.append("")
    lines.append("请基于该安全案件给出专业安全分析和可执行防御建议，优先给出立即动作。")
    return "\n".join(lines)


def _load_incident_context(
    db: Session, user: User, incident_id: str
) -> dict[str, Any] | None:
    """owner-隔离加载 incident context(``event_limit=5``)。

    - 走 ``incident_service.get_incident_detail``(M3-04 owner 隔离路径)。
    - 非 owner / 不存在统一返回 ``None``,**不**区分。
    - 路由层不需关心 404 / 403 区分,直接映射 SSE error。
    """
    return incident_service.get_incident_detail(
        db, int(user.id), str(incident_id), event_limit=_INCIDENT_CONTEXT_EVENT_LIMIT
    )


async def stream_user_chat_completion(
    *,
    runtime: AnalyzerConfig,
    provider: str,
    user_message: str,
    context_block: str,
    history: list[CopilotMessageIn],
) -> AsyncIterator[str]:
    """Stream a chat completion from the chosen LLM provider.

    Dispatches to the provider strategy in `server.services.llm_providers`.
    New providers can be added without touching this function.
    """
    if not runtime.api_key or not runtime.base_url:
        yield sse_error("请先在配置页设置可用的 API Key 与 Base URL")
        return

    strategy = resolve_provider(provider)
    try:
        async for token in stream_completion(
            strategy,
            runtime,
            user_message=user_message,
            context_block=context_block,
            history=history,
        ):
            yield token
        yield sse_done(provider, runtime.model)
    except Exception as exc:
        logger.exception(
            "copilot stream failed provider={} model={} err_type={}",
            provider, runtime.model, type(exc).__name__,
        )
        yield sse_error("AI 服务暂时不可用，请稍后重试")


async def copilot_stream(user: User, data: CopilotStreamIn, client_ip: str, db: Session) -> AsyncIterator[str]:
    async with app_state.rate_limit.copilot_lock:
        if not app_state.rate_limit._check_rate_limit(app_state.rate_limit.copilot_attempts, client_ip, COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX):  # noqa: E501
            raise HTTPException(status_code=429, detail="Copilot请求过于频繁，请1分钟后再试")

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    runtime, provider = user_config_to_llm_runtime(config, user)

    # ---- context lookup(incident 优先;alert_id 作为 selected_alert_id) ----
    # 推荐顺序:rate limit -> user config -> context lookup -> Guardrails input
    # -> create_log -> provider stream。incident path 不能绕过 Guardrails;
    # context lookup 失败先于 Guardrails 返回,以保护"不区分不存在/非 owner"。
    context_block = ""
    if data.incident_id:
        detail = _load_incident_context(db, user, str(data.incident_id))
        if detail is None:
            yield sse_error(_INCIDENT_NOT_FOUND_SSE_ERROR)
            return
        selected_alert_id = (
            str(data.alert_id).strip() if data.alert_id else None
        )
        context_block = _build_context_from_incident(
            detail, selected_alert_id=selected_alert_id
        )
    elif data.alert_id:
        from server.services.alert_service import find_alert_by_id
        alert = await find_alert_by_id(str(data.alert_id).strip(), user_id=user.id)
        context_block = _build_context_from_alert(alert)

    # LLM Guardrails: input rail. Runs BEFORE the LLM is invoked so a
    # jailbreak / prompt-injection attempt is caught with zero cost.
    try:
        from server.security.llm_guardrails.core import GuardrailEngine

        reason = await GuardrailEngine.instance().check_input(
            scope="copilot",
            message=str(data.message).strip(),
            history=[{"role": m.role, "content": m.content} for m in (data.history or [])],
        )
        if reason:
            # The full reason (including the matched L1 regex) goes ONLY
            # to the audit log. The user-facing SSE error shows only the
            # category, so an attacker probing the endpoint cannot learn
            # the exact regex (security review SC-2).
            category = reason.split(" ", 1)[0] if reason else "policy_violation"
            log_guardrail_event(
                scope="copilot", layer="input", status="blocked",
                reason=reason[:200], user_id=user.id,
            )
            yield sse_error(
                f"请求被安全护栏拦截(类别: {category})。"
                f"如需协助请改写请求,或联系管理员。"
            )
            return
        log_guardrail_event(
            scope="copilot", layer="input", status="passed", reason="",
            user_id=user.id,
        )
    except Exception as exc:  # noqa: BLE001
        # Guardrail 异常绝不能阻断用户请求 —— 记录 warning 后继续
        logger.warning("copilot guardrail input check failed err={}", exc)
        log_guardrail_event(
            scope="copilot", layer="input", status="warning",
            reason=f"infrastructure_error:{type(exc).__name__}", user_id=user.id,
        )

    # ---- audit log:含 incident_id 维度;不写 title / summary / note / payload ----
    log_detail_parts = [
        f"provider={provider}",
        f"model={runtime.model}",
        f"alert_id={data.alert_id or ''}",
    ]
    if data.incident_id:
        log_detail_parts.append(f"incident_id={data.incident_id}")
    create_log(
        db,
        user_id=user.id,
        level="info",
        action="copilot_stream",
        detail=";".join(log_detail_parts),
    )

    async for chunk in stream_user_chat_completion(
        runtime=runtime,
        provider=provider,
        user_message=str(data.message).strip(),
        context_block=context_block,
        history=data.history,
    ):
        yield chunk
