import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Menu } from "lucide-react";
import { health } from "../../api/endpoints";
import {useAuth} from '../../auth';

type Status = "checking" | "online" | "offline";

function useBackendHealth(): Status {
  const [status, setStatus] = useState<Status>("checking");
  useEffect(() => {
    let alive = true;
    const check = () =>
      health()
        .then(() => alive && setStatus("online"))
        .catch(() => alive && setStatus("offline"));
    check();
    const t = window.setInterval(check, 30000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, []);
  return status;
}

function HealthIndicator() {
  const status = useBackendHealth();
  if (status === "checking") {
    return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Checking engine…</span>;
  }
  if (status === "online") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-mint-100 px-3 py-1 text-xs font-semibold text-success-ink">
        <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden="true" />
        Engine online
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-warning-tint px-3 py-1 text-xs font-semibold text-warning-ink">
      <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true" />
      Backend unavailable
    </span>
  );
}

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const {user,logout}=useAuth();
  return (
    <div className="flex h-16 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur lg:px-6">
      <button
        onClick={onMenu}
        className="rounded-md p-2 text-ink-700 hover:bg-slate-100 lg:hidden"
        aria-label="Open navigation menu"
      >
        <Menu size={20} aria-hidden="true" />
      </button>
      <Link to="/" className="flex min-w-0 items-center gap-2.5 rounded-md">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-700 text-white" aria-hidden="true">
          <Activity size={16} />
        </span>
        <span className="truncate text-[15px] font-bold text-ink-900">Production Intelligence</span>
        <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-bold tracking-wide text-indigo-700">RCA</span>
      </Link>
      <div className="ml-auto">
        <HealthIndicator />
      </div>
      <span className="hidden text-xs sm:inline">{user?.email} · {user?.role}</span><button className="rounded-full border border-slate-200 px-3 py-2 text-sm" onClick={()=>void logout().catch(()=>{})}>Sign out</button>
    </div>
  );
}
