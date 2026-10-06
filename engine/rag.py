"""BM25 retrieval over the SOP knowledge base (data/sops/*.md). No hardcoded hypothesis -> SOP mapping.

The query is built from deterministic engine output only (category, subcause, evidence, missing checks);
the LLM never chooses the SOP.
"""

import re

from rank_bm25 import BM25Okapi

from backend.core.config import SOPS_DIR

TRIAGE_SOP = "SOP-002"  # appended when the window contains alarms or downtime (Phase-2 rule)
STOPWORDS = set("""a an and are as at be before by for from in into is it its of on or that the this to was were
with while within than then there their them over per same""".split())

_TITLE_RE = re.compile(r"^#\s*(SOP-\d+):\s*(.+)$", re.MULTILINE)
_STEP_RE = re.compile(r"^\s*\d+\.\s+(.+)$", re.MULTILINE)


def _tokens(text: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z]+", text.lower()):
        if t in STOPWORDS or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]  # crude plural folding: alarms -> alarm, spikes -> spike
        out.append(t)
    return out


def _load() -> list[dict]:
    sops = []
    for path in sorted(SOPS_DIR.glob("SOP-*.md")):
        text = path.read_text(encoding="utf-8")
        m = _TITLE_RE.search(text)
        steps_block = text.split("## Verification steps", 1)[-1].split("##", 1)[0]
        sops.append({"id": m.group(1), "title": m.group(2).strip(), "steps": _STEP_RE.findall(steps_block), "text": text})
    return sops


SOPS: list[dict] = _load()
SOP_INDEX: dict[str, dict] = {s["id"]: s for s in SOPS}
_BM25 = BM25Okapi([_tokens(s["text"]) for s in SOPS]) if SOPS else None


def get_sop(sop_id: str) -> dict | None:
    s = SOP_INDEX.get(sop_id)
    return {"id": s["id"], "title": s["title"], "steps": list(s["steps"]), "score": None} if s else None


def build_query(hypothesis: dict) -> str:
    parts = [hypothesis.get("category") or "", hypothesis.get("subcause") or ""]
    for e in hypothesis.get("supporting_evidence", []):
        parts += [e.get("signal", "").replace("_", " "), e.get("description", "")]
    parts += hypothesis.get("missing_checks", [])
    return " ".join(parts)


def retrieve_for_hypothesis(hypothesis: dict, top_k: int = 2) -> list[dict]:
    """Top-k SOPs by BM25 score: [{id, title, steps, score}]."""
    if not _BM25:
        return []
    scores = _BM25.get_scores(_tokens(build_query(hypothesis)))
    order = sorted(range(len(SOPS)), key=lambda i: -scores[i])[:top_k]
    return [{"id": SOPS[i]["id"], "title": SOPS[i]["title"], "steps": list(SOPS[i]["steps"]), "score": round(float(scores[i]), 3)}
            for i in order]
