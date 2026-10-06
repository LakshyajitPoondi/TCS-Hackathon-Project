import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import type { IncidentWindow, SignalRecord, SignalsResponse } from "../../types/api";
import { fmtDateTime, fmtNumber, fmtTime } from "../../lib/format";
import { Card } from "../ui/Card";

const SIGNALS = [
  { key: "temperature", label: "Temperature" },
  { key: "speed", label: "Speed" },
  { key: "vibration", label: "Vibration" },
  { key: "motor_current", label: "Motor current" },
  { key: "defect_count", label: "Defects" },
] as const;
type SignalKey = (typeof SIGNALS)[number]["key"];

// Tokens resolved once; SVG attributes can't reliably use var().
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const isMarkerEvent = (code: string) => code === "CHG" || code === "SHIFT_CHG" || code.startsWith("ALM_");

type Row = { ts: string; events: string[] } & Record<string, number | string | string[] | null>;

function buildRows(records: SignalRecord[], signal: SignalKey): Row[] {
  const byTs = new Map<string, Row>();
  for (const r of records) {
    let row = byTs.get(r.timestamp);
    if (!row) {
      row = { ts: r.timestamp, events: [] } as Row;
      byTs.set(r.timestamp, row);
    }
    if (r.machine) row[r.machine] = r[signal];
    if (r.event_code && isMarkerEvent(r.event_code)) {
      row.events.push(r.machine ? `${r.event_code} · ${r.machine}` : r.event_code);
    }
  }
  return Array.from(byTs.values()).sort((a, b) => a.ts.localeCompare(b.ts));
}

/** Snap a window bound onto an existing x category so ReferenceArea can place it. */
function snap(rows: Row[], iso: string, dir: "start" | "end") {
  if (!rows.length) return undefined;
  if (dir === "start") return (rows.find((r) => r.ts >= iso) ?? rows[rows.length - 1]).ts;
  return ([...rows].reverse().find((r) => r.ts <= iso) ?? rows[0]).ts;
}

function ChartTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Row;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-card">
      <p className="mb-1 font-mono font-semibold text-ink-900">{fmtDateTime(String(label))}</p>
      {payload.map((p) => (
        <p key={String(p.dataKey)} className="flex items-center gap-2 font-mono text-ink-700">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} aria-hidden="true" />
          {String(p.dataKey)}: {typeof p.value === "number" ? fmtNumber(p.value) : "–"}
        </p>
      ))}
      {row.events.length > 0 && (
        <div className="mt-1.5 border-t border-slate-200 pt-1.5">
          {row.events.map((e) => (
            <p key={e} className="font-mono font-semibold text-warning-ink">
              ⚑ {e}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function SignalChart({ data, window }: { data: SignalsResponse; window: IncidentWindow | null }) {
  const [signal, setSignal] = useState<SignalKey>("temperature");
  const rows = useMemo(() => buildRows(data.records, signal), [data.records, signal]);
  const colors = useMemo(() => ["--series-1", "--series-2", "--series-3", "--series-4"].map(css), []);
  const tok = useMemo(
    () => ({ grid: css("--color-slate-200"), axis: css("--color-slate-500"), window: css("--color-window"), event: css("--color-warning"), danger: css("--color-danger-ink") }),
    [],
  );
  const eventRows = rows.filter((r) => r.events.length > 0);
  const x1 = window ? snap(rows, window.start, "start") : undefined;
  const x2 = window ? snap(rows, window.end, "end") : undefined;

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-ink-900">Production signals</h2>
        <div role="radiogroup" aria-label="Signal" className="flex flex-wrap gap-1 rounded-full bg-slate-100 p-1">
          {SIGNALS.map((s) => (
            <button
              key={s.key}
              role="radio"
              aria-checked={signal === s.key}
              onClick={() => setSignal(s.key)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors duration-150 ${
                signal === s.key ? "bg-white text-indigo-700 shadow-card" : "text-ink-700 hover:text-indigo-700"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-700" aria-label="Legend">
        {data.machines.map((m, i) => (
          <span key={m} className="inline-flex items-center gap-1.5 font-mono">
            <span className="h-0.5 w-4 rounded" style={{ background: colors[i % colors.length] }} aria-hidden="true" />
            {m}
          </span>
        ))}
        {x1 && x2 && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-4 rounded-sm bg-window ring-1 ring-danger/30" aria-hidden="true" />
            Incident window
          </span>
        )}
        {window && eventRows.length > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-0 border-l border-dashed border-warning-ink" aria-hidden="true" />
            Event marker (CHG / SHIFT_CHG / alarm)
          </span>
        )}
      </div>

      <div className="h-60 sm:h-80" role="img" aria-label={`${SIGNALS.find((s) => s.key === signal)!.label} by machine over time`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 18, right: 12, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke={tok.grid} strokeDasharray="3 3" />
            <XAxis
              dataKey="ts"
              tickFormatter={fmtTime}
              minTickGap={40}
              tick={{ fontSize: 11, fill: tok.axis, fontFamily: "JetBrains Mono, monospace" }}
              tickLine={false}
              axisLine={{ stroke: tok.grid }}
            />
            <YAxis
              width={48}
              tick={{ fontSize: 11, fill: tok.axis, fontFamily: "JetBrains Mono, monospace" }}
              tickLine={false}
              axisLine={false}
              domain={["auto", "auto"]}
            />
            {x1 && x2 && (
              <ReferenceArea
                x1={x1}
                x2={x2}
                fill={tok.window}
                fillOpacity={1}
                ifOverflow="extendDomain"
                label={{ value: "Incident window", position: "insideTop", fill: tok.danger, fontSize: 11, fontWeight: 600 }}
              />
            )}
            {window &&
              eventRows.map((r) => (
                <ReferenceLine key={r.ts} x={r.ts} stroke={tok.event} strokeDasharray="4 3" strokeWidth={1} />
              ))}
            <Tooltip content={ChartTooltip} cursor={{ stroke: tok.axis, strokeWidth: 1 }} />
            {data.machines.map((m, i) => (
              <Line
                key={m}
                dataKey={m}
                name={m}
                type="monotone"
                stroke={colors[i % colors.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
