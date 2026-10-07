"""Evaluation worker: incident workflow, draft versioning and memory-agent behaviour through the real HTTP API.

Runs in its own scratch database (see run_evals.subprocess_result). Uses the fake LLM provider and deterministic
bag-of-words embeddings only - no live calls. Prints one JSON line: {"workflow": [...], "memory": [...]}.
"""
import hashlib
import json
import secrets
from unittest.mock import patch
import bcrypt
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend import db
from backend.core import config
from backend.core.config import WARNING
from backend.init_db import init_db
from backend.auth import issue_token


def bag_embed(texts):
    out = []
    for text in texts:
        v = np.zeros(db.EMBEDDING_DIM)
        for word in text.lower().split():
            v[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % db.EMBEDDING_DIM] += 1
        out.append((v if v.any() else v + 1).tolist())
    return out


def run():
    from engine import retrieval
    from engine.memory import all_cases, recall
    init_db()
    hashed = bcrypt.hashpw(secrets.token_urlsafe(12).encode(), bcrypt.gensalt(rounds=4)).decode()
    tokens = {}
    with db.Session.begin() as s:
        for role in ('admin', 'engineer', 'qa_lead', 'viewer'):
            u = db.User(id='wf-' + role, email=f'wf-{role}@demo.local', role=role, password_hash=hashed, active=True, token_version=0)
            s.add(u); s.flush(); tokens[role] = issue_token(u)
    from backend.main import app
    client = TestClient(app, raise_server_exceptions=False)
    as_ = lambda role: {'Authorization': 'Bearer ' + tokens[role]}  # noqa: E731
    status = lambda iid: client.get(f'/api/incidents/{iid}/workflow', headers=as_('viewer')).json()['status']  # noqa: E731
    workflow, memory = [], []

    def check(rows, name, ok, **detail):
        rows.append({'check': name, 'passed': bool(ok), **detail})

    # Status transitions: new -> analysed -> draft_saved -> case_proposed -> case_approved; and the rejected branch.
    seen = [status('INC-001')]
    run1 = client.post('/api/incidents/INC-001/analyze', headers=as_('engineer')).json(); seen.append(status('INC-001'))
    client.post('/api/incidents/INC-001/drafts', headers=as_('engineer'), json={'content': 'Version one.', 'run_id': run1['run_id']}); seen.append(status('INC-001'))
    with patch.object(config, 'LLM_PROVIDER', 'groq'), patch.object(config, 'LLM_API_KEY', ''):
        draft = client.post('/api/cases/draft', headers=as_('engineer'), json={'incident_id': 'INC-001'}).json()
    body = {'incident_id': 'INC-001', 'rca_draft': 'Version one.', 'confirmed_category': draft['confirmed_category'],
            'confirmed_subcause': draft['confirmed_subcause'], 'fix_applied': 'Cleaned the chiller filter.', 'summary': draft['summary'],
            'symptoms': draft['symptoms'], 'documents_used': draft['documents_used'], 'text_source': draft['text_source']}
    case_id = client.post('/api/cases', headers=as_('engineer'), json=body).json()['case_id']; seen.append(status('INC-001'))
    client.post(f'/api/cases/{case_id}/approve', headers=as_('qa_lead')); seen.append(status('INC-001'))
    check(workflow, 'status_sequence', seen == ['new', 'analysed', 'draft_saved', 'case_proposed', 'case_approved'], observed=seen)
    other = client.post('/api/cases', headers=as_('engineer'), json={**body, 'incident_id': 'INC-002', 'confirmed_category': 'material',
                                                                       'confirmed_subcause': None}).json()['case_id']
    client.post(f'/api/cases/{other}/reject', headers=as_('qa_lead'))
    check(workflow, 'rejected_status', status('INC-002') == 'case_rejected')

    # Draft versioning and exports.
    v2 = client.post('/api/incidents/INC-001/drafts', headers=as_('engineer'), json={'content': 'Version two.'}).json()
    v3 = client.post('/api/incidents/INC-001/drafts/1/restore', headers=as_('qa_lead')).json()
    versions = [d['version'] for d in client.get('/api/incidents/INC-001/drafts', headers=as_('viewer')).json()]
    check(workflow, 'every_save_is_a_version', v2['version'] == 2 and versions == [3, 2, 1], versions=versions)
    check(workflow, 'restore_creates_new_version', v3['version'] == 3 and v3['content'] == 'Version one.' and v3['note'] == 'Restored from version 1')
    md = client.get('/api/incidents/INC-001/drafts/2/export?format=md', headers=as_('viewer'))
    pdf = client.get('/api/incidents/INC-001/drafts/2/export?format=pdf', headers=as_('viewer'))
    check(workflow, 'markdown_export_keeps_notice', md.status_code == 200 and WARNING in md.text)
    check(workflow, 'pdf_export_valid', pdf.status_code == 200 and pdf.content.startswith(b'%PDF'))
    check(workflow, 'viewer_cannot_save', client.post('/api/incidents/INC-001/drafts', headers=as_('viewer'), json={'content': 'x'}).status_code == 403)

    # Memory agent: summary fields (template and fake LLM).
    fields = ('symptoms', 'evidence_summary', 'lessons_learned', 'summary', 'documents_used', 'confirmed_category')
    check(memory, 'template_summary_fields_filled', draft['text_source'] == 'template' and all(draft[f] for f in fields))
    client.post('/api/incidents/INC-009/analyze', headers=as_('engineer'))
    with patch.object(config, 'LLM_PROVIDER', 'fake'), patch.object(config, 'LLM_ENABLED', True):
        fake = client.post('/api/cases/draft', headers=as_('engineer'), json={'incident_id': 'INC-009'}).json()
    check(memory, 'fake_llm_summary_fields_filled', fake['text_source'] == 'llm' and all(fake[f] for f in fields))
    # Duplicates: same incident blocked without a reason; very similar approved case found.
    dup = client.post('/api/cases', headers=as_('engineer'), json=body)
    check(memory, 'duplicate_same_incident_blocked', dup.status_code == 409 and dup.json()['detail']['duplicates'][0]['case_id'] == case_id)
    ok = client.post('/api/cases', headers=as_('engineer'), json={**body, 'duplicate_reason': 'Evaluation override probe'})
    check(memory, 'duplicate_override_with_reason', ok.status_code == 201)
    from backend.services.memory_agent import find_duplicates
    from engine.memory import case_text
    with patch.object(config, 'EMBEDDINGS_PROVIDER', 'openai_compatible'), patch.object(retrieval, 'embed', bag_embed):
        with db.Session.begin() as s:
            from engine.memory import embed_case
            for c in s.scalars(select(db.Case).where(db.Case.status == 'approved')):
                embed_case(c)
        with db.Session() as s:
            approved = s.get(db.Case, case_id)
            similar = find_duplicates(s, 'UPL-probe', approved.data['machine_uid'], approved.data['confirmed_category'],
                                      approved.data['confirmed_subcause'], case_text(approved.data))
        check(memory, 'similar_approved_case_detected', any(d['case_id'] == case_id and d.get('similarity', 0) >= 0.9 for d in similar))
        # Semantic recall: the approved case is recalled for INC-009 with a summary-similarity reason.
        result = client.post('/api/incidents/INC-009/analyze', headers=as_('engineer')).json()
        match = next((c for c in result['similar_cases'] if c['case_id'] == case_id), None)
        check(memory, 'semantic_recall', bool(match) and any(r.startswith('summary similarity') for r in match['match_reasons']),
              reasons=match['match_reasons'] if match else None)
    # Edit keeps the previous version; retired cases are never recalled.
    edited = client.patch(f'/api/cases/{case_id}', headers=as_('qa_lead'), json={'reason': 'Evaluation edit', 'lessons': 'Check weekly.'}).json()
    history = client.get(f'/api/cases/{case_id}/history', headers=as_('viewer')).json()
    check(memory, 'edit_keeps_previous_version', edited['version'] == 2 and history['versions'][0]['version'] == 1)
    signals = next(c for c in all_cases() if c['case_id'] == case_id)
    client.post(f'/api/cases/{case_id}/retire', headers=as_('qa_lead'), json={'reason': 'Evaluation retire probe'})
    recalled = [c.case_id for c in recall(signals['signals'], context=signals)]
    after = [c['case_id'] for c in client.post('/api/incidents/INC-009/analyze', headers=as_('engineer')).json()['similar_cases']]
    check(memory, 'retired_never_recalled', case_id not in recalled and case_id not in after and case_id not in {c['case_id'] for c in all_cases()})
    return {'workflow': workflow, 'memory': memory}


if __name__ == '__main__':
    print(json.dumps(run(), default=str))
