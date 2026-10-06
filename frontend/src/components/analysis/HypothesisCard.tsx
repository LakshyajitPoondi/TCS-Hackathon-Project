import { useId, useState } from "react";
import { Check, ChevronDown, ClipboardCheck, FileText, Square, X } from "lucide-react";
import type { Evidence, Hypothesis, VerificationStep } from "../../types/api";
import { categoryWithSubcause, fmtValue } from "../../lib/format";
import { ConfidenceBadge } from "../ui/Badge";

export function EvidenceList({ items, kind }: { items: Evidence[]; kind: "supporting" | "contradicting" }) {
  const supporting = kind === "supporting";
  if (!items.length) {
    return <p className="text-sm text-slate-500">{supporting ? "No supporting evidence." : "No contradicting evidence."}</p>;
  }
  return (
    <ul className="space-y-1.5">
      {items.map((e, i) => {
        const value = fmtValue(e.value);
        return (
          <li
            key={`${e.signal}-${i}`}
            className={`flex items-start gap-2.5 rounded-md px-3 py-2 text-sm ${supporting ? "bg-success-tint/60" : "bg-slate-100"}`}
          >
            <span className={`mt-0.5 shrink-0 ${supporting ? "text-success-ink" : "text-slate-500"}`}>
              {supporting ? <Check size={16} aria-label="Supports" /> : <X size={16} aria-label="Contradicts" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="rounded-full bg-white px-2 py-0.5 font-mono text-[11px] text-indigo-700">{e.signal}</span>
                {e.machine && <span className="font-mono text-[11px] font-semibold text-ink-700">{e.machine}</span>}
                {value && <span className="font-mono text-[11px] text-slate-500">value {value}</span>}
              </div>
              <p className="mt-1 break-words text-ink-700">{e.description}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function SopChip({ source, title, onOpen }: { source: string; title: string; onOpen: (id: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(source)}
      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-left text-xs font-semibold text-indigo-700 transition-colors duration-150 hover:border-indigo-500 hover:bg-white"
      aria-label={`Open source ${source}: ${title}`}
    >
      <FileText size={13} aria-hidden="true" className="shrink-0" />
      <span className="font-mono">{source}</span>
      <span className="truncate">· {title}</span>
    </button>
  );
}

function VerificationSteps({ steps, onOpenSop }: { steps: VerificationStep[]; onOpenSop: (id: string) => void }) {
  if (!steps.length) return <p className="text-sm text-slate-500">No verification actions retrieved.</p>;
  return (
    <ol className="space-y-2">
      {steps.map((s, i) => (
        <li key={i} className="flex gap-3 rounded-md border border-slate-200 bg-white px-3 py-2.5">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 font-mono text-[11px] font-semibold text-indigo-700">
            {i + 1}
          </span>
          <div className="min-w-0 flex-1 space-y-1.5">
            <p className="break-words text-sm text-ink-700">{s.step}</p>
            <SopChip source={s.source} title={s.source_title} onOpen={id=>onOpenSop(id+(s.chunk_id?'#'+s.chunk_id:''))} />
            <p className="text-xs text-slate-500">{s.page_or_section}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">{title}</h4>
      {children}
    </div>
  );
}

export function HypothesisCard({ h, onOpenSop }: { h: Hypothesis; onOpenSop: (id: string) => void }) {
  const leading = h.rank === 1;
  const [open, setOpen] = useState(leading);
  const bodyId = useId();

  return (
    <article
      className={`rounded-lg bg-white shadow-card transition-shadow duration-200 hover:shadow-hover ${
        leading ? "border-2 border-indigo-700" : "border border-slate-200"
      }`}
      aria-label={`Hypothesis ${h.rank}`}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex w-full flex-wrap items-center gap-3 rounded-lg p-4 text-left sm:p-5"
      >
        <span
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-mono text-base font-bold ${
            leading ? "bg-indigo-700 text-white" : "bg-indigo-50 text-indigo-700"
          }`}
          aria-hidden="true"
        >
          {h.rank}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 text-xs font-semibold text-slate-500">
            Hypothesis #{h.rank}
            {leading && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-indigo-700">Leading hypothesis</span>}
          </span>
          <span className="mt-0.5 block text-lg font-bold text-ink-900">{categoryWithSubcause(h.category, h.subcause)}</span>
        </span>
        <ConfidenceBadge confidence={h.confidence} />
        <ChevronDown
          size={20}
          aria-hidden="true"
          className={`shrink-0 text-slate-500 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
        <span className="sr-only">{open ? "Collapse details" : "Expand details"}</span>
      </button>

      <div id={bodyId} className={`grid transition-[grid-template-rows] duration-250 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        <div className="overflow-hidden" inert={!open}>
          <div className="space-y-5 border-t border-slate-200 px-4 pb-5 pt-4 sm:px-5">
            <p className="text-[15px] leading-relaxed text-ink-700">{h.narrative}</p>

            <div className="grid gap-5 lg:grid-cols-2">
              <Block title="Supporting evidence">
                <EvidenceList items={h.supporting_evidence} kind="supporting" />
              </Block>
              <Block title="Contradicting evidence">
                <EvidenceList items={h.contradicting_evidence} kind="contradicting" />
              </Block>
            </div>

            <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
              <Block title="Missing checks">
                {h.missing_checks.length ? (
                  <ul className="space-y-1.5">
                    {h.missing_checks.map((c, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-ink-700">
                        <Square size={15} className="mt-0.5 shrink-0 text-slate-500" aria-hidden="true" />
                        <span className="break-words">{c}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-500">No missing checks listed.</p>
                )}
              </Block>
              <Block title="Verification required">
                <div className="mb-2 flex items-center gap-1.5 text-xs text-slate-500">
                  <ClipboardCheck size={14} aria-hidden="true" />
                  Verification actions from SOP sources
                </div>
                <VerificationSteps steps={h.verification_steps} onOpenSop={onOpenSop} />
              </Block>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
