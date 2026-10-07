import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FileSpreadsheet, Search, Upload } from "lucide-react";
import { request, errorMessage } from "../api/client";
import type { IncidentRow, IncidentStatus } from "../types/workflow";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Skeleton } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { SourceBadge, StatusBadge, STATUS_ORDER, statusLabel, TopHypothesisText } from "../components/ui/StatusBadge";
import { fmtDateTime } from "../lib/format";
import { useAuth } from "../auth";

const pill = "h-11 rounded-full border border-slate-200 bg-white px-4 text-sm text-ink-900 focus:border-indigo-500 focus:shadow-ring focus:outline-none";

export function IncidentsPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const [incidents, setIncidents] = useState<IncidentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const navigate = useNavigate();
  const q = params.get("q") || "", status = params.get("status") || "", source = params.get("source") || "", machine = params.get("machine") || "";
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };

  useEffect(() => {
    setError(null);
    setIncidents(null);
    request<IncidentRow[]>("/api/incidents").then(setIncidents).catch((e) => setError(errorMessage(e)));
  }, [reload]);

  const machines = useMemo(() => [...new Set((incidents || []).flatMap((r) => r.machines.map((m) => `${r.line}/${m}`)))].sort(), [incidents]);
  const rows = (incidents || []).filter((r) =>
    (!q || r.id.toLowerCase().includes(q.toLowerCase()) || r.filename.toLowerCase().includes(q.toLowerCase())) &&
    (!status || r.status === status) && (!source || r.source === source) &&
    (!machine || r.machines.some((m) => `${r.line}/${m}` === machine)));

  return (
    <div className="fade-in space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold tracking-wide text-indigo-700">Incidents</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink-900 sm:text-[34px]">Production incidents</h1>
          <p className="mt-2 text-[15px] leading-relaxed text-slate-600">
            Sample incidents form the evaluation set; uploaded incidents are labelled and never join evaluations.
          </p>
        </div>
        {can("upload") && <Button variant="secondary" to="/upload" icon={<Upload size={18} aria-hidden="true" />}>Upload CSV</Button>}
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="relative min-w-[220px] flex-1">
          <span className="sr-only">Search incident ID</span>
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <input className={`${pill} w-full pl-10`} placeholder="Search incident ID" value={q} onChange={(e) => set("q", e.target.value)} />
        </label>
        <select aria-label="Filter by status" className={pill} value={status} onChange={(e) => set("status", e.target.value)}>
          <option value="">All statuses</option>
          {STATUS_ORDER.map((s: IncidentStatus) => <option key={s} value={s}>{statusLabel(s)}</option>)}
        </select>
        <select aria-label="Filter by source" className={pill} value={source} onChange={(e) => set("source", e.target.value)}>
          <option value="">Sample and uploaded</option>
          <option value="sample">Sample</option>
          <option value="uploaded">Uploaded</option>
        </select>
        <select aria-label="Filter by machine" className={pill} value={machine} onChange={(e) => set("machine", e.target.value)}>
          <option value="">All machines</option>
          {machines.map((m) => <option key={m}>{m}</option>)}
        </select>
      </div>

      {error && (
        <Alert tone="danger" title="Could not load incidents" action={<Button size="sm" variant="outline" onClick={() => setReload((n) => n + 1)}>Retry</Button>}>
          {error}
        </Alert>
      )}
      {!error && incidents === null && (
        <Card className="space-y-3 p-5">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</Card>
      )}
      {incidents && incidents.length === 0 && (
        <EmptyState icon={<FileSpreadsheet size={24} />} title="No incidents yet">Upload a production CSV to start an investigation.</EmptyState>
      )}
      {incidents && incidents.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <caption className="sr-only">Incidents</caption>
              <thead className="bg-surface-alt text-[13px] font-semibold text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3">Incident</th>
                  <th scope="col" className="px-5 py-3">Source</th>
                  <th scope="col" className="px-5 py-3">Line · machines</th>
                  <th scope="col" className="px-5 py-3">Date</th>
                  <th scope="col" className="px-5 py-3">Top hypothesis</th>
                  <th scope="col" className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => navigate(`/incidents/${r.id}`)} className="cursor-pointer border-t border-slate-200 transition-colors duration-150 hover:bg-indigo-50">
                    <td className="px-5 py-3">
                      <a href={`/incidents/${r.id}`} onClick={(e) => { e.preventDefault(); navigate(`/incidents/${r.id}`); }} className="font-mono text-[13px] font-semibold text-ink-900 hover:text-indigo-700">{r.id}</a>
                      <span className="block max-w-[220px] truncate font-mono text-[11px] text-slate-500">{r.filename}</span>
                    </td>
                    <td className="px-5 py-3"><SourceBadge source={r.source} />{r.uploaded_by_name && <span className="block text-[11px] text-slate-500">by {r.uploaded_by_name}</span>}</td>
                    <td className="px-5 py-3 font-mono text-[13px]">{r.line} · {r.machines.join(", ")}</td>
                    <td className="px-5 py-3 font-mono text-[13px]">{fmtDateTime(r.start_time)}</td>
                    <td className="px-5 py-3"><TopHypothesisText top={r.top_hypothesis} /></td>
                    <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length === 0 && <p className="border-t border-slate-200 p-5 text-sm text-slate-600">No incidents match these filters.</p>}
        </Card>
      )}
    </div>
  );
}
