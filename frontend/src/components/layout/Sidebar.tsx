import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { CheckCircle2, GitBranch, Upload, X,Factory,FileText,Users,BookOpen } from "lucide-react";
import {useAuth} from '../../auth';

const NAV = [
  // "Analysis" covers the incident list and every incident page.
  { to: "/", label: "Analysis", icon: GitBranch, match: (p: string) => p === "/" || p.startsWith("/incidents") },
  { to: "/upload", label: "Upload data", icon: Upload, match: (p: string) => p.startsWith("/upload") },
  { to:'/machines',label:'Machines',icon:Factory,match:(p:string)=>p.startsWith('/machines')},
  { to:'/documents',label:'Documents',icon:FileText,match:(p:string)=>p.startsWith('/documents')},
  { to:'/cases',label:'Cases',icon:BookOpen,match:(p:string)=>p.startsWith('/cases')},
  { to:'/users',label:'Users',icon:Users,match:(p:string)=>p.startsWith('/users')},
  { to: "/evaluations", label: "Evaluations", icon: CheckCircle2, match: (p: string) => p.startsWith("/evaluations") },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();
  const {can}=useAuth();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1 p-3">
      {NAV.filter(n=>(n.to!='/upload'||can('upload'))&&(n.to!='/users'||can('users'))).map(({ to, label, icon: Icon, match }) => {
        const active = match(pathname);
        return (
          <Link
            key={to}
            to={to}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`relative flex h-11 items-center gap-3 rounded-md px-3 text-[15px] font-medium transition-colors duration-150 ${
              active ? "bg-indigo-50 text-indigo-700" : "text-ink-700 hover:bg-slate-100"
            }`}
          >
            {active && <span className="absolute bottom-2 left-0 top-2 w-[3px] rounded-r bg-indigo-700" aria-hidden="true" />}
            <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">
        <div className="sticky top-[var(--header-h)]">
          <NavItems />
        </div>
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="fade-in absolute inset-0 bg-ink-900/30" onClick={onClose} aria-hidden="true" />
          <aside className="fade-in absolute inset-y-0 left-0 w-64 max-w-[85vw] bg-white shadow-hover" aria-label="Navigation drawer">
            <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4">
              <span className="text-sm font-bold text-ink-900">Menu</span>
              <button onClick={onClose} className="rounded-md p-2 text-ink-700 hover:bg-slate-100" aria-label="Close navigation menu">
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            <NavItems onNavigate={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}
