"""Experience Memory (local JSON). Similar cases are supporting context only; they never change scores or ranks.

Signatures use the vocabulary of data/memory_seed.json ("signals" lists). The seed file is read-only;
saved cases are appended to data/memory_cases.json. Hindsight adapter deferred (MEMORY_BACKEND=local only).
"""

import json
import re
from datetime import datetime, timezone

from backend.core.config import MEMORY_CASES_PATH, MEMORY_SEED_PATH
from backend.models.schemas import SimilarCase

MIN_SHARED = 2
TOP_K = 3

# evidence `notes` category -> seed note tag (the seed has no method-note tag)
NOTE_TAGS = {"cooling": "note_heat", "mechanical": "note_noise", "material": "note_lot",
             "people": "note_calibration", "measurement": "note_panel_vs_probe", "environment": "note_ambient"}


def build_signature(evidence: dict) -> list[str]:
    """Map the evidence dict onto the seed's tag vocabulary. Sorted, deduplicated."""
    if evidence.get("insufficient_data"):
        return []
    ms, machines = evidence["machine_stats"], evidence["machines"]
    co, d, ev = evidence["co_movement"], evidence["defects"], evidence["events"]

    def any_flag(signal, flag, where=None):
        return any(ms[m][signal][flag] for m in machines if where is None or where(m))

    odd_temp = lambda m: ms[m]["temperature"]["flat"] or ms[m]["temperature"]["spiky"]  # noqa: E731
    affected = set(co["machines_deviating"]) | set(d["machines_up"])
    alarm_codes = " ".join(evidence.get("alarms", {}))
    tags = {
        "temp_up": any_flag("temperature", "rose", lambda m: not odd_temp(m)) and not co["temp_rise_multi_machine"],
        "multi_machine_temp_up": co["temp_rise_multi_machine"],
        "temp_flatline": any_flag("temperature", "flat"),
        "temp_spike": any_flag("temperature", "spiky"),
        "vibration_up": any_flag("vibration", "rose"),
        "current_up": any_flag("motor_current", "rose"),
        "speed_down": any_flag("speed", "fell"),
        "speed_jitter": any_flag("speed", "jittery"),
        # speed moved on a machine whose temperature did not rise (not explained by cooling)
        "speed_setpoint_shift": any(
            (ms[m]["speed"]["rose"] or ms[m]["speed"]["fell"]) and not ms[m]["temperature"]["rose"] for m in machines),
        "alarm_temp_hi": "TEMP" in alarm_codes,
        "alarm_vib_hi": "VIB" in alarm_codes,
        "defects_up": d["defects_up"] or bool(d["machines_up"]),
        "defects_up_all_machines": len(machines) >= 2 and len(d["machines_up"]) == len(machines),
        "defects_baseline": d["near_baseline"],
        "downtime_up": (evidence.get("window_downtime_min") or 0) > 0,
        "batch_concentration": evidence["batch"].get("concentrated", False),
        "chg_precedes_rise": ev["changeover_before_incident"],
        "shift_chg_precedes_rise": ev["shift_change_before_incident"],
        "sensors_normal": evidence["sensors_broadly_normal"],
        "single_machine": co["applicable"] and len(affected) == 1,
    }
    for cat, tag in NOTE_TAGS.items():
        tags[tag] = bool(evidence["notes"][cat]["keywords"])
    return sorted(t for t, on in tags.items() if on)


def _read(path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else list(data.values())


def all_cases() -> list[dict]:
    from backend.db import Session, Case
    from sqlalchemy import select
    with Session() as session:
        return [{**c.data, "case_id":c.case_id, "source_incident_id":c.source_incident_id} for c in session.scalars(select(Case).where(Case.status == "approved"))]


def recall(signature: list[str], exclude_incident_id: str | None = None, top_k: int = TOP_K) -> list[SimilarCase]:
    sig = set(signature)
    scored = []
    for case in all_cases():
        if exclude_incident_id and case.get("source_incident_id") == exclude_incident_id:
            continue
        tags = set(case.get("signals", []))
        shared = sig & tags
        if len(shared) < MIN_SHARED:
            continue
        jaccard = len(shared) / len(sig | tags)
        scored.append((jaccard, len(shared), case, sorted(shared)))
    scored.sort(key=lambda r: (-r[0], -r[1], r[2]["case_id"]))
    return [
        SimilarCase(case_id=c["case_id"], confirmed_category=c["confirmed_category"],
                    confirmed_subcause=c.get("confirmed_subcause"), shared_signals=shared,
                    similarity_description=f"Shares {len(shared)} of {len(c.get('signals', []))} key signals with {c['case_id']}.")
        for _, _, c, shared in scored[:top_k]
    ]


def _next_case_id(cases: list[dict]) -> str:
    """Continue the seed convention: INC-H12 -> INC-H13 (keeps zero-padding width)."""
    nums = [(int(m.group(1)), len(m.group(1))) for c in cases if (m := re.match(r"^INC-H(\d+)$", c.get("case_id", "")))]
    n, width = (max(nums)[0], max(w for _, w in nums)) if nums else (0, 2)
    return f"INC-H{n + 1:0{width}d}"


def retain(case: dict) -> str:
    """Append a saved case to memory_cases.json. `case` must hold `signals`, `confirmed_category`,
    `confirmed_subcause`, `source_incident_id`; a case_id and saved_at are assigned here."""
    from backend.db import Session, Case
    import uuid
    case_id = "CASE-" + uuid.uuid4().hex
    with Session.begin() as session:
        session.add(Case(case_id=case_id, source_incident_id=case.get("source_incident_id"), status="approved", data=case))
    return case_id
