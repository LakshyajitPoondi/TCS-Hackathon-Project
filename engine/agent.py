"""Bounded, read-only investigation. Tool authorization is independent of the LLM.

AGENT_MODE=deterministic (default): the fixed tool sequence below, no LLM calls.
AGENT_MODE=llm_plan: ONE LLM call returns the whole plan as JSON (cached); the tools then run without
further LLM calls. Every tool call is checked against the investigation scope, whoever proposed it.
The trace never changes hypotheses, ranks or confidence.
"""
import copy
import json
import time
from pydantic import BaseModel, ConfigDict, Field
from backend import db
from backend.core import config
from backend.services.machines import serialize
from engine import llm, retrieval
from engine.memory import recall

PLAN_PROMPT_VERSION = 'agent-plan-v1'
TOOL_NAMES = ['get_incident_summary', 'get_hypotheses_and_evidence', 'get_machine', 'search_machine_documents',
              'read_document_chunk', 'recall_similar_cases', 'finish']
PLAN_PROMPT = ('Plan a read-only investigation. Return JSON {"steps":[{"tool":...,"args":{...}}]} with at most '
               '{max_steps} steps, using only these tools: ' + ', '.join(TOOL_NAMES) + '. Use only allowed_machines and '
               'only chunk ids listed in retrieved_chunks. Never rerank or rescore hypotheses. End with finish.')


class ToolCall(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tool: str
    args: dict = Field(default_factory=dict)


class ToolPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    steps: list[ToolCall] = Field(min_length=1, max_length=30)


def _plan(incident_id, payload, fallback):
    """One LLM request (or a cache hit) for the whole plan. Returns (steps|None, source)."""
    parse = lambda out: [c.model_dump() for c in ToolPlan.model_validate_json(json.dumps(out)).steps]  # noqa: E731
    cached = llm.cache_get('agent_plan', incident_id, payload, parse, PLAN_PROMPT_VERSION)
    if cached:
        llm._cache_hit('agent_plan')
        return cached, 'cache'
    out = llm.request_json(PLAN_PROMPT.replace('{max_steps}', str(config.AGENT_MAX_STEPS)), payload, ToolPlan,
                           purpose='agent_plan', fake_output={'steps': fallback})
    if not out:
        return None, 'deterministic'
    steps = parse(out)
    llm.cache_put('agent_plan', incident_id, payload, out, parse, PLAN_PROMPT_VERSION)
    return steps, 'llm'


def investigate(incident_id, line, machines, evidence, hyps, signature, rag_results, context):
    allowed = set()
    for h in hyps:
        target = h.get('target'); allowed.update([line+'/'+target] if target in machines else [line+'/'+m for m in machines])
    if not hyps: allowed.update(line+'/'+m for m in machines)
    permitted_chunks = {hit['chunk_id']: hit for result in rag_results.values() for hit in result['hits']}
    sequence = [{'tool': 'get_incident_summary', 'args': {}}, {'tool': 'get_hypotheses_and_evidence', 'args': {}}]
    sequence += [{'tool': 'get_machine', 'args': {'machine_uid': uid}} for uid in sorted(allowed)]
    for h in hyps:
        target = h.get('target'); uid = line+'/'+target if target in machines else sorted(allowed)[0]
        sequence.append({'tool': 'search_machine_documents', 'args': {'machine_uid': uid, 'query': retrieval.build_query(h)}})
    if permitted_chunks:
        hit = next(iter(permitted_chunks.values()))
        sequence.append({'tool': 'read_document_chunk', 'args': {'doc_id': hit['doc_id'], 'chunk_id': hit['chunk_id']}})
    sequence.append({'tool': 'recall_similar_cases', 'args': {'incident_id': incident_id}})
    frozen = copy.deepcopy(hyps); trace = []; denials = 0
    mode, plan_source, calls = 'deterministic', 'deterministic', sequence
    if config.AGENT_MODE == 'llm_plan' and config.AGENT_ENABLED and llm.available():
        payload = {'incident_id': incident_id, 'allowed_machines': sorted(allowed), 'recommended_plan': sequence,
                   'retrieved_chunks': sorted(permitted_chunks), 'max_steps': config.AGENT_MAX_STEPS,
                   'hypotheses': [{k: h.get(k) for k in ('rank', 'category', 'subcause', 'confidence', 'target')} for h in frozen]}
        planned, plan_source = _plan(incident_id, payload, sequence)
        if planned:
            mode, calls = 'llm_plan', planned
    for index in range(config.AGENT_MAX_STEPS):
        call = calls[index] if index < len(calls) else {'tool': 'finish', 'args': {}}
        tool, args = call['tool'], call['args']; start = time.perf_counter()
        try:
            if tool not in TOOL_NAMES: raise ValueError('Unknown tool')
            if tool == 'finish': break
            if tool == 'get_incident_summary':
                if args: raise ValueError('Unexpected arguments')
                result = {'incident_id': incident_id, 'line': line, 'machines': machines, 'kpis': evidence.get('kpis')}
            elif tool == 'get_hypotheses_and_evidence':
                if args: raise ValueError('Unexpected arguments')
                result = frozen
            elif tool in ('get_machine', 'search_machine_documents'):
                if args.get('machine_uid') not in allowed: raise ValueError('Machine outside investigation scope')
                if tool == 'get_machine':
                    if set(args) != {'machine_uid'}: raise ValueError('Unexpected arguments')
                    with db.Session() as session: result = serialize(session.get(db.Machine, args['machine_uid']))
                else:
                    if set(args) != {'machine_uid', 'query'} or not isinstance(args['query'], str) or len(args['query']) > 8000:
                        raise ValueError('Invalid search arguments')
                    result = retrieval.search(args['machine_uid'], args['query'])
                    for hit in result['hits']: permitted_chunks[hit['chunk_id']] = hit
            elif tool == 'read_document_chunk':
                hit = permitted_chunks.get(args.get('chunk_id'))
                if set(args) != {'doc_id', 'chunk_id'} or not hit or hit['doc_id'] != args.get('doc_id'):
                    raise ValueError('Chunk was not retrieved in scope')
                result = hit
            else:
                if args != {'incident_id': incident_id}: raise ValueError('Invalid incident')
                result = [c.model_dump() for c in recall(signature, incident_id, context=context)]
            summary = {'status': 'ok', 'data': result}
        except Exception as exc:
            denials += 1; summary = {'status': 'denied', 'reason': str(exc)[:200]}
        trace.append({'step': len(trace)+1, 'tool': tool, 'args': args, 'result_summary': summary,
                      'latency_ms': round((time.perf_counter()-start)*1000, 2), 'tokens': None})
    assert hyps == frozen
    return {'mode': mode, 'plan_source': plan_source, 'steps': len(trace), 'max_steps': config.AGENT_MAX_STEPS,
            'capped': len(trace) == config.AGENT_MAX_STEPS, 'denied_calls': denials, 'allowed_machines': sorted(allowed)}, trace
