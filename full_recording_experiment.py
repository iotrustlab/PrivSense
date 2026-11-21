"""Execute only the frozen 14-recording C1–C5 direct-inference pilot."""
import argparse,json,os,time,hashlib
from pathlib import Path
from project_paths import dataset_path
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import requests
from dotenv import load_dotenv
from direct_llm import CLASSES,classification,validate,read_lines,write_lines,dump
from stage2_screen import ROOT,sha,read_binary
DATA=ROOT/'data/full-recording-screen';RUN=ROOT/'runs/full-recording-screen';FROZEN=ROOT/'data/full-recording-audit'
CONDITIONS=['C1','C2','C3','C4','C5']

def unpack(messages):
    text=messages[1]['content'];dec=json.JSONDecoder()
    refs=dec.raw_decode(text.split('Labeled references from other participants:\n')[1])[0]
    target=dec.raw_decode(text.split('Unlabeled target observation:\n')[1])[0]
    return refs,target

def prepare():
    if (DATA/'manifest.json').exists():raise ValueError('Already frozen')
    protected={str(p.relative_to(ROOT)):sha(p) for directory in ['runs','data/direct-stage1','data/stage2-screen','data/e3-screen','data/full-recording-audit','reports'] for p in (ROOT/directory).rglob('*') if p.is_file()}
    for name in ['direct_llm.py','stage2_screen.py','e3_experiment.py']:protected[name]=sha(ROOT/name)
    dump(DATA/'preservation.json',protected)
    selections=json.loads((ROOT/'reports/full_recording_audit/proposed_selections.json').read_text());targets=selections['targets'];refs=selections['references']
    source=dataset_path();bits={};hashes={}
    for r in refs+targets:
        path=source/r['source'];a,segments=read_binary(path);assert len(segments)==1
        bits[r['source']]=a[:,1].astype(int).tolist();hashes[r['source']]=sha(path)
        assert len(bits[r['source']])==r['samples']
        if 'sha256' in r:assert sha(path)==r['sha256']
    audited={r['source']:r['sha256'] for r in json.loads((ROOT/'reports/full_recording_audit/recordings.json').read_text())}
    assert all(h==audited[p] for p,h in hashes.items())
    raw=[j for j in read_lines(FROZEN/'proposed_prompts.jsonl') if j['id'].endswith('-string')]+read_lines(FROZEN/'proposed_controls.jsonl')
    provider=next(e for e in json.loads((DATA/'provider_metadata.json').read_text())['data']['endpoints'] if e['tag']=='deepinfra/fp8')
    assert all(p in provider['supported_parameters'] for p in ['reasoning','response_format','max_tokens','temperature'])
    from tokenizers import Tokenizer  # Optional: needed only when preparing token budgets.
    tok=Tokenizer.from_file(str(FROZEN/'tokenizer.json'));jobs=[]
    for r in targets:
        for c in CONDITIONS:
            j=next(j for j in raw if j['id']==r['id']+'-'+c+'-string');rr,tt=unpack(j['messages'])
            assert set(tt)=={'observation_extent','binary_sequence'} and len(rr)==7
            expected=bits[r['source']]
            if c in ['C1','C2']:expected=expected[r['short_start']:r['short_start']+100]
            elif c=='C5':expected=expected[:500]
            assert list(map(int,tt['binary_sequence']))==expected
            assert tt['observation_extent']==('complete recording' if c in ['C3','C4'] else 'contiguous excerpt')
            for exported,ref in zip(rr,refs):
                assert set(exported)=={'activity','observation_extent','binary_sequence'}
                assert exported['activity']==ref['activity'] and ref['subject']<8
                expectedref=bits[ref['source']] if c in ['C2','C4','C5'] else bits[ref['source']][:100]
                assert list(map(int,exported['binary_sequence']))==expectedref
            assert all(set(x['binary_sequence'])<=set('01') for x in rr+[tt])
            text=json.dumps(j['messages']);assert '.csv' not in text and r['id'] not in text and 'User 8' not in text and 'User 9' not in text
            n=sum(len(tok.encode(m['content']).ids) for m in j['messages'])
            assert n+1624<provider['context_length'] and n+1024<(provider.get('max_prompt_tokens') or provider['context_length'])
            jobs.append({'id':r['id']+'-'+c,'target_id':r['id'],'condition':c,'messages':j['messages'],'local_content_tokens':n})
    order=np.random.default_rng(47).permutation(CONDITIONS).tolist()
    schedule=[next(j for j in jobs if j['target_id']==r['id'] and j['condition']==order[(i+position)%5]) for position in range(5) for i,r in enumerate(targets)]
    probe=next(j for j in schedule if j['condition']=='C4');schedule=[probe]+[j for j in schedule if j['id']!=probe['id']]
    settings={'model':'qwen/qwen3.5-35b-a3b','temperature':.1,'max_tokens':600,'reasoning':{'enabled':False},'response_format':{'type':'json_object'},'provider':{'only':['deepinfra/fp8'],'allow_fallbacks':False,'require_parameters':True}}
    write_lines(DATA/'requests.jsonl',schedule);dump(DATA/'truth.json',targets);dump(DATA/'references.json',refs)
    dump(DATA/'manifest.json',{'settings':settings,'request_count':70,'schedule_seed':47,'probe_id':probe['id'],'requests_sha256':sha(DATA/'requests.jsonl'),'source_hashes':hashes,'provider':provider,'baseline_protocol':'Same seven exposed reference observations: nearest observed length, tie class-list order; binary+length restricts to same majority bit then nearest length. Fixed rule ones-majority Walking else Sitting. Additional full-training nearest-length/bit-length diagnostic uses 147 training files only, tie source path. No tuning.','preflight':'All decoded bits match source, all objects allowlisted, budget content+1024 framing+600 output checked','timeout_seconds':180,'concurrency':2,'repeat_count':1,'retry_policy':'No automatic retries; first invalid/technical failure stops before remainder; later schema failures scored and retained; provider/input mismatch or HTTP error stops further batches.'})
    print('Frozen 70 verified requests; first',probe['id'],'max content',max(j['local_content_tokens'] for j in jobs))

def request_one(job,settings,key):
    r={**job,'settings':settings};start=time.monotonic()
    try:
        response=requests.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':f'Bearer {key}'},json={**settings,'messages':job['messages']},timeout=180)
        r['http_status']=response.status_code
        if response.status_code!=200:r.update(status='api_error',error=f'HTTP {response.status_code}')
        else:
            p=response.json();ch=p['choices'][0]
            r.update(api_id=p.get('id'),returned_model=p.get('model'),returned_provider=p.get('provider'),usage=p.get('usage'),finish_reason=ch.get('finish_reason'),raw_content=ch['message'].get('content'))
            try:r.update(prediction=validate(r['raw_content']),status='valid')
            except (ValueError,TypeError,KeyError):r.update(status='invalid_response',error='Strict JSON/schema failure')
    except (requests.RequestException,ValueError,TypeError,KeyError,IndexError) as e:r.update(status='api_error',error=type(e).__name__)
    r['seconds']=time.monotonic()-start
    return json.loads(json.dumps(r).replace(key,'[REDACTED]'))

def technical(r,meta):
    n=(r.get('usage') or {}).get('prompt_tokens');delta=n-r['local_content_tokens'] if n is not None else None
    return r.get('http_status')==200 and r.get('returned_provider')=='DeepInfra' and r.get('returned_model')==meta['settings']['model'] and delta is not None and 0<=delta<=1024 and n+600<meta['provider']['context_length']

def infer():
    m=json.loads((DATA/'manifest.json').read_text());assert sha(DATA/'requests.jsonl')==m['requests_sha256']
    jobs=read_lines(DATA/'requests.jsonl');assert len(jobs)==70
    RUN.mkdir(exist_ok=False,parents=True);dump(RUN/'run.json',{'manifest_sha256':sha(DATA/'manifest.json'),'started':time.time()})
    load_dotenv(ROOT/'.env');key=os.environ['OPENROUTER_API_KEY'];start=time.monotonic()
    with (RUN/'responses.jsonl').open('w') as f:
        def save(r):f.write(json.dumps(r)+'\n');f.flush()
        r=request_one(jobs[0],m['settings'],key);save(r)
        ok=technical(r,m) and r['status']=='valid' and r.get('finish_reason')=='stop'
        dump(RUN/'preflight.json',{'id':r['id'],'passed':ok,'status':r['status'],'provider':r.get('returned_provider'),'usage':r.get('usage'),'local_content_tokens':r['local_content_tokens'],'note':'Usage agreement supports complete submission; provider-internal attention/truncation cannot be directly observed.'})
        print('First C4:',r['status'],r.get('returned_provider'),r.get('usage'),'passed',ok,flush=True)
        if not ok:return
        with ThreadPoolExecutor(max_workers=2) as pool:
            for offset in range(1,70,2):
                batch=list(pool.map(lambda j:request_one(j,m['settings'],key),jobs[offset:offset+2]))
                for r in batch:save(r)
                print('Completed',min(offset+2,70),'/70',flush=True)
                if any(not technical(r,m) for r in batch):print('Stopped on technical failure',flush=True);break
    dump(RUN/'runtime.json',{'wall_seconds':time.monotonic()-start})

def evaluate():
    rows=read_lines(RUN/'responses.jsonl');response={r['id']:r for r in rows};jobs=read_lines(DATA/'requests.jsonl');truth=json.loads((DATA/'truth.json').read_text());ts={t['id']:t for t in truth};m=json.loads((DATA/'manifest.json').read_text())
    assert len(rows)==len(response) and set(response)<=set(j['id'] for j in jobs)
    assert sha(DATA/'requests.jsonl')==m['requests_sha256'] and sha(DATA/'manifest.json')==json.loads((RUN/'run.json').read_text())['manifest_sha256']
    out={'conditions':{},'contrasts':{},'calls':len(rows)};preds={}
    source_records=json.loads((ROOT/'reports/full_recording_audit/recordings.json').read_text());training=[r for r in source_records if r['split']=='train']
    for c in CONDITIONS:
        js=[next(j for j in jobs if j['condition']==c and j['target_id']==t['id']) for t in truth];rr=[response.get(j['id'],{'status':'missing'}) for j in js];y=[t['activity'] for t in truth];p=[r.get('prediction',{}).get('predicted_activity','INVALID') for r in rr];preds[c]=p;valid=[i for i,r in enumerate(rr) if r['status']=='valid']
        base={'duration_only':[],'binary_plus_duration':[],'fixed_bit':[]};groups=defaultdict(Counter);group_preds=defaultdict(Counter)
        for j,label,pred in zip(js,y,p):
            refs,target=unpack(j['messages']);bit=lambda x:int(x.count('1')>len(x)/2);b=bit(target['binary_sequence']);n=len(target['binary_sequence'])
            ref=min(refs,key=lambda r:(abs(len(r['binary_sequence'])-n),CLASSES.index(r['activity'])))
            same=[r for r in refs if bit(r['binary_sequence'])==b] or refs
            refbit=min(same,key=lambda r:(abs(len(r['binary_sequence'])-n),CLASSES.index(r['activity'])))
            base['duration_only'].append(ref['activity']);base['binary_plus_duration'].append(refbit['activity']);base['fixed_bit'].append('Walking' if b else 'Sitting')
            key=hashlib.sha256(json.dumps(j['messages']).encode()).hexdigest();groups[key][label]+=1;group_preds[key][pred]+=1
        mean=lambda x:float(np.mean(x)) if x else None
        v={**classification(y,p),'predictions':p,'status_counts':dict(Counter(r['status'] for r in rr)),'prediction_counts':dict(Counter(p)),'mean_confidence':mean([rr[i]['prediction']['confidence'] for i in valid]),'confidence_correct':mean([rr[i]['prediction']['confidence'] for i in valid if p[i]==y[i]]),'confidence_wrong':mean([rr[i]['prediction']['confidence'] for i in valid if p[i]!=y[i]]),'high_confidence_errors':sum(rr[i]['prediction']['confidence']>=.8 and p[i]!=y[i] for i in valid),'insufficient_fraction':mean([not rr[i]['prediction']['sufficient_information'] for i in valid]),'baselines':{name:{**classification(y,pr),'predictions':pr} for name,pr in base.items()},'unique_inputs':len(groups),'pattern_bound':sum(max(g.values()) for g in groups.values())/14,'groups':[{'label_counts':dict(groups[g]),'prediction_counts':dict(group_preds[g])} for g in groups],'usage':{k:sum((r.get('usage') or {}).get(k,0) or 0 for r in rr) for k in ['prompt_tokens','completion_tokens','total_tokens','cost']},'by_subject':{str(s):classification([y[i] for i,t in enumerate(truth) if t['subject']==s],[p[i] for i,t in enumerate(truth) if t['subject']==s]) for s in [8,9]}}
        v['valid_only']=classification([y[i] for i in valid],[p[i] for i in valid]) if valid else None
        v['valid_only_baselines']={name:classification([y[i] for i in valid],[pr[i] for i in valid]) for name,pr in base.items()} if valid else {}
        out['conditions'][c]=v
    for a,b in [('C2','C1'),('C4','C3'),('C3','C1'),('C4','C2'),('C4','C5'),('C5','C2')]:
        pa,pb=preds[a],preds[b];ix=[i for i in range(14) if pa[i] in CLASSES and pb[i] in CLASSES]
        out['contrasts'][a+'-'+b]={'accuracy_difference':out['conditions'][a]['accuracy']-out['conditions'][b]['accuracy'],'changes':sum(x!=z for x,z in zip(pa,pb)),'wrong_to_correct':sum(x==label and z!=label for x,z,label in zip(pa,pb,y)),'correct_to_wrong':sum(x!=label and z==label for x,z,label in zip(pa,pb,y)),'valid_pair_n':len(ix),'valid_pair_accuracy_difference':(sum(pa[i]==y[i] for i in ix)-sum(pb[i]==y[i] for i in ix))/len(ix) if ix else None}
    diagnostic={name:[] for name in ['duration_only','binary_plus_duration']}
    for t in truth:
        tr=next(r for r in source_records if r['source']==t['source']);bit=int(tr['percent_ones']>50)
        for name in diagnostic:
            pool=training if name=='duration_only' else [r for r in training if int(r['percent_ones']>50)==bit]
            diagnostic[name].append(min(pool,key=lambda r:(abs(r['samples']-t['samples']),r['source']))['activity'])
    out['full_training_length_diagnostics']={k:{**classification(y,p),'predictions':p} for k,p in diagnostic.items()}
    dump(RUN/'evaluation.json',out)
    if not (RUN/'explanation_review.jsonl').exists():write_lines(RUN/'explanation_review.jsonl',[{'id':r['id'],'condition':r['condition'],'status':r['status'],'explanation':r.get('prediction',{}).get('explanation'),'unsupported':None,'notes':''} for r in rows])
    for c,v in out['conditions'].items():print(c,v['accuracy'],v['status_counts'],v['prediction_counts'],v['mean_confidence'])
    preserved=json.loads((DATA/'preservation.json').read_text());assert all(sha(ROOT/p)==h for p,h in preserved.items());print('Preserved',len(preserved),'files')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','infer','evaluate']);a=p.parse_args();globals()[a.command]()
