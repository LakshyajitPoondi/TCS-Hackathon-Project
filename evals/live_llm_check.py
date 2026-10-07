"""Live provider check that spends at most --max-calls real requests (default 2).

Runs ONE analysis of INC-001 with AGENT_MODE=llm_plan (one planning call + one wording call) or, with
--agent-mode deterministic, only the wording call (up to two requests if the provider returns 503). Results are cached,
so re-running spends nothing unless the cache is cleared. Quota errors are reported, never retried.
Run: python -m evals.live_llm_check [--max-calls 2] [--incident INC-001]
"""
import argparse
import json
import sys
from backend.core import config


def run(max_calls=2, incident='INC-001', agent_mode='llm_plan'):
    if not config.LLM_API_KEY or config.LLM_PROVIDER == 'fake':
        print('Live checks skipped: no live LLM_API_KEY (GROQ_API_KEY is read only when LLM_PROVIDER=groq). '
              'Set LLM_PROVIDER, LLM_MODEL and LLM_API_KEY, then rerun python -m evals.live_llm_check. '
              'No-key and fake paths are covered by pytest/evals.')
        return 0
    from backend.init_db import init_db
    from backend.services.analysis_service import run_analysis
    from backend.services.data_loader import load_incident
    from engine import llm
    from evals.run_evals import settings
    init_db()
    before = llm.status()
    with settings(LLM_ENABLED=True, AGENT_ENABLED=True, AGENT_MODE=agent_mode, LLM_MAX_CALLS_PER_ANALYSIS=min(max_calls, 2)):
        response, meta = run_analysis(incident, load_incident(incident))
    after = llm.status()
    report = {'provider': config.LLM_PROVIDER, 'model': config.LLM_MODEL, 'incident_id': incident,
              'calls_today_before': before['calls_today'], 'calls_today_after': after['calls_today'],
              'live_requests_this_run': response.llm_usage['requests'], 'cache_hits': response.llm_usage['cache_hits'],
              'text_source': response.text_source, 'agent_mode': response.investigation['mode'],
              'plan_source': response.investigation.get('plan_source'), 'denied_calls': response.investigation['denied_calls'],
              'grounding_passed': response.grounding.passed, 'grounding_flags': response.grounding.flagged,
              'calls': [{k: c.get(k) for k in ('purpose', 'success', 'fallback_reason', 'latency_ms', 'cache_hit')} for c in meta['llm_calls']],
              'blocked_until': after['blocked_until']}
    passed = response.text_source == 'llm' and response.investigation['mode'] == agent_mode and response.investigation['denied_calls'] == 0
    report['status'] = 'Verified' if passed else 'Unverified (' + (response.llm_usage['fallback_reason'] or 'see calls') + ')'
    print(json.dumps(report, indent=2, default=str))
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-calls', type=int, default=2)
    parser.add_argument('--incident', default='INC-001')
    parser.add_argument('--agent-mode', choices=['llm_plan', 'deterministic'], default='llm_plan',
                        help='deterministic spends the whole budget on the wording call')
    args = parser.parse_args()
    sys.exit(run(args.max_calls, args.incident, args.agent_mode))
