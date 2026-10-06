import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FileSpreadsheet, Trash2, Upload, XCircle } from "lucide-react";
import { uploadIncident } from "../api/endpoints";
import { errorMessage } from "../api/client";
import { fmtBytes } from "../lib/format";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Chip } from "../components/ui/Badge";

// Mirrors backend EXPECTED_COLUMNS (backend/core/config.py).
const REQUIRED_COLUMNS = [
  "timestamp",
  "line",
  "machine",
  "event_code",
  "temperature",
  "speed",
  "vibration",
  "motor_current",
  "defect_count",
  "downtime_min",
  "batch",
  "operator_note",
];

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const choose = (f: File | undefined) => {
    setError(null);
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Only .csv files are supported.");
      return;
    }
    setFile(f);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    choose(e.dataTransfer.files?.[0]);
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const ref = await uploadIncident(file);
      navigate(`/incidents/${ref.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setUploading(false);
    }
  };

  return (
    <div className="fade-in mx-auto max-w-[720px] space-y-6">
      <div>
        <p className="text-sm font-semibold text-indigo-700">Upload data</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink-900">Upload a production CSV</h1>
        <p className="mt-2 text-[15px] text-slate-600">
          The file is validated, stored as a new incident and opened in the same RCA workflow as built-in incidents.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors duration-150 sm:p-10 ${
          dragOver ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-surface-alt"
        }`}
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-700" aria-hidden="true">
          <Upload size={24} />
        </div>
        <p className="mt-4 font-semibold text-ink-900">Drop a CSV or browse</p>
        <p className="mt-1 text-sm text-slate-500">One incident per file · .csv only</p>
        <input
          ref={inputRef}
          id="csv-input"
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(e) => {
            choose(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button variant="outline" size="sm" className="mt-4" onClick={() => inputRef.current?.click()}>
          Browse files
        </Button>

        {file && (
          <div className="mx-auto mt-6 flex max-w-lg flex-wrap items-center gap-3 rounded-md border border-slate-200 bg-white p-3 text-left">
            <FileSpreadsheet size={20} className="shrink-0 text-indigo-700" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-sm font-semibold text-ink-900">{file.name}</p>
              <p className="text-xs text-slate-500">{fmtBytes(file.size)}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setFile(null);
                setError(null);
              }}
              disabled={uploading}
              className="rounded-full p-2 text-slate-500 hover:bg-slate-100 hover:text-danger-ink disabled:opacity-45"
              aria-label={`Remove ${file.name}`}
            >
              <Trash2 size={17} aria-hidden="true" />
            </button>
            <Button size="sm" onClick={upload} loading={uploading} arrow>
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </div>
        )}

        {error && (
          <div role="alert" className="mx-auto mt-5 flex max-w-lg items-start gap-2 rounded-md border-l-4 border-danger bg-danger-tint px-4 py-3 text-left text-sm text-ink-900">
            <XCircle size={18} className="mt-0.5 shrink-0 text-danger-ink" aria-hidden="true" />
            <div className="min-w-0 break-words">
              <p className="font-semibold">Upload rejected</p>
              <p className="mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      <Card className="p-5">
        <h2 className="font-bold text-ink-900">Required columns</h2>
        <p className="mt-1 text-sm text-slate-500">The CSV header must contain all {REQUIRED_COLUMNS.length} columns.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {REQUIRED_COLUMNS.map((c) => (
            <Chip key={c}>{c}</Chip>
          ))}
        </div>
      </Card>
    </div>
  );
}
