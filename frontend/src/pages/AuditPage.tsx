import { useSearchParams } from "react-router-dom";
import { useResource } from "../lib/resource";
import { Card, SectionTitle } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { fmtStamp } from "../lib/format";

interface AuditItem { id: number; created_at: string; user_id: string | null; user_name: string | null; action: string; data: Record<string, unknown> }
interface AuditPageData { total: number; limit: number; offset: number; actions: string[]; users: { id: string; name: string }[]; items: AuditItem[] }

const pill = "h-11 rounded-full border border-slate-200 bg-white px-4 text-sm text-ink-900 focus:border-indigo-500 focus:shadow-ring focus:outline-none";
const LIMIT = 50;

/** Administrators: every recorded change, filterable by user, action and date. */
export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); if (k !== "offset") n.delete("offset"); setParams(n, { replace: true }); };
  const offset = Number(params.get("offset") || 0);
  const query = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
  for (const k of ["user_id", "action", "date_from", "date_to"]) { const v = params.get(k); if (v) query.set(k, v); }
  const { data, error } = useResource<AuditPageData>("/api/audit?" + query.toString());
  return (
    <div className="space-y-6">
      <SectionTitle title="Audit log" sub="Every change is recorded with the user who made it. Newest first." />
      <div className="flex flex-wrap gap-3">
        <select aria-label="Filter by user" className={pill} value={params.get("user_id") || ""} onChange={(e) => set("user_id", e.target.value)}>
          <option value="">All users</option>
          {data?.users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
        <select aria-label="Filter by action" className={pill} value={params.get("action") || ""} onChange={(e) => set("action", e.target.value)}>
          <option value="">All actions</option>
          {data?.actions.map((a) => <option key={a} value={a}>{a.replaceAll("_", " ")}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm">From<input type="date" className={pill} value={params.get("date_from") || ""} onChange={(e) => set("date_from", e.target.value)} /></label>
        <label className="flex items-center gap-2 text-sm">To<input type="date" className={pill} value={params.get("date_to") || ""} onChange={(e) => set("date_to", e.target.value)} /></label>
      </div>
      {error && <Alert tone="danger" title="Audit log">{error}</Alert>}
      {data && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-surface-alt text-[13px] font-semibold text-slate-500">
                <tr><th className="px-4 py-3">When</th><th className="px-4 py-3">User</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Details</th></tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className="border-t border-slate-200 align-top">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-[13px]">{fmtStamp(r.created_at)}</td>
                    <td className="px-4 py-3">{r.user_name || "system"}</td>
                    <td className="px-4 py-3"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">{r.action.replaceAll("_", " ")}</span></td>
                    <td className="max-w-xl break-words px-4 py-3 font-mono text-xs text-ink-700">{JSON.stringify(r.data)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.items.length === 0 && <p className="border-t border-slate-200 p-5 text-sm">No entries match these filters.</p>}
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm">
            <span>{data.total === 0 ? "0" : `${offset + 1}–${Math.min(offset + LIMIT, data.total)}`} of {data.total}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => set("offset", String(Math.max(0, offset - LIMIT)))}>Newer</Button>
              <Button size="sm" variant="outline" disabled={offset + LIMIT >= data.total} onClick={() => set("offset", String(offset + LIMIT))}>Older</Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
