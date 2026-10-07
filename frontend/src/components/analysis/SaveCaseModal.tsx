import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { saveCase } from "../../api/endpoints";
import { ApiError, errorMessage, request } from "../../api/client";
import { ALL_CATEGORIES, type AnalysisResponse, type Category, type Subcause } from "../../types/api";
import { categoryLabel } from "../../lib/format";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Alert";

const field =
  "block w-full rounded-md border border-transparent bg-slate-100 px-3 text-[15px] text-ink-900 transition-colors duration-150 focus:border-indigo-500 focus:bg-white focus:shadow-ring focus:outline-none";
const labelCls = "mb-1.5 block text-[13px] font-semibold text-ink-700";

interface Duplicate { case_id: string; status: string; reason: string; similarity?: number }
interface CaseDraft {
  incident_id: string; run_id: string; machine_uid: string | null;
  confirmed_category: Category | null; confirmed_subcause: Subcause;
  symptoms: string[]; evidence_summary: string; lessons_learned: string; summary: string; fix_applied: string;
  documents_used: string[]; documents_available: { doc_id: string; title: string }[];
  text_source: "llm" | "template"; fallback_reasons: string[]; duplicates: Duplicate[];
}

/**
 * "Propose case" in two steps: 1) the memory agent drafts a structured case from the analysis, draft and
 * documents accessed (LLM within budget, template otherwise); 2) the engineer reviews and edits every field.
 */
export function SaveCaseModal({
  open, onClose, incidentId, draft, analysis,
}: {
  open: boolean;
  onClose: () => void;
  incidentId: string;
  draft: string;
  analysis?: AnalysisResponse | null;
}) {
  const [step, setStep] = useState<1 | 2>(1);
  const [generating, setGenerating] = useState(false);
  const [agent, setAgent] = useState<CaseDraft | null>(null);
  const [category, setCategory] = useState<Category | "">("");
  const [subcause, setSubcause] = useState<Exclude<Subcause, null> | "">("");
  const [summary, setSummary] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [evidence, setEvidence] = useState("");
  const [fix, setFix] = useState("");
  const [lessons, setLessons] = useState("");
  const [notes, setNotes] = useState("");
  const [docs, setDocs] = useState<string[]>([]);
  const [duplicates, setDuplicates] = useState<Duplicate[]>([]);
  const [dupReason, setDupReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(1); setAgent(null); setError(null); setSavedId(null); setTouched(false); setDupReason(""); setNotes(""); setFix("");
  }, [open]);

  const generate = async () => {
    setGenerating(true); setError(null);
    try {
      const d = await request<CaseDraft>("/api/cases/draft", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incidentId, run_id: analysis?.run_id ?? null, rca_draft: draft }),
      });
      setAgent(d);
      setCategory(d.confirmed_category ?? ""); setSubcause((d.confirmed_subcause ?? "") as "cooling" | "mechanical" | "");
      setSummary(d.summary); setSymptoms(d.symptoms.join("\n")); setEvidence(d.evidence_summary); setLessons(d.lessons_learned);
      setFix(d.fix_applied); setDocs(d.documents_used); setDuplicates(d.duplicates);
      setStep(2);
    } catch (e) { setError(errorMessage(e)); } finally { setGenerating(false); }
  };

  const needsSubcause = category === "machine";
  const invalid = !category || (needsSubcause && !subcause) || fix.trim().length < 3 || !summary.trim() ||
    (duplicates.length > 0 && dupReason.trim().length < 5);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (invalid || !category) return;
    setSaving(true); setError(null);
    try {
      const res = await saveCase({
        incident_id: incidentId, rca_draft: draft, confirmed_category: category,
        confirmed_subcause: needsSubcause ? (subcause as Exclude<Subcause, null>) : null,
        notes: notes.trim() || null, fix_applied: fix.trim(), lessons, documents_used: docs,
        summary: summary.trim(), symptoms: symptoms.split("\n").map((s) => s.trim()).filter(Boolean), evidence_summary: evidence.trim(),
        text_source: agent?.text_source ?? "template", duplicate_reason: dupReason.trim() || null,
      });
      setSavedId(res.case_id);
      window.dispatchEvent(new Event('rca-counts-changed'));
    } catch (err) {
      const d = err instanceof ApiError && err.status === 409 ? (err.detail as { duplicates?: Duplicate[] } | null) : null;
      if (d?.duplicates) { setDuplicates(d.duplicates); setError("Possible duplicate: give a reason to submit anyway."); }
      else setError(errorMessage(err));
    } finally { setSaving(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title={savedId ? "Case proposed" : step === 1 ? "Propose case · step 1 of 2" : "Propose case · step 2 of 2: review and edit"} wide>
      {savedId ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-md bg-success-tint p-4 text-sm text-ink-900" role="status">
            <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-success-ink" aria-hidden="true" />
            <p>Case proposed · <Link to={`/cases/${savedId}`} className="font-mono font-semibold text-indigo-700">{savedId}</Link>. It becomes recallable after QA or administrator approval.</p>
          </div>
          <div className="flex justify-end"><Button onClick={onClose}>Done</Button></div>
        </div>
      ) : step === 1 ? (
        <div className="space-y-4">
          <p className="rounded-md bg-warning-tint px-3 py-2 text-sm font-semibold text-ink-900">Confirm only after engineering validation.</p>
          <p className="text-sm text-slate-600">
            The memory agent drafts symptoms, the suggested cause, an evidence summary, documents used, lessons and a one-paragraph
            summary for <span className="font-mono font-semibold text-ink-900">{incidentId}</span>. You review and edit every field before submitting.
            It uses the LLM when available and within budget, otherwise a template.
          </p>
          {error && <Alert tone="danger" title="Draft not generated">{error}</Alert>}
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={() => void generate()} loading={generating} icon={<Sparkles size={17} aria-hidden="true" />} arrow>
              {generating ? "Drafting…" : "Generate draft"}
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700">
              {agent?.text_source === "llm" ? "Drafted with the LLM" : "Template draft"}
            </span>
            {agent?.fallback_reasons.map((r, i) => <span key={i} className="rounded-full bg-slate-100 px-2.5 py-1 text-ink-700">{r.replaceAll("_", " ")}</span>)}
            <span className="text-slate-500">Your edits are authoritative.</span>
          </div>
          {duplicates.length > 0 && (
            <Alert tone="warning" title="Possible duplicate case">
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {duplicates.map((d) => <li key={d.case_id}><Link to={`/cases/${d.case_id}`} className="font-mono font-semibold text-indigo-700">{d.case_id}</Link> · {d.reason}</li>)}
              </ul>
              <label htmlFor="case-dup-reason" className="mt-3 block text-[13px] font-semibold text-ink-700">Reason to submit anyway *</label>
              <textarea id="case-dup-reason" className={`${field} mt-1 py-2`} rows={2} value={dupReason} onChange={(e) => setDupReason(e.target.value)} />
              {touched && dupReason.trim().length < 5 && <p className="mt-1 text-[13px] text-danger-ink">Give a reason (at least 5 characters).</p>}
            </Alert>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="confirmed-category" className={labelCls}>Confirmed category *</label>
              <select id="confirmed-category" value={category} className={`${field} h-12`}
                onChange={(e) => { setCategory(e.target.value as Category); if (e.target.value !== "machine") setSubcause(""); }}>
                <option value="" disabled>Select the validated category…</option>
                {ALL_CATEGORIES.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
              </select>
              <p className="mt-1 text-xs text-slate-500">Suggested from the top hypothesis; change it if verification showed otherwise.</p>
              {touched && !category && <p className="mt-1 text-[13px] text-danger-ink">Select a confirmed category.</p>}
            </div>
            {needsSubcause && (
              <div>
                <label htmlFor="confirmed-subcause" className={labelCls}>Subcause *</label>
                <select id="confirmed-subcause" value={subcause} className={`${field} h-12`} onChange={(e) => setSubcause(e.target.value as "cooling" | "mechanical")}>
                  <option value="" disabled>Select a subcause…</option>
                  <option value="cooling">Cooling</option>
                  <option value="mechanical">Mechanical</option>
                </select>
                {touched && !subcause && <p className="mt-1 text-[13px] text-danger-ink">Select a subcause for a machine case.</p>}
              </div>
            )}
          </div>
          <div>
            <label htmlFor="case-summary" className={labelCls}>Summary (one paragraph) *</label>
            <textarea id="case-summary" className={`${field} py-2.5`} rows={4} value={summary} onChange={(e) => setSummary(e.target.value)} />
          </div>
          <div>
            <label htmlFor="case-symptoms" className={labelCls}>Symptoms (one per line)</label>
            <textarea id="case-symptoms" className={`${field} py-2.5`} rows={4} value={symptoms} onChange={(e) => setSymptoms(e.target.value)} />
          </div>
          <div>
            <label htmlFor="case-evidence" className={labelCls}>Evidence summary</label>
            <textarea id="case-evidence" className={`${field} py-2.5`} rows={3} value={evidence} onChange={(e) => setEvidence(e.target.value)} />
          </div>
          <div>
            <label htmlFor="case-fix" className={labelCls}>Fix applied *</label>
            <textarea id="case-fix" className={`${field} py-2.5`} rows={2} value={fix} onChange={(e) => setFix(e.target.value)} placeholder="What was done on the line?" />
          </div>
          {touched && fix.trim().length < 3 && <p className="text-[13px] text-danger-ink">Describe the fix that was applied.</p>}
          <div>
            <label htmlFor="case-lessons" className={labelCls}>Lessons learned</label>
            <textarea id="case-lessons" className={`${field} py-2.5`} rows={2} value={lessons} onChange={(e) => setLessons(e.target.value)} />
          </div>
          <fieldset>
            <legend className={labelCls}>Documents used</legend>
            <div className="space-y-1.5">
              {(agent?.documents_available || []).map((d) => (
                <label key={d.doc_id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={docs.includes(d.doc_id)}
                    onChange={(e) => setDocs((all) => (e.target.checked ? [...all, d.doc_id] : all.filter((x) => x !== d.doc_id)))} />
                  {d.title} <span className="font-mono text-xs text-slate-500">{d.doc_id}</span>
                </label>
              ))}
              {!agent?.documents_available.length && <p className="text-sm text-slate-500">No documents were accessed by this analysis.</p>}
            </div>
          </fieldset>
          <div>
            <label htmlFor="case-notes" className={labelCls}>Notes <span className="font-normal text-slate-500">(optional)</span></label>
            <textarea id="case-notes" className={`${field} py-2.5`} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What was checked and confirmed on the line?" />
          </div>
          {error && <Alert tone={duplicates.length ? "warning" : "danger"} title="Case not proposed">{error}</Alert>}
          {touched && invalid && !error && (
            <p className="flex items-center gap-1.5 text-[13px] text-danger-ink"><AlertTriangle size={14} aria-hidden="true" />Complete the required fields.</p>
          )}
          <div className="flex flex-wrap justify-between gap-3 pt-1">
            <Button type="button" variant="ghost" onClick={() => setStep(1)}>Back</Button>
            <div className="flex gap-3">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" loading={saving} arrow>Submit proposal</Button>
            </div>
          </div>
        </form>
      )}
    </Modal>
  );
}
