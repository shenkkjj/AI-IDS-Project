export interface PersistedUserConfig {
  ai_provider: string;
  model: string;
  base_url: string;
  timeout_seconds: number;
  alert_email_enabled: boolean;
  alert_voice_enabled: boolean;
  webhook_url: string;
  webhook_type: string;
  ui_theme: string;
  ui_density: string;
  has_api_key: boolean;
  api_key_masked: string;
}

export interface ConfigDraft {
  ai_provider: string;
  model: string;
  base_url: string;
  api_key: string;
  webhook_url: string;
  webhook_type: string;
}

export const WEBHOOK_TYPES = ["generic", "dingtalk", "feishu"] as const;
export type WebhookType = (typeof WEBHOOK_TYPES)[number];
