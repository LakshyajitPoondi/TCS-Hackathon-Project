// Mirrors backend/models/schemas.py exactly. Datetimes arrive as ISO strings.

export type Category = "machine" | "material" | "method" | "measurement" | "people" | "environment";
export type Subcause = "cooling" | "mechanical" | null;
export type Confidence = "high" | "medium" | "low";
export type AnalysisStatus = "complete" | "insufficient_evidence";
export type HealthStatus = "normal" | "watch" | "degraded";

export const ALL_CATEGORIES: Category[] = ["machine", "material", "method", "measurement", "people", "environment"];

// ---------- Incidents ----------

export interface IncidentRef {
  id: string;
  filename: string;
}

export interface IncidentSummary {
  id: string;
  line: string;
  machines: string[];
  machine_count: number;
  record_count: number;
  start_time: string;
  end_time: string;
  total_defects: number;
  total_downtime_min: number;
  event_codes: string[];
}

export interface SignalRecord {
  timestamp: string;
  machine: string | null;
  temperature: number | null;
  speed: number | null;
  vibration: number | null;
  motor_current: number | null;
  defect_count: number | null;
  downtime_min: number | null;
  event_code: string | null;
  batch: string | null;
  operator_note: string | null;
}

export interface SignalsResponse {
  incident_id: string;
  machines: string[];
  records: SignalRecord[];
}

// ---------- Analysis ----------

export interface Evidence {
  signal: string;
  description: string;
  value: number | string | null;
  machine: string | null;
}

export interface VerificationStep {
  chunk_id: string|null;
  page_or_section: string|null;
  step: string;
  source: string;
  source_title: string;
}

export interface Hypothesis {
  rank: number;
  category: Category;
  subcause: Subcause;
  confidence: Confidence;
  /** Internal only: used for ranking. Never shown in the UI. */
  score: number | null;
  supporting_evidence: Evidence[];
  contradicting_evidence: Evidence[];
  missing_checks: string[];
  verification_steps: VerificationStep[];
  narrative: string;
}

export interface CategoryEvidence {
  category: Category;
  supporting: Evidence[];
  contradicting: Evidence[];
}

export interface IncidentWindow {
  start: string;
  end: string;
  detected_by: string[];
}

export interface KPIs {
  defect_rate: number;
  total_defects: number;
  downtime_min: number;
  alarm_count: number;
  event_count: number;
  threshold_breaches: number;
}

export interface MachineHealth {
  machine: string;
  score: number;
  status: HealthStatus;
}

export interface SimilarCase {
  label:string;
  fix_applied:string;
  match_reasons:string[];
  case_id: string;
  confirmed_category: Category;
  confirmed_subcause: Subcause;
  shared_signals: string[];
  similarity_description: string;
}

export interface Grounding {
  sections:{section:string;passed:boolean;flagged:string[];replaced:boolean}[];
  passed: boolean;
  flagged: string[];
}

export interface AnalysisResponse {
  run_id:string;
  text_source:'llm'|'template';
  investigation:{mode:string;steps:number;max_steps:number;capped:boolean;denied_calls:number};
  retrieval_status:Record<string,string>;
  documents_accessed:{doc_id:string;title:string;version:string;doc_type:string;scope:string;matched_machine:string[];why_allowed:string;chunks:{chunk_id:string;page_or_section:string;score:number;snippet:string}[];used_for:string[]}[];
  documents_filtered_out:{doc_id:string;title:string;reason:string}[];
  incident_id: string;
  analysis_status: AnalysisStatus;
  incident_window: IncidentWindow | null;
  kpis: KPIs | null;
  machine_health: MachineHealth[];
  category_evidence: CategoryEvidence[];
  hypotheses: Hypothesis[];
  similar_cases: SimilarCase[];
  rca_draft: string;
  grounding: Grounding | null;
  validation_required: true;
  warning: string;
}

// ---------- Cases ----------

export interface SaveCaseRequest {
  fix_applied:string;
  lessons?:string;
  documents_used?:string[];
  incident_id: string;
  rca_draft: string;
  confirmed_category: Category;
  confirmed_subcause: Subcause;
  notes: string | null;
}

export interface SaveCaseResponse {
  status: "proposed";
  case_id: string;
}

// ---------- SOPs (GET /api/sops/{id}) ----------

export interface Sop {
  id: string;
  title: string;
  content: string;
}

// ---------- Evals (Phase 5; shape not final) ----------

export interface EvalsResponse {
  metrics?: Record<string, unknown>[] | Record<string, unknown>;
  cases?: Record<string, unknown>[];
}
