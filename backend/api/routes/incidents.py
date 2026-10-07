from fastapi import APIRouter, File, UploadFile, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from backend import db
from backend.auth import require
from backend.models.schemas import IncidentSummary, SignalsResponse
from backend.services import data_loader, workflow
from backend.services.incidents import build_signals, build_summary

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("")
def list_incidents():
    """Sample and uploaded incidents with source label, machines, dates, top hypothesis and derived status (B5)."""
    with db.Session.begin() as session:
        return workflow.list_rows(session)


@router.post("/upload")
def upload_incident(file: UploadFile = File(...), user=Depends(require("upload"))):
    from backend.core.config import UPLOAD_MAX_MB
    result = data_loader.save_upload(file.file.read(int(UPLOAD_MAX_MB * 1024 * 1024) + 1), file.filename or "")
    with db.Session.begin() as session:
        workflow.register(session, result["id"], data_loader.load_incident(result["id"]), "uploaded", result["filename"], user.id)
        db.audit(session, user.id, "upload_incident", result)
    return {**result, "source": "uploaded", "source_label": "Uploaded"}


@router.get("/{incident_id}", response_model=IncidentSummary)
def get_incident(incident_id: str):
    return build_summary(incident_id, data_loader.load_incident(incident_id))


@router.get("/{incident_id}/signals", response_model=SignalsResponse)
def get_signals(incident_id: str):
    return build_signals(incident_id, data_loader.load_incident(incident_id))


@router.get("/{incident_id}/workflow")
def incident_workflow(incident_id: str):
    """Status badge data plus links: cases created from this incident and draft versions."""
    with db.Session.begin() as session:
        row = workflow.get_incident(session, incident_id)
        info = workflow.incident_rows(session, [row])[0]
        cases = list(session.scalars(select(db.Case).where(db.Case.source_incident_id == incident_id).order_by(db.Case.created_at.desc())))
        names = workflow.user_names(session, [c.proposer_id for c in cases] + [c.approver_id for c in cases])
        info["cases"] = [{"case_id": c.case_id, "status": c.status, "confirmed_category": c.data.get("confirmed_category"),
                          "confirmed_subcause": c.data.get("confirmed_subcause"), "created_at": c.created_at,
                          "proposer_name": names.get(c.proposer_id), "approver_name": names.get(c.approver_id)} for c in cases]
        return info


class DraftBody(BaseModel):
    content: str = Field(max_length=workflow.DRAFT_MAX_CHARS)
    run_id: str | None = None
    note: str | None = Field(default=None, max_length=300)


@router.get("/{incident_id}/drafts")
def drafts(incident_id: str):
    with db.Session() as session:
        return workflow.list_drafts(session, incident_id)


@router.post("/{incident_id}/drafts", status_code=201)
def save_draft(incident_id: str, body: DraftBody, user=Depends(require("draft"))):
    with db.Session.begin() as session:
        return workflow.save_draft(session, incident_id, body.content, user, body.run_id, body.note)


@router.post("/{incident_id}/drafts/{version}/restore", status_code=201)
def restore_draft(incident_id: str, version: int, user=Depends(require("draft"))):
    with db.Session.begin() as session:
        old = workflow.get_draft(session, incident_id, version)
        return workflow.save_draft(session, incident_id, old.content, user, old.run_id, f"Restored from version {version}")


@router.get("/{incident_id}/drafts/{version}/export")
def export_draft(incident_id: str, version: int, format: str = Query("md", pattern="^(md|pdf)$")):
    with db.Session() as session:
        draft = workflow.get_draft(session, incident_id, version)
        author = workflow.user_names(session, [draft.author_id]).get(draft.author_id)
        if format == "pdf":
            body, media = workflow.export_pdf(draft, author), "application/pdf"
        else:
            body, media = workflow.export_markdown(draft, author).encode("utf-8"), "text/markdown; charset=utf-8"
    name = workflow.safe_filename(incident_id, version, format)
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})
