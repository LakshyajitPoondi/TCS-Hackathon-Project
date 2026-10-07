"""Stage 4: memory-agent draft (fake LLM + template), edit-before-submit, duplicates (B7), case embeddings in recall,
B15, lifecycle (edit versions, retire), end-to-end recall of an approved case."""
import hashlib
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select
from backend import db
from backend.core import config
from engine import llm, retrieval
from engine.memory import all_cases, recall


def bag_embed(texts):
    """Deterministic bag-of-words vectors (384 dims) so similar summaries are similar."""
    out = []
    for text in texts:
        v = np.zeros(db.EMBEDDING_DIM)
        for word in text.lower().split():
            v[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % db.EMBEDDING_DIM] += 1
        out.append((v if v.any() else v + 1).tolist())
    return out


def role(client, tokens, name):
    client.headers['Authorization'] = 'Bearer ' + tokens[name]
    return client


def analysed(client, tokens, incident='INC-001'):
    run = role(client, tokens, 'engineer').post(f'/api/incidents/{incident}/analyze').json()
    assert run['hypotheses'], run
    return run


def usage_count():
    with db.Session() as s:
        return len(list(s.scalars(select(db.LLMUsage))))


def proposal(draft, **changes):
    body = {'incident_id': draft['incident_id'], 'rca_draft': 'Edited draft.', 'confirmed_category': draft['confirmed_category'],
            'confirmed_subcause': draft['confirmed_subcause'], 'fix_applied': 'Replaced the clogged chiller filter.',
            'lessons': draft['lessons_learned'], 'documents_used': draft['documents_used'], 'summary': draft['summary'],
            'symptoms': draft['symptoms'], 'evidence_summary': draft['evidence_summary'], 'text_source': draft['text_source']}
    return {**body, **changes}


def test_template_draft_fields_filled(client, tokens, monkeypatch):
    monkeypatch.setattr(config, 'LLM_PROVIDER', 'groq'); monkeypatch.setattr(config, 'LLM_API_KEY', '')
    run = analysed(client, tokens)
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001', 'rca_draft': 'x'}).json()
    assert d['text_source'] == 'template' and d['run_id'] == run['run_id']
    assert d['symptoms'] and d['evidence_summary'] and d['summary'] and d['lessons_learned']
    assert (d['confirmed_category'], d['confirmed_subcause']) == (run['hypotheses'][0]['category'], run['hypotheses'][0]['subcause'])
    assert d['documents_used'] == [x['doc_id'] for x in run['documents_accessed']] and d['fix_applied'] == ''
    assert d['machine_uid'] == 'LINE-A/IMM-02' and d['duplicates'] == []
    assert client.post('/api/cases/draft', json={'incident_id': 'INC-002'}).status_code == 409   # not analysed yet
    assert role(client, tokens, 'viewer').post('/api/cases/draft', json={'incident_id': 'INC-001'}).status_code == 403


def test_fake_llm_draft_one_call_then_cache_and_number_guard(client, tokens, monkeypatch):
    monkeypatch.setattr(config, 'LLM_PROVIDER', 'fake')
    analysed(client, tokens)
    before = usage_count()
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001', 'rca_draft': 'draft text'}).json()
    assert d['text_source'] == 'llm' and usage_count() == before + 1
    again = client.post('/api/cases/draft', json={'incident_id': 'INC-001', 'rca_draft': 'draft text'}).json()
    assert again['text_source'] == 'llm' and usage_count() == before + 1   # cached
    original = llm.request_json
    def invented(system, payload, schema, **kw):
        if schema.__name__ == 'MemoryDraft':
            return {'symptoms': ['Temperature reached 999.9 on IMM-02'], 'evidence_summary': 'Evidence as given.',
                    'lessons_learned': 'Check the fan.', 'summary': 'Cooling failure cost 4321 hours.'}
        return original(system, payload, schema, **kw)
    monkeypatch.setattr(llm, 'request_json', invented)
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001', 'rca_draft': 'other text'}).json()
    assert d['text_source'] == 'llm' and '4321' not in d['summary'] and '999.9' not in ' '.join(d['symptoms'])
    assert d['evidence_summary'] == 'Evidence as given.' and any('summary' in r for r in d['fallback_reasons'])


def test_engineer_edits_are_stored(client, tokens):
    analysed(client, tokens)
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001'}).json()
    body = proposal(d, summary='Engineer summary: chiller filter clogged on LINE-A/IMM-02.', symptoms=['Hot housing', 'Slow cycle'],
                    lessons='Inspect filter weekly.', documents_used=['SOP-007'])
    cid = client.post('/api/cases', json=body).json()['case_id']
    case = client.get('/api/cases/' + cid).json()
    assert case['summary'] == body['summary'] and case['symptoms'] == ['Hot housing', 'Slow cycle']
    assert case['lessons'] == 'Inspect filter weekly.' and case['documents'] == [{'doc_id': 'SOP-007', 'title': 'Cooling System Troubleshooting'}]
    assert case['engineer_edited'] and case['status'] == 'proposed'


def test_b7_duplicate_same_incident_and_similar_approved(client, tokens, monkeypatch):
    analysed(client, tokens)
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001'}).json()
    assert client.post('/api/cases', json=proposal(d)).status_code == 201
    d2 = client.post('/api/cases/draft', json={'incident_id': 'INC-001'}).json()
    assert d2['duplicates'] and d2['duplicates'][0]['status'] == 'proposed'
    blocked = client.post('/api/cases', json=proposal(d2))
    assert blocked.status_code == 409 and blocked.json()['detail']['duplicates']
    ok = client.post('/api/cases', json=proposal(d2, duplicate_reason='Second confirmed occurrence on night shift.'))
    assert ok.status_code == 201
    assert client.get('/api/cases/' + ok.json()['case_id']).json()['duplicate_override']['reason'].startswith('Second')
    # Very similar APPROVED case on the same machine/cause from a different incident (an upload of the same data).
    first = client.get('/api/cases?status=proposed').json()[0]['case_id']
    role(client, tokens, 'qa_lead').post(f'/api/cases/{first}/approve')
    csv = pd.read_csv('data/incidents/incident_001.csv').to_csv(index=False).encode()
    upl = role(client, tokens, 'engineer').post('/api/incidents/upload', files={'file': ('copy.csv', csv)}).json()['id']
    client.post(f'/api/incidents/{upl}/analyze')
    d3 = client.post('/api/cases/draft', json={'incident_id': upl}).json()
    similar = [x for x in d3['duplicates'] if x['case_id'] == first]
    assert similar and 'shared signal tags' in similar[0]['reason']   # embeddings off -> signal overlap
    monkeypatch.setattr(config, 'EMBEDDINGS_PROVIDER', 'openai_compatible'); monkeypatch.setattr(retrieval, 'embed', bag_embed)
    with db.Session.begin() as s:
        from engine.memory import embed_case
        assert embed_case(s.get(db.Case, first))
    with db.Session() as s:
        from backend.services.memory_agent import find_duplicates
        from engine.memory import case_text
        same = find_duplicates(s, upl, 'LINE-A/IMM-02', 'machine', 'cooling', case_text(s.get(db.Case, first).data))
    assert same and same[0]['similarity'] >= 0.9 and 'very similar description' in same[0]['reason']


def test_lifecycle_edit_versions_retire_never_recalled(client, tokens):
    analysed(client, tokens)
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001'}).json()
    cid = client.post('/api/cases', json=proposal(d)).json()['case_id']
    qa = role(client, tokens, 'qa_lead')
    assert qa.patch('/api/cases/' + cid, json={'reason': 'not yet', 'summary': 'x'}).status_code == 409   # proposed
    approved = qa.post(f'/api/cases/{cid}/approve').json()
    assert 'Approved by' in approved['summary'] and approved['reviewed_by_name']
    assert role(client, tokens, 'engineer').patch('/api/cases/' + cid, json={'reason': 'engineer edit', 'summary': 'x'}).status_code == 403
    qa = role(client, tokens, 'qa_lead')
    assert qa.patch('/api/cases/' + cid, json={'summary': 'no reason'}).status_code == 422
    edited = qa.patch('/api/cases/' + cid, json={'reason': 'Clarify the fix', 'fix_applied': 'Replaced chiller filter and flushed loop.'}).json()
    assert edited['version'] == 2 and edited['fix_applied'].startswith('Replaced chiller')
    history = client.get(f'/api/cases/{cid}/history').json()
    assert history['versions'][0]['version'] == 1 and history['versions'][0]['data']['fix_applied'] == 'Replaced the clogged chiller filter.'
    assert [e['action'] for e in history['events']] == ['propose_case', 'approved_case', 'edit_case']
    saved = next(c for c in all_cases() if c['case_id'] == cid)
    assert any(c.case_id == cid for c in recall(saved['signals'], context=saved))
    assert qa.post(f'/api/cases/{cid}/retire', json={'reason': 'x'}).status_code == 422
    retired = qa.post(f'/api/cases/{cid}/retire', json={'reason': 'Superseded by the new chiller design.'}).json()
    assert retired['status'] == 'retired' and retired['version'] == 3
    assert cid not in {c['case_id'] for c in all_cases()}
    assert not any(c.case_id == cid for c in recall(saved['signals'], context=saved))
    assert qa.patch('/api/cases/' + cid, json={'reason': 'edit retired', 'summary': 'x'}).status_code == 409
    assert client.get(f'/api/cases/{cid}/history').json()['events'][-1]['action'] == 'retire_case'
    assert client.get('/api/cases?status=retired').json()[0]['case_id'] == cid


def test_end_to_end_recall_semantic_factor_and_b15(client, tokens, monkeypatch):
    monkeypatch.setattr(config, 'EMBEDDINGS_PROVIDER', 'openai_compatible'); monkeypatch.setattr(retrieval, 'embed', bag_embed)
    analysed(client, tokens)
    d = client.post('/api/cases/draft', json={'incident_id': 'INC-001'}).json()
    cid = client.post('/api/cases', json=proposal(d)).json()['case_id']
    with db.Session() as s:
        assert s.get(db.Case, cid).embedding is not None   # summary embedded on proposal
    before = [c['case_id'] for c in role(client, tokens, 'engineer').post('/api/incidents/INC-009/analyze').json()['similar_cases']]
    assert cid not in before   # proposed cases are never recalled
    role(client, tokens, 'qa_lead').post(f'/api/cases/{cid}/approve')
    result = role(client, tokens, 'engineer').post('/api/incidents/INC-009/analyze').json()
    match = next(c for c in result['similar_cases'] if c['case_id'] == cid)
    assert any(r.startswith('summary similarity') for r in match['match_reasons'])
    assert any('matches current top hypothesis (+1' in r for r in match['match_reasons'])
    assert not any(r == 'confirmed_category agrees' for r in match['match_reasons'])   # B15: no hidden +4 echo
