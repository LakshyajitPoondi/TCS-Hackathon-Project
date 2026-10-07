import { Link } from "react-router-dom";
import { AlertTriangle, BookOpen, Brain, CheckCircle2, FileText, Upload } from "lucide-react";
import { useAuth } from "../auth";
import { useResource } from "../lib/resource";
import type { Dashboard, IncidentStatus } from "../types/workflow";
import { Card, SectionTitle } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Spinner";
import { SourceBadge, StatusBadge, STATUS_ORDER, TopHypothesisText } from "../components/ui/StatusBadge";
import { fmtDateTime, fmtStamp } from "../lib/format";

function Kpi({ value, label, caption, to }: { value: string | number; label: string; caption: string; to?: string }) {
  const body = (
    <Card className="h-full p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-hover">
      <p className="text-[40px] font-bold leading-none tracking-tight text-indigo-700">{value}</p>
      <p className="mt-3 font-semibold text-ink-900">{label}</p>
      <p className="mt-1 text-xs text-slate-500">{caption}</p>
    </Card>
  );
  return to ? <Link to={to} className="block rounded-lg focus-visible:shadow-ring focus-visible:outline-none">{body}</Link> : body;
}

const PENDING_ICON = { case_review: BookOpen, document_mapping: FileText, analyse: AlertTriangle, propose: Brain };

export function DashboardPage() {
  const { user, can } = useAuth();
  const { data, error } = useResource<Dashboard>("/api/dashboard");
  const k = data?.kpis;
  const open = k ? k.incidents_by_status.new + k.incidents_by_status.analysed + k.incidents_by_status.draft_saved : 0;
  return (
    <div className="fade-in space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-indigo-700">Dashboard</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink-900 sm:text-[34px]">Welcome, {user?.name || user?.email}</h1>
          <p className="mt-2 text-[15px] text-slate-600">Incident workflow at a glance: analyse, draft, propose and approve.</p>
        </div>
        {can("upload") && <Button variant="secondary" to="/upload" icon={<Upload size={18} aria-hidden="true" />}>Upload CSV</Button>}
      </div>
      {error && <Alert tone="danger" title="Dashboard unavailable">{error}</Alert>}
      {!k && !error && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-lg" />)}</div>}
      {k && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi value={open} label="Open incidents" caption={`${k.incidents_total} total · ${k.incidents_uploaded} uploaded`} to="/incidents" />
            <Kpi value={k.cases_pending} label="Cases pending approval" caption={`${k.cases_approved} approved in memory`} to="/cases?status=proposed" />
            <Kpi value={k.documents_pending} label="Documents pending mapping" caption="Confirm scope before they are used" to="/documents?status=pending_mapping" />
            <Kpi value={`${k.llm_calls_today}/${k.llm_daily_budget}`} label="LLM calls today"
              caption={k.llm_blocked_until ? "Quota exhausted · template wording" : "Template wording when unavailable"} />
          </div>
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-ink-900">Incidents by status</h2>
            <div className="mt-3 flex flex-wrap gap-3">
              {STATUS_ORDER.map((s: IncidentStatus) => (
                <Link key={s} to={`/incidents?status=${s}`} className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-sm hover:bg-indigo-50">
                  <StatusBadge status={s} /> <span className="font-mono font-semibold text-ink-900">{k.incidents_by_status[s]}</span>
                </Link>
              ))}
            </div>
          </Card>
          <div className="grid gap-6 xl:grid-cols-12">
            <section className="xl:col-span-8">
              <SectionTitle title="Recent incidents" right={<Button variant="ghost" size="sm" to="/incidents" arrow>All incidents</Button>} />
              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead className="bg-surface-alt text-[13px] font-semibold text-slate-500">
                      <tr><th className="px-4 py-3">Incident</th><th className="px-4 py-3">Machines</th><th className="px-4 py-3">Start</th><th className="px-4 py-3">Top hypothesis</th><th className="px-4 py-3">Status</th></tr>
                    </thead>
                    <tbody>
                      {data.recent_incidents.map((r) => (
                        <tr key={r.id} className="border-t border-slate-200 hover:bg-indigo-50">
                          <td className="px-4 py-3"><Link to={`/incidents/${r.id}`} className="font-mono text-[13px] font-semibold text-indigo-700">{r.id}</Link> <SourceBadge source={r.source} /></td>
                          <td className="px-4 py-3 font-mono text-[13px]">{r.line} · {r.machines.join(", ")}</td>
                          <td className="px-4 py-3 font-mono text-[13px]">{fmtDateTime(r.start_time)}</td>
                          <td className="px-4 py-3"><TopHypothesisText top={r.top_hypothesis} /></td>
                          <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>
            <section className="xl:col-span-4">
              <SectionTitle title="Pending for you" sub={user ? `Role: ${user.role.replace("_", " ")}` : undefined} />
              <Card className="divide-y divide-slate-200">
                {data.pending.length === 0 && (
                  <p className="flex items-center gap-2 p-5 text-sm text-slate-600"><CheckCircle2 size={18} className="text-success-ink" aria-hidden="true" />Nothing waiting for your role.</p>
                )}
                {data.pending.map((p, i) => {
                  const Icon = PENDING_ICON[p.kind];
                  return (
                    <Link key={i} to={p.link} className="flex gap-3 p-4 hover:bg-indigo-50">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700" aria-hidden="true"><Icon size={18} /></span>
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold text-ink-900">{p.title}</span>
                        <span className="block break-words text-xs text-slate-500">{p.detail}{p.created_at ? ` · ${fmtStamp(p.created_at)}` : ""}</span>
                      </span>
                    </Link>
                  );
                })}
              </Card>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
