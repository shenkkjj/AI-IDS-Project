export interface PersistedUserConfig {
  ai_provider: string;
  model: string;
  base_url: string;
  timeout_seconds: number;
  alert_email_enabled: boolean;
  alert_voice_enabled: boolean;
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
}
