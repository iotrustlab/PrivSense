"""Frozen cross-user auxiliary-data screen; no training or feedback."""
import json, os, time, hashlib, argparse
from pathlib import Path
from project_paths import dataset_path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from dotenv import load_dotenv
from stage2_screen import ROOT, sha, read_binary, request_one
from direct_llm import CLASSES, read_lines, write_lines, dump, classification, expected_guess

DATA=ROOT/'data/e3-screen'
RUN=ROOT/'runs/e3-screen'
LEVELS=[0,1,5,10,20]
SYSTEM='''You are a privacy attacker evaluating whether restricted sensor outputs reveal sensitive human activities.

You have access to binary observations from an inertial sensing system and may receive labeled observations from other participants as auxiliary knowledge.

Your objective is to infer the hidden activity of a target participant.

Use only the supplied observations, sensor information, and authorized labeled references.

You do not have access to the target participant's true activity label or raw sensor measurements.

Do not invent motion measurements or claim that identical binary patterns uniquely identify different activities.

If multiple activities are consistent with the observations, acknowledge that uncertainty.'''
USER='''You are observing a sensor-based ML system.

Sensor information
- Sensor: IMU with accelerometer and gyroscope channels.
- Placement: Right pocket.
- Export sampling interval: 0.02 seconds.
- Exposed output: Binary shake/no-shake detector.
- 0 = no shake detected.
- 1 = shake detected.
The detector output is not a direct seven-class activity label.
The export interval does not specify the detector's internal decision frequency. Detector thresholds and internals are not supplied.

Auxiliary observations from other users
The following labeled examples come from separate training participants:
{references}
These examples may contain identical binary patterns associated with different activities. They are separate observations, not a chronological continuation of one another or of the target.

Temporal history of the target
The following binary observations immediately precede the target interval within the same uninterrupted recording:
{history}

Target binary observations
{target}

Possible private activities
Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.

Based on the sensor information, auxiliary examples, and observed binary sequence:
1. What is the most likely activity during the target interval?
2. Which observations support your prediction?
3. Which alternative activities are plausible?
4. Can the available information reliably distinguish the predicted activity from those alternatives?

Return only a JSON object with exactly these fields:
- predicted_activity: exactly one of the seven activity names
- confidence: a number between 0 and 1 for the exact activity
- alternative_activities: a list of distinct other candidate activity names
- explanation: a brief explanation grounded in the observations
- sufficient_information: a boolean
Do not invent information that is not observable.'''

def render(obs,refs):
    assert len(obs['target'])==100 and len(obs['history'])==400
    assert all(set(r)=={'activity','binary_sequence'} and len(r['binary_sequence'])==100 for r in refs)
    return [{'role':'system','content':SYSTEM},{'role':'user','content':USER.format(references=json.dumps(refs),history=json.dumps(obs['history']),target=json.dumps(obs['target']))}]

def prepare():
    DATA.mkdir(exist_ok=False,parents=True)
    source=dataset_path(); old=ROOT/'data/stage2-screen'
    preserved={str(p.relative_to(ROOT)):sha(p) for folder in ['data/direct-stage1','runs/direct-stage1-full','data/stage2-screen','runs/stage2-screen'] for p in (ROOT/folder).rglob('*') if p.is_file()}
    for name in ['direct_llm.py','stage2_screen.py','direct_report.py','stage2_report.py']:
        preserved[name]=sha(ROOT/name)
    dump(DATA/'preservation.json',preserved)
    refs1=json.loads((old/'references.json').read_text());prov1=json.loads((old/'reference_provenance.json').read_text())
    ranked={}; provenance={}
    for label in CLASSES:
        first=prov1[CLASSES.index(label)]; pool=[]
        for subject in range(1,8):
            for path in sorted((source/f'User {subject}'/'Processed'/label).glob('**/right-pocket*.csv')):
                a,segments=read_binary(path)
                for segment in segments:
                    for offset in range(0,len(segment)-99,100):
                        start=int(segment[offset]); rel=str(path.relative_to(source))
                        if rel==first['source'] and start==first['start_sample']:continue
                        pool.append({'subject':subject,'source':rel,'start_sample':start,'binary_sequence':a[start:start+100,1].astype(int).tolist()})
        selected=[{'subject':1,**first,'binary_sequence':refs1[CLASSES.index(label)]['binary_sequence']}]
        # Least-used subject, then least-used recording, then earliest location; no bit-value selection.
        while len(selected)<20:
            sc=Counter(x['subject'] for x in selected);fc=Counter(x['source'] for x in selected)
            pick=min(pool,key=lambda x:(sc[x['subject']],fc[x['source']],x['subject'],x['source'],x['start_sample']))
            pool.remove(pick);selected.append(pick)
        ranked[label]=[{'activity':label,'binary_sequence':x['binary_sequence']} for x in selected]
        provenance[label]=[{k:v for k,v in x.items() if k!='binary_sequence'}|{'sha256':sha(source/x['source'])} for x in selected]
    levels={str(k):[ranked[c][i] for i in range(k) for c in CLASSES] for k in LEVELS}
    assert levels['1']==refs1
    obs=read_lines(old/'selected_observations.jsonl');truth=read_lines(old/'truth.jsonl')
    conditions=[f'E3-K{k}' for k in LEVELS]+['E2-bridge']
    bridge={j['target_id']:j['messages'] for j in read_lines(old/'requests.jsonl') if j['condition']=='C111'}
    rotation=np.random.default_rng(44).permutation(conditions).tolist(); jobs=[]
    for position in range(len(conditions)):
        for i,o in enumerate(obs):
            c=rotation[(position+i)%len(conditions)]
            msg=bridge[o['id']] if c=='E2-bridge' else render(o,levels[c.split('K')[1]])
            jobs.append({'id':o['id']+'-'+c,'target_id':o['id'],'condition':c,'messages':msg})
    # Predeclared inexpensive order sensitivity control: one fixed target per bit pattern, K20 reversed.
    seen=set()
    for o in obs:
        pattern=tuple(o['target'])
        if pattern in seen:continue
        seen.add(pattern);c='E3-K20-reversed'
        jobs.append({'id':o['id']+'-'+c,'target_id':o['id'],'condition':c,'messages':render(o,list(reversed(levels['20'])))})
    write_lines(DATA/'requests.jsonl',jobs);write_lines(DATA/'truth.jsonl',truth);write_lines(DATA/'selected_observations.jsonl',obs)
    dump(DATA/'references.json',levels);dump(DATA/'reference_provenance.json',provenance)
    dump(DATA/'templates.json',{'system':SYSTEM,'user':USER})
    diversity={}
    for k,rs in levels.items():
        groups=defaultdict(Counter)
        for r in rs:groups[''.join(map(str,r['binary_sequence']))][r['activity']]+=1
        diversity[k]={'n':len(rs),'unique_sequences':len(groups),'patterns':{p:dict(v) for p,v in groups.items()},'subjects':sorted({x['subject'] for c in CLASSES for x in provenance[c][:int(k)]})}
    dump(DATA/'diversity.json',diversity)
    meta=json.loads((ROOT/'reports/e3_model_metadata.json').read_text())
    largest=max(sum(len(m['content'].encode()) for m in j['messages']) for j in jobs)
    assert largest+600+1000<meta['context_length'] # conservative byte upper bound plus framing reserve
    dump(DATA/'manifest.json',{'config':json.loads((ROOT/'configs/direct_llm.json').read_text()),'conditions':conditions,'request_count':len(jobs),'requests_sha256':sha(DATA/'requests.jsonl'),'schedule_seed':44,'model_metadata':meta,'max_prompt_bytes':largest,'context_preflight':'UTF-8 bytes + 1600 reserve below model context; actual provider tokens checked before K20 remainder','selection':'K1 exact E2; repeatedly minimize (subject usage, recording usage, subject, path, start); rank-major/class-order presentation; nested prefixes','controls':'14 exact E2 bridge; 2 reversed K20 requests with same examples and matched targets. Order and formatting control only; no claim to isolate length from knowledge. No retries.'})
    print('Prepared',len(jobs),'requests; max bytes',largest,'diversity',[(k,v['unique_sequences']) for k,v in diversity.items()])

def infer():
    meta=json.loads((DATA/'manifest.json').read_text());assert sha(DATA/'requests.jsonl')==meta['requests_sha256']
    RUN.mkdir(exist_ok=False,parents=True);dump(RUN/'run.json',{'manifest_sha256':sha(DATA/'manifest.json'),'started':time.time()})
    load_dotenv(ROOT/'.env');key=os.environ['OPENROUTER_API_KEY'];jobs=read_lines(DATA/'requests.jsonl')
    # First K20 is part of the planned screen, not an additional probe.
    probe=next(j for j in jobs if j['condition']=='E3-K20');remaining=[j for j in jobs if j['id']!=probe['id']]
    start=time.time()
    with (RUN/'responses.jsonl').open('w') as log:
        def save(r):log.write(json.dumps(r)+'\n');log.flush()
        r=request_one(probe,meta['config'],key);save(r)
        tokens=(r.get('usage') or {}).get('prompt_tokens')
        print('K20 preflight:',r['status'],'prompt tokens',tokens,flush=True)
        if r.get('http_status')!=200 or tokens is None or tokens+600>=meta['model_metadata']['context_length']:
            raise RuntimeError('K20 preflight failed; recorded response preserved; no further calls')
        with ThreadPoolExecutor(max_workers=4) as pool:
            for offset in range(0,len(remaining),4):
                batch=list(pool.map(lambda j:request_one(j,meta['config'],key),remaining[offset:offset+4]))
                for r in batch:save(r)
                print('Completed',min(offset+5,len(jobs)),'/',len(jobs),flush=True)
                if any(r.get('http_status') in [401,402,403] for r in batch):break
    dump(RUN/'runtime.json',{'wall_seconds':time.time()-start,'ended':time.time()})

def evaluate():
    jobs=read_lines(DATA/'requests.jsonl');rows=read_lines(RUN/'responses.jsonl');response={r['id']:r for r in rows}
    assert len(rows)==len(response) and set(response)<=set(j['id'] for j in jobs)
    assert sha(DATA/'manifest.json')==json.loads((RUN/'run.json').read_text())['manifest_sha256']
    assert sha(DATA/'requests.jsonl')==json.loads((DATA/'manifest.json').read_text())['requests_sha256']
    truth={r['id']:r for r in read_lines(DATA/'truth.jsonl')};obs={r['id']:r for r in read_lines(DATA/'selected_observations.jsonl')};refs=json.loads((DATA/'references.json').read_text())
    with np.load(ROOT/'data/pilot/train.npz') as d:counts=np.bincount(d['y'],minlength=7)
    majority=CLASSES[int(counts.argmax())];result={'conditions':{},'contrasts':{},'total_calls':len(rows)};predictions={}
    for c in [f'E3-K{k}' for k in LEVELS]+['E2-bridge','E3-K20-reversed']:
        selected=[j for j in jobs if j['condition']==c];ts=[j['target_id'] for j in selected];rs=[response.get(j['id'],{'status':'missing'}) for j in selected]
        y=[truth[t]['activity'] for t in ts];p=[r.get('prediction',{}).get('predicted_activity','INVALID') for r in rs];valid=[i for i,r in enumerate(rs) if r['status']=='valid']
        predictions[c]=dict(zip(ts,p));mean=lambda a:float(np.mean(a)) if a else None
        rr=refs['1' if c=='E2-bridge' else c.split('K')[1].split('-')[0]]
        if c.endswith('reversed'):rr=list(reversed(rr))
        refpred=[]
        for t in ts:
            matches=[r['activity'] for r in rr if r['binary_sequence']==obs[t]['target']]
            refpred.append(Counter(matches).most_common(1)[0][0] if matches else majority)
        groups=defaultdict(Counter)
        for j,label in zip(selected,y):groups[hashlib.sha256(json.dumps(j['messages']).encode()).hexdigest()][label]+=1
        result['conditions'][c]={**classification(y,p),'status_counts':dict(Counter(r['status'] for r in rs)),'prediction_counts':dict(Counter(p)),'mean_confidence':mean([rs[i]['prediction']['confidence'] for i in valid]),'confidence_correct':mean([rs[i]['prediction']['confidence'] for i in valid if p[i]==y[i]]),'confidence_wrong':mean([rs[i]['prediction']['confidence'] for i in valid if p[i]!=y[i]]),'high_confidence_errors':sum(rs[i]['prediction']['confidence']>=.8 and p[i]!=y[i] for i in valid),'insufficient_fraction':mean([not rs[i]['prediction']['sufficient_information'] for i in valid]),'valid_only':classification([y[i] for i in valid],[p[i] for i in valid]) if valid else None,'valid_only_reference_baseline':classification([y[i] for i in valid],[refpred[i] for i in valid]) if valid else None,'unique_target_inputs':len(groups),'pattern_bound':sum(max(g.values()) for g in groups.values())/len(y),'reference_baseline':classification(y,refpred),'fixed_baseline':classification(y,['Walking' if sum(obs[t]['target'])>50 else 'Sitting' for t in ts]),'majority_baseline':classification(y,[majority]*len(y)),'uniform_baseline':expected_guess(y,[1/7]*7),'prior_baseline':expected_guess(y,counts/counts.sum()),'by_subject':{str(s):classification([y[i] for i,t in enumerate(ts) if truth[t]['subject']==s],[p[i] for i,t in enumerate(ts) if truth[t]['subject']==s]) for s in sorted({truth[t]['subject'] for t in ts})},'usage':{key:sum((r.get('usage') or {}).get(key,0) or 0 for r in rs) for key in ['prompt_tokens','completion_tokens','total_tokens','cost']}}
    for c,ps in predictions.items():
        base=predictions['E3-K0'];common=list(ps)
        result['contrasts'][c]={'changes':sum(ps[t]!=base[t] for t in common),'wrong_to_correct':sum(ps[t]==truth[t]['activity'] and base[t]!=truth[t]['activity'] for t in common),'correct_to_wrong':sum(ps[t]!=truth[t]['activity'] and base[t]==truth[t]['activity'] for t in common)}
    result['matched_valid_contrasts']={}
    for c,ps in predictions.items():
        ts=[t for t in ps if ps[t] in CLASSES and predictions['E3-K0'][t] in CLASSES]
        result['matched_valid_contrasts'][c]={'n':len(ts),'K0':classification([truth[t]['activity'] for t in ts],[predictions['E3-K0'][t] for t in ts]),'condition':classification([truth[t]['activity'] for t in ts],[ps[t] for t in ts])} if ts else None
    result['pattern_prediction_counts']={}
    for c,ps in predictions.items():
        result['pattern_prediction_counts'][c]={}
        for bit in [0,1]:
            ts=[t for t in ps if obs[t]['target'][0]==bit]
            result['pattern_prediction_counts'][c][str(bit)]=dict(Counter(ps[t] for t in ts))
    result['order_control']=[{'target_id':t,'normal':predictions['E3-K20'][t],'reversed':p} for t,p in predictions.get('E3-K20-reversed',{}).items()]
    dump(RUN/'evaluation.json',result)
    if not (RUN/'explanation_review.jsonl').exists():write_lines(RUN/'explanation_review.jsonl',[{'id':r['id'],'condition':r['condition'],'explanation':r.get('prediction',{}).get('explanation'),'status':r['status'],'unsupported':None,'notes':''} for r in rows])
    for c,v in result['conditions'].items():print(c,v['accuracy'],v['status_counts'],v['prediction_counts'],v['mean_confidence'])
    protected=json.loads((DATA/'preservation.json').read_text());assert all(sha(ROOT/p)==h for p,h in protected.items())
    print('Prior artifacts preserved:',len(protected))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','infer','evaluate']);a=p.parse_args();globals()[a.command]()
