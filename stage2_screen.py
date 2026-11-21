"""Approved Stage 2 screen only: 14 matched targets x six conditions = 84 requests."""
import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from project_paths import dataset_path

import numpy as np
import requests
from dotenv import load_dotenv
from direct_llm import CLASSES, MOVING, classification, expected_guess, messages as stage1_messages, validate, read_lines, write_lines, dump

ROOT = Path(__file__).resolve().parent
CONDITIONS = ['C000', 'C010', 'C100', 'C001', 'C111', 'R0']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def templates():
    document = (ROOT/'reports/stage2_temporal_context_design.md').read_text()
    sections = {}
    for number in ['6.1','6.2','6.3','6.4','6.5']:
        section = document.split('### '+number+' ',1)[1].split('\n### ',1)[0]
        sections[number] = re.findall(r'```text\n(.*?)\n```',section,re.S)
    return {'system':sections['6.1'][0], 'user':sections['6.2'][0], 'sensor':sections['6.3'], 'history':sections['6.4'], 'auxiliary':sections['6.5']}


def render(condition, target, history, references, t):
    if len(target)!=100 or len(history)!=400 or any(type(b) is not int or b not in [0,1] for b in target+history):
        raise ValueError('Invalid matched binary observations')
    if condition=='R0':
        return stage1_messages(target)
    if condition not in CONDITIONS:
        raise ValueError('Only the approved screen conditions are allowed')
    temporal,sensor,aux=map(int,condition[1:])
    if any(set(r)!={'activity','binary_sequence'} for r in references):
        raise ValueError('Reference export contains unauthorized metadata')
    user=t['user'].format(SENSOR_BLOCK=t['sensor'][sensor], AUXILIARY_BLOCK=t['auxiliary'][aux].replace('{REFERENCE_JSON}',json.dumps(references)), HISTORY_BLOCK=t['history'][temporal].replace('{PRECEDING_400_BITS}',json.dumps(history)), TARGET_BITS=json.dumps(target))
    return [{'role':'system','content':t['system']},{'role':'user','content':user}]


def read_binary(path):
    a=np.loadtxt(path,delimiter=',',skiprows=1,usecols=(0,7),ndmin=2)
    if not len(a) or not np.isfinite(a).all() or not np.isin(a[:,1],[0,1]).all() or np.any(np.diff(a[:,0])<=0):
        raise ValueError(f'Invalid trace: {path}')
    cuts=np.flatnonzero(~np.isclose(np.diff(a[:,0]),20000,atol=1,rtol=0))+1
    return a,np.split(np.arange(len(a)),cuts)


def prepare(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    source=dataset_path()
    candidates=[];sources={}
    for subject in [8,9]:
        base=source/f'User {subject}'/'Processed'
        for path in sorted(base.glob('**/right-pocket*.csv')):
            a,segments=read_binary(path);label=path.relative_to(base).parts[0]
            if label not in CLASSES:raise ValueError('Unknown activity')
            sources[str(path.relative_to(source))]=sha(path)
            for segment in segments:
                for offset in range(0,len(segment)-499,500):
                    start=int(segment[offset]);bits=a[start:start+500,1].astype(int).tolist()
                    candidates.append({'id':f'target-{len(candidates):04d}','subject':subject,'activity':label,'recording':str(path.relative_to(source)),'block_start_sample':start,'target_start_sample':start+400,'history':bits[:400],'target':bits[400:]})
    if len(candidates)!=372:raise ValueError('Expected 372 matched candidates; inspect data before proceeding')
    rng=np.random.default_rng(42);chosen=[];seen=set()
    for i in rng.permutation(len(candidates)):
        r=candidates[i];pair=(r['subject'],r['activity'])
        if pair not in seen:seen.add(pair);chosen.append(r)
    if len(chosen)!=14:raise ValueError('Expected 14 subject/activity targets')
    refs=[];ref_provenance=[]
    for label in CLASSES:
        for path in sorted((source/'User 1'/'Processed'/label).glob('**/right-pocket*.csv')):
            a,segments=read_binary(path)
            if len(segments[0])>=100:
                refs.append({'activity':label,'binary_sequence':a[:100,1].astype(int).tolist()})
                ref_provenance.append({'activity':label,'source':str(path.relative_to(source)),'sha256':sha(path),'start_sample':0})
                break
        else:raise ValueError('No authorized reference')
    t=templates()
    # Freeze balanced rotation of conditions, then interleave by position across targets.
    permutation=np.random.default_rng(43).permutation(CONDITIONS).tolist()
    jobs=[]
    for position in range(6):
        for i,r in enumerate(chosen):
            condition=permutation[(position+i)%6]
            jobs.append({'id':r['id']+'-'+condition,'target_id':r['id'],'condition':condition,'messages':render(condition,r['target'],r['history'],refs,t)})
    write_lines(out/'requests.jsonl',jobs)
    write_lines(out/'truth.jsonl',[{k:v for k,v in r.items() if k not in ['history','target']} for r in chosen])
    write_lines(out/'selected_observations.jsonl',[{k:r[k] for k in ['id','history','target']} for r in chosen])
    dump(out/'references.json',refs)
    dump(out/'reference_provenance.json',ref_provenance)
    dump(out/'candidate_manifest.json',[{k:v for k,v in r.items() if k not in ['history','target']} for r in candidates])
    config=json.loads((ROOT/'configs/direct_llm.json').read_text())
    dump(out/'manifest.json',{'target_count':14,'request_count':84,'conditions':CONDITIONS,'selection_seed':42,'schedule_seed':43,'condition_rotation':permutation,'source_hashes':sources,'config':config,'templates':t,'design_sha256':sha(ROOT/'reports/stage2_temporal_context_design.md'),'requests_sha256':sha(out/'requests.jsonl'),'annotation_rubric':'Use reports/stage2_temporal_context_design.md section 9; annotate all valid explanations without true labels; explicit unique inference, intensity/rhythm/frequency, unprovided metadata, or no-shake=physical-immobility claims unsupported. Mere forced choice or qualified plausible prior is not itself an unsupported uniqueness claim.'})
    print('Prepared and froze 14 targets, 7 training references, 84 requests.')


def request_one(job,c,key):
    settings={k:c[k] for k in ['model','temperature','max_tokens']}
    settings.update(reasoning={'enabled':False},response_format={'type':'json_object'},provider={'require_parameters':True})
    record={**job,'settings':settings};start=time.monotonic()
    try:
        response=requests.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':f'Bearer {key}'},json={**settings,'messages':job['messages']},timeout=c['timeout_seconds'])
        record['http_status']=response.status_code
        if response.status_code!=200:
            record.update(status='api_error',error=f'HTTP {response.status_code}')
        else:
            payload=response.json();choice=payload['choices'][0]
            record.update(api_id=payload.get('id'),returned_model=payload.get('model'),returned_provider=payload.get('provider'),usage=payload.get('usage'),finish_reason=choice.get('finish_reason'),raw_content=choice['message'].get('content'))
            try:record.update(prediction=validate(record['raw_content']),status='valid')
            except (TypeError,ValueError,KeyError):record.update(status='invalid_response',error='Strict JSON/schema validation failed')
    except (requests.RequestException,ValueError,KeyError,IndexError,TypeError) as exc:
        record.update(status='api_error',error=type(exc).__name__)
    record['seconds']=time.monotonic()-start
    return json.loads(json.dumps(record).replace(key,'[REDACTED]'))


def infer(data,out,resume=False):
    data,out=Path(data),Path(out)
    meta=json.loads((data/'manifest.json').read_text());jobs=read_lines(data/'requests.jsonl')
    if len(jobs)!=84 or len({j['id'] for j in jobs})!=84 or sha(data/'requests.jsonl')!=meta['requests_sha256']:
        raise ValueError('Approved request manifest mismatch')
    runmeta={'manifest_sha256':sha(data/'manifest.json'),'requests_sha256':sha(data/'requests.jsonl'),'config':meta['config']}
    if resume:
        if json.loads((out/'run.json').read_text())!=runmeta:raise ValueError('Resume mismatch')
    else:out.mkdir(parents=True,exist_ok=False);dump(out/'run.json',runmeta)
    previous=read_lines(out/'responses.jsonl') if (out/'responses.jsonl').exists() else []
    done={r['id'] for r in previous}
    load_dotenv(ROOT/'.env');key=os.environ.get('OPENROUTER_API_KEY')
    if not key:raise ValueError('Missing key')
    iterator=iter(j for j in jobs if j['id'] not in done);stopped=False;count=len(done)
    with ThreadPoolExecutor(max_workers=meta['config']['concurrency']) as pool:
        active=set()
        def schedule():
            job=next(iterator,None)
            if job is not None:active.add(pool.submit(request_one,job,meta['config'],key))
        for _ in range(meta['config']['concurrency']):schedule()
        with (out/'responses.jsonl').open('a') as log:
            while active:
                finished,active=wait(active,return_when=FIRST_COMPLETED)
                for future in finished:
                    result=future.result();log.write(json.dumps(result)+'\n');log.flush();count+=1
                    if result.get('http_status') in [401,402,403]:stopped=True
                    if count%12==0 or count==84:print(f'Completed {count}/84',flush=True)
                if not stopped:
                    for _ in finished:schedule()
    print('Screen inference stopped/completed. No labels loaded; no automatic expansion or retries.')


def evaluate(data,out):
    data,out=Path(data),Path(out)
    jobs=read_lines(data/'requests.jsonl');truth={r['id']:r for r in read_lines(data/'truth.jsonl')}
    rows=read_lines(out/'responses.jsonl');responses={r['id']:r for r in rows}
    if len(rows)!=len(responses):raise ValueError('Duplicate response')
    if sha(data/'requests.jsonl')!=json.loads((out/'run.json').read_text())['requests_sha256']:raise ValueError('Input mismatch')
    obs={r['id']:r for r in read_lines(data/'selected_observations.jsonl')}
    refs=json.loads((data/'references.json').read_text())
    with np.load(ROOT/'data/pilot/train.npz') as d:counts=np.bincount(d['y'],minlength=7)
    targets=list(truth);y=[truth[t]['activity'] for t in targets];majority=CLASSES[int(counts.argmax())]
    result={'target_count':len(targets),'request_count':len(jobs),'conditions':{},'contrasts':{}}
    predictions={}
    for condition in CONDITIONS:
        rs=[responses.get(t+'-'+condition,{'status':'missing'}) for t in targets]
        pred=[r.get('prediction',{}).get('predicted_activity','INVALID') for r in rs];predictions[condition]=pred
        valid=[i for i,r in enumerate(rs) if r['status']=='valid'];details=[rs[i]['prediction'] for i in valid]
        groups=defaultdict(list)
        for i,t in enumerate(targets):
            prompt=next(j['messages'] for j in jobs if j['id']==t+'-'+condition)
            groups[hashlib.sha256(json.dumps(prompt,sort_keys=True).encode()).hexdigest()].append(i)
        diag=[]
        for signature,ix in groups.items():
            lc=Counter(y[i] for i in ix);pc=Counter(pred[i] for i in ix)
            diag.append({'prompt_sha256':signature,'n':len(ix),'truth_counts':dict(lc),'prediction_counts':dict(pc),'inconsistent':len({pred[i] for i in ix if pred[i] in CLASSES})>1,'accuracy':sum(y[i]==pred[i] for i in ix)/len(ix)})
        def mean(values):return float(np.mean(values)) if values else None
        c={**classification(y,pred),'status_counts':dict(Counter(r['status'] for r in rs)),'mean_confidence':mean([d['confidence'] for d in details]),'confidence_correct':mean([rs[i]['prediction']['confidence'] for i in valid if pred[i]==y[i]]),'confidence_wrong':mean([rs[i]['prediction']['confidence'] for i in valid if pred[i]!=y[i]]),'insufficient_fraction':mean([not d['sufficient_information'] for d in details]),'high_confidence_wrong':sum(rs[i]['prediction']['confidence']>=.8 and pred[i]!=y[i] for i in valid),'alternative_coverage':mean([y[i] in rs[i]['prediction']['alternative_activities'] for i in valid]),'prediction_counts':dict(Counter(pred)),'identical_inputs':diag,'pattern_bound':sum(max(d['truth_counts'].values()) for d in diag)/len(y),'by_subject':{},'by_recording':{},'usage':{'total_tokens':sum((r.get('usage') or {}).get('total_tokens',0) or 0 for r in rs),'reported_cost_usd':sum((r.get('usage') or {}).get('cost',0) or 0 for r in rs)}}
        for field in ['subject','recording']:
            for value in sorted({truth[t][field] for t in targets}):
                ix=[i for i,t in enumerate(targets) if truth[t][field]==value]
                c['by_'+field][str(value)]=classification([y[i] for i in ix],[pred[i] for i in ix])
        c['valid_only']=classification([y[i] for i in valid],[pred[i] for i in valid]) if valid else None
        c['valid_only_fixed_rule']=classification([y[i] for i in valid],['Walking' if sum(obs[targets[i]]['target'])>50 else 'Sitting' for i in valid]) if valid else None
        c['mean_recording_accuracy']=float(np.mean([v['accuracy'] for v in c['by_recording'].values()]))
        result['conditions'][condition]=c
    for condition in ['C010','C100','C001','C111','R0']:
        a,b=predictions['C000'],predictions[condition]
        result['contrasts'][condition+'-C000']={'prediction_changes':sum(x!=z for x,z in zip(a,b)),'wrong_to_correct':sum(x!=label and z==label for x,z,label in zip(a,b,y)),'correct_to_wrong':sum(x==label and z!=label for x,z,label in zip(a,b,y)),'accuracy_difference':result['conditions'][condition]['accuracy']-result['conditions']['C000']['accuracy']}
    result['valid_pair_contrasts']={}
    for condition in ['C010','C100','C001','C111','R0']:
        indexes=[i for i in range(len(y)) if predictions['C000'][i] in CLASSES and predictions[condition][i] in CLASSES]
        result['valid_pair_contrasts'][condition+'-C000']={'n':len(indexes),'baseline':classification([y[i] for i in indexes],[predictions['C000'][i] for i in indexes]),'condition':classification([y[i] for i in indexes],[predictions[condition][i] for i in indexes])}
    rule=['Walking' if sum(obs[t]['target'])>50 else 'Sitting' for t in targets]
    refpred=[]
    for t in targets:
        matched=[r['activity'] for r in refs if r['binary_sequence']==obs[t]['target']]
        refpred.append(matched[0] if matched else majority)
    result['baselines']={'training_majority':classification(y,[majority]*len(y)),'fixed_rule':classification(y,rule),'reference_rule':classification(y,refpred),'uniform_guess':expected_guess(y,[1/7]*7),'training_prior_guess':expected_guess(y,counts/counts.sum())}
    dump(out/'evaluation.json',result)
    # Review sheet deliberately omits truth, subject, recording and correctness.
    if not (out/'explanation_review.jsonl').exists():
        write_lines(out/'explanation_review.jsonl',[{'id':r['id'],'condition':r['condition'],'predicted_activity':r.get('prediction',{}).get('predicted_activity'),'explanation':r.get('prediction',{}).get('explanation'),'status':r['status'],'unsupported':None,'categories':[],'note':''} for r in sorted(rows,key=lambda r:r['id'])])
    for name,c in result['conditions'].items():print(name,{k:c[k] for k in ['accuracy','macro_f1','moving_stationary_accuracy','mean_confidence','insufficient_fraction','status_counts']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','infer','evaluate'])
    p.add_argument('--data',default=str(ROOT/'data/stage2-screen'));p.add_argument('--run',default=str(ROOT/'runs/stage2-screen'));p.add_argument('--resume',action='store_true');a=p.parse_args()
    if a.command=='prepare':prepare(a.data)
    elif a.command=='infer':infer(a.data,a.run,a.resume)
    else:evaluate(a.data,a.run)
