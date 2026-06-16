"use client";

import { Button } from "@/components/ui/button";

/**
 * § 04 站点监测与威胁确认 区块。
 *
 * 包含三列：
 *  - 站点监测：状态 / URL / 保存
 *  - 代理 WAF：路径 / 测试链路
 *  - 威胁确认：选中告警后入库 / 语音预警开关
 *
 * 不在内部发请求；事件向上抛。
 */

export interface SiteTargetState {
  text: string;
  tone: "online" | "warning" | "offline";
  url?: string;
}

export interface ThreatState {
  status: string;
  statusTone: "default" | "ok" | "error";
  confirming: boolean;
  voiceEnabled: boolean;
}

export interface SystemStatusSectionProps {
  siteTargetInput: string;
  onChangeTargetInput: (value: string) => void;
  onSaveTarget: () => void;
  targetSaving: boolean;
  siteState: SiteTargetState;
  proxyPathInput: string;
  onChangeProxyPath: (value: string) => void;
  onTestProxy: () => void;
  proxyTesting: boolean;
  threat: ThreatState;
  canConfirmThreat: boolean;
  onConfirmThreat: () => void;
  onToggleVoiceAlert: () => void;
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
      {children}
    </label>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary"
    />
  );
}

const TONE_CLASS: Record<SiteTargetState["tone"], string> = {
  online: "text-success",
  warning: "text-warning",
  offline: "text-danger",
};

export default function SystemStatusSection({
  siteTargetInput,
  onChangeTargetInput,
  onSaveTarget,
  targetSaving,
  siteState,
  proxyPathInput,
  onChangeProxyPath,
  onTestProxy,
  proxyTesting,
  threat,
  canConfirmThreat,
  onConfirmThreat,
  onToggleVoiceAlert,
}: SystemStatusSectionProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      {/* 站点监测 */}
      <div className="space-y-5">
        <div>
          <FieldLabel>站点状态</FieldLabel>
          <div
            data-testid="site-health-text"
            data-tone={siteState.tone}
            className={`text-2xl font-display ${TONE_CLASS[siteState.tone]}`}
          >
            {siteState.text}
          </div>
        </div>
        <div>
          <FieldLabel>目标 URL</FieldLabel>
          <TextInput
            value={siteTargetInput}
            onChange={(event) => onChangeTargetInput(event.target.value)}
            placeholder="https://example.com"
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onSaveTarget}
          disabled={targetSaving || !siteTargetInput.trim()}
          className="w-full"
        >
          {targetSaving ? "保存中..." : "保存目标"}
        </Button>
        <div className="text-[10px] font-mono text-ink-tertiary">
          {siteState.url ? `当前 · ${siteState.url}` : "未设置"}
        </div>
      </div>

      {/* 代理 WAF */}
      <div className="space-y-5">
        <FieldLabel>代理与 WAF</FieldLabel>
        <TextInput
          value={proxyPathInput}
          onChange={(event) => onChangeProxyPath(event.target.value)}
          placeholder="/"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={onTestProxy}
          disabled={proxyTesting}
          className="w-full"
        >
          {proxyTesting ? "测试中..." : "测试代理链路"}
        </Button>
        <div className="text-[10px] font-mono text-ink-tertiary leading-relaxed">
          路径支持 URL 或相对路径。
          <br />
          命中策略会返回 403。
        </div>
      </div>

      {/* 威胁确认 */}
      <div className="space-y-5">
        <FieldLabel>告警确认与语音</FieldLabel>
        <Button
          variant="outline"
          size="sm"
          onClick={onConfirmThreat}
          disabled={threat.confirming || !canConfirmThreat}
          className="w-full"
        >
          {threat.confirming ? "确认中..." : "确认威胁入库"}
        </Button>
        <div
          data-testid="threat-confirm-status"
          data-tone={threat.statusTone}
          className={`text-[11px] px-3 py-2.5 border-l-2 rounded-md ${
            threat.statusTone === "ok"
              ? "border-success text-success bg-success-soft"
              : threat.statusTone === "error"
                ? "border-danger text-danger bg-danger-soft"
                : "border-line text-ink-secondary bg-bg-sunken"
          }`}
        >
          {threat.status}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleVoiceAlert}
          className="w-full"
        >
          {threat.voiceEnabled ? "关闭语音预警" : "开启语音预警"}
        </Button>
      </div>
    </div>
  );
}
