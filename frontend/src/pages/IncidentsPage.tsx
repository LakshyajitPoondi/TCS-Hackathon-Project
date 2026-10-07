import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileSpreadsheet, Upload } from "lucide-react";
import { listIncidents } from "../api/endpoints";
import { errorMessage } from "../api/client";
import type { IncidentRef } from "../types/api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Skeleton } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import {useAuth} from '../auth';

export function IncidentsPage() {
  const {can}=useAuth();
  const [incidents, setIncidents] = useState<IncidentRef[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    setError(null);
    setIncidents(null);
    listIncidents()
      .then(setIncidents)
      .catch((e) => setError(errorMessage(e)));
  }, [reload]);

  return (
    <div className="fade-in space-y-6">
      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold tracking-wide text-indigo-700">Analysis</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink-900 sm:text-[34px]">Production Intelligence &amp; RCA</h1>
          <p className="mt-2 text-[15px] leading-relaxed text-slate-600">
            Investigate production incidents using evidence-driven RCA hypotheses, machine-health context and SOP-backed verification.
          </p>
        </div>
        {can('upload')&&<Button variant="secondary" to="/upload" icon={<Upload size={18} aria-hidden="true" />}>
          Upload CSV
        </Button>}
      </div>

      {error && (
        <Alert
          tone="danger"
          title="Could not load incidents"
          action={
            <Button size="sm" variant="outline" onClick={() => setReload((n) => n + 1)}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {!error && incidents === null && (
        <Card className="space-y-3 p-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </Card>
      )}

      {incidents && incidents.length === 0 && (
        <EmptyState icon={<FileSpreadsheet size={24} />} title="No incidents yet">
          Upload a production CSV to start an investigation.
        </EmptyState>
      )}

      {incidents && incidents.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <caption className="sr-only">Incidents</caption>
              <thead className="bg-surface-alt text-[13px] font-semibold text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3">Incident</th>
                  <th scope="col" className="px-5 py-3">File</th>
                  <th scope="col" className="px-5 py-3 text-right">
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => navigate(`/incidents/${inc.id}`)}
                    className="cursor-pointer border-t border-slate-200 transition-colors duration-150 hover:bg-indigo-50"
                  >
                    <td className="px-5 py-3 font-mono text-[13px] font-semibold text-ink-900">{inc.id}</td>
                    <td className="px-5 py-3 font-mono text-[13px] text-slate-600">{inc.filename}</td>
                    <td className="px-5 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" to={`/incidents/${inc.id}`} arrow>
                        Open<span className="sr-only"> {inc.id}</span>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
