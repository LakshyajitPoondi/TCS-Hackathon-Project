"""Idempotent schema and synthetic historical-case seed. Run as a module."""
import json
from backend import db
from backend.core.config import MEMORY_SEED_PATH

def init_db():
    db.Base.metadata.create_all(db.engine)
    with db.Session.begin() as session:
        for item in json.loads(MEMORY_SEED_PATH.read_text(encoding="utf-8")):
            if not session.get(db.Case, item["case_id"]):
                item = {**item, "label":"synthetic seed", "summary":f"Synthetic seed {item['confirmed_category']} case.", "fix_applied":"Synthetic fixture; no actual repair performed."}
                session.add(db.Case(case_id=item["case_id"], status="approved", data=item))
    from backend.auth import seed_users
    seed_users()

if __name__ == "__main__":
    init_db()
    print("Database schema and synthetic cases initialized (idempotent).")
