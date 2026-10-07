"""Real-embedding retrieval benchmark (fastembed by default). On Postgres this measures pgvector (HNSW cosine,
filtered in SQL) fused with full-text search; on SQLite it measures BM25 + in-memory cosine.
Metrics: recall@4, MRR (first expected document), wrong-machine leaks, filtered-out correctness."""
import json
import sys
from backend import db
from backend.core import config

QUERY = 'coolant flow synthetic specification vibration limit chiller reference manual'


def run(provider='fastembed'):
    from backend.init_db import init_db
    from evals.generate_docs import install_fixtures
    from engine import retrieval
    config.EMBEDDINGS_PROVIDER = provider
    init_db(); _, key = install_fixtures(); rows = []
    # Earlier probes in the same worker may have stored mock vectors; embed every chunk with the real model.
    from sqlalchemy import select
    with db.Session.begin() as session:
        stale = [c for c in session.scalars(select(db.DocumentChunk)) if c.embedding_model != retrieval.embedding_key()]
        done, status = retrieval.embed_chunks(stale)
        if status not in ('enabled', 'disabled'):
            return {'status': 'Unverified', 'reason': status}
    with db.Session() as session:
        embedded = sum(1 for c in session.scalars(select(db.DocumentChunk)) if c.embedding_model == retrieval.embedding_key())
    backend = 'postgres+pgvector' if db.is_postgres() else 'sqlite (in-memory cosine)'
    for iid, item in key['incidents'].items():
        uids = list(item['expected_facts'])
        result = retrieval.search(uids, QUERY, 4)
        if result['embedding_status'] != 'enabled':
            return {'status': 'Unverified', 'reason': result['embedding_status'], 'backend': backend}
        actual = [h['doc_id'] for h in result['hits']]; expected = set(item['expected_doc_ids'])
        positions = [actual.index(d) + 1 for d in expected if d in actual]
        rows.append({'incident_id': iid, 'recall_at_4': len(set(actual) & expected) / len(expected),
                     'reciprocal_rank': 1 / min(positions) if positions else 0,
                     'wrong_machine_leaks': len(set(actual) & set(item['forbidden_doc_ids'])),
                     'filtered_correct': all(f['doc_id'] not in actual for f in result['filtered'])})
    n = len(rows)
    return {'status': 'Verified', 'backend': backend, 'model': config.EMBEDDINGS_MODEL, 'chunks_embedded': embedded,
            'recall_at_4': sum(r['recall_at_4'] for r in rows) / n, 'mrr': sum(r['reciprocal_rank'] for r in rows) / n,
            'wrong_machine_leaks': sum(r['wrong_machine_leaks'] for r in rows),
            'filtered_correctness': sum(r['filtered_correct'] for r in rows) / n, 'details': rows}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else 'fastembed')))
