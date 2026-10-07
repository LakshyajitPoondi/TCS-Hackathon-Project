"""Alembic on an empty database, v1 adoption, schema drift and the SQLite -> Postgres copy."""
import json
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic import command
from sqlalchemy import create_engine, inspect, text, select
from backend import db
from backend.init_db import migrate, alembic_config
from evals.dbutil import scratch_database

UNMAPPED = {("column", "tsv"), ("index", "ix_document_chunks_tsv")}


def _diff(engine):
    def include(obj, name, type_, reflected, compare_to):
        if (type_, name) in UNMAPPED or name == "alembic_version":
            return False
        # Postgres-only index declared with ddl_if.
        return not (engine.dialect.name != "postgresql" and name == "ix_document_chunks_embedding_hnsw")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": False, "include_object": include})
        return compare_metadata(context, db.Base.metadata)


def test_upgrade_empty_database_matches_models(tmp_path, db_kind):
    with scratch_database(db_kind, tmp_path) as url:
        engine = db.make_engine(url)
        migrate(engine)
        assert _diff(engine) == []
        tables = set(inspect(engine).get_table_names())
        assert {"users", "documents", "document_chunks", "cases", "alembic_version"} <= tables
        if db_kind == "postgres":
            with engine.connect() as c:
                kinds = dict(c.execute(text("SELECT column_name, udt_name FROM information_schema.columns "
                                            "WHERE table_name='document_chunks' AND table_schema=current_schema()")).all())
                assert kinds["embedding"] == "vector" and kinds["tsv"] == "tsvector"
                ts = c.execute(text("SELECT data_type FROM information_schema.columns WHERE table_name='cases' "
                                    "AND column_name='created_at' AND table_schema=current_schema()")).scalar()
                assert ts == "timestamp with time zone"
        migrate(engine)  # idempotent
        engine.dispose()


def test_v1_database_is_adopted_and_timestamps_converted(tmp_path, db_kind):
    """A database created by the v1 code (no Alembic, ISO-string timestamps) upgrades in place."""
    with scratch_database(db_kind, tmp_path) as url:
        engine = db.make_engine(url)
        with engine.begin() as connection:
            command.upgrade(alembic_config(connection), "0001")
            connection.execute(text("DROP TABLE alembic_version"))  # v1 never had Alembic
            connection.execute(text("INSERT INTO cases (case_id, status, created_at, data) VALUES "
                                    "('C1', 'approved', '2026-10-06T09:22:53.257285+00:00', :d)"), {"d": json.dumps({"x": 1})})
        migrate(engine)
        with engine.connect() as connection:
            from alembic.script import ScriptDirectory
            head = ScriptDirectory.from_config(alembic_config()).get_current_head()
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            case = session.get(db.Case, "C1")
            assert case.created_at.year == 2026 and case.created_at.utcoffset().total_seconds() == 0
            assert case.data == {"x": 1}
        engine.dispose()


def test_sqlite_to_postgres_copy_is_idempotent(tmp_path, db_kind):
    if db_kind != "postgres":
        pytest.skip("copy target must be Postgres; run with --db postgres")
    from backend.migrate_sqlite import copy
    source_url = "sqlite:///" + str((tmp_path / "v1.db").resolve())
    source = create_engine(source_url)
    with source.begin() as connection:
        command.upgrade(alembic_config(connection), "0001")
        connection.execute(text("INSERT INTO users VALUES ('u1','a@b.c','hash','admin',1,0)"))
        connection.execute(text("INSERT INTO cases (case_id,status,proposer_id,created_at,data) VALUES "
                                "('C1','approved','u1','2026-10-06T09:22:53.257285+00:00',:d)"), {"d": json.dumps({"summary": "s"})})
        connection.execute(text("INSERT INTO audit_log (id,user_id,action,created_at,data) VALUES (7,'u1','login','2026-10-06T10:00:00+00:00','{}')"))
    source.dispose()
    with scratch_database("postgres", tmp_path) as target_url:
        target = db.make_engine(target_url)
        migrate(target)
        first = copy(source_url, target_url)
        assert first["cases"]["inserted"] == 1 and first["users"]["inserted"] == 1
        assert copy(source_url, target_url)["cases"]["inserted"] == 0
        from sqlalchemy.orm import Session
        with Session(target) as session:
            assert session.get(db.User, "u1").active is True
            assert session.get(db.Case, "C1").data == {"summary": "s"}
            session.add(db.AuditLog(user_id="u1", action="after_copy", data={}))
            session.commit()  # the id sequence was moved past the copied ids
            assert max(session.scalars(select(db.AuditLog.id))) > 7
        target.dispose()
