"""Descriptive views of a loaded incident: summary and raw signal rows. No analysis here."""

import pandas as pd

from backend.core.config import NUMERIC_COLUMNS, TEXT_COLUMNS
from backend.models.schemas import IncidentSummary, SignalRecord, SignalsResponse


def _machines(df: pd.DataFrame) -> list[str]:
    return sorted(df["machine"].dropna().astype(str).unique().tolist())


def _clean(value):
    """Turn pandas/numpy scalars into plain JSON-safe values (NaN -> None)."""
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def build_summary(incident_id: str, df: pd.DataFrame) -> IncidentSummary:
    machines = _machines(df)
    lines = sorted(df["line"].dropna().astype(str).unique().tolist())
    return IncidentSummary(
        id=incident_id,
        line=", ".join(lines),
        machines=machines,
        machine_count=len(machines),
        record_count=len(df),
        start_time=df["timestamp"].min().to_pydatetime(),
        end_time=df["timestamp"].max().to_pydatetime(),
        total_defects=int(df["defect_count"].sum()),
        total_downtime_min=float(df["downtime_min"].sum()),
        event_codes=sorted(df["event_code"].dropna().astype(str).unique().tolist()),
    )


def build_signals(incident_id: str, df: pd.DataFrame) -> SignalsResponse:
    cols = ["machine", *NUMERIC_COLUMNS, *[c for c in TEXT_COLUMNS if c not in ("line", "machine")]]
    records = [
        SignalRecord(timestamp=ts.isoformat(), **{c: _clean(row[c]) for c in cols})
        for ts, (_, row) in zip(df["timestamp"], df[cols].iterrows())
    ]
    return SignalsResponse(incident_id=incident_id, machines=_machines(df), records=records)
