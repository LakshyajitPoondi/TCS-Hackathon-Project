import { useState } from "react";
import { CheckCircle2, ChevronDown, Info, SearchX } from "lucide-react";
import type { Grounding, IncidentWindow } from "../../types/api";
import { fmtDateTime } from "../../lib/format";

export function AnalysisComplete({ window }: { window: IncidentWindow | null }) {
  return (
    <div className="fade-in flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-card">
      <span className="inline-flex items-center gap-1.5 font-semibold text-success-ink">
        <CheckCircle2 size={16} aria-hidden="true" />
        Analysis complete
      </span>
      {window ? (
        <>
          <span className="text-slate-600">
            Incident window{" "}
            <span className="font-mono text-ink-900">{fmtDateTime(window.start)}</span> →{" "}
            <span className="font-mono text-ink-900">{fmtDateTime(window.end)}</span>
          </span>
          <span className="flex flex-wrap gap-1.5" aria-label="Detected by">
            {window.detected_by.map((d) => (
              <span key={d} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-ink-700">
                {d}
              </span>
            ))}
          </span>
        </>
      ) : (
        <span className="text-slate-600">No sustained incident window was detected.</span>
      )}
    </div>
  );
}

export function InsufficientEvidence({ window }: { window: IncidentWindow | null }) {
  return (
    <section
      aria-labelledby="insufficient-title"
      className="fade-in relative overflow-hidden rounded-lg border-2 border-slate-300 bg-white p-6 shadow-card sm:p-8"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-ink-700" aria-hidden="true">
          <SearchX size={24} />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Analysis status</p>
          <h2 id="insufficient-title" className="mt-1 text-2xl font-bold text-ink-900">
            Insufficient evidence
          </h2>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-700">
            The available signals do not support a sufficiently strong RCA hypothesis. Additional engineering verification is
            required.
          </p>
          {window && (
            <p className="mt-3 text-sm text-slate-600">
              Deviation observed{" "}
              <span className="font-mono text-ink-900">{fmtDateTime(window.start)}</span> →{" "}
              <span className="font-mono text-ink-900">{fmtDateTime(window.end)}</span>
              {window.detected_by.length > 0 && <> ({window.detected_by.join(", ")})</>}
            </p>
          )}
          <p className="mt-3 text-sm text-slate-600">
            No hypotheses are ranked. The evidence, similar cases and verification draft below remain available for review.
          </p>
        </div>
      </div>
    </section>
  );
}

export function GroundingNote({ grounding }: { grounding: Grounding | null }) {
  const [open, setOpen] = useState(false);
  if (!grounding) return null;
  if (grounding.passed) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-slate-500">
        <Info size={14} aria-hidden="true" />
        Generated wording passed evidence grounding.
      </p>
    );
  }
  return (
    <div className="text-xs text-slate-600">
      <p className="flex items-start gap-1.5">
        <Info size={14} className="mt-px shrink-0" aria-hidden="true" />
        <span>
          Some generated wording was replaced because it was not fully supported by the available evidence.
          {grounding.flagged.length > 0 && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="ml-1.5 inline-flex items-center gap-0.5 font-semibold text-indigo-700 hover:underline"
            >
              {open ? "Hide details" : `Show ${grounding.flagged.length} flagged item${grounding.flagged.length > 1 ? "s" : ""}`}
              <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
            </button>
          )}
        </span>
      </p>
      {open && (
        <ul className="ml-5 mt-1.5 list-disc space-y-0.5">
          {grounding.flagged.map((f, i) => (
            <li key={i} className="break-words">
              {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
