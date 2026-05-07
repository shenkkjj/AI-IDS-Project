export { parseRisk, mapBackendAlert, classifyAttack, formatTimestamp, formatLoadError } from "./alertUtils";
export { parseSseBuffer, parseSseJson } from "./sseUtils";
export { buildReportMarkdown, listToMarkdownLines, REPORT_LATEST_ALERTS_LIMIT } from "./reportUtils";
export { runTerminalCommand, buildTerminalBootstrapLines, formatTerminalLine } from "./terminalUtils";
export { mapSiteHealthToUptime, inferProxyPath } from "./siteUtils";
export { routeDescription } from "./routeUtils";

export async function fetchWithRetry(url: string, options?: RequestInit & { retries?: number }): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  };
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  return response;
}
