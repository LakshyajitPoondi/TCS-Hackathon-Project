"""Idempotent schema and synthetic historical-case seed. Run as a module.

Postgres: schema comes from Alembic (`upgrade head`). SQLite (tests/dev): `create_all`.
DB_BOOTSTRAP=create_all|migrate overrides the choice (tests use create_all for speed).
"""
import json
import os
from sqlalchemy import inspect
from backend import db
from backend.core.config import MEMORY_SEED_PATH, ROOT_DIR


def alembic_config(connection=None):
    from alembic.config import Config
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "backend" / "migrations"))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def migrate(engine=None):
    """alembic upgrade head. A v1 database created without Alembic is stamped at 0001 first."""
    from alembic import command
    engine = engine or db.engine
    with engine.begin() as connection:
        if db.is_postgres(connection):
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        tables = set(inspect(connection).get_table_names())
        cfg = alembic_config(connection)
        if "users" in tables and "alembic_version" not in tables:
            command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")


def create_schema(engine=None):
    engine = engine or db.engine
    if db.is_postgres(engine):
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    db.Base.metadata.create_all(engine)


def bootstrap_mode():
    mode = os.getenv("DB_BOOTSTRAP", "").strip().lower()
    if mode in ("create_all", "migrate"):
        return mode
    return "migrate" if db.is_postgres() else "create_all"


def init_db():
    if bootstrap_mode() == "migrate":
        migrate()
    else:
        create_schema()
    with db.Session.begin() as session:
        from backend.services.machines import seed_machines
        seed_machines(session)
        session.flush()
        from backend.services.documents import ingest
        from backend.core.config import SOPS_DIR
        for path in sorted(SOPS_DIR.glob('SOP-*.md')):
            if not session.get(db.Document,path.stem):
                title=path.read_text(encoding='utf-8').splitlines()[0].split(':',1)[1].strip()
                ingest(session,path.name,path.read_bytes(),title,'sop','1','plant',[],None,doc_id=path.stem)
        for item in json.loads(MEMORY_SEED_PATH.read_text(encoding="utf-8")):
            if not session.get(db.Case, item["case_id"]):
                item = {**item, 'machine_uid':item['line']+'/'+item['machine'], 'model':'IMM',
                        "label":"synthetic seed", "summary":f"Synthetic seed {item['confirmed_category']} case.", "fix_applied":"Synthetic fixture; no actual repair performed."}
                session.add(db.Case(case_id=item["case_id"], status="approved", data=item))
    from backend.auth import seed_users
    seed_users()

if __name__ == "__main__":
    init_db()
    print(f"Database schema ({bootstrap_mode()}) and synthetic cases initialized (idempotent).")
