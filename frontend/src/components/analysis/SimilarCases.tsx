import { History } from "lucide-react";
import type { SimilarCase } from "../../types/api";
import { categoryWithSubcause } from "../../lib/format";
import { Card, SectionTitle } from "../ui/Card";
import { Chip } from "../ui/Badge";

export function SimilarCases({ cases }: { cases: SimilarCase[] }) {
  return (
    <section>
      <SectionTitle
        title="Similar Past Cases"
        sub="Historical cases provide supporting context only and do not determine the current RCA ranking."
      />
      {cases.length === 0 ? (
        <Card className="flex items-center gap-3 p-5 text-sm text-slate-600">
          <History size={18} className="shrink-0 text-slate-500" aria-hidden="true" />
          No sufficiently similar historical cases were found.
        </Card>
      ) : (
        <Card className="divide-y divide-slate-200">
          {cases.map((c) => (
            <div key={c.case_id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:gap-5">
              <div className="shrink-0 sm:w-28">
                <p className="font-mono text-sm font-bold text-ink-900">{c.case_id}</p>
              </div>
              <div className="min-w-0 flex-1 space-y-1.5">
                <p className="text-sm text-ink-700">
                  <span className="text-slate-500">{c.label} · Past category: </span>
                  <span className="font-semibold">{categoryWithSubcause(c.confirmed_category, c.confirmed_subcause)}</span>
                </p>
                <p className="text-sm text-slate-600">{c.similarity_description}</p>
                <p className="text-sm">Matched: {c.match_reasons.join(', ')}</p>
                <p className="text-sm">Fix applied: {c.fix_applied}</p>
                <div className="flex flex-wrap gap-1.5" aria-label="Shared signals">
                  {c.shared_signals.map((s) => (
                    <Chip key={s}>{s}</Chip>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </Card>
      )}
    </section>
  );
}
