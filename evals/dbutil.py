"""Scratch databases for tests and evaluation workers: a temp SQLite file or a throwaway Postgres schema.

Choose with `pytest --db postgres` / TEST_DB=postgres (tests) and EVAL_DB=postgres (evaluation workers).
The Postgres server comes from TEST_POSTGRES_URL (default: the docker-compose database on port 5433).
"""
import contextlib
import os
import uuid
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

DEFAULT_PG_URL = "postgresql+psycopg://rca:rca@localhost:5433/rca_test"


_ensured = set()


def postgres_url():
    """Test server URL. The database (default rca_test, never the app database) is created if missing;
    its public schema must stay free of app tables because scratch schemas fall back to public."""
    url = os.getenv("TEST_POSTGRES_URL", DEFAULT_PG_URL)
    if url not in _ensured:
        target = make_url(url)
        admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as connection:
                exists = connection.exec_driver_sql("SELECT 1 FROM pg_database WHERE datname = %s", (target.database,)).first()
                if not exists:
                    connection.exec_driver_sql(f'CREATE DATABASE "{target.database}"')
        finally:
            admin.dispose()
        _ensured.add(url)
    return url


def schema_url(base_url, schema):
    """Same server, but every unqualified table lives in `schema` (pgvector types stay in public)."""
    return make_url(base_url).update_query_dict({"options": f"-csearch_path={schema},public"}).render_as_string(hide_password=False)


@contextlib.contextmanager
def scratch_database(kind, directory):
    """Yields a DATABASE_URL for an empty database and removes it afterwards."""
    if kind == "postgres":
        schema = "t_" + uuid.uuid4().hex[:16]
        admin = create_engine(postgres_url(), isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as connection:
                connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
                connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            yield schema_url(postgres_url(), schema)
        finally:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            admin.dispose()
    else:
        path = Path(directory) / f"scratch-{uuid.uuid4().hex}.db"
        try:
            yield "sqlite:///" + str(path.resolve())
        finally:
            for suffix in ("", "-shm", "-wal"):
                p = Path(str(path) + suffix)
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
