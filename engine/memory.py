"""Approved SQLite experience memory, used only as explanatory context."""


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


SEMANTIC_WEIGHT = 3.0      # score += 3 * cosine(summary embeddings) when cosine >= SEMANTIC_MIN
SEMANTIC_MIN = 0.5
TOP_HYPOTHESIS_WEIGHT = 1  # B15: small, separately shown; memory must not simply echo the engine's guess
CONTEXT_WEIGHTS = [('machine_uid', 5), ('line', 2), ('model', 1), ('confirmed_category', 4), ('confirmed_subcause', 2)]


def case_text(data: dict) -> str:
    """Text embedded for a case: engineer-confirmed summary, symptoms, fix and lessons."""
    parts = [data.get('summary', ''), data.get('evidence_summary', ''), ' '.join(data.get('symptoms', []) or []),
             data.get('fix_applied', ''), data.get('lessons', '')]
    return ' '.join(p for p in parts if p).strip()


def embed_case(case) -> bool:
    """Embed one Case row in place (caller commits). Returns False when embeddings are off or fail."""
    from engine import retrieval
    from backend.core import config
    if config.EMBEDDINGS_PROVIDER == 'none':
        return False
    try:
        vector = retrieval.embed([case_text(case.data) or case.case_id])[0]
        retrieval._check_vector(vector)
        case.embedding, case.embedding_model = list(map(float, vector)), retrieval.embedding_key()
        return True
    except Exception:
        return False


def all_cases() -> list[dict]:
    """Approved cases only: proposed, rejected and retired cases are never recalled."""
    from backend.db import Session, Case
    from sqlalchemy import select
    with Session() as session:
        return [{**c.data, "case_id": c.case_id, "source_incident_id": c.source_incident_id,
                 "_embedding": c.embedding, "_embedding_model": c.embedding_model}
                for c in session.scalars(select(Case).where(Case.status == "approved"))]


def _query_vector(text):
    from engine import retrieval
    from backend.core import config
    if not text or config.EMBEDDINGS_PROVIDER == 'none':
        return None, None
    try:
        return retrieval.embed_query(text), retrieval.embedding_key()
    except Exception:
        return None, None


def recall(signature: list[str], exclude_incident_id: str | None = None, top_k: int = TOP_K, context: dict | None = None) -> list[SimilarCase]:
    """Weighted recall over approved cases. Factors: shared signal tags (required), physical machine, line, model,
    confirmed category/subcause of the reference (when given), shared events, summary-embedding similarity,
    and a small separately-labelled bonus when a case agrees with the current top hypothesis (B15)."""
    import numpy as np
    sig = set(signature)
    scored = []
    context = context or {}
    qvec, qkey = _query_vector(context.get('query_text'))
    for case in all_cases():
        if exclude_incident_id and case.get("source_incident_id") == exclude_incident_id:
            continue
        tags = set(case.get("signals", []))
        shared = sig & tags
        if len(shared) < MIN_SHARED:
            continue
        score = 3*len(shared)/max(1, len(sig | tags)); reasons = [f'{len(shared)} shared signal tags']
        for field, weight in CONTEXT_WEIGHTS:
            if context.get(field) and context[field] == case.get(field): score += weight; reasons.append(field+' agrees')
        top = context.get('top_hypothesis')
        if top and top.get('category') == case.get('confirmed_category') and top.get('subcause') == case.get('confirmed_subcause'):
            score += TOP_HYPOTHESIS_WEIGHT; reasons.append(f'matches current top hypothesis (+{TOP_HYPOTHESIS_WEIGHT}, context only)')
        event_shared = set(context.get('events', [])) & set(case.get('events', []))
        if event_shared: score += len(event_shared); reasons.append('shared events: '+', '.join(sorted(event_shared)))
        if qvec is not None and case.get('_embedding') is not None and case.get('_embedding_model') == qkey:
            a, b = np.asarray(qvec, dtype=float), np.asarray(case['_embedding'], dtype=float)
            sim = float(a @ b / max(np.linalg.norm(a)*np.linalg.norm(b), 1e-12))
            if sim >= SEMANTIC_MIN:
                score += SEMANTIC_WEIGHT*sim; reasons.append(f'summary similarity {sim:.2f}')
        scored.append((score, len(shared), case, sorted(shared), reasons))
    scored.sort(key=lambda r: (-r[0], -r[1], r[2]["case_id"]))
    return [
        SimilarCase(case_id=c["case_id"], confirmed_category=c["confirmed_category"],
                    label=c.get('label', 'synthetic seed'), fix_applied=c.get('fix_applied', ''), match_reasons=reasons,
                    confirmed_subcause=c.get("confirmed_subcause"), shared_signals=shared,
                    similarity_description=f"Shares {len(shared)} of {len(c.get('signals', []))} key signals with {c['case_id']}.")
        for _, _, c, shared, reasons in scored[:top_k]
    ]
