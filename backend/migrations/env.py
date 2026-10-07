"""Alembic environment. Uses DATABASE_URL unless `-x url=...` or a connection is supplied."""
from alembic import context
from sqlalchemy import engine_from_config, pool
from backend import db
from backend.core import config as app_config

target_metadata = db.Base.metadata
# Postgres-only objects created by raw DDL are not part of the ORM metadata.
UNMAPPED = {("column", "tsv"), ("index", "ix_document_chunks_tsv")}


def include_object(obj, name, type_, reflected, compare_to):
    return (type_, name) not in UNMAPPED and name != "alembic_version"


def run_migrations_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    url = context.get_x_argument(as_dictionary=True).get("url") or app_config.DATABASE_URL
    section = {"sqlalchemy.url": url}
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _run(connection)


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object,
                      render_as_batch=connection.dialect.name == "sqlite", compare_type=False)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline SQL generation is not supported; run against a database.")
run_migrations_online()
