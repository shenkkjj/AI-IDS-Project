"use client";

import { Button } from "@/components/ui/button";
import {
  FieldLabel,
  SelectInput,
  TextInput,
} from "@/components/dashboard/DashboardFields";
import { ChannelRow } from "@/components/dashboard/DashboardRows";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { ConfigDraft, PersistedUserConfig } from "@/types/config";

export interface DashboardWebhookSectionProps {
  draft: ConfigDraft;
  config: PersistedUserConfig | null;
  saving: boolean;
  refreshing: boolean;
  webhookTesting: boolean;
  onChangeDraft: React.Dispatch<React.SetStateAction<ConfigDraft>>;
  onSaveConfig: () => void;
  onTestWebhook: () => void;
}

export default function DashboardWebhookSection({
  draft,
  config,
  saving,
  refreshing,
  webhookTesting,
  onChangeDraft,
  onSaveConfig,
  onTestWebhook,
}: DashboardWebhookSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-webhook">
      <SectionHeading
        index="§ 06"
        title="Webhook 通知与渠道状态"
        description="高危告警触发时自动推送到外部通道"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-5">
          <div>
            <FieldLabel>类型</FieldLabel>
            <SelectInput
              value={draft.webhook_type}
              onChange={(event) =>
                onChangeDraft((prev) => ({
                  ...prev,
                  webhook_type: event.target.value,
                }))
              }
              disabled={saving || refreshing}
            >
              <option value="generic">通用 Webhook (JSON)</option>
              <option value="dingtalk">钉钉机器人 (Markdown)</option>
              <option value="feishu">飞书机器人 (Interactive Card)</option>
            </SelectInput>
          </div>
          <div>
            <FieldLabel>URL</FieldLabel>
            <TextInput
              autoComplete="off"
              value={draft.webhook_url}
              onChange={(event) =>
                onChangeDraft((prev) => ({
                  ...prev,
                  webhook_url: event.target.value,
                }))
              }
              placeholder="https://oapi.dingtalk.com/robot/ send?access_token=…"
              disabled={saving || refreshing}
            />
            <div className="text-[10px] font-mono text-ink-tertiary mt-1.5 break-all">
              当前:
              {config?.webhook_url
                ? `${config.webhook_type} · ${config.webhook_url.slice(0, 60)}`
                : "未配置"}
            </div>
          </div>
          <div className="flex gap-2 flex-wrap pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onSaveConfig}
              disabled={saving || refreshing || webhookTesting}
            >
              {saving ? "保存中..." : "保存"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onTestWebhook}
              disabled={saving || refreshing || webhookTesting}
            >
              {webhookTesting ? "测试中..." : "发送测试"}
            </Button>
          </div>
        </div>

        <div className="space-y-5">
          <FieldLabel>通知渠道状态</FieldLabel>
          <div className="divide-y divide-line-subtle">
            <ChannelRow
              label="邮件告警"
              enabled={Boolean(config?.alert_email_enabled)}
            />
            <ChannelRow
              label="语音预警"
              enabled={Boolean(config?.alert_voice_enabled)}
            />
            <ChannelRow
              label="Webhook"
              enabled={Boolean(config?.webhook_url)}
              customText={config?.webhook_url ? "已配置" : "未配置"}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
