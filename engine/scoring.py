"""Deterministic RCA scoring: evidence dict -> scored candidates, category evidence, top hypotheses.

Each candidate has a rule table of (weight, condition, evidence, narrative phrase) in code; the weight bands,
thresholds, categories, display names and texts come from config/cause_categories.yaml.
A rule adds its weight when its condition holds. Output is hypotheses, never diagnoses.
"""

from engine.cause_config import CONFIG

# ---- Weight bands and thresholds: config/cause_categories.yaml (validated at start-up) ----
W_STRONG = CONFIG.weights.strong            # strong signal evidence
W_MODERATE = CONFIG.weights.moderate        # moderate signal evidence
W_WEAK = CONFIG.weights.weak                # weak / non-specific signal (e.g. defects up for machine subcauses)
W_NOTE = CONFIG.weights.note                # operator-note keyword: one rule per category
W_HEALTH = CONFIG.weights.health            # health watch/degraded on target machine: machine subcauses only
W_CONTRA_STRONG = CONFIG.weights.contra_strong
W_CONTRA = CONFIG.weights.contra

MIN_SCORE = CONFIG.thresholds.min_score     # strong signal + at least moderate corroboration; note+health alone never reach it
MEDIUM_SCORE = CONFIG.thresholds.medium_score
HIGH_SCORE = CONFIG.thresholds.high_score
MAX_HYPOTHESES = CONFIG.thresholds.max_hypotheses

CATEGORIES = [c.key for c in CONFIG.categories]
CANDIDATES = [(c.key, c.category, c.subcause, c.label) for c in CONFIG.candidates]  # (key, category, subcause, narrative label)
DISPLAY_NAMES = {c.key: c.display_name for c in CONFIG.candidates}
LABEL = {"temperature": "Temperature", "speed": "Speed", "vibration": "Vibration", "motor_current": "Motor current"}

# ---- Templated text (config); LLM wording may replace it, these stay as the fallback ----
VERIFY_SENTENCE = {c.key: c.verify_sentence for c in CONFIG.candidates}
MISSING_CHECKS = {c.key: list(c.missing_checks) for c in CONFIG.candidates}
SOP_TITLES = {
    "SOP-002": "Downtime and Alarm Triage",
    "SOP-004": "Abnormal Vibration Investigation",
    "SOP-007": "Cooling System Troubleshooting",
    "SOP-012": "Defect Analysis and Batch Check",
    "SOP-015": "Sensor Verification",
    "SOP-018": "Changeover Verification",
    "SOP-021": "Shift Handover and Calibration Check",
    "SOP-024": "Ambient Condition Check",
}
SOP_STEPS = {  # temporary fixed mapping until Phase 3 BM25 retrieval
    "mechanical": ("SOP-004", ["Take a manual vibration reading at the drive end and compare with baseline.",
                               "Inspect bearings and gearbox for noise, play or overheating."]),
    "cooling": ("SOP-007", ["Check coolant level and chiller flow on the affected machine.",
                            "Inspect the cooling fan and heat-exchanger fins for blockage."]),
    "material": ("SOP-012", ["Quarantine the suspect lot and pull retained samples for inspection.",
                             "Compare defect counts by lot across machines for the incident period."]),
    "measurement": ("SOP-015", ["Compare the panel reading with a calibrated handheld instrument.",
                                "Inspect the sensor connector and check its calibration record."]),
    "method": ("SOP-018", ["Compare current setpoints against the approved setup sheet.",
                           "Confirm first-off part inspection was completed after the changeover."]),
    "people": ("SOP-021", ["Review the shift handover checklist for incomplete items.",
                           "Verify that required calibration checks were completed at shift start."]),
    "environment": ("SOP-024", ["Record ambient temperature and humidity near the affected machines.",
                                "Check HVAC / AC unit status and bay door positions."]),
}
TRIAGE_STEPS = ("SOP-002", ["Review the alarm and downtime log for the incident window.",
                            "Confirm each alarm was acknowledged and its trigger condition recorded."])


def _num(x) -> str:
    return "unavailable" if x is None else (f"{x:.1f}" if abs(x) >= 10 else f"{x:.2f}")


def _ev(signal, description, value=None, machine=None) -> dict:
    return {"signal": signal, "description": description, "value": value, "machine": machine}


def _a(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _shift_ev(E, m, s):
    e = E["machine_stats"][m][s]
    b, w = e["baseline"]["mean"], e["window"]["mean"]
    if not (e.get("rose") or e.get("fell")) or any(v is None for v in (b, w, e.get("delta_abs"))):
        return None
    word = "rose" if e["delta_abs"] > 0 else "fell"
    pct = f" {abs(e['delta_pct']):.0f}%" if e["delta_pct"] is not None else ""
    return _ev(f"{s}_delta", f"{LABEL[s]} on {m} {word}{pct} vs baseline ({_num(b)} → {_num(w)}).", e["delta_abs"], m)


def _pick(E, signal, prefer):
    """Target machine: largest z-score on `signal` among machines with flag `prefer`, else overall."""
    ms = E["machine_stats"]
    pool = [m for m in E["machines"] if ms[m][signal][prefer]] or E["machines"]
    return max(pool, key=lambda m: ms[m][signal]["z"] or 0.0)


def _alarm_count(E, m, word):
    return sum(n.get(m, 0) for code, n in E["alarms"].items() if word in code)


def _note_rule(E, cat, notes_key=None):
    n = E["notes"][notes_key or cat]
    if not n["keywords"]:
        return (W_NOTE, False, None, None)
    quote = "; ".join(f"“{t}”" for t in n["notes"])
    return (W_NOTE, True, _ev("operator_note", f"Operator note on {', '.join(n['machines'])}: {quote} "
                                               f"(keywords: {', '.join(n['keywords'])}).", ", ".join(n["keywords"]),
                              n["machines"][0] if len(n["machines"]) == 1 else None),
            f"an operator note mentioning {', '.join(n['keywords'])}")


def _health_rule(E, t):
    h = next((h for h in E["health"] if h["machine"] == t), None)
    ok = h is not None and h["status"] in ("watch", "degraded")
    return (W_HEALTH, ok, ok and _ev("machine_health", f"Machine-health score for {t} is {h['score']:.0f} ({h['status']}); "
                                                       "contextual evidence only.", h["score"], t), None)


def _defects_rule(E, t):
    d = E["defects"]
    pm = d["per_machine"].get(t) if t else None
    if pm and pm["up"]:
        return (W_WEAK, True, _ev("defect_rate", f"Defect rate on {t} rose from {pm['baseline_rate']:.2f} to "
                                                 f"{pm['window_rate']:.2f} per record.", pm["window_rate"], t),
                f"increased defects on {t}")
    return (W_WEAK, d["defects_up"], _ev("defect_rate", f"Line defect rate rose from {d['baseline_rate']:.2f} to "
                                                        f"{d['window_rate']:.2f} per record.", d["window_rate"]),
            "increased defects")


def _rules(key, E):
    """Return (target_machine, rule table). Each rule: (weight, condition, evidence, phrase)."""
    ms, co, ev, d, b = E["machine_stats"], E["co_movement"], E["events"], E["defects"], E["batch"]
    temp_up = co["per_signal"]["temperature"]["up"]
    window_min = (E.get("step_minutes") or 2) * 5

    if key == "cooling":
        t = _pick(E, "temperature", "rose")
        tm = ms[t]["temperature"]
        n_alarm = _alarm_count(E, t, "TEMP")
        return t, [
            (W_STRONG, tm["rose"], tm["rose"] and _shift_ev(E, t, "temperature"), f"elevated temperature on {t} ({(tm['delta_abs'] or 0):+.1f})"),
            (W_MODERATE, ms[t]["speed"]["fell"], ms[t]["speed"]["fell"] and _shift_ev(E, t, "speed"), f"reduced speed on {t}"),
            (W_MODERATE, n_alarm > 0, _ev("alarm_temp_hi", f"{n_alarm} high-temperature alarm(s) on {t} during the window.", n_alarm, t),
             "high-temperature alarms"),
            _defects_rule(E, t),
            _note_rule(E, "cooling"),
            _health_rule(E, t),
            (W_CONTRA_STRONG, co["temp_rise_multi_machine"],
             _ev("co_movement", f"Temperature rose on {len(temp_up)} machines together ({', '.join(temp_up)}), "
                                "which suggests a shared cause rather than one machine's cooling.", len(temp_up)),
             "temperature rising on several machines together"),
            (W_CONTRA_STRONG, tm["flat"] or tm["spiky"],
             _ev("temperature_pattern", f"Temperature on {t} {'flat-lined' if tm['flat'] else 'shows isolated spikes'}, "
                                        "a pattern that suggests a measurement issue.", None, t),
             "a non-physical temperature pattern"),
        ]

    if key == "mechanical":
        t = _pick(E, "vibration", "rose")
        vm = ms[t]["vibration"]
        n_alarm = _alarm_count(E, t, "VIB")
        any_vib = any(ms[m]["vibration"]["rose"] for m in E["machines"])
        shared = [s for s, v in co["per_signal"].items() if v["same_direction"]]
        return t, [
            (W_STRONG, vm["rose"], vm["rose"] and _shift_ev(E, t, "vibration"), f"higher vibration on {t} ({(vm['delta_abs'] or 0):+.2f})"),
            (W_MODERATE, ms[t]["motor_current"]["rose"], ms[t]["motor_current"]["rose"] and _shift_ev(E, t, "motor_current"),
             f"higher motor current on {t}"),
            (W_MODERATE, ms[t]["speed"]["jittery"],
             _ev("speed_jitter", f"Speed on {t} became unstable (step changes well above baseline noise).", None, t),
             f"unstable speed on {t}"),
            (W_MODERATE, n_alarm > 0, _ev("alarm_vib_hi", f"{n_alarm} high-vibration alarm(s) on {t} during the window.", n_alarm, t),
             "high-vibration alarms"),
            _defects_rule(E, t),
            _note_rule(E, "mechanical"),
            _health_rule(E, t),
            (W_CONTRA, not any_vib, _ev("vibration_delta", "Vibration stayed within its baseline range on all machines.", 0.0),
             "flat vibration on all machines"),
            (W_CONTRA, bool(shared), bool(shared) and _ev(
                "co_movement", f"{_join([LABEL[s] for s in shared])} moved in the same direction on several machines, "
                               "which suggests a shared cause.", len(shared)),
             "same-direction movement on several machines"),
        ]

    if key == "material":
        total = d["window_rate"]
        conc = b.get("concentrated", False)
        ratio = f"; its defect rate is {b['concentration']:.1f}x the other batches' mean" if b.get("concentration") else ""
        return None, [
            (W_STRONG, conc, conc and _ev("batch_concentration", f"Batch {b['top_batch']} holds {b['top_batch_defects']} of the "
                                                                 f"{E['kpis']['total_defects']} window defects{ratio}.", b["concentration"]),
             f"defects concentrated in batch {b.get('top_batch')}"),
            (W_MODERATE, conc and b["top_batch_machines"] >= 2,
             conc and _ev("batch_machines", f"Batch {b['top_batch']} ran on {b['top_batch_machines']} machines "
                                            f"({', '.join(b['top_batch_machine_list'])}).", b["top_batch_machines"]),
             f"that batch running on {b.get('top_batch_machines')} machines"),
            (W_MODERATE, E["sensors_broadly_normal"],
             _ev("sensors_normal", "No sensor on any machine deviated from its baseline in the window."), "normal sensor readings"),
            _note_rule(E, "material"),
            (W_CONTRA, b.get("applicable", False) and not conc and total > 0,
             b.get("applicable") and _ev("batch_concentration", f"Window defects are spread across {b['batch_count']} batches "
                                                                f"(top batch {b['top_batch']} holds {b['top_batch_defects']}).",
                                         b.get("concentration")),
             "defects spread across batches"),
        ]

    if key == "method":
        chg = ev["changeover"]
        t = (chg["machine"] or [None])[0] or (d["machines_up"][0] if len(d["machines_up"]) == 1 else None) \
            or max(E["machines"], key=lambda m: d["per_machine"][m]["window_rate"] or 0)
        sp = ms[t]["speed"]
        others = [p for p in E["deviating_pairs"] if not (p["machine"] == t and p["signal"] == "speed")]
        return t, [
            (W_STRONG, chg["before_incident"],
             chg["before_incident"] and _ev("chg_event", f"Changeover (CHG) on {', '.join(chg['machine'])} at {chg['timestamp'][11:16]}, "
                                                         f"{chg['steps_before_start']} step(s) before the window start.",
                                            chg["timestamp"], t),
             f"a changeover on {t} shortly before the rise"),
            (W_MODERATE, d["machines_up"] == [t],
             _ev("defect_rate", f"The defect rise is confined to {t} ({d['per_machine'][t]['baseline_rate']:.2f} → "
                                f"{d['per_machine'][t]['window_rate']:.2f} per record).", d["per_machine"][t]["window_rate"], t),
             f"a defect rise confined to {t}"),
            (W_MODERATE, sp["rose"] or sp["fell"], (sp["rose"] or sp["fell"]) and _shift_ev(E, t, "speed"),
             f"a speed shift on {t}"),
            (W_MODERATE, not others, _ev("sensors_normal", f"Apart from speed on {t}, no sensor deviated from baseline."),
             "otherwise normal sensors"),
            _note_rule(E, "method"),
            (W_CONTRA_STRONG, not chg["before_incident"],
             _ev("chg_event", f"No changeover (CHG) event within {window_min:.0f} min before the window start."),
             "no changeover near the window"),
        ]

    if key == "people":
        sh = ev["shift_change"]
        return None, [
            (W_STRONG, sh["before_incident"],
             sh["before_incident"] and _ev("shift_chg_event", f"Shift change (SHIFT_CHG) at {sh['timestamp'][11:16]}, "
                                                              f"{sh['steps_before_start']} step(s) before the window start.",
                                           sh["timestamp"]),
             "a shift change shortly before the rise"),
            (W_MODERATE, E["sensors_broadly_normal"],
             _ev("sensors_normal", "No sensor on any machine deviated from its baseline in the window."), "normal sensor readings"),
            _note_rule(E, "people"),
            (W_CONTRA_STRONG, not sh["before_incident"],
             _ev("shift_chg_event", f"No shift change (SHIFT_CHG) event within {window_min:.0f} min before the window start."),
             "no shift change near the window"),
        ]

    if key == "measurement":
        pool = [m for m in E["machines"] if ms[m]["temperature"]["flat"] or ms[m]["temperature"]["spiky"]]
        t = max(pool, key=lambda m: ms[m]["temperature"]["z"] or 0) if pool else _pick(E, "temperature", "rose")
        tm = ms[t]["temperature"]
        odd = tm["flat"] or tm["spiky"]
        if tm["flat"]:
            desc = f"Temperature on {t} flat-lined (identical readings for several steps) while baseline varied by ±{_num(tm['baseline']['std'])}."
        else:
            desc = (f"Temperature on {t} shows {tm.get('spike_count', 0)} isolated spike(s) up to {_num(tm['window']['max'])} "
                    f"(baseline {_num(tm['baseline']['mean'])}) that do not persist.")
        corrob = [s for s in ("vibration", "motor_current", "speed")
                  if any(ms[t][s][k] for k in ("rose", "fell", "jittery", "spiky"))]
        return t, [
            (W_STRONG, odd, odd and _ev("temperature_pattern", desc, tm["window"]["max"] if tm["spiky"] else tm["window"]["std"], t),
             f"a {'flat-lined' if tm['flat'] else 'spiking'} temperature reading on {t}"),
            (W_MODERATE, odd and not corrob, _ev("other_sensors", f"Vibration, motor current and speed on {t} stayed within baseline.",
                                                 None, t), "normal vibration, current and speed"),
            (W_MODERATE, d["near_baseline"], _ev("defect_rate", f"Line defect rate stayed near baseline ({d['baseline_rate']:.2f} → "
                                                                f"{d['window_rate']:.2f} per record).", d["window_rate"]),
             "defects at baseline"),
            _note_rule(E, "measurement"),
            (W_CONTRA_STRONG, bool(corrob) or d["defects_up"],
             _ev("corroboration", f"Independent signals corroborate a real change on {t}: "
                                  f"{_join([LABEL[s].lower() for s in corrob] + (['defects'] if d['defects_up'] else []))} "
                                  "also deviated.", None, t) if (corrob or d["defects_up"]) else None,
             "corroborating signals"),
        ]

    if key == "environment":
        n_m = co["machine_count"]
        ups = ", ".join(f"{m} {ms[m]['temperature']['delta_abs']:+.1f}" for m in temp_up)
        return None, [
            (W_STRONG, co["temp_rise_multi_machine"],
             _ev("co_movement", f"Temperature rose on {len(temp_up)} machines together ({ups}).", len(temp_up)),
             f"temperature rising on {len(temp_up)} machines together"),
            (W_MODERATE, n_m >= 2 and len(temp_up) == n_m,
             _ev("same_direction", f"Temperature moved in the same direction (up) on all {n_m} machines.", n_m),
             "the same direction on every machine"),
            (W_WEAK, len(d["machines_up"]) >= 2,
             _ev("defect_rate", f"Defects rose mildly on {len(d['machines_up'])} machines ({', '.join(d['machines_up'])}).",
                 len(d["machines_up"])), "a defect rise across machines"),
            _note_rule(E, "environment"),
            (W_CONTRA, co["machines_deviating_count"] == 1,
             _ev("co_movement", f"Only one machine ({', '.join(co['machines_deviating'])}) deviates from baseline.", 1),
             "only one machine deviating"),
        ]
    raise ValueError(key)


def _narrative(key, label, sup_phrases, con_phrases) -> str:
    lead, rest = sup_phrases[0], sup_phrases[1:3]
    text = (f"{lead[0].upper() + lead[1:]} co-occurs with {_join(rest)}, which supports {_a(label)} {label} hypothesis."
            if rest else f"{lead[0].upper() + lead[1:]} suggests {_a(label)} {label} hypothesis, though supporting evidence is limited.")
    if con_phrases:
        text += f" Contradicting evidence ({_join(con_phrases[:2])}) warrants verification."
    return f"{text} {VERIFY_SENTENCE[key]}"


def _confidence(score) -> str:
    return "high" if score >= HIGH_SCORE else "medium" if score >= MEDIUM_SCORE else "low"


def score_hypotheses(evidence: dict) -> dict:
    E = evidence
    empty_cats = {c: {"supporting": [], "contradicting": []} for c in CATEGORIES}
    if E.get("insufficient_data"):
        return {"status": "insufficient_evidence", "abstain_reason": E.get("reason"),
                "candidates": [], "category_evidence": empty_cats, "hypotheses": []}

    candidates = []
    for key, cat, sub, label in CANDIDATES:
        target, rules = _rules(key, E)
        sup = [(w, ev, ph) for w, cond, ev, ph in rules if cond and w > 0]
        con = [(w, ev, ph) for w, cond, ev, ph in rules if cond and w < 0]
        score = sum(w for w, _, _ in sup) + sum(w for w, _, _ in con)
        candidates.append({
            "key": key, "category": cat, "subcause": sub, "label": label, "target": target,
            "score": score, "n_support": len(sup), "eligible": score >= MIN_SCORE,
            "supporting": [ev for _, ev, _ in sorted(sup, key=lambda r: -r[0])],
            "contradicting": [ev for _, ev, _ in con],
            "_sup_phrases": [ph for _, _, ph in sorted(sup, key=lambda r: -r[0]) if ph],
            "_con_phrases": [ph for _, _, ph in con if ph],
            "_sup_weights": [w for w, _, _ in sorted(sup, key=lambda r: -r[0])],
            "_con_weights": [w for w, _, _ in con],
        })

    # Category evidence: all six; machine merges cooling + mechanical (deduplicated).
    cat_ev = {c: {"supporting": [], "contradicting": []} for c in CATEGORIES}
    for c in candidates:
        for side in ("supporting", "contradicting"):
            for ev in c[side]:
                if ev not in cat_ev[c["category"]][side]:
                    cat_ev[c["category"]][side].append(ev)

    ranked = sorted((c for c in candidates if c["eligible"]), key=lambda c: (-c["score"], -c["n_support"]))[:MAX_HYPOTHESES]
    k = E["kpis"]
    triage = (k["alarm_count"] > 0 or k["downtime_min"] > 0) and bool(E.get("window"))
    hypotheses = []
    for rank, c in enumerate(ranked, 1):
        sop, steps = SOP_STEPS[c["key"]]
        vsteps = [{"step": s, "source": sop, "source_title": SOP_TITLES[sop]} for s in steps]
        if triage:
            vsteps += [{"step": s, "source": TRIAGE_STEPS[0], "source_title": SOP_TITLES[TRIAGE_STEPS[0]]} for s in TRIAGE_STEPS[1]]
        hypotheses.append({
            "rank": rank, "key": c["key"], "category": c["category"], "subcause": c["subcause"], "target": c["target"],
            "confidence": _confidence(c["score"]), "score": float(c["score"]),
            "supporting_evidence": [{**ev, "weight": w} for ev, w in zip(c["supporting"], c["_sup_weights"])],
            "contradicting_evidence": [{**ev, "weight": w} for ev, w in zip(c["contradicting"], c["_con_weights"])],
            "missing_checks": MISSING_CHECKS[c["key"]], "verification_steps": vsteps,
            "narrative": _narrative(c["key"], c["label"], c["_sup_phrases"], c["_con_phrases"]),
        })

    for c in candidates:
        for key in ("_sup_phrases", "_con_phrases", "_sup_weights", "_con_weights"):
            c.pop(key)
    status = "complete" if hypotheses else "insufficient_evidence"
    return {
        "status": status,
        "abstain_reason": None if hypotheses else f"No hypothesis reached the minimum evidence score ({MIN_SCORE}).",
        "candidates": candidates, "category_evidence": cat_ev, "hypotheses": hypotheses,
    }
