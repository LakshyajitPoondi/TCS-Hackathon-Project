"""Optional real fastembed retrieval benchmark; isolated process with a bounded parent wait."""
import json
import sys
from backend.core import config
def run(provider='fastembed'):
    from backend.init_db import init_db
    from evals.generate_docs import install_fixtures
    from backend.services.data_loader import load_incident
    from engine import retrieval
    init_db();_,key=install_fixtures();config.EMBEDDINGS_PROVIDER=provider;rows=[]
    for iid,item in key['incidents'].items():
        frame=load_incident(iid);uids=list(item['expected_facts'])
        result=retrieval.search(uids,'coolant flow synthetic specification vibration limit chiller reference manual',4)
        if result['embedding_status']!='enabled':return {'status':'Unverified','reason':result['embedding_status']}
        actual={h['doc_id'] for h in result['hits']};expected=set(item['expected_doc_ids'])
        rows.append({'incident_id':iid,'recall_at_4':len(actual&expected)/len(expected),'wrong_machine_leaks':len(actual&set(item['forbidden_doc_ids']))})
    return {'status':'Verified','model':config.EMBEDDINGS_MODEL,'recall_at_4':sum(r['recall_at_4'] for r in rows)/len(rows),'wrong_machine_leaks':sum(r['wrong_machine_leaks'] for r in rows),'details':rows}
if __name__=='__main__':print(json.dumps(run()))
