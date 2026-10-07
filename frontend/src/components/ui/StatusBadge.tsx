import type { IncidentSource, IncidentStatus, TopHypothesis } from "../../types/workflow";
import { categoryWithSubcause } from "../../lib/format";

const STATUS: Record<IncidentStatus, { label: string; cls: string; dot: string }> = {
  new: { label: "New", cls: "bg-slate-100 text-ink-700", dot: "bg-slate-500" },
  analysed: { label: "Analysed", cls: "bg-indigo-50 text-indigo-700", dot: "bg-indigo-500" },
  draft_saved: { label: "Draft saved", cls: "bg-indigo-50 text-indigo-700", dot: "bg-indigo-700" },
  case_proposed: { label: "Case proposed", cls: "bg-warning-tint text-warning-ink", dot: "bg-warning" },
  case_approved: { label: "Case approved", cls: "bg-success-tint text-success-ink", dot: "bg-success" },
  case_rejected: { label: "Case rejected", cls: "bg-danger-tint text-danger-ink", dot: "bg-danger" },
};

/** Incident workflow status, derived on the server. Text label + dot, never colour alone. */
export function StatusBadge({ status }: { status: IncidentStatus }) {
  const s = STATUS[status];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}

export const STATUS_ORDER: IncidentStatus[] = ["new", "analysed", "draft_saved", "case_proposed", "case_approved", "case_rejected"];
export const statusLabel = (s: IncidentStatus) => STATUS[s].label;

export function SourceBadge({ source }: { source: IncidentSource }) {
  return source === "uploaded" ? (
    <span className="inline-flex rounded-full bg-mint-100 px-2 py-0.5 text-[11px] font-bold text-success-ink">Uploaded</span>
  ) : (
    <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600">Sample</span>
  );
}

/** Case status chip (proposed / approved / rejected / retired). */
export function CaseStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    proposed: "bg-warning-tint text-warning-ink", approved: "bg-success-tint text-success-ink",
    rejected: "bg-danger-tint text-danger-ink", retired: "bg-slate-100 text-slate-600",
  };
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${map[status] || "bg-slate-100 text-ink-700"}`}>{status}</span>;
}

export function TopHypothesisText({ top }: { top: TopHypothesis | null }) {
  if (!top) return <span className="text-slate-500">Not analysed</span>;
  if (!top.category) return <span className="text-slate-600">Insufficient evidence</span>;
  return (
    <span className="text-ink-900">
      {categoryWithSubcause(top.category, top.subcause ?? null)}
      {top.confidence && <span className="text-slate-500"> · {top.confidence}</span>}
    </span>
  );
}
