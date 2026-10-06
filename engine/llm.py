"""Groq wording layer: one JSON-mode call per analysis. It rewords supplied evidence; it never computes,
reranks or chooses SOPs. Order: cache -> Groq -> None (caller falls back to deterministic templates).
"""

import hashlib
import json
import logging

import httpx
from pydantic import BaseModel, ValidationError

from backend.core import config

log = logging.getLogger("rca.llm")

SYSTEM_PROMPT = """You write wording for a manufacturing Root Cause Analysis tool. Rules:
1. Use only the supplied evidence.
2. Never invent or compute numbers; only repeat numbers exactly as they appear in the input.
3. Never state a confirmed root cause. Use "co-occurs with", "supports", "suggests", "requires verification".
   Never write "caused by", "root cause is", "confirmed", "diagnosis" or "AI detected".
4. Do not change any hypothesis rank, category or confidence.
5. Introduce no new causes or signals.
6. Each verification step must paraphrase one of the SOP steps supplied for that hypothesis and cite that SOP id as "source".
7. Give no repair or replacement actions beyond what the SOP says.
8. Return JSON only, in exactly this shape:
{"hypotheses":[{"rank":1,"narrative":"1-2 sentences","verification_steps":[{"step":"...","source":"SOP-xxx"}]}],
 "rca_draft":"plain text, 150-250 words, short headed sections: Incident summary; Leading hypothesis; Supporting evidence;
 Alternatives; Missing verification; Verification actions; then end with the exact validation warning line supplied."}
Give 2-3 verification steps per hypothesis."""


class LLMStep(BaseModel):
    step: str
    source: str


class LLMHypothesis(BaseModel):
    rank: int
    narrative: str
    verification_steps: list[LLMStep]


class LLMOutput(BaseModel):
    hypotheses: list[LLMHypothesis]
    rca_draft: str


def input_hash(llm_input: dict) -> str:
    return hashlib.sha256(json.dumps(llm_input, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def _cache_path(incident_id: str, llm_input: dict):
    return config.LLM_CACHE_DIR / f"{incident_id}_{input_hash(llm_input)}.json"


def load_cache(incident_id: str, llm_input: dict) -> dict | None:
    p = _cache_path(incident_id, llm_input)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(incident_id: str, llm_input: dict, output: dict) -> None:
    try:
        config.LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(incident_id, llm_input).write_text(json.dumps(output, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("LLM cache write failed: %s", exc)


def _parse(content: str, ranks: set[int]) -> dict:
    out = LLMOutput.model_validate_json(content)
    if {h.rank for h in out.hypotheses} != ranks:
        raise ValueError("ranks in LLM output do not match the input")
    return out.model_dump()


def _call_groq(llm_input: dict) -> str:
    resp = httpx.post(
        config.GROQ_URL,
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={
            "model": config.GROQ_MODEL,
            "temperature": config.LLM_TEMPERATURE,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False)}],
        },
        timeout=config.LLM_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate(incident_id: str, llm_input: dict) -> tuple[dict | None, str]:
    """Returns (output, source) with source in {"cache", "llm", "template"}; output None means use templates."""
    cached = load_cache(incident_id, llm_input)
    if cached:
        return cached, "cache"
    if not config.LLM_ENABLED or not config.GROQ_API_KEY:
        return None, "template"
    ranks = {h["rank"] for h in llm_input["hypotheses"]}
    for attempt in (1, 2):  # one retry, for invalid JSON only
        try:
            return _parse(_call_groq(llm_input), ranks), "llm"
        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
            log.warning("LLM output invalid (attempt %d): %s", attempt, str(exc)[:200])
        except (httpx.HTTPError, OSError) as exc:
            log.warning("LLM call failed: %s", str(exc)[:200])
            break
    return None, "template"
