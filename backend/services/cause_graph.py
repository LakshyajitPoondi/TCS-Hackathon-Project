"""Cause-and-effect graph built from a stored analysis (never recomputed, never re-ranked).

Columns: evidence (signals, events, notes) -> hypotheses (or, when the engine abstained, the categories that
had evidence) -> verification actions and missing checks -> cited documents. Evidence edges carry the rule
weight from config/cause_categories.yaml (+ supporting, - contradicting).
"""
from engine.cause_config import CONFIG

COLUMN_X = {'evidence': 0, 'cause': 400, 'action': 800, 'document': 1200}
# Abstain mode adds a verdict column between the categories and the checks.
ABSTAIN_X = {'evidence': 0, 'cause': 400, 'verdict': 800, 'action': 1200, 'document': 1600}
ROW = 96


def _evidence_label(e):
    signal = e.get('signal', '').replace('_', ' ')
    return f"{signal} · {e['machine']}" if e.get('machine') else signal


def _weight_label(w):
    if w is None:
        return None
    w = int(w) if float(w).is_integer() else w
    return f'+{w}' if w > 0 else f'−{abs(w)}'


def build(analysis: dict) -> dict:
    columns = COLUMN_X if analysis.get('hypotheses') else ABSTAIN_X
    nodes, edges, rows = {}, [], {k: 0 for k in columns}

    def node(node_id, column, kind, label, **data):
        if node_id not in nodes:
            nodes[node_id] = {'id': node_id, 'type': 'cause', 'position': {'x': columns[column], 'y': rows[column] * ROW},
                              'data': {'kind': kind, 'label': label, **data}}
            rows[column] += 1
        return node_id

    def edge(source, target, kind, label=None, weight=None):
        edges.append({'id': f'e{len(edges)}', 'source': source, 'target': target, 'kind': kind, 'label': label, 'weight': weight})

    evidence_ids = {}

    def evidence_node(e, polarity):
        key = (e.get('signal'), e.get('description'))
        if key not in evidence_ids:
            evidence_ids[key] = node(f'ev{len(evidence_ids)}', 'evidence', 'evidence', _evidence_label(e),
                                     description=e['description'], signal=e.get('signal'), machine=e.get('machine'),
                                     value=e.get('value'), polarity=polarity)
        return evidence_ids[key]

    docs = {d['doc_id']: d for d in analysis.get('documents_accessed', [])}

    def document_node(doc_id, chunk_id=None, page=None):
        d = docs.get(doc_id, {'doc_id': doc_id, 'title': doc_id, 'scope': None})
        return node(f'doc:{doc_id}', 'document', 'document', d.get('title', doc_id), doc_id=doc_id, scope=d.get('scope'),
                    why_allowed=d.get('why_allowed'), link=f'/documents/{doc_id}' + (f'#{chunk_id}' if chunk_id else ''),
                    chunk_id=chunk_id, page_or_section=page)

    hyps = analysis.get('hypotheses') or []
    if hyps:
        mode = 'ranked'
        for h in hyps:
            name = h['category'].capitalize() + (f" · {h['subcause'].capitalize()}" if h.get('subcause') else '')
            hid = node(f"hyp{h['rank']}", 'cause', 'hypothesis', f"#{h['rank']} {name}", rank=h['rank'],
                       confidence=h['confidence'], narrative=h.get('narrative'), category=h['category'], subcause=h.get('subcause'))
            for e in h['supporting_evidence']:
                edge(evidence_node(e, 'supporting'), hid, 'supports', _weight_label(e.get('weight')), e.get('weight'))
            for e in h['contradicting_evidence']:
                edge(evidence_node(e, 'contradicting'), hid, 'contradicts', _weight_label(e.get('weight')), e.get('weight'))
            for i, s in enumerate(h.get('verification_steps', [])):
                sid = node(f"step{h['rank']}-{i}", 'action', 'action', s['step'][:90], step=s['step'], source=s['source'],
                           chunk_id=s.get('chunk_id'))
                edge(hid, sid, 'verify', 'verify')
                edge(sid, document_node(s['source'], s.get('chunk_id'), s.get('page_or_section')), 'cites',
                     s.get('page_or_section') or 'cites')
            for i, m in enumerate(h.get('missing_checks', [])):
                edge(hid, node(f"miss{h['rank']}-{i}", 'action', 'missing', m, step=m), 'missing', 'missing check')
    else:
        mode = 'abstain'
        aid = node('abstain', 'verdict', 'abstain', 'Insufficient evidence',
                   description=f'No hypothesis reached the minimum evidence score ({CONFIG.thresholds.min_score}).')
        names = CONFIG.category_names()
        for c in analysis.get('category_evidence', []):
            if not c['supporting'] and not c['contradicting']:
                continue
            cid = node(f"cat:{c['category']}", 'cause', 'category', names.get(c['category'], c['category']),
                       category=c['category'], supporting=len(c['supporting']), contradicting=len(c['contradicting']))
            edge(cid, aid, 'below_minimum', 'below minimum')
            for e in c['supporting']:
                edge(evidence_node(e, 'supporting'), cid, 'supports')
            for e in c['contradicting']:
                edge(evidence_node(e, 'contradicting'), cid, 'contradicts')
            if c['supporting']:
                for cand in CONFIG.candidates:
                    if cand.category == c['category']:
                        for i, m in enumerate(cand.missing_checks):
                            edge(cid, node(f'miss:{cand.key}:{i}', 'action', 'missing', m, step=m), 'missing', 'missing check')
        for d in docs.values():
            chunk = (d.get('chunks') or [{}])[0]
            edge(aid, document_node(d['doc_id'], chunk.get('chunk_id'), chunk.get('page_or_section')), 'reference', 'suggested reference')
    # Vertically centre each cause node on its evidence so edges stay short.
    for n in nodes.values():
        if n['data']['kind'] in ('hypothesis', 'category'):
            ys = [nodes[e['source']]['position']['y'] for e in edges if e['target'] == n['id'] and e['source'] in nodes
                  and nodes[e['source']]['data']['kind'] == 'evidence']
            if ys:
                n['position']['y'] = sum(ys) / len(ys)
    if 'abstain' in nodes:  # verdict sits level with the middle of the categories
        cats = [n['position']['y'] for n in nodes.values() if n['data']['kind'] == 'category']
        nodes['abstain']['position']['y'] = (min(cats) + max(cats)) / 2 if cats else 0
    causes = sorted((n for n in nodes.values() if n['data']['kind'] in ('hypothesis', 'category')), key=lambda n: n['position']['y'])
    for prev, cur in zip(causes, causes[1:]):  # keep at least one row between cause nodes
        cur['position']['y'] = max(cur['position']['y'], prev['position']['y'] + ROW)
    return {'mode': mode, 'run_id': analysis.get('run_id'), 'incident_id': analysis.get('incident_id'),
            'nodes': list(nodes.values()), 'edges': edges}
