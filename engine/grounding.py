"""Deterministic grounding check for generated text (LLM or template). No LLM involved.

Checks: (1) every number exists in the LLM input, (2) every step cites a retrieved SOP,
(3) no banned causal/diagnostic phrases, (4) no claimed signal change absent from the evidence.
"""

import json
import re

from backend.core.config import WARNING
from backend.models.schemas import Grounding

# Tokens whose digits are identifiers, not measurements (stripped before number extraction)
ALLOWLIST = [
    r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?",   # dates / timestamps
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b",                           # times
    r"\b[A-Za-z]{1,6}[-_][A-Za-z]?\d+[A-Za-z0-9]*\b",          # SOP-007, IMM-01, INC-H13, UPL-1a2b, LOT-0399
    r"\bM\d+\b",                                               # M1, M2
    r"(?im)^\s*\d+[.)]\s",                                     # list numbering "1. "
    r"(?i)\b(?:rank|hypothesis|hypotheses|step|steps|top|#)\s*\d\b",  # rank words
    r"(?i)\b\d(?:st|nd|rd|th)\b",
]
BANNED = re.compile(r"root cause (?:is|was)|caused by|\bconfirmed\b|diagnos|AI detected", re.IGNORECASE)
_NUM = re.compile(r"\d+(?:\.\d+)?")
SIGNAL_WORDS = {
    "temperature": r"temp(?:erature)?",
    "vibration": r"vibration",
    "motor_current": r"(?:motor )?current",
    "speed": r"speed",
}
_CHANGE = r"(?:rose|rise|rising|increas\w*|higher|elevated|fell|fall|falling|drop\w*|decreas\w*|lower|reduced)"


def _strip_ids(text: str) -> str:
    for p in ALLOWLIST:
        text = re.sub(p, " ", text)
    return text


def _numbers(text: str) -> list[str]:
    return _NUM.findall(_strip_ids(text))


def _supported(num: str, pool: list[float]) -> bool:
    k = len(num.split(".")[1]) if "." in num else 0
    x = float(num)
    return any(abs(round(v, k) - x) < 1e-9 for v in pool)


def _claims(text: str, signal: str) -> bool:
    w = SIGNAL_WORDS[signal]
    return bool(re.search(rf"\b{w}\b\W+(?:\w+\W+){{0,4}}?{_CHANGE}\b", text, re.IGNORECASE)
                or re.search(rf"\b{_CHANGE}\s+(?:\w+\s+){{0,1}}{w}\b", text, re.IGNORECASE))


def check_detailed(llm_output: dict, llm_input: dict, retrieved_sop_ids: dict[int, list[str]]):
    """Returns (Grounding, bad) where bad = {"narrative": {rank,...}, "steps": {rank,...}, "draft": bool}."""
    pool = [float(n) for n in _NUM.findall(json.dumps(llm_input, ensure_ascii=False))]
    hyp_in = {h["rank"]: h for h in llm_input.get("hypotheses", [])}
    flagged: list[str] = []
    bad = {"narrative": set(), "steps": set(), "draft": False}

    def scan(text: str, where: str) -> bool:
        ok = True
        for n in _numbers(text):
            if not _supported(n, pool):
                flagged.append(f"Unsupported number '{n}' in {where}")
                ok = False
        m = BANNED.search(text.replace(WARNING, ""))
        if m:
            flagged.append(f"Banned phrase '{m.group(0)}' in {where}")
            ok = False
        return ok

    for h in llm_output.get("hypotheses", []):
        rank = h["rank"]
        where = f"hypothesis {rank} narrative"
        ok = scan(h.get("narrative", ""), where)
        ev_text = " ".join(e["description"] for e in hyp_in.get(rank, {}).get("supporting_evidence", [])
                           + hyp_in.get(rank, {}).get("contradicting_evidence", [])).lower()
        for sig in SIGNAL_WORDS:
            if _claims(h.get("narrative", ""), sig) and not re.search(SIGNAL_WORDS[sig], ev_text):
                flagged.append(f"Unsupported signal claim '{sig.replace('_', ' ')}' in {where}")
                ok = False
        if not ok:
            bad["narrative"].add(rank)
        allowed = set(retrieved_sop_ids.get(rank, []))
        for i, s in enumerate(h.get("verification_steps", []), 1):
            if s.get("source") not in allowed:
                flagged.append(f"Step {i} of hypothesis {rank} cites {s.get('source')}, which was not retrieved")
                bad["steps"].add(rank)
            if not scan(s.get("step", ""), f"hypothesis {rank} step {i}"):
                bad["steps"].add(rank)

    if not scan(llm_output.get("rca_draft", ""), "rca_draft"):
        bad["draft"] = True
    return Grounding(passed=not flagged, flagged=flagged), bad


def check(llm_output: dict, llm_input: dict, retrieved_sop_ids_per_hypothesis: dict[int, list[str]]) -> Grounding:
    return check_detailed(llm_output, llm_input, retrieved_sop_ids_per_hypothesis)[0]
