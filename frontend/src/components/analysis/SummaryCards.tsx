import type { ReactNode } from "react";
import type { IncidentSummary, KPIs, MachineHealth } from "../../types/api";
import { fmtDateTime, fmtNumber } from "../../lib/format";
import { Card, SectionTitle } from "../ui/Card";
import { HealthBadge, healthBarClass } from "../ui/Badge";

function Stat({ label, value, mono = true, sub }: { label: string; value: ReactNode; mono?: boolean; sub?: string }) {
  return (
    <Card className="min-w-0 p-4">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className={`mt-1 break-words text-lg font-bold text-ink-900 ${mono ? "font-mono" : ""}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </Card>
  );
}

export function SummaryCards({ summary }: { summary: IncidentSummary }) {
  return (
    <section aria-label="Incident summary" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
      <Stat label="Line" value={summary.line} />
      <Stat label="Machines" value={summary.machine_count} />
      <Stat label="Records" value={summary.record_count} />
      <Stat label="Total defects" value={summary.total_defects} />
      <Stat label="Downtime" value={`${fmtNumber(summary.total_downtime_min, 1)} min`} />
      <Stat label="Start" value={<span className="text-sm">{fmtDateTime(summary.start_time)}</span>} />
      <Stat label="End" value={<span className="text-sm">{fmtDateTime(summary.end_time)}</span>} />
    </section>
  );
}

export function KpiCards({ kpis }: { kpis: KPIs }) {
  return (
    <section aria-labelledby="kpi-title">
      <h2 id="kpi-title" className="mb-3 text-sm font-semibold text-ink-700">
        Incident-window KPIs
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Defect rate" value={fmtNumber(kpis.defect_rate)} sub="defects per record" />
        <Stat label="Total defects" value={kpis.total_defects} />
        <Stat label="Downtime" value={`${fmtNumber(kpis.downtime_min, 1)} min`} />
        <Stat label="Alarms" value={kpis.alarm_count} />
        <Stat label="Events" value={kpis.event_count} />
        <Stat label="Threshold breaches" value={kpis.threshold_breaches} />
      </div>
    </section>
  );
}

export function HealthCards({ health }: { health: MachineHealth[] }) {
  return (
    <section>
      <SectionTitle
        title="Machine health"
        sub="Machine-health scores are contextual evidence relative to the incident baseline, not failure probabilities or Remaining Useful Life predictions."
      />
      {health.length === 0 ? (
        <p className="text-sm text-slate-500">Not enough records to compute machine-health context.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {health.map((m) => (
            <Card key={m.machine} className="p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-sm font-semibold text-ink-900">{m.machine}</span>
                <HealthBadge status={m.status} />
              </div>
              <p className="mt-2 font-mono text-2xl font-bold text-ink-900">
                {fmtNumber(m.score, 1)}
                <span className="text-sm font-medium text-slate-500"> / 100</span>
              </p>
              <div
                className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"
                role="meter"
                aria-label={`${m.machine} health score`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={m.score}
              >
                <div className={`h-full rounded-full ${healthBarClass(m.status)}`} style={{ width: `${m.score}%` }} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
