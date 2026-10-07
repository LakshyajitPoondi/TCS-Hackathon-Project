"""One entry point for live provider, three agent runs, live schema/grounding and judge checks."""
import json
import sys
from backend.core import config

def run():
    if not config.LLM_API_KEY or config.LLM_PROVIDER=='fake':
        print('Live checks skipped: no live LLM_API_KEY (or GROQ_API_KEY for groq). Set LLM_PROVIDER, LLM_MODEL and the key, then rerun python -m evals.live_llm_check. No-key and fake paths are covered by pytest/evals.')
        return 0
    from backend.init_db import init_db
    from backend.services.analysis_service import run_analysis
    from backend.services.data_loader import load_incident
    from engine import llm
    from evals.run_evals import settings,judge,provider_suite
    init_db();llm.reset_calls()
    payload={'hypotheses':[],'template_draft':'Engineering validation is required.','validation_warning':config.WARNING}
    with settings(LLM_ENABLED=True,AGENT_ENABLED=True):
        probe=llm.request_json(llm.SYSTEM_PROMPT,payload,llm.LLMOutput)
        provider_calls=llm.calls();analyses=[];details=[]
        for iid in ('INC-001','INC-002','INC-003'):
            response,meta=run_analysis(iid,load_incident(iid));analyses.append(response)
            live_wording=any(c['success'] and not c.get('cache_hit') for c in meta['llm_calls'])
            details.append({'incident_id':iid,'text_source':response.text_source,'grounding':response.grounding.model_dump(),
                            'investigation':response.investigation,'trace':meta['trace'],'calls':meta['llm_calls'],
                            'passed':response.text_source=='llm' and response.grounding.passed and response.investigation['mode']=='llm' and response.investigation['denied_calls']==0 and live_wording})
        report={'provider_probe':{'passed':probe is not None,'calls':provider_calls},'live_LLM_agent_suite':details,
                'provider_regression_suite':provider_suite(),'optional_judge':judge(analyses)}
    print(json.dumps(report,indent=2))
    return 0 if probe is not None and all(d['passed'] for d in details) else 1
if __name__=='__main__':sys.exit(run())
