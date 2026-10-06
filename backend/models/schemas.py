"""All Pydantic models. The React types mirror this file, so keep names stable (plan.md section 5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.core.config import WARNING

Category = Literal["machine", "material", "method", "measurement", "people", "environment"]
Subcause = Literal["cooling", "mechanical"] | None
Confidence = Literal["high", "medium", "low"]
AnalysisStatus = Literal["complete", "insufficient_evidence"]
HealthStatus = Literal["normal", "watch", "degraded"]

ALL_CATEGORIES: tuple[str, ...] = ("machine", "material", "method", "measurement", "people", "environment")


# ---------- Incidents ----------

class IncidentRef(BaseModel):
    id: str
    filename: str


class IncidentSummary(BaseModel):
    id: str
    line: str
    machines: list[str]
    machine_count: int
    record_count: int
    start_time: datetime
    end_time: datetime
    total_defects: int
    total_downtime_min: float
    event_codes: list[str]


class SignalRecord(BaseModel):
    timestamp: str
    machine: str | None
    temperature: float | None
    speed: float | None
    vibration: float | None
    motor_current: float | None
    defect_count: float | None
    downtime_min: float | None
    event_code: str | None
    batch: str | None
    operator_note: str | None


class SignalsResponse(BaseModel):
    incident_id: str
    machines: list[str]
    records: list[SignalRecord]


# ---------- Analysis ----------

class Evidence(BaseModel):
    signal: str
    description: str
    value: float | str | None = None
    machine: str | None = None


class VerificationStep(BaseModel):
    chunk_id: str | None = None
    page_or_section: str | None = None
    step: str
    source: str  # SOP id, e.g. "SOP-007"
    source_title: str


class Hypothesis(BaseModel):
    rank: int = Field(ge=1, le=3)
    category: Category
    subcause: Subcause = None
    confidence: Confidence
    score: float | None = None
    """Internal only: used for ranking. Never shown in the UI, never rendered as a percentage."""
    supporting_evidence: list[Evidence]
    contradicting_evidence: list[Evidence]
    missing_checks: list[str]
    verification_steps: list[VerificationStep]
    narrative: str


class CategoryEvidence(BaseModel):
    category: Category
    supporting: list[Evidence]
    contradicting: list[Evidence]


class IncidentWindow(BaseModel):
    start: datetime
    end: datetime
    detected_by: list[str]


class KPIs(BaseModel):
    defect_rate: float
    total_defects: int
    downtime_min: float
    alarm_count: int
    event_count: int
    threshold_breaches: int


class MachineHealth(BaseModel):
    machine: str
    score: float = Field(ge=0, le=100)
    status: HealthStatus


class SimilarCase(BaseModel):
    label: str = 'synthetic seed'
    fix_applied: str = ''
    match_reasons: list[str] = Field(default_factory=list)
    case_id: str
    confirmed_category: Category  # past, engineer-validated case
    confirmed_subcause: Subcause = None
    shared_signals: list[str]
    similarity_description: str


class Grounding(BaseModel):
    sections: list[dict] = Field(default_factory=list)
    passed: bool
    flagged: list[str]


class AnalysisResponse(BaseModel):
    investigation: dict = Field(default_factory=dict)
    documents_accessed: list[dict] = Field(default_factory=list)
    documents_filtered_out: list[dict] = Field(default_factory=list)
    retrieval_status: dict = Field(default_factory=dict)
    run_id: str | None = None
    text_source: Literal['llm', 'template'] = 'template'
    incident_id: str
    analysis_status: AnalysisStatus
    incident_window: IncidentWindow | None
    kpis: KPIs | None
    machine_health: list[MachineHealth]
    category_evidence: list[CategoryEvidence]
    hypotheses: list[Hypothesis] = Field(max_length=3)
    similar_cases: list[SimilarCase]
    rca_draft: str
    grounding: Grounding | None
    validation_required: Literal[True] = True
    warning: str = WARNING

    @model_validator(mode="after")
    def _check_contract(self) -> "AnalysisResponse":
        if self.analysis_status == "insufficient_evidence" and self.hypotheses:
            raise ValueError("hypotheses must be empty when analysis_status is insufficient_evidence")
        if sorted(c.category for c in self.category_evidence) != sorted(ALL_CATEGORIES):
            raise ValueError("category_evidence must contain each of the 6 categories exactly once")
        return self


# ---------- Cases ----------

class SaveCaseRequest(BaseModel):
    fix_applied: str = Field(min_length=3, max_length=4000)
    lessons: str = Field(default='', max_length=4000)
    documents_used: list[str] = Field(default_factory=list)
    incident_id: str
    rca_draft: str
    confirmed_category: Category
    confirmed_subcause: Subcause = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_subcause(self) -> "SaveCaseRequest":
        if self.confirmed_category == "machine" and self.confirmed_subcause not in ("cooling", "mechanical"):
            raise ValueError("confirmed_subcause must be 'cooling' or 'mechanical' when confirmed_category is 'machine'")
        if self.confirmed_category != "machine" and self.confirmed_subcause is not None:
            raise ValueError("confirmed_subcause must be null unless confirmed_category is 'machine'")
        return self


class SaveCaseResponse(BaseModel):
    status: Literal["proposed"]
    case_id: str
