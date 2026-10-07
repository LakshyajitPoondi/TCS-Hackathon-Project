"""Builds the AnalysisResponse.

signals -> scoring (frozen, deterministic) -> BM25 SOPs per hypothesis -> memory recall
-> wording (cache -> Groq -> templates) -> grounding -> template fallback for flagged parts.
RAG, memory and the LLM only enrich the output; they never change scores, ranks or confidence.
"""

import logging

import pandas as pd

from backend.core.config import WARNING
from backend.models.schemas import (
    AnalysisResponse,
    CategoryEvidence,
    Evidence,
    Grounding,
    Hypothesis,
    IncidentWindow,
    KPIs,
    MachineHealth,
    VerificationStep,
)
from engine import llm
from engine import retrieval
from engine.agent import investigate
from engine.grounding import check_detailed
from engine.memory import build_signature, recall
from engine.rag import SOP_INDEX, TRIAGE_SOP, get_sop, retrieve_for_hypothesis
from engine.scoring import CATEGORIES, MIN_SCORE, score_hypotheses
from engine.signals import analyze_signals

log = logging.getLogger("rca.analysis")

KPI_FIELDS = ("defect_rate", "total_defects", "downtime_min", "alarm_count", "event_count", "threshold_breaches")
TEMPLATE_STEPS_PER_SOP = 2
MEASUREMENT_SOP = "SOP-015"  # added to the abstention draft when sensor anomalies are present


def analyze_incident(incident_id: str, df: pd.DataFrame) -> AnalysisResponse:
    return run_analysis(incident_id, df)[0]


def _hyp_name(h: dict) -> str:
    return h["category"] + (f" / {h['subcause']}" if h["subcause"] else "")


def _needs_triage(evidence: dict) -> bool:
    k = evidence["kpis"]
    return bool(evidence.get("window")) and (k["alarm_count"] > 0 or k["downtime_min"] > 0)


def _retrieve(h: dict, triage: bool) -> list[dict]:
    sops = retrieve_for_hypothesis(h, top_k=2)
    if triage and TRIAGE_SOP not in [s["id"] for s in sops]:
        sops.append(get_sop(TRIAGE_SOP))
    return sops


def _template_steps(sops: list[dict], triage: bool) -> list[dict]:
    chosen = sops[:1] + ([get_sop(TRIAGE_SOP)] if triage and sops and sops[0]["id"] != TRIAGE_SOP else [])
    return [{"step": st, "source": s["id"]} for s in chosen for st in s["steps"][:TEMPLATE_STEPS_PER_SOP]]


def _summary_line(evidence: dict) -> str:
    k, w = evidence["kpis"], evidence.get("window")
    win = (f"Window {w['start'][:16].replace('T', ' ')} to {w['end'][11:16]} (detected by: {', '.join(w['detected_by'][:3])}). "
           if w else "No sustained incident window was detected. ")
    return (f"{win}{k['total_defects']} defects ({k['defect_rate']:.2f} per record), {k['downtime_min']:.0f} min downtime, "
            f"{k['alarm_count']} alarm(s), {k['threshold_breaches']} signal deviation(s).")


def _template_draft(incident_id: str, evidence: dict, hyps: list[dict], steps: dict[int, list[dict]]) -> str:
    top = hyps[0]
    alts = [f"{_hyp_name(h)} ({h['confidence']})" for h in hyps[1:]]
    lines = [f"RCA draft: {incident_id}", "", "Incident summary:", _summary_line(evidence), "",
             "Leading hypothesis:", f"{_hyp_name(top)} ({top['confidence']} confidence), pending verification.", "",
             "Supporting evidence:"]
    lines += [f"- {e['description']}" for e in top["supporting_evidence"][:4]]
    lines += [f"- Contradicting: {e['description']}" for e in top["contradicting_evidence"][:2]]
    lines += ["", "Alternatives:", ", ".join(alts) + "." if alts else "None reached the minimum evidence score.", "",
              "Missing verification:"]
    lines += [f"- {m}" for m in top["missing_checks"]]
    lines += ["", "Verification actions:"]
    lines += [retrieval.draft_line(s) for s in steps[top["rank"]]]
    lines += ["", WARNING]
    return "\n".join(lines)


def _abstain_draft(incident_id: str, evidence: dict, scored: dict, steps: list[dict]) -> str:
    lines = [f"RCA draft: {incident_id}", "", "Status: Insufficient evidence - additional verification required.", "",
             "Incident summary:", _summary_line(evidence) if evidence.get("kpis") else "No KPIs available."]
    reason = evidence.get("reason") or scored.get("abstain_reason")
    if reason:
        lines.append(f"Reason: {reason}")
    observed = [e["description"] for c in CATEGORIES for e in scored["category_evidence"][c]["supporting"]][:5]
    if observed:
        lines += ["", "Observed (none sufficient on its own):"] + [f"- {o}" for o in observed]
    lines += ["", "Suggested checks:"]
    # B19: suggested checks come from the in-scope retrieved procedures.
    lines += [retrieval.draft_line(s) for s in steps] or ["- No in-scope procedure was retrieved; follow plant triage."]
    lines += ["", WARNING]
    return "\n".join(lines)


def _llm_input(incident_id, evidence, hyps, retrieved, similar) -> dict:
    w = evidence.get("window")
    strip = lambda evs: [{"description": e["description"], "machine": e["machine"], "value": e["value"]} for e in evs]  # noqa: E731
    return {
        "incident_id": incident_id,
        "scoring_policy":{'minimum_score':MIN_SCORE},
        "window": {"start": w["start"], "end": w["end"], "detected_by": w["detected_by"]} if w else None,
        "kpis": {f: evidence["kpis"][f] for f in KPI_FIELDS},
        "machine_health": evidence.get("health", []),
        "hypotheses": [{
            "rank": h["rank"], "category": h["category"], "subcause": h["subcause"], "confidence": h["confidence"],
            "target_machine": h.get("target"), "supporting_evidence": strip(h["supporting_evidence"]),
            "contradicting_evidence": strip(h["contradicting_evidence"]), "missing_checks": h["missing_checks"],
            "sops": [{"id": s["doc_id"], "title": s["title"], "steps": [s['text']], "chunk_id":s['chunk_id']} for s in retrieved[h["rank"]]],
            "chunks": retrieved[h['rank']],
        } for h in hyps],
        "similar_cases": [c.model_dump() for c in similar],
        "validation_warning": WARNING,
    }


def run_analysis(incident_id: str, df: pd.DataFrame) -> tuple[AnalysisResponse, dict]:
    """Returns (response, meta). meta = {text_source, retrieved_sops{rank: [ids]}, signature}."""
    evidence = analyze_signals(df)
    llm.reset_calls()
    scored = score_hypotheses(evidence)
    hyps = scored["hypotheses"]
    signature = build_signature(evidence)
    line=str(df['line'].iloc[0]);machines=sorted(df['machine'].unique())
    target=hyps[0].get('target') if hyps else None
    context={'machine_uid':line+'/'+target if target in machines else None,'line':line,'model':'IMM',
             'confirmed_category':hyps[0]['category'] if hyps else None,'confirmed_subcause':hyps[0]['subcause'] if hyps else None,
             'events':sorted(df['event_code'].dropna().unique())}
    similar = recall(signature, exclude_incident_id=incident_id,context=context)
    rag_results={h['rank']:retrieval.for_hypothesis(h,line,machines) for h in hyps}
    if not hyps:
        rag_results={0:retrieval.search([line+'/'+m for m in machines],'incident triage measurement verification')}
    accessed,filtered=retrieval.provenance(rag_results)
    investigation,trace=investigate(incident_id,line,machines,evidence,hyps,signature,rag_results,context)

    if not hyps:
        steps=retrieval.verification_steps(rag_results[0]['hits'])
        draft = _abstain_draft(incident_id, evidence, scored, steps)
        final = {"hypotheses": [], "rca_draft": draft}
        observed=[e for c in CATEGORIES for e in scored['category_evidence'][c]['supporting']]
        grounding,_=check_detailed(final,{'scoring_policy':{'minimum_score':MIN_SCORE},'kpis':evidence.get('kpis',{}),'observed_evidence':observed,'chunks':rag_results[0]['hits']},{})
        source, retrieved = 'template', {}
    else:
        triage = _needs_triage(evidence)
        retrieved = {h['rank']:rag_results[h['rank']]['hits'] for h in hyps}
        tpl_steps = {h['rank']:retrieval.verification_steps(retrieved[h['rank']]) for h in hyps}
        template = {
            "hypotheses": [{"rank": h["rank"], "narrative": f"The {_hyp_name(h)} hypothesis requires verification. "+' '.join(e['description'] for e in h['supporting_evidence'][:3]), "verification_steps": tpl_steps[h["rank"]]}
                           for h in hyps],
            "rca_draft": _template_draft(incident_id, evidence, hyps, tpl_steps),
        }
        llm_input = _llm_input(incident_id, evidence, hyps, retrieved, similar)
        llm_input['template_draft']=template['rca_draft']
        for h, t in zip(llm_input['hypotheses'], template['hypotheses']):
            h['template_narrative']=t['narrative'];h['template_steps']=t['verification_steps']
        out, source = llm.generate(incident_id, llm_input)
        final = out or template
        retrieved_ids = {r: [s["doc_id"] for s in sops] for r, sops in retrieved.items()}
        grounding, bad = check_detailed(final, llm_input, retrieved_ids)
        if source == "llm" and grounding.passed:
            llm.save_cache(incident_id, llm_input, final)
        # Replace only the flagged parts with the deterministic template.
        tpl_by_rank = {h["rank"]: h for h in template["hypotheses"]}
        out_by_rank = {h["rank"]: h for h in final["hypotheses"]}
        final = {
            "hypotheses": [{
                "rank": r,
                "narrative": (tpl_by_rank if r in bad["narrative"] else out_by_rank)[r]["narrative"],
                "verification_steps": (tpl_by_rank if r in bad["steps"] else out_by_rank)[r]["verification_steps"],
            } for r in tpl_by_rank],
            "rca_draft": template["rca_draft"] if bad["draft"] else final["rca_draft"],
        }
        for section in grounding.sections:
            match=__import__('re').search(r'hypothesis (\d+) (narrative|step)',section['section'])
            section['replaced']=bool(match and int(match[1]) in bad['narrative' if match[2]=='narrative' else 'steps']) or (section['section']=='rca_draft' and bad['draft'])
        final_check,_=check_detailed(final,llm_input,retrieved_ids)
        grounding.passed=final_check.passed

    text = {h["rank"]: h for h in final["hypotheses"]}
    w, kpis = evidence.get("window"), evidence.get("kpis")
    response = AnalysisResponse(
        investigation=investigation,
        documents_accessed=accessed,documents_filtered_out=filtered,
        retrieval_status={str(r):v['embedding_status'] for r,v in rag_results.items()},
        text_source=source,
        incident_id=incident_id,
        analysis_status=scored["status"],
        incident_window=IncidentWindow(start=w["start"], end=w["end"], detected_by=w["detected_by"]) if w else None,
        kpis=KPIs(**{f: kpis[f] for f in KPI_FIELDS}) if kpis else None,
        machine_health=[MachineHealth(**h) for h in evidence.get("health", [])],
        category_evidence=[
            CategoryEvidence(category=c, supporting=[Evidence(**e) for e in scored["category_evidence"][c]["supporting"]],
                             contradicting=[Evidence(**e) for e in scored["category_evidence"][c]["contradicting"]])
            for c in CATEGORIES
        ],
        hypotheses=[
            Hypothesis(
                rank=h["rank"], category=h["category"], subcause=h["subcause"], confidence=h["confidence"],
                score=h["score"], supporting_evidence=[Evidence(**e) for e in h["supporting_evidence"]],
                contradicting_evidence=[Evidence(**e) for e in h["contradicting_evidence"]],
                missing_checks=h["missing_checks"],
                verification_steps=[VerificationStep(step=s["step"], source=s["source"],chunk_id=s.get('chunk_id'),
                                                     source_title=next((hit['title'] for hit in retrieved[h['rank']] if hit['doc_id']==s['source']),s['source']),
                                                     page_or_section=next((hit['page_or_section'] for hit in retrieved[h['rank']] if hit['chunk_id']==s.get('chunk_id')),None))
                                    for s in text[h["rank"]]["verification_steps"]],
                narrative=text[h["rank"]]["narrative"],
            )
            for h in hyps
        ],
        similar_cases=similar,
        rca_draft=final["rca_draft"],
        grounding=grounding,
    )
    meta = {"trace":trace, "llm_calls":llm.calls(), "text_source": source, "retrieved_sops": {r: [s["doc_id"] for s in v] for r, v in retrieved.items()},
            "signature": signature}
    log.info("analysis %s: status=%s text_source=%s grounding=%s", incident_id, scored["status"], source, grounding.passed)
    return response, meta
