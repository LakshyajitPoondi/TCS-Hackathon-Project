"""Stage 5: cause-and-effect graph built from the real stored analysis, including the abstain case."""


def test_graph_ranked_incident(client):
    run = client.post('/api/incidents/INC-001/analyze').json()
    g = client.get(f"/api/analyses/{run['run_id']}/graph").json()
    kinds = {n['id']: n['data']['kind'] for n in g['nodes']}
    assert g['mode'] == 'ranked' and {'evidence', 'hypothesis', 'action', 'document', 'missing'} <= set(kinds.values())
    hyps = [n for n in g['nodes'] if n['data']['kind'] == 'hypothesis']
    assert [n['data']['rank'] for n in hyps] == [h['rank'] for h in run['hypotheses']]
    top = run['hypotheses'][0]
    into_top = [e for e in g['edges'] if e['target'] == 'hyp1' and e['kind'] in ('supports', 'contradicts')]
    assert len(into_top) == len(top['supporting_evidence']) + len(top['contradicting_evidence'])
    assert sum(e['weight'] for e in into_top) == top['score'] and all(e['label'][0] in '+−' for e in into_top)
    cited = {e['target'] for e in g['edges'] if e['kind'] == 'cites'}
    assert cited and cited <= {f"doc:{d['doc_id']}" for d in run['documents_accessed']}
    assert all(kinds[e['source']] and kinds[e['target']] for e in g['edges'])   # no dangling edges
    doc = next(n for n in g['nodes'] if n['id'] in cited)
    assert doc['data']['link'].startswith('/documents/')
    ys = sorted(n['position']['y'] for n in hyps)
    assert all(b - a >= 96 for a, b in zip(ys, ys[1:]))


def test_graph_abstain_shows_evidence_and_missing_checks(client):
    run = client.post('/api/incidents/INC-008/analyze').json()
    assert run['analysis_status'] == 'insufficient_evidence'
    g = client.get(f"/api/analyses/{run['run_id']}/graph").json()
    kinds = [n['data']['kind'] for n in g['nodes']]
    assert g['mode'] == 'abstain' and kinds.count('abstain') == 1 and 'hypothesis' not in kinds
    assert 'evidence' in kinds and 'category' in kinds and 'missing' in kinds
    assert any(e['kind'] == 'below_minimum' for e in g['edges'])
    assert client.get('/api/analyses/nope/graph').status_code == 404
