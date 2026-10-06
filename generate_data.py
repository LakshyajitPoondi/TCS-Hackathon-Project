"""Seeded synthetic data generator for Production Intelligence & RCA.

Writes:
  data/incidents/incident_001.csv .. incident_018.csv  (1 line x 3 machines x 40 steps of 2 min)
  data/answer_key.json   (read ONLY by the eval script)
  data/memory_seed.json  (historical cases for Experience Memory, separate seed)

Run: python generate_data.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
INCIDENTS_DIR = ROOT / "data" / "incidents"
SEED = 42
MEMORY_SEED = 7

STEPS = 40
STEP_MIN = 2
MACHINES = ["IMM-01", "IMM-02", "IMM-03"]
LINES = ["LINE-A", "LINE-B", "LINE-C"]
COLUMNS = [
    "timestamp", "line", "machine", "event_code", "temperature", "speed",
    "vibration", "motor_current", "defect_count", "downtime_min", "batch", "operator_note",
]

# Per-machine baselines: temperature (C), speed (units/min), vibration (mm/s), motor current (A)
BASE_TEMP = np.array([62.0, 65.0, 68.0])
BASE_SPEED = np.array([120.0, 118.0, 122.0])
BASE_VIB = np.array([2.4, 2.6, 2.5])
BASE_CURRENT = np.array([14.5, 15.0, 15.5])

SCENARIOS = {
    1: "cooling", 9: "cooling", 17: "cooling",
    2: "mechanical", 10: "mechanical", 18: "mechanical",
    3: "material", 11: "material",
    4: "method", 12: "method",
    5: "people", 13: "people",
    6: "measurement", 14: "measurement",
    7: "environment", 15: "environment",
    8: "insufficient", 16: "insufficient",
}

ANSWER = {  # scenario -> (category, subcause, expected SOP)
    "cooling": ("machine", "cooling", "SOP-007"),
    "mechanical": ("machine", "mechanical", "SOP-004"),
    "material": ("material", None, "SOP-012"),
    "method": ("method", None, "SOP-018"),
    "people": ("people", None, "SOP-021"),
    "measurement": ("measurement", None, "SOP-015"),
    "environment": ("environment", None, "SOP-024"),
    "insufficient": (None, None, "SOP-002"),
}

ALSO_PLAUSIBLE = {
    11: [{"category": "method", "subcause": None}],
    17: [{"category": "machine", "subcause": "mechanical"}],
    18: [{"category": "machine", "subcause": "cooling"}],
}


def profile(ws: int, we: int, ramp: int = 4) -> np.ndarray:
    """0 outside the window, ramps linearly to 1 over `ramp` steps, holds until we, then drops back."""
    p = np.zeros(STEPS)
    for t in range(ws, we + 1):
        p[t] = min(1.0, (t - ws + 1) / ramp)
    return p


def window_mask(ws: int, we: int) -> np.ndarray:
    m = np.zeros(STEPS, dtype=bool)
    m[ws:we + 1] = True
    return m


def build_incident(n: int, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    scenario = SCENARIOS[n]
    line = LINES[(n - 1) % len(LINES)]
    start = pd.Timestamp(2026, 3, 1, 6, 0) + pd.Timedelta(days=n - 1)
    times = [start + pd.Timedelta(minutes=STEP_MIN * t) for t in range(STEPS)]

    ws = int(rng.integers(16, 22))
    we = min(STEPS - 4, ws + int(rng.integers(11, 15)))
    target = int(rng.integers(0, 3))
    prof, win = profile(ws, we), window_mask(ws, we)

    temp = BASE_TEMP[:, None] + rng.normal(0, 0.6, (3, STEPS))
    speed = BASE_SPEED[:, None] + rng.normal(0, 1.2, (3, STEPS))
    vib = BASE_VIB[:, None] + rng.normal(0, 0.08, (3, STEPS))
    current = BASE_CURRENT[:, None] + rng.normal(0, 0.25, (3, STEPS))
    defects = rng.poisson(0.3, (3, STEPS)).astype(int)
    downtime = np.zeros((3, STEPS))
    events = np.full((3, STEPS), "RUN", dtype=object)
    notes = np.full((3, STEPS), "", dtype=object)
    batch = np.array([[f"LOT-{n:02d}{m + 1}{t // 10 + 1}" for t in range(STEPS)] for m in range(3)], dtype=object)

    def add_defects(m: int, lam: float) -> None:
        defects[m, win] += rng.poisson(lam, win.sum())

    def stop(m: int, t: int, minutes: float) -> None:
        events[m, t], downtime[m, t] = "STOP", minutes

    mid = (ws + we) // 2

    if scenario == "cooling":
        temp[target] += rng.uniform(15.5, 18.5) * prof
        speed[target] -= BASE_SPEED[target] * rng.uniform(0.08, 0.12) * prof
        add_defects(target, 2.5)
        for t in range(ws + 3, we + 1, 3):
            events[target, t] = "ALM_TEMP_HI"
        stop(target, mid + 1, float(rng.integers(5, 9)))
        notes[target, ws + 3] = {1: "housing hot to touch, cooling fan sounds weak",
                                 9: "coolant flow low on chiller gauge",
                                 17: "cabinet fan noisy, barrel temp climbing"}[n]
        if n == 17:  # ambiguous: some vibration as well
            vib[target] += BASE_VIB[target] * 0.22 * prof

    elif scenario == "mechanical":
        vib[target] += BASE_VIB[target] * rng.uniform(0.55, 0.70) * prof
        current[target] += BASE_CURRENT[target] * rng.uniform(0.10, 0.15) * prof
        speed[target] += rng.normal(0, 4.5, STEPS) * prof
        add_defects(target, 2.0)
        for t in range(ws + 3, we + 1, 3):
            events[target, t] = "ALM_VIB_HI"
        stop(target, mid, float(rng.integers(4, 8)))
        notes[target, ws + 2] = {2: "grinding noise near gearbox",
                                 10: "grinding sound from drive, bearing feels rough",
                                 18: "grinding noise and some heat at motor housing"}[n]
        if n == 18:  # ambiguous: moderate temperature rise as well
            temp[target] += 7.0 * prof

    elif scenario == "material":
        bad_lot = f"LOT-{n:02d}99"
        batch[:, win] = bad_lot
        for m in range(3):
            add_defects(m, 2.2)
        events[target, mid] = "QC_HOLD"
        downtime[target, mid] = 10.0
        notes[target, ws] = "new supplier resin lot started"
        notes[(target + 1) % 3, ws + 4] = "short shots, lot looks off-spec"
        if n == 11:  # ambiguous: a changeover on one machine just before the rise
            other = (target + 2) % 3
            events[other, ws - 1] = "CHG"
            notes[other, ws - 1] = "changeover to part 7741"

    elif scenario == "method":
        chg = ws - 2
        events[target, chg] = "CHG"
        notes[target, chg] = "changeover to part 4410, new setpoints loaded"
        shift = BASE_SPEED[target] * 0.08
        speed[target, chg + 1:we + 1] += shift
        add_defects(target, 2.2)
        notes[target, we + 1] = "setpoints restored per setup sheet"

    elif scenario == "people":
        events[:, ws - 1] = "SHIFT_CHG"
        affected = [target] if n == 5 else [target, (target + 1) % 3]
        for m in affected:
            add_defects(m, 2.0)
        notes[target, ws] = ("handover: calibration check skipped" if n == 5
                             else "new operator on line, handover checklist incomplete")

    elif scenario == "measurement":
        if n == 6:  # non-physical spikes
            for t in sorted(rng.choice(np.arange(ws, we + 1), 3, replace=False)):
                temp[target, t] += rng.uniform(35, 45)
                events[target, t] = "ALM_TEMP_HI"
            notes[target, ws + 1] = "panel temp reads high, housing probe normal"
        else:  # flat-lined reading
            temp[target, ws:we + 1] = round(float(temp[target, ws]), 1)
            notes[target, ws + 2] = "panel display stuck, handheld reading differs"

    elif scenario == "environment":
        drift = profile(ws, we, ramp=6)
        for m in range(3):
            temp[m] += rng.uniform(6.0, 8.0) * drift
            add_defects(m, 0.8)
        notes[target, ws + 1] = ("plant AC unit tripped, ambient high" if n == 7
                                 else "hot afternoon, bay doors open, ambient high")

    elif scenario == "insufficient":
        if n == 8:  # weak signals
            temp[target] += 2.5 * prof
            add_defects(target, 0.5)
        else:  # conflicting weak signals on different machines
            vib[target] += BASE_VIB[target] * 0.12 * prof
            temp[(target + 1) % 3] += 3.0 * prof
            add_defects((target + 2) % 3, 0.6)
            notes[(target + 2) % 3, mid] = "minor jam cleared"

    rows = []
    for t in range(STEPS):
        for m in range(3):
            rows.append({
                "timestamp": times[t].strftime("%Y-%m-%d %H:%M:%S"),
                "line": line,
                "machine": MACHINES[m],
                "event_code": events[m, t],
                "temperature": round(float(temp[m, t]), 1),
                "speed": round(float(speed[m, t]), 1),
                "vibration": round(float(vib[m, t]), 2),
                "motor_current": round(float(current[m, t]), 2),
                "defect_count": int(defects[m, t]),
                "downtime_min": float(downtime[m, t]),
                "batch": batch[m, t],
                "operator_note": notes[m, t],
            })

    category, subcause, sop = ANSWER[scenario]
    key = {
        "file": f"incident_{n:03d}.csv",
        "scenario": scenario,
        "category": category,
        "subcause": subcause,
        "also_plausible": ALSO_PLAUSIBLE.get(n, []),
        "expect_abstain": scenario == "insufficient",
        "expected_sop": sop,
        "window": {"start": times[ws].isoformat(), "end": times[we].isoformat()},
        "target_machine": MACHINES[target],
    }
    return pd.DataFrame(rows, columns=COLUMNS), key


# Signal vocabulary for memory signatures (Phase 2/3 maps engine output onto these names)
CORE_SIGNALS = {
    ("machine", "cooling"): ["temp_up", "speed_down", "alarm_temp_hi", "defects_up", "note_heat"],
    ("machine", "mechanical"): ["vibration_up", "current_up", "speed_jitter", "alarm_vib_hi", "defects_up", "note_noise"],
    ("material", None): ["batch_concentration", "defects_up_all_machines", "sensors_normal", "note_lot"],
    ("method", None): ["chg_precedes_rise", "single_machine", "speed_setpoint_shift", "sensors_normal", "defects_up"],
    ("people", None): ["shift_chg_precedes_rise", "sensors_normal", "note_calibration", "defects_up"],
    ("measurement", None): ["temp_spike", "temp_flatline", "defects_baseline", "note_panel_vs_probe"],
    ("environment", None): ["multi_machine_temp_up", "defects_up_all_machines", "note_ambient"],
}
NOISE_SIGNALS = ["downtime_up", "speed_down", "defects_up", "current_up", "single_machine"]
MEMORY_PLAN = [
    ("machine", "cooling"), ("machine", "cooling"),
    ("machine", "mechanical"), ("machine", "mechanical"),
    ("material", None), ("material", None),
    ("method", None), ("method", None),
    ("people", None), ("people", None),
    ("measurement", None), ("environment", None),
]


def build_memory_seed() -> list[dict]:
    rng = np.random.default_rng(MEMORY_SEED)
    cases = []
    for i, (cat, sub) in enumerate(MEMORY_PLAN, start=1):
        core = CORE_SIGNALS[(cat, sub)]
        keep = max(3, len(core) - int(rng.integers(0, 2)))
        signals = sorted(rng.choice(core, keep, replace=False).tolist())
        if rng.random() < 0.5:
            extra = str(rng.choice(NOISE_SIGNALS))
            if extra not in signals:
                signals.append(extra)
        label = f"{cat}/{sub}" if sub else cat
        cases.append({
            "case_id": f"INC-H{i:02d}",
            "date": (pd.Timestamp(2025, 6, 1) + pd.Timedelta(days=int(rng.integers(0, 240)))).date().isoformat(),
            "line": LINES[int(rng.integers(0, 3))],
            "machine": MACHINES[int(rng.integers(0, 3))],
            "signals": signals,
            "confirmed_category": cat,
            "confirmed_subcause": sub,
            "sop": ANSWER["cooling" if sub == "cooling" else "mechanical" if sub == "mechanical" else cat][2],
            "summary": f"Engineer-validated {label} case.",
        })
    return cases


def main() -> None:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    answer_key = {}
    for n in range(1, 19):
        df, key = build_incident(n, np.random.default_rng(SEED + n))
        df.to_csv(INCIDENTS_DIR / f"incident_{n:03d}.csv", index=False)
        answer_key[f"INC-{n:03d}"] = key
    (ROOT / "data" / "answer_key.json").write_text(json.dumps(answer_key, indent=2))
    (ROOT / "data" / "memory_seed.json").write_text(json.dumps(build_memory_seed(), indent=2))
    print(f"Wrote 18 incidents to {INCIDENTS_DIR}, answer_key.json and memory_seed.json")


if __name__ == "__main__":
    main()
