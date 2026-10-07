import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ArrowLeft, FileQuestion, Play } from "lucide-react";
import { analyzeIncident, getIncident, getSignals } from "../api/endpoints";
import { ApiError, errorMessage } from "../api/client";
import type { AnalysisResponse, IncidentSummary, SignalsResponse } from "../types/api";
import { fmtDateTime } from "../lib/format";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { Card, SectionTitle } from "../components/ui/Card";
import { Chip } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton, Spinner } from "../components/ui/Spinner";
import { useWarning } from "../components/layout/ValidationBanner";
import { SummaryCards, KpiCards, HealthCards } from "../components/analysis/SummaryCards";
import { SignalChart } from "../components/charts/SignalChart";
import { AnalysisComplete, GroundingNote, InsufficientEvidence } from "../components/analysis/StatusPanels";
import { HypothesisCard } from "../components/analysis/HypothesisCard";
import { SopModal } from "../components/analysis/SopModal";
import { CategoryEvidenceGrid } from "../components/analysis/CategoryEvidenceGrid";
import { SimilarCases } from "../components/analysis/SimilarCases";
import { DraftPanel } from "../components/analysis/DraftPanel";
import { SaveCaseModal } from "../components/analysis/SaveCaseModal";
import {useAuth} from '../auth';
import {request} from '../api/client';
import {InvestigationPanels} from '../components/analysis/InvestigationPanels';
import { Link } from 'react-router-dom';
import type { Draft, IncidentWorkflow } from '../types/workflow';
import { CaseStatusBadge, SourceBadge, StatusBadge } from '../components/ui/StatusBadge';

// UI wording only — not real backend stages.
const LOADING_LABELS = [
  "Analyzing production signals…",
  "Detecting incident window",
  "Ranking RCA hypotheses",
  "Retrieving verification procedures",
  "Checking similar cases",
];

function useCyclingLabel(active: boolean) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (!active) return setI(0);
    const t = window.setInterval(() => setI((n) => (n + 1) % LOADING_LABELS.length), 1400);
    return () => window.clearInterval(t);
  }, [active]);
  return LOADING_LABELS[i];
}

export function IncidentPage() {
  const { id = "" } = useParams();
  const {can}=useAuth();
  const { warning, setWarning } = useWarning();

  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [summaryError, setSummaryError] = useState<ApiError | Error | null>(null);
  const [signals, setSignals] = useState<SignalsResponse | null>(null);
  const [signalsError, setSignalsError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [baseline, setBaseline] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [workflow, setWorkflow] = useState<IncidentWorkflow | null>(null);
  const refreshWorkflow = () => request<IncidentWorkflow>('/api/incidents/'+encodeURIComponent(id)+'/workflow').then(setWorkflow).catch(()=>{});
  const [sopId, setSopId] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const resultsRef = useRef<HTMLDivElement>(null);
  const activeRun = useRef(0);
  const loadingLabel = useCyclingLabel(analyzing);

  useEffect(() => {
    let alive = true;
    activeRun.current++;
    const historyToken=activeRun.current;
    setAnalyzing(false);
    setSummary(null);
    setSummaryError(null);
    setSignals(null);
    setSignalsError(null);
    setAnalysis(null);
    setAnalyzeError(null);
    setDraft("");
    setBaseline("");
    setDrafts([]);
    setWorkflow(null);
    request<IncidentWorkflow>('/api/incidents/'+encodeURIComponent(id)+'/workflow').then(w=>alive&&setWorkflow(w)).catch(()=>{});
    const savedDrafts=request<Draft[]>('/api/incidents/'+encodeURIComponent(id)+'/drafts').catch(()=>[] as Draft[]);
    getIncident(id)
      .then((s) => alive && setSummary(s))
      .catch((e) => alive && setSummaryError(e));
    getSignals(id)
      .then((s) => alive && setSignals(s))
      .catch((e) => alive && setSignalsError(errorMessage(e)));
    request<{run_id:string}[]>('/api/analyses?incident_id='+encodeURIComponent(id)).then(async runs=>{
      const versions=await savedDrafts;
      if(!alive||historyToken!==activeRun.current)return;
      setDrafts(versions);
      const result=runs.length?await request<AnalysisResponse>('/api/analyses/'+runs[0].run_id):null;
      if(!alive||historyToken!==activeRun.current)return;
      if(result)setAnalysis(result);
      // A saved draft survives reloads; otherwise start from the analysis draft.
      const text=versions[0]?.content??result?.rca_draft??'';
      setDraft(text);setBaseline(text);
    }).catch(()=>{});
    return () => {
      alive = false;
    };
  }, [id]);

  const run = async () => {
    const runToken = ++activeRun.current;
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const res = await analyzeIncident(id);
      if (runToken !== activeRun.current) return;
      setAnalysis(res);
      setDraft(res.rca_draft); // a new analysis starts a new draft; saved versions stay in the history
      setBaseline(res.rca_draft);
      void refreshWorkflow();
      setWarning(res.warning);
      window.dispatchEvent(new Event('rca-llm-used'));
      window.setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (e) {
      if (runToken === activeRun.current) setAnalyzeError(errorMessage(e));
    } finally {
      if (runToken === activeRun.current) setAnalyzing(false);
    }
  };

  if (summaryError) {
    const notFound = summaryError instanceof ApiError && summaryError.status === 404;
    return notFound ? (
      <EmptyState icon={<FileQuestion size={24} />} title="Incident not found">
        <p>
          No incident with id <span className="font-mono font-semibold text-ink-900">{id}</span> exists.
        </p>
        <div className="mt-4">
          <Button to="/" variant="outline" icon={<ArrowLeft size={16} aria-hidden="true" />}>
            Back to incidents
          </Button>
        </div>
      </EmptyState>
    ) : (
      <Alert tone="danger" title="Could not load this incident">
        {summaryError.message}
      </Alert>
    );
  }

  return (
    <div className="fade-in space-y-6">
      <Button to="/incidents" variant="ghost" size="sm" icon={<ArrowLeft size={15} aria-hidden="true" />} className="-ml-2">
        All incidents
      </Button>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-indigo-700">Incident investigation</p>
          <h1 className="mt-1 break-all font-mono text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl">{id}</h1>
          {workflow && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge status={workflow.status} />
              <SourceBadge source={workflow.source} />
              {workflow.cases.map((c) => (
                <Link key={c.case_id} to={`/cases/${c.case_id}`} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-50">
                  Case {c.case_id.slice(0, 13)} <CaseStatusBadge status={c.status} />
                </Link>
              ))}
            </div>
          )}
          {summary ? (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <span className="font-mono font-semibold text-ink-700">{summary.line}</span>
              <span aria-hidden="true">·</span>
              {summary.machines.map((m) => (
                <Chip key={m}>{m}</Chip>
              ))}
              <span aria-hidden="true">·</span>
              <span className="font-mono text-[13px]">
                {fmtDateTime(summary.start_time)} → {fmtDateTime(summary.end_time)}
              </span>
            </div>
          ) : (
            <Skeleton className="mt-3 h-6 w-80 max-w-full" />
          )}
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          {can('analyze')&&<Button
            size="lg"
            onClick={run}
            loading={analyzing}
            arrow={!analyzing}
            disabled={!summary}
            icon={!analyzing ? <Play size={18} aria-hidden="true" /> : undefined}
          >
            {analyzing ? "Analyzing…" : analysis ? "Re-run RCA Analysis" : "Run RCA Analysis"}
          </Button>}
          {analyzing && (
            <p className="text-sm text-slate-600" aria-live="polite">
              {loadingLabel}
            </p>
          )}
        </div>
      </div>

      {summary ? (
        <SummaryCards summary={summary} />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      )}

      {signalsError ? (
        <Alert tone="warning" title="Signals unavailable">
          {signalsError}
        </Alert>
      ) : signals ? (
        <SignalChart data={signals} window={analysis?.incident_window ?? null} />
      ) : (
        <Card className="flex h-80 items-center justify-center">
          <Spinner label="Loading signals…" />
        </Card>
      )}

      {analyzeError && (
        <Alert
          tone="danger"
          title="Analysis failed"
          action={
            <Button size="sm" variant="outline" onClick={run}>
              Retry
            </Button>
          }
        >
          {analyzeError}
        </Alert>
      )}

      {!analysis && !analyzing && !analyzeError && summary && (
        <Card className="p-5 text-sm text-slate-600">
          Run the RCA analysis to detect the incident window, rank hypotheses against the evidence and retrieve SOP-backed
          verification actions.
        </Card>
      )}

      {analysis && (
        <div ref={resultsRef} className="scroll-mt-28 space-y-8">
          {analysis.analysis_status === "insufficient_evidence" ? (
            <InsufficientEvidence window={analysis.incident_window} />
          ) : (
            <AnalysisComplete window={analysis.incident_window} />
          )}

          {analysis.kpis && <KpiCards kpis={analysis.kpis} />}
          <HealthCards health={analysis.machine_health} />

          {analysis.analysis_status === "complete" && (
            <section>
              <SectionTitle
                title="Ranked hypotheses"
                sub="Possible contributors ranked by the available evidence. Each requires verification before corrective action."
              />
              {analysis.hypotheses.length > 0 ? (
                <div className="space-y-4">
                  {analysis.hypotheses.map((h) => (
                    <HypothesisCard key={`${h.rank}-${h.category}`} h={h} onOpenSop={setSopId} />
                  ))}
                </div>
              ) : (
                <Card className="p-5 text-sm text-slate-600">No hypotheses were returned for this incident.</Card>
              )}
              <div className="mt-3">
                <GroundingNote grounding={analysis.grounding} />
              </div>
            </section>
          )}

          <CategoryEvidenceGrid items={analysis.category_evidence} />
          <InvestigationPanels analysis={analysis}/>
          <SimilarCases cases={analysis.similar_cases} />
          <DraftPanel
            incidentId={id}
            runId={analysis.run_id}
            value={draft}
            baseline={baseline}
            onChange={setDraft}
            drafts={drafts}
            onSaved={(d) => { setDrafts((all) => [d, ...all]); setDraft(d.content); setBaseline(d.content); void refreshWorkflow(); }}
            warning={analysis.warning || warning}
            onPropose={() => setSaveOpen(true)}
          />
        </div>
      )}

      <SopModal sopId={sopId} onClose={() => setSopId(null)} />
      <SaveCaseModal open={saveOpen} onClose={() => { setSaveOpen(false); void refreshWorkflow(); }} incidentId={id} draft={draft} analysis={analysis} />
    </div>
  );
}
