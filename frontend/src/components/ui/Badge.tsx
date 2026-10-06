import type { ReactNode } from "react";
import type { Confidence, HealthStatus } from "../../types/api";

type Tone = "neutral" | "indigo" | "success" | "warning" | "danger";

const tones: Record<Tone, string> = {
  neutral: "bg-slate-100 text-ink-700",
  indigo: "bg-indigo-50 text-indigo-700",
  success: "bg-success-tint text-success-ink",
  warning: "bg-warning-tint text-warning-ink",
  danger: "bg-danger-tint text-danger-ink",
};

export function Badge({ tone = "neutral", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** Mono chip for IDs, signal names and event codes. */
export function Chip({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 font-mono text-xs text-indigo-700 ${className}`}>
      {children}
    </span>
  );
}

const CONF: Record<Confidence, { label: string; bars: number; fill: string }> = {
  high: { label: "High confidence", bars: 3, fill: "bg-conf-high" },
  medium: { label: "Medium confidence", bars: 2, fill: "bg-conf-medium" },
  low: { label: "Low confidence", bars: 1, fill: "bg-conf-low" },
};

/** Confidence = text label + bar count. Never colour alone, never a percentage. */
export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const c = CONF[confidence];
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-ink-700">
      <span className="flex items-end gap-0.5" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span key={i} className={`w-1 rounded-sm ${i <= c.bars ? c.fill : "bg-slate-200"}`} style={{ height: 4 + i * 3 }} />
        ))}
      </span>
      {c.label}
    </span>
  );
}

const HEALTH: Record<HealthStatus, { tone: Tone; label: string; dot: string }> = {
  normal: { tone: "success", label: "Normal", dot: "bg-success" },
  watch: { tone: "warning", label: "Watch", dot: "bg-warning" },
  degraded: { tone: "danger", label: "Degraded", dot: "bg-danger" },
};

export function HealthBadge({ status }: { status: HealthStatus }) {
  const h = HEALTH[status];
  return (
    <Badge tone={h.tone}>
      <span className={`h-2 w-2 rounded-full ${h.dot}`} aria-hidden="true" />
      {h.label}
    </Badge>
  );
}

export const healthBarClass = (s: HealthStatus) => HEALTH[s].dot;
