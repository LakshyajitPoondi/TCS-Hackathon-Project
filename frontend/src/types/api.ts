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
  case_id: string;
  confirmed_category: Category;
  confirmed_subcause: Subcause;
  shared_signals: string[];
  similarity_description: string;
}

export interface Grounding {
  passed: boolean;
  flagged: string[];
}

export interface AnalysisResponse {
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
  incident_id: string;
  rca_draft: string;
  confirmed_category: Category;
  confirmed_subcause: Subcause;
  notes: string | null;
}

export interface SaveCaseResponse {
  status: "saved";
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
