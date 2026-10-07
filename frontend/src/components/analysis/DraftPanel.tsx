import { useState } from "react";
import { Check, Copy, Download, Eye, History, RotateCcw, Save, Send, ShieldAlert } from "lucide-react";
import { Card, SectionTitle } from "../ui/Card";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Alert";
import { Modal } from "../ui/Modal";
import { useAuth } from "../../auth";
import { request, errorMessage } from "../../api/client";
import { downloadFile } from "../../lib/download";
import { fmtStamp } from "../../lib/format";
import type { Draft } from "../../types/workflow";

/**
 * Versioned RCA draft. Every save creates a new version; restore copies an old version into a new one.
 * Exports always carry the engineering-validation notice (added by the server). Viewers read only.
 */
export function DraftPanel({
  incidentId, runId, value, baseline, onChange, drafts, onSaved, warning, onPropose,
}: {
  incidentId: string;
  runId: string | null;
  value: string;
  baseline: string;
  onChange: (v: string) => void;
  drafts: Draft[];
  onSaved: (d: Draft) => void;
  warning: string;
  onPropose: () => void;
}) {
  const { can } = useAuth();
  const editable = can("draft");
  const latest = drafts[0] ?? null;
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"save" | "restore" | "md" | "pdf" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [viewing, setViewing] = useState<Draft | null>(null);
  const [copied, setCopied] = useState(false);
  const edited = value !== baseline;
  const unsaved = !latest || value !== latest.content;

  const save = async () => {
    setBusy("save"); setError(null);
    try {
      const d = await request<Draft>(`/api/incidents/${encodeURIComponent(incidentId)}/drafts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: value, run_id: runId, note: note.trim() || null }),
      });
      setNote(""); setSaved(d.version); onSaved(d);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(null); }
  };
  const restore = async (version: number) => {
    setBusy("restore"); setError(null);
    try {
      const d = await request<Draft>(`/api/incidents/${encodeURIComponent(incidentId)}/drafts/${version}/restore`, { method: "POST" });
      setViewing(null); setSaved(d.version); onSaved(d);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(null); }
  };
  const exportAs = async (format: "md" | "pdf", d: Draft | null = latest) => {
    if (!d) return;
    setBusy(format); setError(null);
    try { await downloadFile(`/api/incidents/${encodeURIComponent(incidentId)}/drafts/${d.version}/export?format=${format}`, `rca-draft-${incidentId}-v${d.version}.${format}`); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(null); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); window.setTimeout(() => setCopied(false), 2000); } catch { /* clipboard blocked */ }
  };

  return (
    <section aria-labelledby="draft-title">
      <SectionTitle
        title="RCA Draft"
        sub={editable ? "Edit, then save a version. Every save is kept; restore any earlier version." : "Read-only for your role."}
        right={
          <div className="flex flex-wrap gap-2">
            {editable && edited && (
              <Button variant="ghost" size="sm" onClick={() => onChange(baseline)} icon={<RotateCcw size={15} aria-hidden="true" />}>Revert edits</Button>
            )}
            <Button variant="outline" size="sm" onClick={copy} icon={copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}>{copied ? "Copied" : "Copy"}</Button>
            <Button variant="outline" size="sm" disabled={!latest} loading={busy === "md"} onClick={() => void exportAs("md")} icon={<Download size={15} aria-hidden="true" />}>Markdown</Button>
            <Button variant="outline" size="sm" disabled={!latest} loading={busy === "pdf"} onClick={() => void exportAs("pdf")} icon={<Download size={15} aria-hidden="true" />}>PDF</Button>
          </div>
        }
      />
      <div className="grid gap-4 xl:grid-cols-12">
        <Card className="p-4 sm:p-5 xl:col-span-8">
          <label htmlFor="rca-draft" className="mb-2 flex flex-wrap items-center gap-2 text-[13px] font-semibold text-ink-700">
            Draft text
            {latest && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-ink-700">Saved version {latest.version}</span>}
            {editable && unsaved && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] text-indigo-700">Unsaved changes</span>}
          </label>
          <textarea
            id="rca-draft"
            value={value}
            readOnly={!editable}
            onChange={(e) => onChange(e.target.value)}
            rows={16}
            spellCheck
            className="block min-h-[300px] w-full resize-y rounded-md border border-transparent bg-slate-100 p-4 font-mono text-[13px] leading-relaxed text-ink-900 transition-colors duration-150 focus:border-indigo-500 focus:bg-white focus:shadow-ring focus:outline-none read-only:cursor-default"
          />
          <p className="mt-3 flex items-start gap-2 rounded-md bg-warning-tint px-3 py-2 text-sm font-medium text-ink-900">
            <ShieldAlert size={16} className="mt-0.5 shrink-0 text-warning-ink" aria-hidden="true" />
            {warning} This notice is always included in exports.
          </p>
          {error && <div className="mt-3"><Alert tone="danger" title="Draft">{error}</Alert></div>}
          {saved && !error && <p role="status" className="mt-3 text-sm font-semibold text-success-ink">Saved as version {saved}.</p>}
          {editable && (
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <label className="min-w-[200px] flex-1 text-[13px] font-semibold text-ink-700">
                Version note <span className="font-normal text-slate-500">(optional)</span>
                <input className="field mt-1" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What changed?" />
              </label>
              <Button onClick={() => void save()} loading={busy === "save"} disabled={!value.trim() || !unsaved} icon={<Save size={17} aria-hidden="true" />}>Save version</Button>
              {can("propose") && <Button variant="secondary" onClick={onPropose} disabled={!value.trim()} icon={<Send size={17} aria-hidden="true" />} arrow>Propose case</Button>}
            </div>
          )}
        </Card>
        <Card className="p-4 sm:p-5 xl:col-span-4">
          <h3 className="flex items-center gap-2 font-bold text-ink-900"><History size={18} aria-hidden="true" />Version history</h3>
          {drafts.length === 0 && <p className="mt-3 text-sm text-slate-600">No saved versions yet. The text shown is the analysis draft.</p>}
          <ol className="mt-3 space-y-2">
            {drafts.map((d) => (
              <li key={d.id} className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-semibold text-ink-900">Version {d.version}</p>
                <p className="text-xs text-slate-500">{d.author_name || "unknown"} · {fmtStamp(d.created_at)}</p>
                {d.note && <p className="mt-1 text-xs text-ink-700">{d.note}</p>}
                <div className="mt-2 flex flex-wrap gap-1">
                  <Button variant="ghost" size="sm" onClick={() => setViewing(d)} icon={<Eye size={14} aria-hidden="true" />}>View</Button>
                  {editable && d.version !== latest?.version && (
                    <Button variant="ghost" size="sm" loading={busy === "restore"} onClick={() => void restore(d.version)} icon={<RotateCcw size={14} aria-hidden="true" />}>Restore</Button>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
      <Modal open={!!viewing} onClose={() => setViewing(null)} title={viewing ? `Draft version ${viewing.version}` : ""} wide>
        {viewing && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">{viewing.author_name || "unknown"} · {fmtStamp(viewing.created_at)}{viewing.note ? ` · ${viewing.note}` : ""}</p>
            <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap rounded-md bg-slate-100 p-4 font-mono text-[13px] text-ink-900">{viewing.content}</pre>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => void exportAs("md", viewing)}>Export Markdown</Button>
              <Button variant="outline" size="sm" onClick={() => void exportAs("pdf", viewing)}>Export PDF</Button>
              {editable && viewing.version !== latest?.version && <Button size="sm" loading={busy === "restore"} onClick={() => void restore(viewing.version)}>Restore as new version</Button>}
            </div>
          </div>
        )}
      </Modal>
    </section>
  );
}
