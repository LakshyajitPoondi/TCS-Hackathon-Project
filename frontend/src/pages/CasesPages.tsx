import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuth } from "../auth";
import { useResource, mutation, countsChanged } from "../lib/resource";
import { errorMessage } from "../api/client";
import type { Case, CaseHistory } from "../types/registry";
import { Card, SectionTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { CaseStatusBadge } from "../components/ui/StatusBadge";
import { fmtStamp } from "../lib/format";

const field = "h-11 rounded-full border border-slate-200 bg-white px-4 text-sm text-ink-900 focus:border-indigo-500 focus:shadow-ring focus:outline-none";
const cause = (c: Case) => c.confirmed_category + (c.confirmed_subcause ? " / " + c.confirmed_subcause : "");

function ReviewButtons({ c, onDone }: { c: Case; onDone: () => void }) {
  const { can } = useAuth();
  const [failure, setFailure] = useState("");
  if (!can("approve") || c.status !== "proposed") return null;
  const review = async (action: "approve" | "reject") => {
    try { await mutation(`/api/cases/${c.case_id}/${action}`, {}); countsChanged(); onDone(); } catch (e) { setFailure(errorMessage(e)); }
  };
  return (
    <div className="space-y-2">
      <div className="flex gap-3">
        <Button size="sm" onClick={() => void review("approve")}>Approve</Button>
        <Button size="sm" variant="outline" onClick={() => void review("reject")}>Reject</Button>
      </div>
      {failure && <Alert tone="danger" title="Case review">{failure}</Alert>}
    </div>
  );
}

export function CasesPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "", machine = params.get("machine") || "", category = params.get("category") || "";
  const [rev, setRev] = useState(0);
  const { data: cases, error } = useResource<Case[]>("/api/cases" + (status ? "?status=" + status : ""), rev);
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const machines = [...new Set((cases || []).map((c) => c.machine_uid || c.line).filter(Boolean))].sort();
  const categories = [...new Set((cases || []).map((c) => c.confirmed_category))].sort();
  const shown = (cases || []).filter((c) => (!machine || (c.machine_uid || c.line) === machine) && (!category || c.confirmed_category === category));
  return (
    <div className="space-y-6">
      <SectionTitle title="Experience memory" sub="Proposals become recallable after QA or administrator approval. Seed cases are synthetic." />
      <div className="flex flex-wrap gap-3">
        <select className={field} aria-label="Case status" value={status} onChange={(e) => set("status", e.target.value)}>
          <option value="">All statuses</option>
          {["proposed", "approved", "rejected", "retired"].map((s) => <option key={s}>{s}</option>)}
        </select>
        <select className={field} aria-label="Machine" value={machine} onChange={(e) => set("machine", e.target.value)}>
          <option value="">All machines</option>
          {machines.map((m) => <option key={m}>{m}</option>)}
        </select>
        <select className={field} aria-label="Category" value={category} onChange={(e) => set("category", e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
      {error && <Alert tone="danger" title="Cases">{error}</Alert>}
      <div className="grid gap-4 md:grid-cols-2">
        {shown.map((c) => (
          <Card key={c.case_id} className="space-y-3 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link to={`/cases/${c.case_id}`} className="break-all font-mono text-xs font-semibold text-indigo-700">{c.case_id}</Link>
              <CaseStatusBadge status={c.status} />
            </div>
            <h3 className="font-bold capitalize text-ink-900">{cause(c)}</h3>
            <p className="text-sm">{c.summary}</p>
            <p className="text-sm">
              {c.source_incident_id ? <Link className="font-mono font-semibold text-indigo-700" to={`/incidents/${c.source_incident_id}`}>{c.source_incident_id}</Link> : "Synthetic seed"}
              {" · "}<span className="font-mono">{c.machine_uid || c.line}</span>
            </p>
            <p className="text-xs text-slate-500">
              Proposed by {c.proposer_name || "synthetic seed"} · {fmtStamp(c.created_at)}
              {c.approver_name && <> · reviewed by {c.approver_name}</>}
            </p>
            <ReviewButtons c={c} onDone={() => setRev((n) => n + 1)} />
          </Card>
        ))}
      </div>
      {cases && shown.length === 0 && <p className="text-sm">No cases match these filters.</p>}
    </div>
  );
}

function CaseActions({ c, onDone }: { c: Case; onDone: () => void }) {
  const { can } = useAuth();
  const [mode, setMode] = useState<"" | "edit" | "retire">("");
  const [reason, setReason] = useState("");
  const [summary, setSummary] = useState(c.summary);
  const [fix, setFix] = useState(c.fix_applied);
  const [lessons, setLessons] = useState(c.lessons || "");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  if (!can("approve") || c.status !== "approved") return null;
  const send = async () => {
    setBusy(true); setFailure("");
    try {
      if (mode === "edit") await mutation(`/api/cases/${c.case_id}`, { reason, summary, fix_applied: fix, lessons }, "PATCH");
      else await mutation(`/api/cases/${c.case_id}/retire`, { reason });
      setMode(""); setReason(""); onDone();
    } catch (e) { setFailure(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Card className="space-y-4 p-6">
      <div className="flex flex-wrap gap-3">
        <Button size="sm" variant={mode === "edit" ? "primary" : "outline"} onClick={() => setMode(mode === "edit" ? "" : "edit")}>Edit approved case</Button>
        <Button size="sm" variant={mode === "retire" ? "primary" : "outline"} onClick={() => setMode(mode === "retire" ? "" : "retire")}>Retire case</Button>
      </div>
      {mode === "edit" && (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">The current version is kept in the history.</p>
          <div><label htmlFor="edit-summary" className="block text-[13px] font-semibold text-ink-700">Summary</label><textarea id="edit-summary" className="field mt-1 h-auto py-2" rows={4} value={summary} onChange={(e) => setSummary(e.target.value)} /></div>
          <div><label htmlFor="edit-fix" className="block text-[13px] font-semibold text-ink-700">Fix applied</label><textarea id="edit-fix" className="field mt-1 h-auto py-2" rows={2} value={fix} onChange={(e) => setFix(e.target.value)} /></div>
          <div><label htmlFor="edit-lessons" className="block text-[13px] font-semibold text-ink-700">Lessons learned</label><textarea id="edit-lessons" className="field mt-1 h-auto py-2" rows={2} value={lessons} onChange={(e) => setLessons(e.target.value)} /></div>
        </div>
      )}
      {mode === "retire" && <p className="text-sm text-slate-600">Retired cases stay visible for audit but are never recalled for new incidents.</p>}
      {mode && (
        <div className="space-y-3">
          <label htmlFor="case-change-reason" className="block text-[13px] font-semibold text-ink-700">Reason *</label><input id="case-change-reason" className="field mt-1" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button size="sm" loading={busy} disabled={reason.trim().length < 5} onClick={() => void send()}>{mode === "edit" ? "Save new version" : "Retire case"}</Button>
        </div>
      )}
      {failure && <Alert tone="danger" title="Case update">{failure}</Alert>}
    </Card>
  );
}

const ACTION_LABEL: Record<string, string> = { propose_case: "Proposed", approved_case: "Approved", rejected_case: "Rejected", edit_case: "Edited", retire_case: "Retired" };

function CaseHistoryPanel({ history }: { history: CaseHistory | null }) {
  return (
    <section>
      <SectionTitle title="History" sub="Every action is recorded in the audit log; earlier versions are kept." />
      <Card className="divide-y divide-slate-200">
        {history?.events.map((e, i) => (
          <div key={i} className="flex flex-wrap justify-between gap-2 p-4 text-sm">
            <span><strong>{ACTION_LABEL[e.action] || e.action}</strong> by {e.user_name || "system"}{typeof e.data.reason === "string" ? ` · ${e.data.reason}` : ""}</span>
            <span className="text-slate-500">{fmtStamp(e.created_at)}</span>
          </div>
        ))}
        {history?.versions.map((v) => (
          <details key={v.version} className="p-4 text-sm">
            <summary className="cursor-pointer font-semibold text-indigo-700">Version {v.version} ({v.status}) · replaced by {v.change} · {v.editor_name} · {fmtStamp(v.created_at)}</summary>
            <p className="mt-2">{String(v.data.summary ?? "")}</p>
            <p className="mt-1 text-slate-600">Fix: {String(v.data.fix_applied ?? "")}</p>
          </details>
        ))}
        {history && !history.events.length && !history.versions.length && <p className="p-4 text-sm">No recorded changes (synthetic seed).</p>}
      </Card>
    </section>
  );
}

export function CaseDetailPage() {
  const { id = "" } = useParams();
  const [rev, setRev] = useState(0);
  const { data: c, error } = useResource<Case>("/api/cases/" + encodeURIComponent(id), rev);
  const { data: history } = useResource<CaseHistory>("/api/cases/" + encodeURIComponent(id) + "/history", rev);
  return (
    <div className="space-y-6">
      <Button to="/cases" variant="ghost" size="sm" icon={<ArrowLeft size={15} aria-hidden="true" />} className="-ml-2">All cases</Button>
      {error && <Alert tone="danger" title="Case">{error}</Alert>}
      {c && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-indigo-700">Case · version {c.version ?? 1}</p>
              <h1 className="mt-1 break-all font-mono text-2xl font-bold text-ink-900">{c.case_id}</h1>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <CaseStatusBadge status={c.status} />
                <span className="capitalize">{cause(c)}</span>
                <span>·</span>
                {c.source_incident_id ? <Link to={`/incidents/${c.source_incident_id}`} className="font-mono font-semibold text-indigo-700">{c.source_incident_id}</Link> : <span>Synthetic seed</span>}
                <span>·</span><span className="font-mono">{c.machine_uid || c.line}</span>
                {c.text_source && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{c.text_source === "llm" ? "LLM-drafted, engineer-edited" : "Template-drafted, engineer-edited"}</span>}
              </div>
            </div>
            <ReviewButtons c={c} onDone={() => setRev((n) => n + 1)} />
          </div>
          {c.status === "retired" && <Alert tone="warning" title="Retired">{c.retired_reason} · {c.retired_by_name}. This case is never recalled.</Alert>}
          {c.duplicate_override && <Alert tone="info" title="Submitted despite a duplicate warning">{c.duplicate_override.reason}</Alert>}
          <Card className="space-y-4 p-6">
            <p>{c.summary}</p>
            {c.evidence_summary && <p className="text-sm text-ink-700"><strong>Evidence:</strong> {c.evidence_summary}</p>}
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div><dt className="font-semibold text-ink-900">Fix applied</dt><dd className="mt-1">{c.fix_applied || "—"}</dd></div>
              <div><dt className="font-semibold text-ink-900">Lessons learned</dt><dd className="mt-1">{c.lessons || "—"}</dd></div>
              <div><dt className="font-semibold text-ink-900">Proposed by</dt><dd className="mt-1">{c.proposer_name || "synthetic seed"} · {fmtStamp(c.created_at)}</dd></div>
              <div><dt className="font-semibold text-ink-900">Reviewed by</dt><dd className="mt-1">{c.approver_name || "pending"}{c.reviewed_at ? ` · ${fmtStamp(c.reviewed_at)}` : ""}</dd></div>
            </dl>
            {!!c.symptoms?.length && (
              <div><h3 className="font-semibold text-ink-900">Symptoms</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{c.symptoms.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
            )}
            <div>
              <h3 className="font-semibold text-ink-900">Documents used</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {(c.documents || []).map((d) => <Link key={d.doc_id} to={`/documents/${d.doc_id}`} className="rounded-full bg-indigo-50 px-3 py-1 text-sm font-semibold text-indigo-700">{d.title}</Link>)}
                {!c.documents?.length && <span className="text-sm">None recorded.</span>}
              </div>
            </div>
            {c.draft && <details><summary className="cursor-pointer font-semibold text-indigo-700">RCA draft submitted with the case</summary><pre className="mt-3 whitespace-pre-wrap rounded-md bg-slate-100 p-4 font-mono text-[13px]">{c.draft}</pre></details>}
          </Card>
          <CaseActions key={`${c.case_id}-${c.version}-${c.status}`} c={c} onDone={() => setRev((n) => n + 1)} />
          <CaseHistoryPanel history={history} />
        </>
      )}
    </div>
  );
}
