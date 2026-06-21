"use client";

import { useCallback, useState } from "react";
import type {
  IncidentCreateResponse,
  IncidentDetailResponse,
  IncidentEvent,
  IncidentLinkResponse,
  IncidentListResponse,
  IncidentReportMeta,
  IncidentSeverity,
  IncidentStatus,
  IncidentSummary,
  IncidentUnlinkResponse,
  IncidentUpdateResponse,
} from "@/types/incident";

/**
 * 安全事件 / 案件 hook (M3-04)。
 *
 * 设计要点:
 * - 全部走 ``/api/backend/incidents...`` 代理(已支持 PATCH/DELETE)。
 * - 错误态返回 ``{ ok: false, error }`` 由 UI 自行展示;
 *   不抛 raw exception,避免污染调用方。
 * - 维护 ``incidentItems`` / ``selectedIncident`` / ``detailState`` / ``actionState`` /
 *   ``error`` 状态机。
 * - 默认 ``limit=50``,与后端契约一致。
 */
export function useIncidents() {
  const [incidentItems, setIncidentItems] = useState<IncidentSummary[]>([]);
  const [loadState, setLoadState] = useState<
    "idle" | "loading" | "ready" | "empty" | "error"
  >("idle");
  const [selectedIncident, setSelectedIncident] = useState<IncidentSummary | null>(
    null
  );
  const [detailState, setDetailState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [detail, setDetail] = useState<IncidentDetailResponse | null>(null);
  const [actionState, setActionState] = useState<"idle" | "saving" | "error">(
    "idle"
  );
  const [error, setError] = useState<string | null>(null);

  /** 读取当前用户的 incident 列表。 */
  const loadIncidents = useCallback(
    async (options?: {
      limit?: number;
      status?: IncidentStatus | null;
      signal?: AbortSignal;
    }): Promise<{ ok: boolean; items?: IncidentSummary[]; error?: string }> => {
      setLoadState("loading");
      setError(null);
      const limit = options?.limit ?? 50;
      const params = new URLSearchParams({ limit: String(limit) });
      if (options?.status) params.set("status", options.status);
      try {
        const response = await fetch(`/api/backend/incidents?${params.toString()}`, {
          credentials: "include",
          cache: "no-store",
          signal: options?.signal,
        });
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          setError(message);
          setLoadState("error");
          return { ok: false, error: message };
        }
        const body = (await response.json().catch(() => ({}))) as Partial<
          IncidentListResponse
        >;
        const items = Array.isArray(body.items) ? body.items : [];
        setIncidentItems(items);
        setLoadState(items.length === 0 ? "empty" : "ready");
        return { ok: true, items };
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return { ok: false, error: "已取消" };
        }
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        setLoadState("error");
        return { ok: false, error: message };
      }
    },
    []
  );

  /** 从当前选中告警创建 incident(可选携带 alert_id 自动 link)。 */
  const createIncidentFromAlert = useCallback(
    async (input: {
      title: string;
      summary?: string | null;
      severity: IncidentSeverity;
      alert_id?: string | null;
    }): Promise<{
      ok: boolean;
      incident?: IncidentSummary;
      error?: string;
    }> => {
      setActionState("saving");
      setError(null);
      try {
        const response = await fetch("/api/backend/incidents", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: input.title,
            summary: input.summary ?? null,
            severity: input.severity,
            alert_id: input.alert_id ?? null,
          }),
          cache: "no-store",
        });
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          setError(message);
          setActionState("error");
          return { ok: false, error: message };
        }
        const body = (await response.json().catch(() => ({}))) as Partial<
          IncidentCreateResponse
        >;
        if (body.status !== "ok" || !body.incident) {
          setActionState("error");
          return { ok: false, error: "创建成功但响应缺少 incident" };
        }
        // 乐观更新列表
        setIncidentItems((prev) => [body.incident!, ...prev]);
        setSelectedIncident(body.incident);
        setActionState("idle");
        return { ok: true, incident: body.incident };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        setActionState("error");
        return { ok: false, error: message };
      }
    },
    []
  );

  /** 加载 incident 完整 detail(linked_alerts + events)。 */
  const loadIncidentDetail = useCallback(
    async (
      incidentId: string,
      options?: { eventLimit?: number; signal?: AbortSignal }
    ): Promise<{
      ok: boolean;
      detail?: IncidentDetailResponse;
      error?: string;
    }> => {
      setDetailState("loading");
      setError(null);
      const eventLimit = options?.eventLimit ?? 20;
      try {
        const response = await fetch(
          `/api/backend/incidents/${encodeURIComponent(incidentId)}?event_limit=${eventLimit}`,
          {
            credentials: "include",
            cache: "no-store",
            signal: options?.signal,
          }
        );
        if (response.status === 404) {
          setDetailState("error");
          setError("案件不存在");
          return { ok: false, error: "案件不存在" };
        }
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          setError(message);
          setDetailState("error");
          return { ok: false, error: message };
        }
        const body = (await response.json().catch(() => ({}))) as Partial<
          IncidentDetailResponse
        >;
        if (body.status !== "ok" || !body.incident) {
          setDetailState("error");
          return { ok: false, error: "响应缺少 incident" };
        }
        setDetail(body as IncidentDetailResponse);
        setDetailState("ready");
        setSelectedIncident(body.incident);
        return { ok: true, detail: body as IncidentDetailResponse };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        setDetailState("error");
        return { ok: false, error: message };
      }
    },
    []
  );

  /** 更新 incident 字段。 */
  const updateIncident = useCallback(
    async (
      incidentId: string,
      input: {
        status?: IncidentStatus | null;
        severity?: IncidentSeverity | null;
        title?: string | null;
        summary?: string | null;
        note?: string | null;
      }
    ): Promise<{
      ok: boolean;
      incident?: IncidentSummary;
      events?: IncidentEvent[];
      error?: string;
    }> => {
      setActionState("saving");
      setError(null);
      try {
        const body: Record<string, unknown> = {};
        if (input.status !== undefined && input.status !== null)
          body.status = input.status;
        if (input.severity !== undefined && input.severity !== null)
          body.severity = input.severity;
        if (input.title !== undefined && input.title !== null)
          body.title = input.title;
        if (input.summary !== undefined && input.summary !== null)
          body.summary = input.summary;
        if (input.note !== undefined && input.note !== null && input.note !== "")
          body.note = input.note;

        const response = await fetch(
          `/api/backend/incidents/${encodeURIComponent(incidentId)}`,
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            cache: "no-store",
          }
        );
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          setError(message);
          setActionState("error");
          return { ok: false, error: message };
        }
        const respBody = (await response.json().catch(() => ({}))) as Partial<
          IncidentUpdateResponse
        >;
        if (respBody.status !== "ok" || !respBody.incident) {
          setActionState("error");
          return { ok: false, error: "响应缺少 incident" };
        }
        // 同步列表
        setIncidentItems((prev) =>
          prev.map((item) =>
            item.incident_id === respBody.incident!.incident_id
              ? respBody.incident!
              : item
          )
        );
        setSelectedIncident(respBody.incident);
        setActionState("idle");
        return {
          ok: true,
          incident: respBody.incident,
          events: respBody.events ?? [],
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        setActionState("error");
        return { ok: false, error: message };
      }
    },
    []
  );

  /** 把 alert 加入 incident(重复 link 幂等)。 */
  const linkAlert = useCallback(
    async (
      incidentId: string,
      alertId: string
    ): Promise<{
      ok: boolean;
      alertCount?: number;
      idempotent?: boolean;
      error?: string;
    }> => {
      setActionState("saving");
      setError(null);
      try {
        const response = await fetch(
          `/api/backend/incidents/${encodeURIComponent(incidentId)}/alerts`,
          {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ alert_id: alertId }),
            cache: "no-store",
          }
        );
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          setError(message);
          setActionState("error");
          return { ok: false, error: message };
        }
        const body = (await response.json().catch(() => ({}))) as Partial<
          IncidentLinkResponse
        >;
        if (body.status !== "ok") {
          setActionState("error");
          return { ok: false, error: "响应缺少 status" };
        }
        // 同步 selected + 列表中的 alert_count
        const updated = body.incident;
        if (updated) {
          setSelectedIncident(updated);
          setIncidentItems((prev) =>
            prev.map((item) =>
              item.incident_id === updated.incident_id ? updated : item
            )
          );
        }
        setActionState("idle");
        return {
          ok: true,
          alertCount: body.alert_count,
          idempotent: body.idempotent ?? false,
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        setActionState("error");
        return { ok: false, error: message };
      }
    },
    []
  );

  /** 把 alert 从 incident 移出(软删除 link)。 */
  const unlinkAlert = useCallback(
    async (
      incidentId: string,
      alertId: string
    ): Promise<{ ok: boolean; alertCount?: number; error?: string }> => {
      setActionState("saving");
      setError(null);
      try {
        const response = await fetch(
          `/api/backend/incidents/${encodeURIComponent(
            incidentId
          )}/alerts/${encodeURIComponent(alertId)}`,
          {
            method: "DELETE",
            credentials: "include",
            cache: "no-store",
          }
        );
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          setError(message);
          setActionState("error");
          return { ok: false, error: message };
        }
        const body = (await response.json().catch(() => ({}))) as Partial<
          IncidentUnlinkResponse
        >;
        if (body.status !== "ok") {
          setActionState("error");
          return { ok: false, error: "响应缺少 status" };
        }
        const updated = body.incident;
        if (updated) {
          setSelectedIncident(updated);
          setIncidentItems((prev) =>
            prev.map((item) =>
              item.incident_id === updated.incident_id ? updated : item
            )
          );
        }
        setActionState("idle");
        return { ok: true, alertCount: body.alert_count };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        setActionState("error");
        return { ok: false, error: message };
      }
    },
    []
  );

  /**
   * M3-07: 拉取案件证据报告(Markdown),不保存到本地长期 state。
   * 不消费 payload / note 全文,只把后端脱敏后的 markdown 字符串交给调用方
   * (复制 / 下载);按按钮触发,避免大字符串滞留。
   */
  const loadIncidentReport = useCallback(
    async (
      incidentId: string,
      options?: { signal?: AbortSignal }
    ): Promise<{
      ok: boolean;
      incidentId?: string;
      filename?: string;
      markdown?: string;
      meta?: IncidentReportMeta;
      error?: string;
    }> => {
      try {
        const response = await fetch(
          `/api/backend/incidents/${encodeURIComponent(incidentId)}/report?format=json`,
          {
            credentials: "include",
            cache: "no-store",
            signal: options?.signal,
          }
        );
        if (response.status === 404) {
          return { ok: false, error: "案件不存在" };
        }
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          const message = payload.detail || `HTTP ${response.status}`;
          return { ok: false, error: message };
        }
        const body = (await response.json().catch(() => ({}))) as {
          status?: string;
          incident_id?: string;
          filename?: string;
          markdown?: string;
          meta?: IncidentReportMeta;
        };
        if (
          body.status !== "ok" ||
          typeof body.markdown !== "string" ||
          typeof body.filename !== "string" ||
          !body.meta
        ) {
          return { ok: false, error: "响应缺少报告字段" };
        }
        return {
          ok: true,
          incidentId: body.incident_id,
          filename: body.filename,
          markdown: body.markdown,
          meta: body.meta,
        };
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return { ok: false, error: "已取消" };
        }
        const message = err instanceof Error ? err.message : String(err);
        return { ok: false, error: message };
      }
    },
    []
  );

  /** M3-19: 前端复合筛选(active / closed)聚合后替换当前列表。 */
  const replaceIncidentItems = useCallback((items: IncidentSummary[]) => {
    setIncidentItems(items);
    setLoadState(items.length === 0 ? "empty" : "ready");
  }, []);

  /** M3-19: 筛选切换后清理不在当前列表中的 stale detail。 */
  const clearSelectedIncident = useCallback(() => {
    setSelectedIncident(null);
    setDetail(null);
    setDetailState("idle");
  }, []);

  return {
    // 状态
    incidentItems,
    loadState,
    selectedIncident,
    detailState,
    detail,
    actionState,
    error,
    // 操作
    loadIncidents,
    createIncidentFromAlert,
    loadIncidentDetail,
    updateIncident,
    linkAlert,
    unlinkAlert,
    loadIncidentReport,
    replaceIncidentItems,
    clearSelectedIncident,
    setSelectedIncident,
  };
}

/**
 * M3-09: useIncidents() 的返回类型,供 dashboard-client.tsx 父层创建实例后,
 * 通过 props 传给 IncidentSection,让案件列表 / selected / detail / 报告导出
 * 共享同一份 state,避免双 hook race(必须点击列表项才能拿到 detail)。
 */
export type IncidentsController = ReturnType<typeof useIncidents>;
