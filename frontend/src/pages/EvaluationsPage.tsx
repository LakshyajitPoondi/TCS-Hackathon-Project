import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { getEvals } from "../api/endpoints";
import { ApiError, errorMessage } from "../api/client";
import type { EvalsResponse } from "../types/api";
import { Alert } from "../components/ui/Alert";
import { Card, SectionTitle } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Spinner } from "../components/ui/Spinner";

type Rows = Record<string, unknown>[];

const toRows = (v: EvalsResponse["metrics"]): Rows =>
  Array.isArray(v) ? v : v ? Object.entries(v).map(([metric, value]) => ({ metric, value })) : [];

const cell = (v: unknown) =>
  v === null || v === undefined ? "–" : typeof v === "object" ? JSON.stringify(v) : String(v);

/** Generic table: renders whatever columns the Phase 5 payload provides. */
function DataTable({ title, rows }: { title: string; rows: Rows }) {
  if (!rows.length) return null;
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  return (
    <section>
      <SectionTitle title={title} />
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-alt text-[13px] font-semibold text-slate-500">
              <tr>
                {cols.map((c) => (
                  <th key={c} scope="col" className="whitespace-nowrap px-4 py-3">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-slate-200">
                  {cols.map((c) => (
                    <td key={c} className="px-4 py-2.5 font-mono text-[13px] text-ink-700">
                      {cell(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </section>
  );
}

export function EvaluationsPage() {
  const [data, setData] = useState<EvalsResponse | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    getEvals()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e : new Error(errorMessage(e))));
  }, []);

  const pending = error instanceof ApiError && error.status === 501;

  return (
    <div className="fade-in space-y-6">
      <div>
        <p className="text-sm font-semibold text-indigo-700">Evaluations</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink-900">Evaluation results</h1>
      </div>

      {!data && !error && <Spinner label="Loading evaluation results…" />}

      {pending && (
        <EmptyState aura icon={<CheckCircle2 size={24} />} title="Evaluation dashboard coming in Phase 5">
          Metrics will be computed against the answer key for the curated incidents and shown here, with per-case results.
        </EmptyState>
      )}

      {error && !pending && (
        <Alert tone="danger" title="Could not load evaluation results">
          {error.message}
        </Alert>
      )}

      {data && (
        <>
          <DataTable title="Metrics" rows={toRows(data.metrics)} />
          <DataTable title="Per-case results" rows={data.cases ?? []} />
        </>
      )}
    </div>
  );
}
