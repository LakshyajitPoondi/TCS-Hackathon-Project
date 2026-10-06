"""Dev-only sanity check: engine output vs data/answer_key.json. Run: python -m evals.sanity_check

The answer key is read ONLY here, never by engine/ or backend/. Phase 5 extends this into run_evals.py.
"""

import json

from backend.core.config import DATA_DIR
from backend.services.data_loader import list_incidents, load_incident
from engine.scoring import score_hypotheses
from engine.signals import analyze_signals


def _name(category, subcause):
    return category + (f"/{subcause}" if subcause else "")


def run() -> dict:
    key = json.loads((DATA_DIR / "answer_key.json").read_text(encoding="utf-8"))
    rows = []
    for ref in list_incidents():
        iid = ref["id"]
        ans = key.get(iid)
        if not ans:
            continue
        scored = score_hypotheses(analyze_signals(load_incident(iid)))
        hyps = [_name(h["category"], h["subcause"]) for h in scored["hypotheses"]]
        expected = None if ans.get("expect_abstain") else _name(ans["category"], ans.get("subcause"))
        also = [_name(a["category"], a.get("subcause")) for a in ans.get("also_plausible", [])]
        rows.append({
            "id": iid, "expected": expected or "ABSTAIN", "also": also, "top1": hyps[0] if hyps else "-",
            "top3": hyps, "status": scored["status"], "abstain_expected": bool(ans.get("expect_abstain")),
            "top1_hit": bool(expected) and hyps[:1] == [expected], "top3_hit": bool(expected) and expected in hyps,
            "also_in_top3": all(a in hyps for a in also) if also else None,
        })

    print(f"{'incident':<9}| {'expected':<18}| {'also_plausible':<18}| {'top-1':<18}| {'top-3':<52}| exp_in_top3 | status")
    for r in rows:
        print(f"{r['id']:<9}| {r['expected']:<18}| {','.join(r['also']) or '-':<18}| {r['top1']:<18}| "
              f"{','.join(r['top3']) or '-':<52}| {('yes' if r['top3_hit'] else 'no') if not r['abstain_expected'] else 'n/a':<11} | {r['status']}")

    clear = [r for r in rows if not r["abstain_expected"]]
    abst = [r for r in rows if r["abstain_expected"]]
    amb = [r for r in rows if r["also"]]
    summary = {
        "top1_hits": f"{sum(r['top1_hit'] for r in clear)}/{len(clear)}",
        "top3_hits": f"{sum(r['top3_hit'] for r in clear)}/{len(clear)}",
        "correct_abstentions": f"{sum(r['status'] == 'insufficient_evidence' for r in abst)}/{len(abst)}",
        "wrong_abstentions": f"{sum(r['status'] == 'insufficient_evidence' for r in clear)}/{len(clear)}",
        "ambiguous_also_plausible_in_top3": f"{sum(bool(r['also_in_top3']) for r in amb)}/{len(amb)}",
    }
    print("\nSummary:", "  ".join(f"{k}={v}" for k, v in summary.items()))
    return {"rows": rows, "summary": summary}


if __name__ == "__main__":
    run()
