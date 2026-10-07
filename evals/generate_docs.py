"""Deterministic synthetic document fixtures and evaluation-only labels."""
import json
from backend.core.config import DATA_DIR,ROOT_DIR
from backend.services.data_loader import load_incident

def generate():
    directory=DATA_DIR/'eval_docs';directory.mkdir(exist_ok=True)
    fixtures=[];mapping={}
    def add(did,filename,text,scope,targets,expected,status='active'):
        (directory/filename).write_text(text,encoding='utf-8')
        fixtures.append(dict(doc_id=did,filename=filename,text=text,scope=scope,targets=targets))
        mapping[did]=dict(machine_uids=expected,status=status)
    uids=[f'{line}/{short}' for line in ('LINE-A','LINE-B','LINE-C') for short in ('IMM-01','IMM-02','IMM-03')]
    facts={}
    for i,uid in enumerate(uids):
        stem=uid.replace('/','_');flow=12+i;vibration=round(2+i*.1,1)
        facts[uid]={'coolant_flow_l_min':flow,'vibration_limit':vibration,'chiller_reference':uid,'synthetic':True}
        text=f'''# {uid} synthetic manual
Synthetic training specification, not an operational safety limit. Physical machine {uid}.
## Cooling and vibration verification
1. Check coolant flow against the synthetic specification of {flow} L/min for {uid}.
2. Inspect the cooling fan and heat-exchanger fins for blockage.
3. Compare vibration with the synthetic limit of {vibration} for {uid}.
4. Review synthetic chiller reference {uid}; this reuses a known identity and adds no machine.
Temperature, speed, vibration, motor current, defects, downtime and alarms support inspection.
## Procedure
Review material batch records, method setup changes, measurement sensors, people handover and environment.
'''
        add('EVAL-MANUAL-'+stem,stem+'_manual.md',text,'machine',[uid],[uid])
        add('EVAL-DECOY-'+stem,stem+'_decoy.md',f'# {uid} decoy\n{uid} cooling temperature vibration coolant flow fan blockage troubleshooting manual. Wrong-machine decoy, synthetic only.','machine',[uid],[uid])
    add('EVAL-MODEL-IMM','model_IMM.md','# Model family\nIMM model family cooling fan vibration temperature verification. Synthetic family guidance.','model',['IMM'],uids)
    for line in ('LINE-A','LINE-B','LINE-C'):
        add('EVAL-LINE-'+line,line+'_guide.md',f'# {line} guidance\n{line} ambient temperature environment HVAC and handover verification. Synthetic guidance.','line',[line],[u for u in uids if u.startswith(line+'/')])
    add('EVAL-PLANT','plant_guide.md','# Plant guide\nReview incident alarms, downtime and defect counts before release. Synthetic guidance.','plant',[],uids)
    add('EVAL-AMBIGUOUS','IMM-01_guide.md','# Short identity\nIMM-01 cooling temperature fan verification.','plant',[],uids,'pending_mapping')
    add('EVAL-CONFLICT','LINE-A_IMM-01_conflict.md','# Contradictory identity\nLINE-B/IMM-01 cooling temperature fan verification.','machine',['LINE-A/IMM-01'],['LINE-A/IMM-01'],'pending_mapping')
    answers=json.loads((DATA_DIR/'answer_key.json').read_text(encoding='utf-8'))
    incidents={}
    for iid,answer in answers.items():
        frame=load_incident(iid);line=str(frame.line.iloc[0]);target=answer.get('target_machine')
        allowed=[line+'/'+target] if answer.get('category')=='machine' and target else [line+'/'+m for m in sorted(frame.machine.unique())]
        expected=['EVAL-MANUAL-'+u.replace('/','_') for u in allowed]
        incidents[iid]={'expected_doc_ids':expected,'expected_facts':{u:facts[u] for u in allowed},
                        'forbidden_doc_ids':[f['doc_id'] for f in fixtures if f['scope']=='machine' and not set(f['targets'])&set(allowed)]}
    key={'fixtures':mapping,'incidents':incidents,'facts':facts}
    (ROOT_DIR/'evals/docs_answer_key.json').write_text(json.dumps(key,indent=2),encoding='utf-8')
    return fixtures,key

def install_fixtures():
    from backend import db
    from backend.services.documents import ingest
    fixtures,_=generate()
    with db.Session.begin() as session:
        for f in fixtures:
            if not session.get(db.Document,f['doc_id']):
                ingest(session,f['filename'],f['text'].encode(),f['doc_id'],'manual','1',f['scope'],f['targets'],None,doc_id=f['doc_id'])
    return fixtures
if __name__=='__main__':
    from backend.init_db import init_db
    init_db();install_fixtures();print('Generated and installed 25 deterministic synthetic documentation fixtures.')
