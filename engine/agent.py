"""Bounded, read-only investigation. Tool authorization is independent of the LLM."""
import copy
import time
from pydantic import BaseModel, ConfigDict, Field
from backend import db
from backend.core import config
from backend.services.machines import serialize
from engine import llm, retrieval
from engine.memory import recall

class ToolCall(BaseModel):
    model_config=ConfigDict(extra='forbid')
    tool: str
    args: dict=Field(default_factory=dict)

def investigate(incident_id,line,machines,evidence,hyps,signature,rag_results,context):
    allowed=set()
    for h in hyps:
        target=h.get('target');allowed.update([line+'/'+target] if target in machines else [line+'/'+m for m in machines])
    if not hyps:allowed.update(line+'/'+m for m in machines)
    permitted_chunks={hit['chunk_id']:hit for result in rag_results.values() for hit in result['hits']}
    sequence=[{'tool':'get_incident_summary','args':{}},{'tool':'get_hypotheses_and_evidence','args':{}}]
    sequence += [{'tool':'get_machine','args':{'machine_uid':uid}} for uid in sorted(allowed)]
    for h in hyps:
        target=h.get('target');uid=line+'/'+target if target in machines else sorted(allowed)[0]
        sequence.append({'tool':'search_machine_documents','args':{'machine_uid':uid,'query':retrieval.build_query(h)}})
    if permitted_chunks:
        hit=next(iter(permitted_chunks.values()))
        sequence.append({'tool':'read_document_chunk','args':{'doc_id':hit['doc_id'],'chunk_id':hit['chunk_id']}})
    sequence.append({'tool':'recall_similar_cases','args':{'incident_id':incident_id}})
    frozen=copy.deepcopy(hyps);trace=[];mode='llm' if config.AGENT_ENABLED and llm.available() else 'deterministic';denials=0
    tool_names=['get_incident_summary','get_hypotheses_and_evidence','get_machine','search_machine_documents','read_document_chunk','recall_similar_cases','finish']
    for index in range(config.AGENT_MAX_STEPS):
        fallback=sequence[index] if index<len(sequence) else {'tool':'finish','args':{}}
        call=fallback
        if mode=='llm':
            generated=llm.request_json('Select one read-only tool and JSON args. Allowed tools: '+', '.join(tool_names)+'. Use only allowed machines. Never rerank. Return {tool,args}.',
                       {'allowed_machines':sorted(allowed),'next_recommended':fallback,'trace':trace,'hypotheses':frozen},ToolCall,fake_output=fallback)
            if generated:call=generated
            else:mode='deterministic';call=fallback
        tool,args=call['tool'],call['args'];start=time.perf_counter()
        try:
            if tool not in tool_names:raise ValueError('Unknown tool')
            if tool=='finish':break
            if tool=='get_incident_summary':
                if args:raise ValueError('Unexpected arguments')
                result={'incident_id':incident_id,'line':line,'machines':machines,'kpis':evidence.get('kpis')}
            elif tool=='get_hypotheses_and_evidence':
                if args:raise ValueError('Unexpected arguments')
                result=frozen
            elif tool in ('get_machine','search_machine_documents'):
                if args.get('machine_uid') not in allowed:raise ValueError('Machine outside investigation scope')
                if tool=='get_machine':
                    if set(args)!={'machine_uid'}:raise ValueError('Unexpected arguments')
                    with db.Session() as session:result=serialize(session.get(db.Machine,args['machine_uid']))
                else:
                    if set(args)!={'machine_uid','query'} or not isinstance(args['query'],str) or len(args['query'])>8000:raise ValueError('Invalid search arguments')
                    result=retrieval.search(args['machine_uid'],args['query'])
                    for hit in result['hits']:permitted_chunks[hit['chunk_id']]=hit
            elif tool=='read_document_chunk':
                hit=permitted_chunks.get(args.get('chunk_id'))
                if set(args)!={'doc_id','chunk_id'} or not hit or hit['doc_id']!=args.get('doc_id'):raise ValueError('Chunk was not retrieved in scope')
                result=hit
            else:
                if args!={'incident_id':incident_id}:raise ValueError('Invalid incident')
                result=[c.model_dump() for c in recall(signature,incident_id,context=context)]
            summary={'status':'ok','data':result}
        except Exception as exc:
            denials+=1;summary={'status':'denied','reason':str(exc)[:200]}
        trace.append({'step':len(trace)+1,'tool':tool,'args':args,'result_summary':summary,'latency_ms':round((time.perf_counter()-start)*1000,2),'tokens':llm.calls()[-1].get('tokens') if mode=='llm' and llm.calls() else None})
    assert hyps==frozen
    return {'mode':mode,'steps':len(trace),'max_steps':config.AGENT_MAX_STEPS,'capped':len(trace)==config.AGENT_MAX_STEPS,'denied_calls':denials,'allowed_machines':sorted(allowed)},trace
