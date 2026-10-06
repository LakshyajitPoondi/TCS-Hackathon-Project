import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

type Tone = "info" | "success" | "warning" | "danger";

const styles: Record<Tone, { box: string; icon: ReactNode }> = {
  info: { box: "bg-indigo-50 border-indigo-500", icon: <Info size={18} className="text-indigo-700" /> },
  success: { box: "bg-success-tint border-success", icon: <CheckCircle2 size={18} className="text-success-ink" /> },
  warning: { box: "bg-warning-tint border-warning", icon: <AlertTriangle size={18} className="text-warning-ink" /> },
  danger: { box: "bg-danger-tint border-danger", icon: <XCircle size={18} className="text-danger-ink" /> },
};

export function Alert({ tone = "info", title, children, action }: { tone?: Tone; title?: string; children?: ReactNode; action?: ReactNode }) {
  const s = styles[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={`flex flex-wrap items-start gap-3 rounded-md border-l-4 px-4 py-3 text-sm text-ink-700 ${s.box}`}>
      <span className="mt-0.5 shrink-0" aria-hidden="true">{s.icon}</span>
      <div className="min-w-0 flex-1 break-words">
        {title && <p className="font-semibold text-ink-900">{title}</p>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
      {action}
    </div>
  );
}
