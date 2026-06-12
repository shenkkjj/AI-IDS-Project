"""Prometheus 指标端点 (P2-B hardening).

公开 ``GET /metrics`` 端点,以 Prometheus text 格式 0.0.4 输出
护栏层的 ``guardrail_checks_total{scope,layer,status}`` 计数器。

注意:本端点**无需鉴权**,假定由内网 Prometheus / 在反向代理后访问。
如暴露在公网,应通过 nginx ``location /metrics { allow 10.0.0.0/8; deny all; }``
或 FastAPI middleware 加白名单 IP。
"""
from __future__ import annotations

from typing import Iterable

from fastapi import APIRouter, Response

from server.security.llm_guardrails.audit import iter_metrics


router = APIRouter(prefix="/metrics", tags=["监控"])


def _escape_label_value(value: str) -> str:
    """Escape per Prometheus exposition format: `\\`, `"`, `\n`."""
    return (
        value.replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
    )


def _format_counter(
    metric_name: str,
    help_text: str,
    rows: Iterable[tuple[str, str, str, int]],
) -> list[str]:
    """Render a labelled counter in Prometheus text format."""
    lines: list[str] = [
        f"# HELP {metric_name} {help_text}",
        f"# TYPE {metric_name} counter",
    ]
    rows = list(rows)
    if not rows:
        # Emit a zero-valued sample so dashboards never see a missing series.
        lines.append(f'{metric_name}{{scope="none",layer="none",status="none"}} 0')
        return lines
    for scope, layer, status, n in rows:
        labels = (
            f'scope="{_escape_label_value(scope)}",'
            f'layer="{_escape_label_value(layer)}",'
            f'status="{_escape_label_value(status)}"'
        )
        lines.append(f"{metric_name}{{{labels}}} {int(n)}")
    return lines


@router.get("", response_class=Response)
async def prometheus_metrics() -> Response:
    """Expose guardrail metrics in Prometheus exposition format.

    P2-B fix: the previous version of the SOC dashboard had to call
    ``/api/llm-guardrails/stats`` and parse a hand-rolled JSON. Operators
    asked for native Prometheus scraping so the same time series can feed
    both Grafana and the existing alert rules.
    """
    rows = iter_metrics(hours=24)
    body = "\n".join(
        _format_counter(
            "guardrail_checks_total",
            "Total guardrail decisions in the last 24h, "
            "broken down by scope, layer, and status.",
            rows,
        )
    )
    return Response(
        content=body + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
