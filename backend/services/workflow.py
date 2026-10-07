"""Incident registry, server-derived incident status, versioned RCA drafts, exports and the dashboard.

Status (derived, never stored): new -> analysed -> draft_saved -> case_proposed -> case_approved | case_rejected.
Uploaded incidents are listed with source "uploaded" and never join the evaluation set (evals read sample files only).
"""
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from backend import db
from backend.core.config import WARNING
from backend.services import data_loader

STATUS_LABELS = {'new': 'New', 'analysed': 'Analysed', 'draft_saved': 'Draft saved', 'case_proposed': 'Case proposed',
                 'case_approved': 'Case approved', 'case_rejected': 'Case rejected'}
SOURCE_LABELS = {'sample': 'Sample', 'uploaded': 'Uploaded'}
DRAFT_MAX_CHARS = 50000
EXPORT_NOTICE = 'Engineering validation notice: ' + WARNING


# ---------- users ----------

def display_name(user):
    if user is None:
        return None
    return user.name or user.email.split('@')[0].replace('.', ' ').replace('_', ' ').title()


def user_names(session, ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: display_name(u) for u in session.scalars(select(db.User).where(db.User.id.in_(ids)))}


# ---------- registry ----------

def register(session, incident_id, frame, source, filename, user_id=None):
    if session.get(db.Incident, incident_id):
        return session.get(db.Incident, incident_id)
    row = db.Incident(incident_id=incident_id, source=source, filename=filename, line=str(frame['line'].iloc[0]),
                      machines=sorted(frame['machine'].astype(str).unique().tolist()),
                      start_time=frame['timestamp'].min().isoformat(), end_time=frame['timestamp'].max().isoformat(),
                      record_count=int(len(frame)), uploaded_by=user_id)
    session.add(row)
    return row


def register_existing(session, frames=None):
    """Register sample CSVs and any upload files on disk that are not yet in the registry (idempotent)."""
    known = set(session.scalars(select(db.Incident.incident_id)))
    frames = frames or {}
    for source, refs in (('sample', data_loader.list_incidents()), ('uploaded', data_loader.list_uploads())):
        for ref in refs:
            if ref['id'] in known:
                continue
            try:
                frame = frames.get(ref['id'])
                frame = frame if frame is not None else data_loader.load_incident(ref['id'])
            except Exception:
                continue  # an unreadable stray file is not listed
            register(session, ref['id'], frame, source, ref['filename'])


def get_incident(session, incident_id):
    row = session.get(db.Incident, incident_id)
    if row is None:
        frame = data_loader.load_incident(incident_id)  # raises 404 for unknown ids
        row = register(session, incident_id, frame, 'sample' if incident_id.startswith('INC-') else 'uploaded',
                       data_loader.incident_id_to_filename(incident_id))
        session.flush()
    return row


def affected_machines(session, row):
    """B12: machines that actually deviated (signals, defects) or are a hypothesis target. Computed once."""
    if row.affected_machines is None:
        from engine.signals import analyze_signals
        from engine.scoring import score_hypotheses
        frame = data_loader.load_incident(row.incident_id)
        evidence = analyze_signals(frame)
        found = set()
        if not evidence.get('insufficient_data'):
            found |= set(evidence['co_movement']['machines_deviating']) | set(evidence['defects']['machines_up'])
            found |= {h['target'] for h in score_hypotheses(evidence)['hypotheses'] if h.get('target')}
        row.affected_machines = sorted(found & set(row.machines)) or list(row.machines)
    return row.affected_machines


# ---------- status ----------

def _top(run):
    config = run.config or {}
    if 'top_hypothesis' in config:
        return config['top_hypothesis']
    hyps = (run.response or {}).get('hypotheses') or []
    if hyps:
        h = hyps[0]
        return {'category': h['category'], 'subcause': h.get('subcause'), 'confidence': h['confidence']}
    return {'category': None, 'status': (run.response or {}).get('analysis_status')}


def workflow_state(session, incident_ids):
    """incident_id -> {status, status_label, top_hypothesis, last_run_id, last_analysed_at, draft_version, cases}."""
    ids = list(incident_ids)
    state = {i: {'status': 'new', 'top_hypothesis': None, 'last_run_id': None, 'last_analysed_at': None,
                 'draft_version': None, 'draft_saved_at': None, 'cases': [], 'last_activity': None} for i in ids}
    if not ids:
        return state
    for run in session.scalars(select(db.AnalysisRun).where(db.AnalysisRun.incident_id.in_(ids)).order_by(db.AnalysisRun.created_at)):
        s = state[run.incident_id]
        s.update(last_run_id=run.run_id, last_analysed_at=run.created_at, top_hypothesis=_top(run), last_activity=run.created_at)
    for draft in session.scalars(select(db.RcaDraft).where(db.RcaDraft.incident_id.in_(ids)).order_by(db.RcaDraft.version)):
        s = state[draft.incident_id]
        s.update(draft_version=draft.version, draft_saved_at=draft.created_at)
        s['last_activity'] = max(filter(None, [s['last_activity'], draft.created_at]))
    for case in session.scalars(select(db.Case).where(db.Case.source_incident_id.in_(ids)).order_by(db.Case.created_at)):
        s = state[case.source_incident_id]
        s['cases'].append({'case_id': case.case_id, 'status': case.status, 'confirmed_category': case.data.get('confirmed_category'),
                           'confirmed_subcause': case.data.get('confirmed_subcause'), 'created_at': case.created_at})
        s['last_activity'] = max(filter(None, [s['last_activity'], case.created_at]))
    for s in state.values():
        statuses = {c['status'] for c in s['cases']}
        s['status'] = ('case_approved' if 'approved' in statuses else 'case_proposed' if 'proposed' in statuses else
                       'case_rejected' if 'rejected' in statuses else 'draft_saved' if s['draft_version'] else
                       'analysed' if s['last_run_id'] else 'new')
        s['status_label'] = STATUS_LABELS[s['status']]
    return state


def incident_rows(session, rows):
    rows = list(rows)
    state = workflow_state(session, [r.incident_id for r in rows])
    names = user_names(session, [r.uploaded_by for r in rows])
    out = []
    for r in rows:
        s = state[r.incident_id]
        out.append({'id': r.incident_id, 'filename': r.filename, 'source': r.source, 'source_label': SOURCE_LABELS[r.source],
                    'line': r.line, 'machines': r.machines, 'affected_machines': r.affected_machines,
                    'start_time': r.start_time, 'end_time': r.end_time, 'record_count': r.record_count,
                    'uploaded_by_name': names.get(r.uploaded_by), 'created_at': r.created_at,
                    **{k: s[k] for k in ('status', 'status_label', 'top_hypothesis', 'last_run_id', 'last_analysed_at',
                                         'draft_version', 'last_activity')},
                    'case_ids': [c['case_id'] for c in s['cases']]})
    return out


def list_rows(session):
    register_existing(session)
    rows = session.scalars(select(db.Incident).order_by(db.Incident.source.desc(), db.Incident.incident_id))
    return incident_rows(session, rows)


# ---------- drafts ----------

def serialize_draft(draft, names):
    return {'id': draft.id, 'incident_id': draft.incident_id, 'run_id': draft.run_id, 'version': draft.version,
            'content': draft.content, 'note': draft.note, 'author_id': draft.author_id,
            'author_name': names.get(draft.author_id), 'created_at': draft.created_at}


def list_drafts(session, incident_id):
    drafts = list(session.scalars(select(db.RcaDraft).where(db.RcaDraft.incident_id == incident_id).order_by(db.RcaDraft.version.desc())))
    names = user_names(session, [d.author_id for d in drafts])
    return [serialize_draft(d, names) for d in drafts]


def save_draft(session, incident_id, content, user, run_id=None, note=None):
    if not content or not content.strip():
        raise HTTPException(422, 'Draft must not be empty')
    if len(content) > DRAFT_MAX_CHARS:
        raise HTTPException(422, f'Draft exceeds {DRAFT_MAX_CHARS} characters')
    get_incident(session, incident_id)
    if run_id:
        run = session.get(db.AnalysisRun, run_id)
        if not run or run.incident_id != incident_id:
            raise HTTPException(422, 'Analysis run does not belong to this incident')
    version = (session.scalar(select(func.max(db.RcaDraft.version)).where(db.RcaDraft.incident_id == incident_id)) or 0) + 1
    draft = db.RcaDraft(incident_id=incident_id, run_id=run_id, version=version, content=content, note=(note or '')[:300] or None,
                        author_id=user.id)
    session.add(draft)
    session.flush()
    db.audit(session, user.id, 'save_draft', {'incident_id': incident_id, 'version': version, 'note': draft.note})
    return serialize_draft(draft, {user.id: display_name(user)})


def get_draft(session, incident_id, version):
    draft = session.scalar(select(db.RcaDraft).where(db.RcaDraft.incident_id == incident_id, db.RcaDraft.version == version))
    if not draft:
        raise HTTPException(404, 'Draft version not found')
    return draft


# ---------- export ----------

def export_markdown(draft, author_name):
    """The engineering-validation notice is always included, whatever the draft text says."""
    return '\n'.join([f'# RCA draft — {draft.incident_id}', '',
                      f'> **{EXPORT_NOTICE}**', '',
                      f'- Version: {draft.version}', f'- Saved: {draft.created_at:%Y-%m-%d %H:%M} UTC',
                      f'- Author: {author_name or "unknown"}', f'- Analysis run: {draft.run_id or "—"}', '',
                      '---', '', draft.content.rstrip(), '', '---', '', f'**{EXPORT_NOTICE}**', ''])


_PDF_REPLACEMENTS = {'—': '-', '–': '-', '→': '->', '≥': '>=', '≤': '<=', '±': '+/-', '“': '"', '”': '"', '‘': "'", '’': "'",
                     '…': '...', '•': '-', '°': ' deg ', '×': 'x'}


def _latin1(text):
    for k, v in _PDF_REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')


def export_pdf(draft, author_name):
    from fpdf import FPDF
    pdf = FPDF(format='A4')
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font('Helvetica', 'B', 16)
    pdf.multi_cell(width, 8, _latin1(f'RCA draft - {draft.incident_id}'))
    pdf.set_font('Helvetica', '', 9)
    pdf.multi_cell(width, 5, _latin1(f'Version {draft.version} | saved {draft.created_at:%Y-%m-%d %H:%M} UTC | '
                                     f'author {author_name or "unknown"} | analysis run {draft.run_id or "-"}'))
    pdf.ln(2)
    pdf.set_fill_color(255, 241, 214)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.multi_cell(width, 6, _latin1(EXPORT_NOTICE), fill=True)
    pdf.ln(3)
    pdf.set_font('Courier', '', 9)
    for line in draft.content.splitlines() or ['']:
        pdf.multi_cell(width, 4.5, _latin1(line) or ' ')
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.multi_cell(width, 6, _latin1(EXPORT_NOTICE), fill=True)
    return bytes(pdf.output())


def safe_filename(incident_id, version, ext):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', f'rca-draft-{incident_id}-v{version}.{ext}')


# ---------- dashboard ----------

def dashboard(session, user):
    from engine import llm
    from backend.auth import PERMISSIONS
    rows = list_rows(session)
    by_status = {k: 0 for k in STATUS_LABELS}
    for r in rows:
        by_status[r['status']] += 1
    pending_cases = list(session.scalars(select(db.Case).where(db.Case.status == 'proposed').order_by(db.Case.created_at.desc())))
    pending_docs = list(session.scalars(select(db.Document).where(db.Document.status == 'pending_mapping').order_by(db.Document.uploaded_at.desc())))
    names = user_names(session, [c.proposer_id for c in pending_cases] + [d.uploaded_by for d in pending_docs])
    llm_status = llm.status()
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    recent = sorted(rows, key=lambda r: r['last_activity'] or r['created_at'] or epoch, reverse=True)[:8]
    pending = []
    if user.role in PERMISSIONS['approve']:
        pending += [{'kind': 'case_review', 'title': f"Review case for {c.source_incident_id or 'seed'}",
                     'detail': f"{c.data.get('confirmed_category')}{'/' + c.data['confirmed_subcause'] if c.data.get('confirmed_subcause') else ''}"
                               f" · proposed by {names.get(c.proposer_id) or 'unknown'}",
                     'link': f'/cases/{c.case_id}', 'created_at': c.created_at} for c in pending_cases]
    if user.role in PERMISSIONS['documents']:
        pending += [{'kind': 'document_mapping', 'title': f'Confirm mapping: {d.title}',
                     'detail': '; '.join((d.detection or {}).get('warnings', [])) or 'Mapping needs confirmation',
                     'link': f'/documents/{d.doc_id}', 'created_at': d.uploaded_at} for d in pending_docs
                    if d.scope != 'plant' or user.role == 'admin']
    if user.role in PERMISSIONS['analyze']:
        pending += [{'kind': 'analyse', 'title': f"Analyse {r['id']}", 'detail': f"{r['source_label']} · {r['line']}",
                     'link': f"/incidents/{r['id']}", 'created_at': r['created_at']} for r in rows
                    if r['status'] == 'new' and r['source'] == 'uploaded']
    if user.role in PERMISSIONS['propose']:
        pending += [{'kind': 'propose', 'title': f"Save draft or propose case for {r['id']}", 'detail': 'Analysed, no case yet',
                     'link': f"/incidents/{r['id']}", 'created_at': r['last_activity']} for r in rows
                    if r['status'] in ('analysed', 'draft_saved')]
    return {'kpis': {'incidents_total': len(rows), 'incidents_by_status': by_status,
                     'incidents_uploaded': sum(r['source'] == 'uploaded' for r in rows),
                     'cases_pending': len(pending_cases), 'cases_approved': session.scalar(select(func.count()).select_from(db.Case).where(db.Case.status == 'approved')),
                     'documents_pending': len(pending_docs),
                     'llm_calls_today': llm_status['calls_today'], 'llm_daily_budget': llm_status['daily_budget'],
                     'llm_blocked_until': llm_status['blocked_until']},
            'status_labels': STATUS_LABELS, 'recent_incidents': recent, 'pending': pending[:20]}


def nav_counts(session):
    return {'documents_pending': session.scalar(select(func.count()).select_from(db.Document).where(db.Document.status == 'pending_mapping')),
            'cases_pending': session.scalar(select(func.count()).select_from(db.Case).where(db.Case.status == 'proposed'))}

