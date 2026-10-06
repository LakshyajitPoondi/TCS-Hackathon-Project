import io
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.data_loader import validate_dataframe, IncidentValidationError
from evals.sanity_check import run

@pytest.mark.parametrize("column,value", [("defect_count", "inf"), ("defect_count", "-2"), ("downtime_min", "-4"), ("defect_count", "1.5"), ("speed", "900000"), ("temperature", "")])
def test_invalid_csv(column, value):
    df = pd.read_csv("data/incidents/incident_001.csv", dtype=str)
    df[column] = value
    if column == "temperature":
        df.loc[0, column] = "65"
    client = TestClient(app)
    response = client.post("/api/incidents/upload", files={"file": ("probe.csv", df.to_csv(index=False).encode())})
    assert response.status_code == 422
    assert response.headers["X-Request-ID"]

def test_extension_and_limit(monkeypatch):
    from backend.core import config
    client = TestClient(app)
    content = Path("data/incidents/incident_001.csv").read_bytes()
    assert client.post("/api/incidents/upload", files={"file": ("probe.txt", content)}).status_code == 422
    monkeypatch.setattr(config, "UPLOAD_MAX_MB", .00001)
    assert client.post("/api/incidents/upload", files={"file": ("probe.csv", content)}).status_code == 422

def test_rank_regression():
    summary = run()["summary"]
    assert summary == {"top1_hits":"16/16", "top3_hits":"16/16", "correct_abstentions":"2/2", "wrong_abstentions":"0/16", "ambiguous_also_plausible_in_top3":"3/3"}

def test_safe_missing_shift():
    from engine.scoring import _shift_ev
    assert _shift_ev({"machine_stats":{"m":{"temperature":{"baseline":{"mean":None},"window":{"mean":None},"delta_abs":None}}}}, "m", "temperature") is None

def test_error_json():
    from backend.api.routes import incidents
    from unittest.mock import patch
    with patch.object(incidents.data_loader, "list_incidents", side_effect=RuntimeError("private detail")):
        response=TestClient(app, raise_server_exceptions=False).get("/api/incidents")
        assert response.status_code == 500
        assert response.json()["request_id"] == response.headers["X-Request-ID"]
        assert "private" not in response.text
