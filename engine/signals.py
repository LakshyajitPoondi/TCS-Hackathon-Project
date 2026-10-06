"""Deterministic signal analysis: incident DataFrame -> evidence dict (plain Python types only).

One fixed method for every incident. All thresholds are the named constants below; they are
global and never tuned per incident. No answer key or generator logic is used here.
"""

import re

import numpy as np
import pandas as pd

SIGNALS = ["temperature", "speed", "vibration", "motor_current"]
SIGNAL_LABELS = {"temperature": "Temperature", "speed": "Speed", "vibration": "Vibration", "motor_current": "Motor current"}

# Event vocabulary (read from the data: normal rows use RUN, alarms start with ALM_)
NORMAL_CODES = {"RUN", ""}
ALARM_PREFIX = "ALM_"
CHANGEOVER_CODE = "CHG"
SHIFT_CHANGE_CODE = "SHIFT_CHG"

# ---- Input guard ----
MIN_TIMESTEPS = 10          # per machine; fewer -> insufficient_data

# ---- Baseline & window detection ----
BASELINE_FRACTION = 0.25    # first 25% of timesteps form the baseline
MIN_BASELINE_STEPS = 4
STD_FLOOR_REL = 0.005       # baseline std floor = 0.5% of |baseline mean| (avoids divide-by-tiny)
COUNT_STD_FLOOR = 0.5       # std floor for defect counts per step
POINT_K = 3.5               # sensor reading deviates if > 3.5 baseline stds from baseline mean
DEFECT_K = 3.0              # defects deviate if > mean + 3 std (per machine or line total)
FLAT_ROLL = 4               # rolling window (steps) for flat-line detection
FLAT_ROLL_STD_RATIO = 0.1   # flat-line if rolling std < 10% of baseline std
JUMP_STEP_FACTOR = 3.0      # temp jump if one step > 3x the largest baseline step
SUSTAIN_LOOKAHEAD = 4       # window starts where >= 3 of the next 4 steps deviate
SUSTAIN_MIN = 3
END_GAP = 3                 # window ends before 3 consecutive non-deviating steps

# ---- Per-signal flags (window vs baseline) ----
SHIFT_K = 3.0               # rose/fell: |mean shift| >= 3 baseline stds ...
SHIFT_MIN_PCT = 3.0         # ... and >= 3% of the baseline mean
FLAT_EPS_STD = 0.1          # consecutive readings "identical" if |diff| <= 0.1 baseline std
FLAT_RUN_MIN = 4            # flat: >= 4 consecutive identical steps in the window
SPIKE_K = 6.0               # spiky: an isolated reading > 6 baseline stds from the mean ...
SPIKE_SHARE = 0.5           # ... whose neighbours are within 50% of that distance (does not persist)
JITTER_RATIO = 3.0          # jittery: median |step change| > 3x the noise-expected median step (ramp/step-robust)
NOISE_MEDIAN_STEP = 0.954   # median |x[t]-x[t-1]| of Gaussian noise, in units of its std

# ---- Defects ----
DEFECT_RATE_FLOOR = 0.05    # defects/record floor for ratios
DEFECT_UP_MIN_DIFF = 0.25   # defects_up: window rate - baseline rate >= 0.25/record ...
DEFECT_UP_RATIO = 2.0       # ... and window rate >= 2x baseline rate
DEFECT_NEAR_DIFF = 0.15     # near baseline: rise < 0.15 defects/record

# ---- Batch concentration ----
BATCH_MIN_DEFECTS = 3
BATCH_SHARE_MIN = 0.5       # top batch holds >= 50% of window defects
BATCH_CONCENTRATION_MIN = 2.0  # top batch defect rate >= 2x mean of other batches

# ---- Event precedence ----
PRECEDE_LOOKBACK = 5        # steps before window start (5 x 2 min = 10 min)
PRECEDE_LOOKAHEAD = 2       # steps after start (events can land on the boundary)

# ---- Operator-note keywords (word-boundary, case-insensitive, optional plural "s") ----
NOTE_KEYWORDS = {
    "mechanical": ["grinding", "noise", "vibration", "bearing", "rattle"],
    "cooling": ["fan", "heat", "hot", "cooling", "overheat", "airflow"],
    "material": ["batch", "lot", "material", "resin", "supplier"],
    "method": ["changeover", "setup", "setpoint", "recipe"],
    "people": ["handover", "checklist", "calibration", "new shift"],
    "measurement": ["panel", "sensor", "reading", "display", "gauge"],
    "environment": ["ambient", "AC", "room", "environment", "humidity"],
}
_NOTE_RE = {
    cat: re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")s?\b", re.IGNORECASE)
    for cat, kws in NOTE_KEYWORDS.items()
}

# ---- Machine health (contextual evidence only; not RUL or failure probability) ----
HEALTH_Z0, HEALTH_Z1 = 2.0, 8.0   # penalty ramps from 0 at z=2 to its cap at z=8
HEALTH_CAPS = {"temperature": 30, "vibration": 30, "motor_current": 20, "speed": 20}
HEALTH_NORMAL_MIN = 80      # >= 80 normal
HEALTH_WATCH_MIN = 60       # 60-79 watch, < 60 degraded


def _f(x, nd=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


def _seg_stats(x: np.ndarray) -> dict:
    v = x[~np.isnan(x)]
    if len(v) == 0:
        return {"mean": None, "std": None, "min": None, "max": None, "max_step_change": None, "flat_ratio": None, "n": 0}
    d = np.abs(np.diff(v))
    return {
        "mean": float(v.mean()), "std": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
        "min": float(v.min()), "max": float(v.max()),
        "max_step_change": float(d.max()) if len(d) else 0.0,
        "flat_ratio": float((d <= 1e-9).mean()) if len(d) else 0.0, "n": int(len(v)),
    }


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


def _std_floor(stats: dict) -> float:
    return max(stats["std"] or 0.0, STD_FLOOR_REL * abs(stats["mean"] or 0.0), 1e-6)


def _insufficient(reason: str, df: pd.DataFrame, machines: list) -> dict:
    codes = df["event_code"].fillna("").astype(str).str.strip().str.upper()
    return {
        "insufficient_data": True, "reason": reason, "machines": machines, "window": None,
        "kpis": {
            "defect_rate": _f(df["defect_count"].fillna(0).sum() / max(len(df), 1)) or 0.0,
            "total_defects": int(df["defect_count"].fillna(0).sum()),
            "downtime_min": float(df["downtime_min"].fillna(0).sum()),
            "alarm_count": int(codes.str.startswith(ALARM_PREFIX).sum()),
            "event_count": int((~codes.isin(NORMAL_CODES)).sum()),
            "threshold_breaches": 0, "computed_over": "file",
        },
        "health": [],
    }


def analyze_signals(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[df["timestamp"].notna() & df["machine"].notna()]
    df["machine"] = df["machine"].astype(str).str.strip()
    df = df.sort_values(["timestamp", "machine"], kind="stable").reset_index(drop=True)
    for c in SIGNALS + ["defect_count", "downtime_min"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["code"] = df["event_code"].fillna("").astype(str).str.strip().str.upper()
    machines = sorted(df["machine"].unique().tolist())

    # ---- 0. Input guard ----
    if df.empty:
        return _insufficient("No usable rows.", df, machines)
    steps_per_machine = df.groupby("machine")["timestamp"].nunique()
    if steps_per_machine.min() < MIN_TIMESTEPS:
        return _insufficient(
            f"Only {int(steps_per_machine.min())} timestep(s) per machine; at least {MIN_TIMESTEPS} are needed for a baseline.",
            df, machines)
    empty = [s for s in SIGNALS if df[s].notna().sum() == 0]
    if empty:
        return _insufficient(f"Signal column(s) with no values: {', '.join(empty)}.", df, machines)

    ts = sorted(df["timestamp"].unique())
    T = len(ts)
    df["step"] = df["timestamp"].map({t: i for i, t in enumerate(ts)})
    step_min = float(pd.Series(ts).diff().median().total_seconds() / 60)
    nb = max(MIN_BASELINE_STEPS, int(round(T * BASELINE_FRACTION)))

    def pivot(col, agg="mean"):
        p = df.pivot_table(index="step", columns="machine", values=col, aggfunc=agg)
        return p.reindex(index=range(T), columns=machines)

    piv = {s: pivot(s) for s in SIGNALS}
    defects_m = pivot("defect_count", "sum").fillna(0)
    downtime_m = pivot("downtime_min", "sum").fillna(0)
    base = {(m, s): _seg_stats(piv[s][m].to_numpy(float)[:nb]) for m in machines for s in SIGNALS}

    # ---- 2. Incident-window detection ----
    dev = np.zeros(T, bool)
    reasons: list[list[str]] = [[] for _ in range(T)]

    def mark(mask, label):
        for t in np.where(mask)[0]:
            if t >= nb:
                dev[t] = True
                if label not in reasons[t]:
                    reasons[t].append(label)

    tot_def = defects_m.sum(axis=1).to_numpy(float)
    b_mu, b_sd = tot_def[:nb].mean(), max(tot_def[:nb].std(ddof=1), COUNT_STD_FLOOR)
    mark(tot_def > b_mu + DEFECT_K * b_sd, "defect increase")
    for m in machines:
        d = defects_m[m].to_numpy(float)
        mu, sd = d[:nb].mean(), max(d[:nb].std(ddof=1), COUNT_STD_FLOOR)
        mark(d > mu + DEFECT_K * sd, "defect increase")
    tot_dt = downtime_m.sum(axis=1).to_numpy(float)
    dt_mu, dt_sd = tot_dt[:nb].mean(), tot_dt[:nb].std(ddof=1)
    mark(tot_dt > 0 if dt_mu == 0 else tot_dt > dt_mu + DEFECT_K * max(dt_sd, COUNT_STD_FLOOR), "downtime")

    for m in machines:
        for s in SIGNALS:
            b = base[(m, s)]
            if b["n"] < 3:
                continue
            x = piv[s][m].to_numpy(float)
            sd = _std_floor(b)
            with np.errstate(invalid="ignore"):
                mark(np.abs(x - b["mean"]) > POINT_K * sd, f"{SIGNAL_LABELS[s].lower()} deviation on {m}")
            if s == "temperature":
                roll = pd.Series(x).rolling(FLAT_ROLL).std().to_numpy()
                flat = np.zeros(T, bool)
                for t in np.where(roll < FLAT_ROLL_STD_RATIO * sd)[0]:
                    flat[max(t - FLAT_ROLL + 1, 0): t + 1] = True
                mark(flat, f"temperature flat-line on {m}")
                jump = np.zeros(T, bool)
                with np.errstate(invalid="ignore"):
                    jump[1:] = np.abs(np.diff(x)) > JUMP_STEP_FACTOR * max(b["max_step_change"], sd)
                mark(jump, f"temperature jump on {m}")

    alarm_steps = df.loc[df["code"].str.startswith(ALARM_PREFIX), "step"].unique()
    alarm_mask = np.zeros(T, bool)
    alarm_mask[alarm_steps.astype(int)] = True
    mark(alarm_mask, "alarm events")

    # Find every sustained run; keep the one with the most deviating steps (earliest on ties),
    # so a short noise burst just after the baseline can't hide the real excursion.
    runs = []
    t = nb
    while t < T:
        if dev[t] and dev[t: t + SUSTAIN_LOOKAHEAD].sum() >= min(SUSTAIN_MIN, T - t):
            end, gap = t, 0
            for u in range(t + 1, T):
                if dev[u]:
                    end, gap = u, 0
                else:
                    gap += 1
                    if gap >= END_GAP:
                        break
            runs.append((int(dev[t: end + 1].sum()), -t, t, end))
            t = end + 1
        else:
            t += 1
    window = None
    ws = we = None
    if runs:
        _, _, ws, we = max(runs)
    if ws is not None and we - ws + 1 >= 2:
        counts: dict[str, int] = {}
        for t in range(ws, we + 1):
            for r in reasons[t]:
                counts[r] = counts.get(r, 0) + 1
        detected_by = sorted(counts, key=lambda r: -counts[r])[:8]
        window = {"start": pd.Timestamp(ts[ws]).isoformat(), "end": pd.Timestamp(ts[we]).isoformat(),
                  "start_step": ws, "end_step": we, "detected_by": detected_by}
    else:
        ws = we = None

    # Analysis period: the detected window, or everything after the baseline if none was found.
    ps, pe = (ws, we) if window else (nb, T - 1)

    # ---- 1. Per-machine statistics & flags ----
    machine_stats: dict = {}
    deviating_pairs = []
    for m in machines:
        machine_stats[m] = {}
        for s in SIGNALS:
            x = piv[s][m].to_numpy(float)
            b = base[(m, s)]
            w = _seg_stats(x[ps: pe + 1])
            entry = {"baseline": {k: _f(v) for k, v in b.items()}, "window": {k: _f(v) for k, v in w.items()},
                     "delta_abs": None, "delta_pct": None, "z": None,
                     "rose": False, "fell": False, "flat": False, "spiky": False, "jittery": False}
            if b["n"] >= 3 and w["n"] >= 3:
                sd = _std_floor(b)
                delta = w["mean"] - b["mean"]
                pct = delta / abs(b["mean"]) * 100 if abs(b["mean"]) > 1e-6 else None
                z = abs(delta) / sd
                shift = z >= SHIFT_K and (pct is None or abs(pct) >= SHIFT_MIN_PCT)
                seg = x[max(ps - 1, 0): min(pe + 2, T)]
                seg = seg[~np.isnan(seg)]
                d = np.diff(seg)
                # Spike = isolated excursion: one reading far from baseline whose neighbours are not.
                dist = np.abs(seg - b["mean"])
                spikes = [i for i in range(1, len(seg) - 1)
                          if dist[i] > SPIKE_K * sd and max(dist[i - 1], dist[i + 1]) <= SPIKE_SHARE * dist[i]]
                # Expected median |step| for pure noise is ~0.954 x std (more stable than a 10-point median).
                base_med_step = NOISE_MEDIAN_STEP * sd
                entry.update({
                    "delta_abs": _f(delta), "delta_pct": _f(pct, 1), "z": _f(z, 2),
                    "rose": bool(shift and delta > 0), "fell": bool(shift and delta < 0),
                    "flat": bool(_longest_run(np.abs(d) <= FLAT_EPS_STD * sd) >= FLAT_RUN_MIN),
                    "spiky": bool(spikes), "spike_count": len(spikes),
                    "jittery": bool(len(d) > 2 and float(np.median(np.abs(d))) > JITTER_RATIO * base_med_step),
                })
            flags = [k for k in ("rose", "fell", "flat", "spiky", "jittery") if entry[k]]
            if flags:
                deviating_pairs.append({"machine": m, "signal": s, "flags": flags})
            machine_stats[m][s] = entry

    # ---- Defects ----
    in_base = df["step"] < nb
    in_win = df["step"].between(ps, pe)

    def rate(mask):
        n = int(mask.sum())
        return float(df.loc[mask, "defect_count"].fillna(0).sum() / n) if n else 0.0

    def is_up(b_rate, w_rate):
        return (w_rate - b_rate >= DEFECT_UP_MIN_DIFF) and w_rate >= DEFECT_UP_RATIO * max(b_rate, DEFECT_RATE_FLOOR)

    per_machine_def = {}
    for m in machines:
        mm = df["machine"] == m
        br, wr = rate(in_base & mm), rate(in_win & mm)
        per_machine_def[m] = {"baseline_rate": _f(br), "window_rate": _f(wr), "up": bool(is_up(br, wr))}
    br, wr = rate(in_base), rate(in_win)
    defects = {
        "baseline_rate": _f(br), "window_rate": _f(wr),
        "defects_up": bool(is_up(br, wr)), "near_baseline": bool(wr - br < DEFECT_NEAR_DIFF),
        "per_machine": per_machine_def, "machines_up": [m for m in machines if per_machine_def[m]["up"]],
    }

    # ---- 3. KPIs ----
    kpi_rows = df[in_win] if window else df
    codes = kpi_rows["code"]
    kpis = {
        "defect_rate": _f(kpi_rows["defect_count"].fillna(0).sum() / max(len(kpi_rows), 1)),
        "total_defects": int(kpi_rows["defect_count"].fillna(0).sum()),
        "downtime_min": _f(kpi_rows["downtime_min"].fillna(0).sum(), 1),
        "alarm_count": int(codes.str.startswith(ALARM_PREFIX).sum()),
        "event_count": int((~codes.isin(NORMAL_CODES)).sum()),
        "threshold_breaches": len(deviating_pairs),
        "computed_over": "window" if window else "file",
    }

    win_rows = df[in_win]
    alarms: dict[str, dict[str, int]] = {}
    for (code, m), n in win_rows[win_rows["code"].str.startswith(ALARM_PREFIX)].groupby(["code", "machine"]).size().items():
        alarms.setdefault(code, {})[m] = int(n)

    # ---- 4. Batch concentration ----
    batch = {"applicable": False, "concentrated": False}
    wb = win_rows[win_rows["batch"].notna()]
    if len(wb) and wb["batch"].nunique() >= 1:
        g = wb.groupby("batch").agg(records=("defect_count", "size"), defects=("defect_count", "sum"),
                                    machines=("machine", "nunique"))
        g["rate"] = g["defects"] / g["records"]
        g = g.sort_values(["defects", "rate"], ascending=False)
        top = g.index[0]
        total = float(g["defects"].sum())
        others = g.drop(top)
        others_rate = float(others["rate"].mean()) if len(others) else None
        top_rate = float(g.loc[top, "rate"])
        conc = (top_rate / others_rate) if others_rate else None
        share = float(g.loc[top, "defects"]) / total if total else 0.0
        batch = {
            "applicable": True, "top_batch": str(top), "top_batch_defects": int(g.loc[top, "defects"]),
            "top_batch_rate": _f(top_rate), "other_batches_mean_rate": _f(others_rate),
            "concentration": _f(conc, 2), "top_batch_share": _f(share, 2),
            "top_batch_machines": int(g.loc[top, "machines"]),
            "top_batch_machine_list": sorted(wb.loc[wb["batch"] == top, "machine"].unique().tolist()),
            "batch_count": int(len(g)),
            "concentrated": bool(g.loc[top, "defects"] >= BATCH_MIN_DEFECTS and share >= BATCH_SHARE_MIN
                                 and (conc is None or conc >= BATCH_CONCENTRATION_MIN)),
        }

    # ---- 5. Co-movement ----
    per_signal = {}
    for s in SIGNALS:
        up = [m for m in machines if machine_stats[m][s]["rose"]]
        down = [m for m in machines if machine_stats[m][s]["fell"]]
        per_signal[s] = {"machines": up + down, "up": up, "down": down,
                         "same_direction": bool(len(up + down) >= 2 and (not up or not down))}
    dev_machines = sorted({p["machine"] for p in deviating_pairs})
    co_movement = {
        "applicable": len(machines) >= 2, "machine_count": len(machines),
        "machines_deviating_count": len(dev_machines), "machines_deviating": dev_machines,
        "per_signal": per_signal,
        "temp_rise_multi_machine": len(per_signal["temperature"]["up"]) >= 2,
    }

    # ---- 6. Event precedence ----
    def precedence(code):
        found = {"before_incident": False, "machine": None, "timestamp": None, "anywhere_in_file": bool((df["code"] == code).any())}
        if window:
            rows = df[(df["code"] == code) & df["step"].between(ws - PRECEDE_LOOKBACK, ws + PRECEDE_LOOKAHEAD)]
            if len(rows):
                found.update({"before_incident": True, "machine": sorted(rows["machine"].unique().tolist()),
                              "timestamp": rows["timestamp"].iloc[0].isoformat(), "steps_before_start": int(ws - rows["step"].iloc[0])})
        return found

    chg, shift = precedence(CHANGEOVER_CODE), precedence(SHIFT_CHANGE_CODE)
    events = {"changeover_before_incident": chg["before_incident"], "changeover": chg,
              "shift_change_before_incident": shift["before_incident"], "shift_change": shift}

    # ---- 7. Operator-note keywords ----
    note_rows = df[df["operator_note"].notna() & df["step"].between(ps - PRECEDE_LOOKBACK, pe)]
    notes = {}
    for cat, rx in _NOTE_RE.items():
        kws, ms, texts = set(), set(), []
        for _, r in note_rows.iterrows():
            hits = [h.lower() for h in rx.findall(str(r["operator_note"]))]
            if hits:
                kws.update(hits)
                ms.add(r["machine"])
                texts.append(str(r["operator_note"]))
        notes[cat] = {"keywords": sorted(kws), "machines": sorted(ms), "notes": sorted(set(texts))[:3]}

    # ---- 8. Machine health (0-100, contextual only) ----
    health = []
    for m in machines:
        score = 100.0
        for s, cap in HEALTH_CAPS.items():
            e = machine_stats[m][s]
            z = e["z"] or 0.0
            if e["jittery"]:
                z = max(z, HEALTH_Z1)
            score -= cap * min(max((z - HEALTH_Z0) / (HEALTH_Z1 - HEALTH_Z0), 0.0), 1.0)
        score = round(min(max(score, 0.0), 100.0), 1)
        status = "normal" if score >= HEALTH_NORMAL_MIN else "watch" if score >= HEALTH_WATCH_MIN else "degraded"
        health.append({"machine": m, "score": score, "status": status})

    return {
        "insufficient_data": False, "reason": None,
        "machines": machines, "timesteps": T, "step_minutes": step_min,
        "baseline": {"start": pd.Timestamp(ts[0]).isoformat(), "end": pd.Timestamp(ts[nb - 1]).isoformat(), "steps": nb},
        "window": window,
        "kpis": kpis,
        "machine_stats": machine_stats,
        "deviating_pairs": deviating_pairs,
        "sensors_broadly_normal": len(deviating_pairs) == 0,
        "defects": defects,
        "alarms": alarms,
        "window_downtime_min": _f(win_rows["downtime_min"].fillna(0).sum(), 1),
        "batch": batch,
        "co_movement": co_movement,
        "events": events,
        "notes": notes,
        "health": health,
    }
