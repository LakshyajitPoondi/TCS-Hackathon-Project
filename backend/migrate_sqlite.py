"""Copy every row from an existing SQLite database into the configured Postgres database. Idempotent.

Run after `alembic upgrade head`:
    python -m backend.migrate_sqlite --source sqlite:///./data/app.db [--target postgresql+psycopg://...]

Rows whose primary key already exists in the target are skipped (ON CONFLICT DO NOTHING), so running it
twice copies nothing new. Old JSON embeddings are dropped unless they already have 384 dimensions;
run `python -m backend.embed_chunks` afterwards.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, Integer, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import insert
from backend import db
from backend.core import config


def _convert(column, value):
    """SQLite stores timestamps and JSON as text and booleans as 0/1; turn them into Python values."""
    if value is None:
        return None
    if isinstance(column.type, db.UTCDateTime):
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    if isinstance(column.type, db.EmbeddingType):
        vector = json.loads(value) if isinstance(value, str) else value
        return vector if isinstance(vector, list) and len(vector) == db.EMBEDDING_DIM else None
    if isinstance(column.type, JSON):
        return json.loads(value) if isinstance(value, str) else value
    if isinstance(column.type, Boolean):
        return bool(value)
    return value


def copy(source_url, target_url):
    source = create_engine(source_url)
    target = create_engine(target_url)
    if target.dialect.name != "postgresql":
        raise SystemExit("Target must be Postgres (postgresql+psycopg://...).")
    source_tables = set(inspect(source).get_table_names())
    report = {}
    with source.connect() as src, target.begin() as dst:
        for table in db.Base.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            source_columns = {c["name"] for c in inspect(source).get_columns(table.name)}
            rows = src.execute(text(f'SELECT * FROM "{table.name}"')).mappings().all()
            inserted = 0
            for row in rows:
                values = {}
                for column in table.columns:
                    if column.name not in source_columns:
                        continue
                    values[column.name] = _convert(column, row[column.name])
                if table.name == "document_chunks" and values.get("embedding") is None:
                    values["embedding_model"] = None
                statement = insert(table).values(**values).on_conflict_do_nothing().returning(*table.primary_key.columns)
                inserted += dst.execute(statement).first() is not None
            report[table.name] = {"source_rows": len(rows), "inserted": inserted}
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and isinstance(pk[0].type, Integer):
                dst.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                                 f"COALESCE((SELECT MAX({pk[0].name}) FROM {table.name}), 0) + 1, false)"))
    source.dispose()
    target.dispose()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="sqlite:///./data/app.db")
    parser.add_argument("--target", default=config.DATABASE_URL)
    args = parser.parse_args()
    if not args.source.startswith("sqlite"):
        sys.exit("Source must be a SQLite URL.")
    result = copy(args.source, args.target)
    for name, counts in result.items():
        print(f"{name:<24} source={counts['source_rows']:<6} inserted={counts['inserted']}")
    print("Done. Run `python -m backend.embed_chunks` to (re)build embeddings.")
