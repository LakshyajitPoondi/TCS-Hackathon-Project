import { Loader2 } from "lucide-react";

export function Spinner({ size = 18, label }: { size?: number; label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <Loader2 size={size} className="animate-spin text-indigo-700" aria-hidden="true" />
      <span className={label ? "text-sm text-slate-600" : "sr-only"}>{label ?? "Loading"}</span>
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-md bg-slate-100 ${className}`} />;
}
