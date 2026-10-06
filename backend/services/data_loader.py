"""Incident discovery, safe path resolution, CSV loading and basic validation.

Range checks, baselines and missing-value handling belong to Phase 2 (engine/).
"""

import io
import re
import uuid
from pathlib import Path

import pandas as pd

from backend.core.config import (
    EXPECTED_COLUMNS,
    INCIDENTS_DIR,
    MAX_UNPARSEABLE_FRACTION,
    NUMERIC_COLUMNS,
    UPLOADS_DIR,
)


class IncidentNotFoundError(Exception):
    """Maps to HTTP 404."""


class IncidentValidationError(Exception):
    """Maps to HTTP 422."""


# id prefix -> (filename prefix, directory). INC = curated eval set, UPL = user uploads.
_SOURCES: dict[str, tuple[str, Path]] = {
    "INC": ("incident_", INCIDENTS_DIR),
    "UPL": ("upload_", UPLOADS_DIR),
}
_ID_RE = re.compile(r"^(INC|UPL)-([A-Za-z0-9]+)$")
_FILENAME_RE = re.compile(r"^(incident|upload)_([A-Za-z0-9]+)\.csv$")


# ---------- ID <-> filename (the only place this mapping lives) ----------

def incident_id_to_filename(incident_id: str) -> str:
    """`INC-001` -> `incident_001.csv`, `UPL-1a2b3c4d` -> `upload_1a2b3c4d.csv`."""
    match = _ID_RE.match(incident_id)
    if not match:
        raise IncidentNotFoundError(f"Incident not found: {incident_id}")
    prefix, suffix = match.groups()
    return f"{_SOURCES[prefix][0]}{suffix}.csv"


def filename_to_incident_id(filename: str) -> str | None:
    """`incident_001.csv` -> `INC-001`. Returns None for filenames that don't follow the rule."""
    match = _FILENAME_RE.match(filename)
    if not match:
        return None
    kind, suffix = match.groups()
    return f"{'INC' if kind == 'incident' else 'UPL'}-{suffix}"


def resolve_incident_path(incident_id: str) -> Path:
    filename = incident_id_to_filename(incident_id)
    directory = _SOURCES[incident_id[:3]][1].resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise IncidentNotFoundError(f"Incident not found: {incident_id}")
    return path


def list_incidents() -> list[dict]:
    """Curated incidents only. Uploads are excluded to keep the eval set clean."""
    refs = []
    for path in INCIDENTS_DIR.glob("incident_*.csv"):
        incident_id = filename_to_incident_id(path.name)
        if incident_id:
            refs.append({"id": incident_id, "filename": path.name})
    return sorted(refs, key=lambda r: r["id"])


# ---------- Reading and validation ----------

def _read_csv(source) -> pd.DataFrame:
    try:
        return pd.read_csv(source, dtype=str, keep_default_na=True, skipinitialspace=True)
    except pd.errors.EmptyDataError:
        raise IncidentValidationError("File is empty")
    except UnicodeDecodeError:
        raise IncidentValidationError("File is not valid UTF-8 text")
    except (pd.errors.ParserError, ValueError) as exc:
        raise IncidentValidationError(f"Malformed CSV: {str(exc).splitlines()[0]}")


def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Schema, timestamp and numeric checks. Returns a cleaned copy sorted by timestamp and machine."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if df.empty:
        raise IncidentValidationError("File has no data rows")

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise IncidentValidationError(f"Missing required columns: {', '.join(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad_ts = int(df["timestamp"].isna().sum())
    if bad_ts:
        raise IncidentValidationError(f"Invalid or missing timestamp in {bad_ts} row(s)")

    for col in NUMERIC_COLUMNS:
        present = df[col].notna()
        parsed = pd.to_numeric(df[col], errors="coerce")
        unparseable = int((present & parsed.isna()).sum())
        if present.sum() == 0 or unparseable / present.sum() > MAX_UNPARSEABLE_FRACTION:
            raise IncidentValidationError(f"Column '{col}' has mostly non-numeric values")
        df[col] = parsed

    if df["machine"].isna().all():
        raise IncidentValidationError("Column 'machine' has no values")

    return df.sort_values(["timestamp", "machine"], kind="stable").reset_index(drop=True)


def load_incident(incident_id: str) -> pd.DataFrame:
    return validate_dataframe(_read_csv(resolve_incident_path(incident_id)))


def save_upload(content: bytes) -> dict:
    """Validate an uploaded CSV, then store it under data/uploads/ and return its id."""
    validate_dataframe(_read_csv(io.BytesIO(content)))
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    short = uuid.uuid4().hex[:8]
    filename = f"upload_{short}.csv"
    (UPLOADS_DIR / filename).write_bytes(content)
    return {"id": filename_to_incident_id(filename), "filename": filename}
