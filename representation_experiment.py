"""Frozen representation comparison; direct Qwen, no classifier in inference path."""
import argparse, hashlib, json, os, time
from collections import Counter
from pathlib import Path
from project_paths import dataset_path
import numpy as np
import requests
from dotenv import load_dotenv
from direct_llm import CLASSES, classification, dump, read_lines, write_lines
from stage2_screen import ROOT, read_binary, sha
from inference_protocol_v2 import VERSION, RESPONSE_FORMAT, validate_v2
from scripts.discover_binary_features import features
DATA=ROOT/'data/representation-screen'
RUN=ROOT/'runs/representation-screen'
SOURCE=dataset_path()
FIELDS=['fraction_ones','transition_count','max_zero_run_fraction','max_one_run_fraction']
SYSTEM='''Infer the activity of the unlabeled target interval using only the supplied observations or deterministic features and labeled reference intervals from other participants. Do not use unavailable measurements or invent activity-specific patterns. Identical observations or feature values may correspond to different activities. Reference class frequencies are a selection choice, not a population prior. Return only the three fields required by the response schema: predicted_activity, confidence for that exact activity, and sufficient_information indicating whether the observation reliably distinguishes that activity. No explanation, extra keys, or markdown.'''
DEFINITIONS='''The inertial sensing system has accelerometer and gyroscope channels; only its shake/no-shake binary output is exposed. Zero means no shake was flagged, not proof of complete immobility; one means shake was flagged, not a measurement of intensity, posture, or gait cadence. Export spacing is 0.02 seconds (50 samples per second); this does not establish detector update frequency.
A binary_sequence string contains all samples in displayed order. fraction_ones is the number of ones divided by sample count. transition_count counts adjacent bit changes. max_zero_run_fraction and max_one_run_fraction are the longest contiguous run of that value divided by sample count; zero means that state is absent. Runs at interval boundaries may extend beyond the observation. Features are computed from the same permitted samples, with fractions rounded to four decimal places. Independent references are not consecutive parts of a session. Do not assume every displayed order preserves acquisition chronology.'''

def represent(bits,condition):
    if condition=='R':return {'binary_sequence':''.join(map(str,bits))}
    f,_=features(bits)
    return {k:int(f[k]) if k=='transition_count' else round(f[k],4) for k in (FIELDS[:1] if condition=='D' else FIELDS)}

def messages(refs,target,placement,extent='Every reference and target interval has 500 samples and a common duration of 10 seconds.'):
    return [{'role':'system','content':SYSTEM},{'role':'user','content':f'''Sensor placement: {placement}.
{DEFINITIONS}
{extent}
Candidate activities: {', '.join(CLASSES)}.
Labeled references from other participants:
{json.dumps(refs)}
Unlabeled target observation:
{json.dumps(target)}
Predict the activity of the target only. Return exactly predicted_activity (one candidate), confidence (number 0 to 1), and sufficient_information (boolean).'''}]

def shuffled(bits,source,start):
    seed=int(hashlib.sha256((source+':'+str(start)+':2026').encode()).hexdigest()[:8],16)
    rng=np.random.default_rng(seed);blocks=np.array(bits).reshape(10,50)
    for attempt in range(10000):
        permutation=rng.permutation(10);out=blocks[permutation].ravel().tolist()
        if len(set(bits))==1 or out!=bits:return out,seed,permutation.tolist()
    raise ValueError('Could not change varying order')

def prepare():
    assert not (DATA/'manifest.json').exists(),'Already frozen'
    DATA.mkdir(parents=True,exist_ok=True)
    preserved={str(p.relative_to(ROOT)):sha(p) for folder in ['data','runs','reports'] for p in (ROOT/folder).rglob('*') if p.is_file() and DATA not in p.parents and RUN not in p.parents}
    dump(DATA/'preservation.json',preserved)
    selection=json.loads((ROOT/'reports/next_inference_audit/proposed_pilot_selection.json').read_text())
    audit=json.loads((ROOT/'reports/stage2_audit/audit.json').read_text())['processed_records']
    audited={r['path']:r['sha256'] for r in audit};cache={};hashes={}
    def read(source):
        if source not in cache:
            p=SOURCE/source;assert sha(p)==audited[source]
            a,segs=read_binary(p);assert len(segs)==1
            cache[source]=a[:,1].astype(int).tolist();hashes[source]=sha(p)
        return cache[source]
    def interval(r):
        b=read(r['source'])[r['start']:r['start']+500];assert len(b)==500
        assert np.mean(b)==r['proportion']
        assert np.allclose(np.array(b).reshape(10,50).mean(axis=1),r['ordered'])
        return b
    refs=selection['references']+selection['additional_varying_references'];assert len(refs)==45
    refs=[dict(r,bits=interval(r)) for r in refs];assert all(r['subject']<=7 for r in refs)
    targets=[];jobs=[]
    for i,r in enumerate(selection['targets']):
        b=interval(r);bb,seed,perm=shuffled(b,r['source'],r['start'])
        # The earlier bin shuffle can be identical; deterministic rejection now ensures changed order.
        assert len(bb)==len(b) and sum(bb)==sum(b)
        assert not r['varying'] or bb!=b
        t=dict(r,id=f'p{i+1:02}',bits=b,disrupted_bits=bb,shuffle_seed=seed,block_permutation=perm,features=features(b)[0],disrupted_features=features(bb)[0]);targets.append(t)
        rr=[x for x in refs if x['placement']==r['placement']];assert len(rr)==9
        for c in ['R','D','T']+(['T-order'] if r['varying'] else []):
            rep='T' if c=='T-order' else c
            obs=represent(bb if c=='T-order' else b,rep)
            exported=[{'activity':x['activity'],**represent(x['bits'],rep)} for x in rr]
            msg=messages(exported,obs,r['placement'])
            assert 'User ' not in json.dumps(msg) and '.csv' not in json.dumps(msg)
            if c=='R':
                assert list(map(int,obs['binary_sequence']))==b
                assert all(list(map(int,x['binary_sequence']))==y['bits'] for x,y in zip(exported,rr))
            jobs.append({'id':t['id']+'-'+c,'target_id':t['id'],'condition':c,'messages':msg})
    assert len(targets)==15 and len(jobs)==50 and sum(t['varying'] for t in targets)==5
    # Freeze label-blind gate: training-only targets, no target labels exported or scored.
    gate=[];gate_sources=[]
    train1=sorted([r for r in audit if r['subject']==1],key=lambda r:r['path'])
    cases=[]
    for bit in [0,1]:
        r=next(r for r in train1 if len(read(r['path']))>=500 and all(x==bit for x in read(r['path'])))
        cases.append(r)
    for profile in ['short','fixed','full']:
        for bit,r in enumerate(cases):
            rr=[]; provenance=[]
            for c in CLASSES:
                q=next(q for q in sorted(audit,key=lambda z:z['path']) if 2<=q['subject']<=7 and q['placement']==r['placement'] and q['activity']==c and len(read(q['path']))>=500)
                rb=read(q['path']);rb=rb if profile=='full' else rb[:500 if profile=='fixed' else 100]
                rr.append({'activity':c,**represent(rb,'R')});provenance.append(q['path'])
            b=read(r['path']);b=b if profile=='full' else b[:500 if profile=='fixed' else 100]
            extent={'short':'Every reference and target has 100 samples covering 2 seconds.','fixed':'Every reference and target has 500 samples covering 10 seconds.','full':'Each reference and the target contains a complete chronological recording; recording lengths may differ.'}[profile]
            msg=messages(rr,represent(b,'R'),r['placement'],extent)
            for repeat in range(2):gate.append({'id':f'gate-{profile}-{bit}-{repeat}','profile':profile,'messages':msg})
            gate_sources.append({'profile':profile,'target_source':r['path'],'reference_sources':provenance,'target_samples':len(b)})
    provider=next(e for e in json.loads((DATA/'provider_metadata.json').read_text())['data']['endpoints'] if e['tag']=='deepinfra/fp8')
    assert {'structured_outputs','response_format','reasoning','temperature','max_tokens'}<=set(provider['supported_parameters'])
    from tokenizers import Tokenizer  # Optional: needed only when preparing token budgets.
    tok=Tokenizer.from_file(str(ROOT/'data/full-recording-audit/tokenizer.json'))
    for j in gate+jobs:
        j['local_content_tokens']=sum(len(tok.encode(m['content']).ids) for m in j['messages'])
        assert j['local_content_tokens']+2048+128<provider['context_length']
    # Counterbalanced R/D/T ordering, then controls interspersed by a frozen random permutation.
    rng=np.random.default_rng(20261111);base=[];order=rng.permutation(['R','D','T']).tolist()
    for position in range(3):
        for i,t in enumerate(targets):base.append(next(j for j in jobs if j['target_id']==t['id'] and j['condition']==order[(i+position)%3]))
    controls=[j for j in jobs if j['condition']=='T-order']
    for pos,j in zip(sorted(rng.choice(50,5,replace=False).tolist()),controls):base.insert(pos,j)
    assert len(base)==50 and len({j['id'] for j in base})==50
    write_lines(DATA/'requests.jsonl',base);write_lines(DATA/'technical_requests.jsonl',gate)
    dump(DATA/'truth.json',targets);dump(DATA/'references.json',refs);dump(DATA/'technical_provenance.json',gate_sources)
    settings={'model':'qwen/qwen3.5-35b-a3b','temperature':.1,'max_tokens':128,'reasoning':{'enabled':False},'response_format':RESPONSE_FORMAT,'provider':{'only':['deepinfra/fp8'],'allow_fallbacks':False,'require_parameters':True}}
    dump(DATA/'manifest.json',{'protocol':VERSION,'settings':settings,'provider':provider,'source_hashes':hashes,'selection_sha256':sha(ROOT/'reports/next_inference_audit/proposed_pilot_selection.json'),'requests_sha256':sha(DATA/'requests.jsonl'),'technical_requests_sha256':sha(DATA/'technical_requests.jsonl'),'request_count':50,'gate_count':12,'schedule_seed':20261111,'shuffle_rule':'Source/start SHA256 seed as previous panel; draw 10-block permutations until full bits differ, maximum 10000 draws; independent of labels and predictions.','no_retries':True,'gate_criteria':'12/12 strict valid, normal stop, pinned provider/model, plausible full-input usage. No activity scoring. Stop immediately on failure.','baseline_protocol':'Fixed bit: majority ones Walking else Sitting. Reference prior and duration-only (all lengths equal): most frequent reference class, ties CLASSES order. Nearest duty and nearest T: mean absolute difference with transition count divided by 499; tied neighbors vote divided by per-class reference support, tie CLASSES order. Same nine references per placement; no fitting on evaluation labels.','created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('Frozen',len(base),'research and',len(gate),'technical requests; token ranges',[(k,min(j['local_content_tokens'] for j in v),max(j['local_content_tokens'] for j in v)) for k,v in [('research',base),('gate',gate)]])

def request_one(j,m,key):
    r={**j,'settings':m['settings']};start=time.monotonic()
    try:
        response=requests.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':f'Bearer {key}'},json={**m['settings'],'messages':j['messages']},timeout=240)
        r['http_status']=response.status_code
        p=response.json();r['raw_response']=p
        if response.status_code!=200:r.update(status='api_error',error=f'HTTP {response.status_code}')
        else:
            ch=p['choices'][0];r.update(returned_provider=p.get('provider'),returned_model=p.get('model'),usage=p.get('usage'),finish_reason=ch.get('finish_reason'),raw_content=ch['message'].get('content'))
            try:r.update(prediction=validate_v2(r['raw_content']),status='valid')
            except (ValueError,TypeError,KeyError) as e:r.update(status='invalid_response',error=str(e))
    except (requests.RequestException,ValueError,KeyError,IndexError,TypeError) as e:r.update(status='api_error',error=type(e).__name__)
    r['seconds']=time.monotonic()-start
    n=(r.get('usage') or {}).get('prompt_tokens');delta=n-j['local_content_tokens'] if n is not None else None
    r['technical_valid']=r.get('http_status')==200 and r.get('returned_provider')=='DeepInfra' and r.get('returned_model')==m['settings']['model'] and r.get('finish_reason')=='stop' and delta is not None and 0<=delta<=2048 and n+128<m['provider']['context_length']
    return json.loads(json.dumps(r).replace(key,'[REDACTED]'))

def run(kind):
    m=json.loads((DATA/'manifest.json').read_text());name='technical_requests' if kind=='gate' else 'requests'
    assert sha(DATA/(name+'.jsonl'))==m[name+'_sha256']
    if kind=='research':
        assert json.loads((RUN/'gate_result.json').read_text())['passed']
        assert (DATA/'baseline_predictions.json').exists(),'Freeze conventional baselines first'
        gate=read_lines(RUN/'gate_responses.jsonl');expected=read_lines(DATA/'technical_requests.jsonl')
        assert len(gate)==len(expected)==12
        assert all(r['messages']==j['messages'] and r['settings']==m['settings'] and r['status']=='valid' and r['technical_valid'] for r,j in zip(gate,expected))
    RUN.mkdir(parents=True,exist_ok=True);out=RUN/(kind+'_responses.jsonl');assert not out.exists(),'No silent reruns or retries'
    load_dotenv(ROOT/'.env');key=os.environ['OPENROUTER_API_KEY'];rows=[]
    with out.open('w') as f:
        for j in read_lines(DATA/(name+'.jsonl')):
            r=request_one(j,m,key);rows.append(r);f.write(json.dumps(r)+'\n');f.flush()
            print(kind,len(rows),r['id'],r['status'],'technical',r['technical_valid'],'cost',(r.get('usage') or {}).get('cost'),flush=True)
            if not r['technical_valid'] or (kind=='gate' and r['status']!='valid'):break
    dump(RUN/(kind+'_result.json'),{'passed':len(rows)==(12 if kind=='gate' else 50) and all(r['technical_valid'] and r['status']=='valid' for r in rows),'calls':len(rows),'valid':sum(r['status']=='valid' for r in rows),'cost':sum((r.get('usage') or {}).get('cost',0) or 0 for r in rows),'label_blind':kind=='gate'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['metadata','prepare','gate','research']);a=p.parse_args()
    if a.command=='metadata':
        assert not (DATA/'manifest.json').exists(),'Do not overwrite frozen metadata'
        response=requests.get('https://openrouter.ai/api/v1/models/qwen/qwen3.5-35b-a3b/endpoints',timeout=40);response.raise_for_status()
        dump(DATA/'provider_metadata.json',response.json())
    elif a.command=='prepare':prepare()
    else:run(a.command)
