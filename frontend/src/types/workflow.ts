// Mirrors backend/services/workflow.py (incident registry, derived status, drafts, dashboard).
import type { Category, Confidence, Subcause } from "./api";

export type IncidentStatus = "new" | "analysed" | "draft_saved" | "case_proposed" | "case_approved" | "case_rejected";
export type IncidentSource = "sample" | "uploaded";

export interface TopHypothesis {
  category: Category | null;
  subcause?: Subcause;
  confidence?: Confidence;
  status?: string;
}

export interface IncidentRow {
  id: string;
  filename: string;
  source: IncidentSource;
  source_label: string;
  line: string;
  machines: string[];
  affected_machines: string[] | null;
  start_time: string;
  end_time: string;
  record_count: number;
  uploaded_by_name: string | null;
  created_at: string | null;
  status: IncidentStatus;
  status_label: string;
  top_hypothesis: TopHypothesis | null;
  last_run_id: string | null;
  last_analysed_at: string | null;
  draft_version: number | null;
  last_activity: string | null;
  case_ids: string[];
}

export interface IncidentCaseLink {
  case_id: string;
  status: string;
  confirmed_category: Category | null;
  confirmed_subcause: Subcause;
  created_at: string;
  proposer_name: string | null;
  approver_name: string | null;
}

export interface IncidentWorkflow extends IncidentRow {
  cases: IncidentCaseLink[];
}

export interface Draft {
  id: number;
  incident_id: string;
  run_id: string | null;
  version: number;
  content: string;
  note: string | null;
  author_id: string | null;
  author_name: string | null;
  created_at: string;
}

export interface PendingItem {
  kind: "case_review" | "document_mapping" | "analyse" | "propose";
  title: string;
  detail: string;
  link: string;
  created_at: string | null;
}

export interface Dashboard {
  kpis: {
    incidents_total: number;
    incidents_by_status: Record<IncidentStatus, number>;
    incidents_uploaded: number;
    cases_pending: number;
    cases_approved: number;
    documents_pending: number;
    llm_calls_today: number;
    llm_daily_budget: number;
    llm_blocked_until: string | null;
  };
  status_labels: Record<IncidentStatus, string>;
  recent_incidents: IncidentRow[];
  pending: PendingItem[];
}
