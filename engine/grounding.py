"""Evidence-bound numeric/direction/machine claims and retrieved chunk-bound actions."""
import re
from backend.core.config import WARNING
from backend.models.schemas import Grounding

ALLOWLIST=[r'\b\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?',r'\b\d{1,2}:\d{2}(?::\d{2})?\b',
           r'\b(?:INC|UPL|SOP|IMM|LOT|BATCH|DOC|CASE)[-_][\w:-]+',r'(?im)^\s*\d+[.)]\s',r'(?i)\b(?:rank|hypothesis|step|top)\s*\d\b']
NUM=re.compile(r'(?<![\w])-?\d+(?:\.\d+)?')
BANNED=re.compile(r'root cause (?:is|was)|caused by|\bconfirmed\b|diagnos|AI detected|\b(?:high|medium|low)\s+\d+%|\d+%\s+confidence',re.I)
SIGNALS={'temperature':r'temp(?:erature)?','vibration':r'vibration','motor_current':r'(?:motor[ _])?current','speed':r'speed'}
UP=re.compile(r'\b(?:rose|rise|rising|increas\w*|higher|elevated)\b',re.I)
DOWN=re.compile(r'\b(?:fell|fall|falling|drop\w*|decreas\w*|lower|reduced)\b',re.I)
def _strip_ids(text):
    for pattern in ALLOWLIST:text=re.sub(pattern,' ',text,flags=re.I)
    return text
def _numbers(text):return NUM.findall(_strip_ids(text))
def _supported(number,pool):
    digits=len(number.partition('.')[2]);value=float(number)
    return any(abs(round(v,digits)-value)<1e-8 for v in pool)
def _norm(text):return ' '.join(re.findall(r'[a-z0-9]+',text.lower()))
def _pool(payload):
    values=[]
    def add(text):values.extend(float(n) for n in _numbers(str(text)))
    for v in payload.get('kpis',{}).values():
        if isinstance(v,(int,float)):values.append(float(v))
    for h in payload.get('hypotheses',[]):
        for e in h.get('supporting_evidence',[])+h.get('contradicting_evidence',[]):
            add(e.get('description',''))
            if isinstance(e.get('value'),(int,float)):values.append(float(e['value']))
        for chunk in h.get('chunks',[]):add(chunk['text'])
    for e in payload.get('observed_evidence',[]):add(e['description'])
    for chunk in payload.get('chunks',[]):add(chunk['text'])
    return values

def check_detailed(output,payload,retrieved_ids):
    pool=_pool(payload);inputs={h['rank']:h for h in payload.get('hypotheses',[])}
    flagged=[];sections=[];bad={'narrative':set(),'steps':set(),'draft':False}
    def scan(text,where,evidence=None):
        errors=[]
        for num in _numbers(text):
            if not _supported(num,pool):errors.append(f"Unsupported number '{num}' in {where}")
        match=BANNED.search(text.replace(WARNING,''))
        if match:errors.append(f"Unsupported certainty '{match.group()}' in {where}")
        if evidence is not None:
            for sentence in re.split(r'(?<=[.!?])\s+|\n',text):
                # Verification requests and conditional document statements are not observed signal claims.
                if re.search(r'\b(?:check|inspect|verify|compare|record|whether|if|should|would|may)\b',sentence,re.I):continue
                for signal,pattern in SIGNALS.items():
                    if not re.search(r'\b'+pattern+r'\b',sentence,re.I):continue
                    direction='up' if UP.search(sentence) else 'down' if DOWN.search(sentence) else None
                    numeric=_numbers(sentence)
                    if direction is None and not numeric:continue
                    candidates=[e for e in evidence if signal in e.get('signal','') or re.search(pattern,e.get('description',''),re.I)]
                    machine_names=set(re.findall(r'IMM-\d+',sentence,re.I))
                    if machine_names:candidates=[e for e in candidates if e.get('machine') in machine_names or all(m in e.get('description','') for m in machine_names)]
                    if direction:
                        candidates=[e for e in candidates if (UP if direction=='up' else DOWN).search(e.get('description',''))]
                    associated=[float(n) for e in candidates for n in _numbers(e.get('description',''))]
                    associated += [float(e['value']) for e in candidates if isinstance(e.get('value'),(float,int))]
                    if not candidates or any(not _supported(n,associated) for n in numeric):errors.append(f'Unsupported {signal} direction/machine/value in {where}')
        flagged.extend(errors);sections.append({'section':where,'passed':not errors,'flagged':errors,'replaced':False})
        return not errors
    all_evidence=[]
    for rank,h in inputs.items():all_evidence+=h.get('supporting_evidence',[])+h.get('contradicting_evidence',[])
    all_evidence+=payload.get('observed_evidence',[])
    for h in output.get('hypotheses',[]):
        rank=h['rank'];given=inputs.get(rank,{})
        if not scan(h.get('narrative',''),f'hypothesis {rank} narrative',given.get('supporting_evidence',[])+given.get('contradicting_evidence',[])):bad['narrative'].add(rank)
        chunks={c['chunk_id']:c for c in given.get('chunks',[])}
        for i,step in enumerate(h.get('verification_steps',[]),1):
            where=f'hypothesis {rank} step {i}';start=len(flagged)
            scan(step.get('step',''),where)
            chunk=chunks.get(step.get('chunk_id'))
            if step.get('source') not in retrieved_ids.get(rank,[]) or not chunk or chunk['doc_id']!=step.get('source'):
                flagged.append(f'{where} does not cite a retrieved chunk')
            elif _norm(step['step']) not in _norm(chunk['text']):
                # Conservative grounding accepts quotes; free paraphrases fall back safely.
                flagged.append(f'{where} action is not supported by its retrieved chunk')
            if len(flagged)>start:
                bad['steps'].add(rank);sections[-1].update(passed=False,flagged=flagged[start:])
    if not scan(output.get('rca_draft',''),'rca_draft',all_evidence):bad['draft']=True
    return Grounding(passed=not flagged,flagged=flagged,sections=sections),bad
def check(output,payload,retrieved):return check_detailed(output,payload,retrieved)[0]
