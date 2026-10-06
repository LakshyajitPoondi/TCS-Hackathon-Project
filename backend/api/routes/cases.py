from datetime import date

from fastapi import APIRouter, Depends
from backend.auth import require

from backend.models.schemas import SaveCaseRequest, SaveCaseResponse
from backend.services.data_loader import load_incident
from engine.memory import build_signature, retain
from engine.signals import analyze_signals

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("", response_model=SaveCaseResponse)
def save_case(request: SaveCaseRequest, user=Depends(require("propose"))):
    df = load_incident(request.incident_id)  # unknown id -> 404 via IncidentNotFoundError
    sub = f"/{request.confirmed_subcause}" if request.confirmed_subcause else ""
    case_id = retain({
        "date": date.today().isoformat(),
        "line": str(df["line"].dropna().iloc[0]) if df["line"].notna().any() else None,
        "signals": build_signature(analyze_signals(df)),  # structured signature, never LLM prose
        "confirmed_category": request.confirmed_category,
        "confirmed_subcause": request.confirmed_subcause,
        "summary": f"Engineer-validated {request.confirmed_category}{sub} case (saved from {request.incident_id}).",
        "source_incident_id": request.incident_id,
        "notes": request.notes,
        "draft": request.rca_draft,  # display only; not used for matching
    })
    from backend import db
    with db.Session.begin() as session: db.audit(session,user.id,"save_case",{"case_id":case_id})
    return SaveCaseResponse(status="saved", case_id=case_id)
