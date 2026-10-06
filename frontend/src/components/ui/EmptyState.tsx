import type { ReactNode } from "react";

export function EmptyState({ icon, title, children, aura = false }: { icon?: ReactNode; title: string; children?: ReactNode; aura?: boolean }) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-white px-6 py-14 text-center shadow-card">
      {aura && <div aria-hidden="true" className="aura absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40" />}
      <div className="relative">
        {icon && (
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-700">{icon}</div>
        )}
        <h3 className="text-lg font-semibold text-ink-900">{title}</h3>
        {children && <div className="mx-auto mt-2 max-w-md text-sm text-slate-600">{children}</div>}
      </div>
    </div>
  );
}
