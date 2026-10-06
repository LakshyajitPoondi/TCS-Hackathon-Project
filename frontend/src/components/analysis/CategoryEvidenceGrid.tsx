import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { ALL_CATEGORIES, type CategoryEvidence } from "../../types/api";
import { categoryLabel } from "../../lib/format";
import { SectionTitle } from "../ui/Card";
import { EvidenceList } from "./HypothesisCard";

function Tile({ ce }: { ce: CategoryEvidence }) {
  const [open, setOpen] = useState(false);
  const active = ce.supporting.length > 0;
  const total = ce.supporting.length + ce.contradicting.length;
  return (
    <div
      className={`rounded-lg border p-4 transition-colors duration-150 ${
        active ? "border-slate-200 bg-white shadow-card" : "border-dashed border-slate-300 bg-surface-alt"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className={`font-bold ${active ? "text-ink-900" : "text-slate-500"}`}>{categoryLabel(ce.category)}</h3>
        {!active && <span className="text-[11px] font-semibold text-slate-500">No support</span>}
      </div>
      <dl className="mt-2 flex gap-4 text-sm">
        <div>
          <dt className="text-xs text-slate-500">✓ Supporting</dt>
          <dd className="font-mono font-semibold text-ink-900">{ce.supporting.length}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">✗ Contradicting</dt>
          <dd className="font-mono font-semibold text-ink-900">{ce.contradicting.length}</dd>
        </div>
      </dl>
      {total > 0 && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:underline"
        >
          {open ? "Hide evidence" : "Show evidence"}
          <span className="sr-only"> for {categoryLabel(ce.category)}</span>
          <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
        </button>
      )}
      {open && (
        <div className="fade-in mt-3 space-y-2">
          {ce.supporting.length > 0 && <EvidenceList items={ce.supporting} kind="supporting" />}
          {ce.contradicting.length > 0 && <EvidenceList items={ce.contradicting} kind="contradicting" />}
        </div>
      )}
    </div>
  );
}

export function CategoryEvidenceGrid({ items }: { items: CategoryEvidence[] }) {
  // Always 6 tiles in the API's fixed order; no frontend ranking.
  const tiles = ALL_CATEGORIES.map((c) => items.find((i) => i.category === c) ?? { category: c, supporting: [], contradicting: [] });
  return (
    <section>
      <SectionTitle title="Evidence by RCA Category" sub="Supporting and contradicting signals observed for each category." />
      <div className="grid grid-cols-1 items-start gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map((ce) => (
          <Tile key={ce.category} ce={ce} />
        ))}
      </div>
    </section>
  );
}
