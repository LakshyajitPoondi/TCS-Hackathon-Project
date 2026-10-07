"""Incident discovery, safe path resolution, CSV loading and basic validation.

Range checks, baselines and missing-value handling belong to Phase 2 (engine/).
"""

import io
import re
import uuid
from pathlib import Path

import pandas as pd
import numpy as np
from backend.core import config

from backend.core.config import (
    EXPECTED_COLUMNS,
    MAX_UNPARSEABLE_FRACTION,
    NUMERIC_COLUMNS,
)


class IncidentNotFoundError(Exception):
    """Maps to HTTP 404."""


class IncidentValidationError(Exception):
    """Maps to HTTP 422."""


# id prefix -> (filename prefix, directory). INC = curated eval set, UPL = user uploads.
# Directories are read from config at call time so tests can redirect uploads.
_PREFIX = {"INC": "incident_", "UPL": "upload_"}


def _directory(kind: str) -> Path:
    return config.INCIDENTS_DIR if kind == "INC" else config.UPLOADS_DIR
_ID_RE = re.compile(r"^(INC|UPL)-([A-Za-z0-9]+)$")
_FILENAME_RE = re.compile(r"^(incident|upload)_([A-Za-z0-9]+)\.csv$")


# ---------- ID <-> filename (the only place this mapping lives) ----------

def incident_id_to_filename(incident_id: str) -> str:
    """`INC-001` -> `incident_001.csv`, `UPL-1a2b3c4d` -> `upload_1a2b3c4d.csv`."""
    match = _ID_RE.match(incident_id)
    if not match:
        raise IncidentNotFoundError(f"Incident not found: {incident_id}")
    prefix, suffix = match.groups()
    return f"{_PREFIX[prefix]}{suffix}.csv"


def filename_to_incident_id(filename: str) -> str | None:
    """`incident_001.csv` -> `INC-001`. Returns None for filenames that don't follow the rule."""
    match = _FILENAME_RE.match(filename)
    if not match:
        return None
    kind, suffix = match.groups()
    return f"{'INC' if kind == 'incident' else 'UPL'}-{suffix}"


def resolve_incident_path(incident_id: str) -> Path:
    filename = incident_id_to_filename(incident_id)
    directory = _directory(incident_id[:3]).resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise IncidentNotFoundError(f"Incident not found: {incident_id}")
    return path


def list_incidents() -> list[dict]:
    """Curated sample incidents only (the evaluation set). Uploads are listed by the incident registry."""
    refs = []
    for path in config.INCIDENTS_DIR.glob("incident_*.csv"):
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
    if df.columns.duplicated().any():
        raise IncidentValidationError("Duplicate column names")

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
        if np.isinf(parsed).any():
            raise IncidentValidationError(f"Column '{col}' contains non-finite values")
        lo, hi = config.PHYSICAL_RANGES[col]
        if ((parsed < lo) | (parsed > hi)).any():
            raise IncidentValidationError(f"Column '{col}' must be between {lo} and {hi}")
        if col == "defect_count" and ((parsed.dropna() % 1) != 0).any():
            raise IncidentValidationError("defect_count must contain integer counts")

    if df["machine"].isna().all():
        raise IncidentValidationError("Column 'machine' has no values")
    for field in ("machine", "line"):
        if df[field].isna().any() or df[field].astype(str).str.strip().eq("").any():
            raise IncidentValidationError(f"Column '{field}' has missing values")
    if df.duplicated(["line", "machine", "timestamp"]).any():
        raise IncidentValidationError("Duplicate machine timestamps")
    if df["line"].nunique() != 1:
        raise IncidentValidationError("One incident must contain one line")
    for machine, group in df.groupby("machine"):
        if group["timestamp"].nunique() < 10:
            raise IncidentValidationError(f"{machine}: at least 10 timesteps required")
        baseline = group.sort_values("timestamp").head(max(4, round(len(group) * .25)))
        for signal in ("temperature", "speed", "vibration", "motor_current"):
            if group[signal].notna().sum() < 10 or baseline[signal].notna().sum() < 3:
                raise IncidentValidationError(f"{machine}: insufficient usable {signal} baseline/data")

    return df.sort_values(["timestamp", "machine"], kind="stable").reset_index(drop=True)


def load_incident(incident_id: str) -> pd.DataFrame:
    return validate_dataframe(_read_csv(resolve_incident_path(incident_id)))


def save_upload(content: bytes, original_filename: str = "incident.csv") -> dict:
    """Validate an uploaded CSV, then store it under data/uploads/ and return its id."""
    if not original_filename.lower().endswith(".csv"):
        raise IncidentValidationError("Only .csv files are supported")
    if len(content) > config.UPLOAD_MAX_MB * 1024 * 1024:
        raise IncidentValidationError("CSV exceeds UPLOAD_MAX_MB")
    frame=validate_dataframe(_read_csv(io.BytesIO(content)))
    from backend import db
    with db.Session() as session:
        for short,group in frame.groupby('machine'):
            uid=str(group.line.iloc[0])+'/'+short
            machine=session.get(db.Machine,uid)
            if not machine:raise IncidentValidationError('Unknown physical machine: '+uid)
            # Baseline ranges are descriptive. Large multipliers reject unit mistakes
            # without rejecting genuine anomalies; global physical bounds still apply.
            for signal,multiplier in [('speed',5),('vibration',20),('motor_current',10)]:
                normal=machine.data.get('normal_ranges',{}).get(signal)
                if normal and normal['max']>0 and (group[signal]>normal['max']*multiplier).any():
                    raise IncidentValidationError(f'{uid}: {signal} exceeds generous baseline plausibility bound')
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    short = uuid.uuid4().hex
    filename = f"upload_{short}.csv"
    (config.UPLOADS_DIR / filename).write_bytes(content)
    return {"id": filename_to_incident_id(filename), "filename": filename}


def list_uploads() -> list[dict]:
    """Uploaded incident files on disk (registered in the incident registry on upload or at seed time)."""
    refs = []
    for path in config.UPLOADS_DIR.glob("upload_*.csv"):
        incident_id = filename_to_incident_id(path.name)
        if incident_id:
            refs.append({"id": incident_id, "filename": path.name})
    return sorted(refs, key=lambda r: r["id"])
