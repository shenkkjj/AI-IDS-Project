"use client";

import { Button } from "@/components/ui/button";
import {
  FieldLabel,
  SelectInput,
  TextInput,
} from "@/components/dashboard/DashboardFields";
import { SessionRow } from "@/components/dashboard/DashboardRows";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { ConfigDraft, PersistedUserConfig } from "@/types/config";

const PROVIDERS = ["custom"] as const;

export interface DashboardAiConfigSectionProps {
  userEmail: string;
  draft: ConfigDraft;
  config: PersistedUserConfig | null;
  statusHint: string;
  wsConnected: boolean;
  totalAlerts: number;
  saving: boolean;
  testing: boolean;
  refreshing: boolean;
  onChangeDraft: React.Dispatch<React.SetStateAction<ConfigDraft>>;
  onSaveConfig: () => void;
  onTestConfig: () => void;
  onRefreshConfig: () => void;
}

export default function DashboardAiConfigSection({
  userEmail,
  draft,
  config,
  statusHint,
  wsConnected,
  totalAlerts,
  saving,
  testing,
  refreshing,
  onChangeDraft,
  onSaveConfig,
  onTestConfig,
  onRefreshConfig,
}: DashboardAiConfigSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-ai-config">
      <SectionHeading
        index="§ 05"
        title="AI 路由配置"
        description="自定义模型、API 密钥、会话上下文"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-5">
          <div>
            <FieldLabel>Provider</FieldLabel>
            <SelectInput
              value={draft.ai_provider}
              onChange={(event) =>
                onChangeDraft((prev) => ({ ...prev, ai_provider: event.target.value }))
              }
            >
              {PROVIDERS.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </SelectInput>
          </div>
          <div>
            <FieldLabel>Model</FieldLabel>
            <TextInput
              autoComplete="off"
              value={draft.model}
              onChange={(event) =>
                onChangeDraft((prev) => ({ ...prev, model: event.target.value }))
              }
              placeholder="gpt-4 / claude-3 ..."
            />
          </div>
          <div>
            <FieldLabel>Base URL</FieldLabel>
            <TextInput
              autoComplete="off"
              value={draft.base_url}
              onChange={(event) =>
                onChangeDraft((prev) => ({ ...prev, base_url: event.target.value }))
              }
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div>
            <FieldLabel>API Key</FieldLabel>
            <TextInput
              type="password"
              autoComplete="new-password"
              value={draft.api_key}
              onChange={(event) =>
                onChangeDraft((prev) => ({ ...prev, api_key: event.target.value }))
              }
              placeholder={
                config?.has_api_key
                  ? "已配置,留空表示不修改"
                  : "输入 API Key"
              }
            />
            <div className="text-[10px] font-mono text-ink-tertiary mt-1.5">
              当前:
              {config?.has_api_key
                ? config.api_key_masked
                : "未配置"}
            </div>
          </div>
          <div className="flex gap-2 flex-wrap pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onSaveConfig}
              disabled={saving || testing || refreshing}
            >
              {saving ? "保存中..." : "保存"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onTestConfig}
              disabled={saving || testing || refreshing}
            >
              {testing ? "测试中..." : "测试路由"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onRefreshConfig}
              disabled={saving || testing || refreshing}
            >
              {refreshing ? "同步中..." : "重新同步"}
            </Button>
          </div>
        </div>

        <div className="space-y-5">
          <FieldLabel>当前会话</FieldLabel>
          <div className="divide-y divide-line-subtle">
            <SessionRow label="用户" value={userEmail || "unknown"} />
            <SessionRow label="上下文" value={statusHint} />
            <SessionRow
              label="WS 连接"
              value={wsConnected ? "已连接" : "已断开"}
              tone={wsConnected ? "ok" : "error"}
            />
            <SessionRow
              label="告警总数"
              value={String(totalAlerts)}
              mono
            />
          </div>
        </div>
      </div>
    </div>
  );
}
