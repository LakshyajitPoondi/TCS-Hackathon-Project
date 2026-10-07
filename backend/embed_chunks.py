"""(Re)embed document chunks with the configured local model. Run: python -m backend.embed_chunks [--all]

Without --all only chunks with no embedding or a different embedding model are processed.
"""
import sys
from sqlalchemy import select, or_
from backend import db
from backend.core import config
from engine.retrieval import embed_chunks, embedding_key


def run(all_chunks=False, batch=256):
    if config.EMBEDDINGS_PROVIDER == "none":
        print("EMBEDDINGS_PROVIDER=none: nothing to embed.")
        return 0
    query = select(db.DocumentChunk).order_by(db.DocumentChunk.chunk_id)
    if not all_chunks:
        query = query.where(or_(db.DocumentChunk.embedding.is_(None), db.DocumentChunk.embedding_model != embedding_key()))
    total = 0
    with db.Session() as session:
        ids = [c.chunk_id for c in session.scalars(query)]
    for start in range(0, len(ids), batch):
        with db.Session.begin() as session:
            chunks = list(session.scalars(select(db.DocumentChunk).where(db.DocumentChunk.chunk_id.in_(ids[start:start + batch]))))
            done, status = embed_chunks(chunks)
            total += done
            if status != "enabled":
                print(f"Embedding stopped: {status}")
                return 1
    print(f"Embedded {total} chunk(s) with {embedding_key()}.")
    return 0


if __name__ == "__main__":
    sys.exit(run("--all" in sys.argv))
