"""Read-only response audit and deterministic cross-user baselines. No inference APIs."""
import sys,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from project_paths import dataset_path
from direct_llm import CLASSES,classification,read_lines,dump,validate
from stage2_screen import sha,read_binary
OUT=ROOT/'reports/next_inference_audit';SOURCE=dataset_path()

def nearest(train,test,features,shuffle=False):
    x=np.array([r[features] for r in train],float).reshape(len(train),-1)
    z=np.array([r['shuffled'] if shuffle else r[features] for r in test],float).reshape(len(test),-1)
    y=np.array([CLASSES.index(r['activity']) for r in train]);prior=np.bincount(y,minlength=7);pred=[]
    for start in range(0,len(test),100):
        dist=np.abs(z[start:start+100,None,:]-x[None,:,:]).mean(axis=2)
        tied=np.isclose(dist,dist.min(axis=1,keepdims=True),atol=1e-10,rtol=0)
        votes=np.stack([tied[:,y==i].sum(axis=1)/prior[i] if prior[i] else np.zeros(len(tied)) for i in range(7)],axis=1)
        pred.extend(CLASSES[i] for i in votes.argmax(axis=1))
    return pred

def score(test,pred):
    v=classification([r['activity'] for r in test],pred)
    files=defaultdict(list)
    for r,p in zip(test,pred):files[r['source']].append(p==r['activity'])
    v['equal_recording_accuracy']=float(np.mean([np.mean(x) for x in files.values()]))
    variable=[i for i,r in enumerate(test) if r['varying']]
    v['varying_support']=len(variable)
    v['varying_accuracy']=float(np.mean([pred[i]==test[i]['activity'] for i in variable])) if variable else None
    return v

def main():
    OUT.mkdir(exist_ok=True)
    protected={str(p.relative_to(ROOT)):sha(p) for directory in ['runs','data'] for p in (ROOT/directory).rglob('*') if p.is_file()}
    dump(OUT/'preservation.json',protected)
    rows=read_lines(ROOT/'runs/full-recording-screen/responses.jsonl');jobs={r['id']:r for r in read_lines(ROOT/'data/full-recording-screen/requests.jsonl')};details=[]
    for r in rows:
        assert r['messages']==jobs[r['id']]['messages']
        flags=[];p=None
        try:p=json.loads(r['raw_content'])
        except (ValueError,TypeError):flags.append('json_format')
        if p is not None:
            if not isinstance(p,dict):flags.append('unexpected_structure')
            else:
                expected={'predicted_activity','confidence','sufficient_information','explanation','alternative_activities'}
                if set(p)!=expected:flags.append('missing_or_misnamed_fields')
                if p.get('predicted_activity') not in CLASSES:flags.append('invalid_activity_name')
                if type(p.get('confidence')) not in [int,float] or not 0<=p['confidence']<=1:flags.append('confidence_error')
                if type(p.get('sufficient_information')) is not bool:flags.append('boolean_error')
                alts=p.get('alternative_activities')
                if not isinstance(alts,list) or len(alts)!=len(set(alts)) or any(x not in CLASSES or x==p.get('predicted_activity') for x in alts):flags.append('alternatives_error')
        if r['finish_reason']=='length':flags.append('truncated')
        try:validate(r['raw_content']);assert r['status']=='valid'
        except (ValueError,TypeError,KeyError):assert r['status']=='invalid_response'
        user=r['messages'][1]['content'];target=json.JSONDecoder().raw_decode(user.split('Unlabeled target observation:\n')[1])[0]['binary_sequence']
        details.append({'id':r['id'],'condition':r['condition'],'status':r['status'],'categories':flags,'missing':sorted(expected-set(p)) if isinstance(p,dict) else None,'extra':sorted(set(p)-expected) if isinstance(p,dict) else None,'input_tokens':r['usage']['prompt_tokens'],'output_tokens':r['usage']['completion_tokens'],'target_bit':target[0],'finish_reason':r['finish_reason'],'reasoning_tokens':r['usage'].get('completion_tokens_details',{}).get('reasoning_tokens'),'provider':r['returned_provider']})
    dump(OUT/'response_failures.json',details)
    summary={}
    for c in ['C1','C2','C3','C4','C5']:
        rr=[r for r in details if r['condition']==c]
        summary[c]={'n':len(rr),'invalid':sum(r['status']!='valid' for r in rr),'categories':dict(Counter(x for r in rr for x in r['categories'])),'wrong_keys':dict(Counter(x for r in rr for x in (r['extra'] or []))),'output_range':[min(r['output_tokens'] for r in rr),max(r['output_tokens'] for r in rr)],'input_range':[min(r['input_tokens'] for r in rr),max(r['input_tokens'] for r in rr)],'zeros_invalid':sum(r['target_bit']=='0' and r['status']!='valid' for r in rr),'ones_invalid':sum(r['target_bit']=='1' and r['status']!='valid' for r in rr)}
    dump(OUT/'reliability_summary.json',summary)
    manifest=json.loads((ROOT/'reports/stage2_audit/audit.json').read_text());files=[];windows=defaultdict(list)
    for r in manifest['processed_records']:
        path=SOURCE/r['path'];assert sha(path)==r['sha256'];a,segments=read_binary(path);bits=a[:,1].astype(int);edges=np.flatnonzero(np.diff(bits)!=0)+1
        rec={'source':r['path'],'subject':r['subject'],'activity':r['activity'],'placement':r['placement'],'samples':len(bits),'duration':len(bits)*.02,'proportion':float(bits.mean()),'transitions':len(edges),'transition_indices':edges.tolist(),'varying':bool(len(edges)),'segments':len(segments)};files.append(rec)
        for seg in segments:
            for off in range(0,len(seg)-499,500):
                start=int(seg[off]);b=bits[start:start+500];bins=b.reshape(10,50).mean(axis=1)
                assert np.isin(bins,[0,1]).all() # observed held-output grid: this block representation is lossless here
                seed=int(hashlib.sha256((r['path']+':'+str(start)+':2026').encode()).hexdigest()[:8],16)
                rng=np.random.default_rng(seed);shuffled=bins[rng.permutation(10)]
                windows[r['placement']].append({'source':r['path'],'subject':r['subject'],'activity':r['activity'],'start':start,'proportion':float(b.mean()),'ordered':bins.tolist(),'shuffled':shuffled.tolist(),'varying':bool(np.any(b!=b[0]))})
    dump(OUT/'recordings.json',files)
    results={};window_manifest=[]
    for placement,ws in windows.items():
        train=[r for r in ws if r['subject']<=7];test=[r for r in ws if r['subject']>=8];v={}
        for name,feature,shuffle in [('count','proportion',False),('ordered','ordered',False),('order_disrupted_target','ordered',True)]:
            pred=nearest(train,test,feature,shuffle);v[name]=score(test,pred);v[name]['subjects']={str(s):score([r for r in test if r['subject']==s],[p for r,p in zip(test,pred) if r['subject']==s]) for s in [8,9]}
        v['train_loso']={}
        for s in range(1,8):
            tr=[r for r in train if r['subject']!=s];te=[r for r in train if r['subject']==s]
            v['train_loso'][str(s)]={name:score(te,nearest(tr,te,feature,shuffle)) for name,feature,shuffle in [('count','proportion',False),('ordered','ordered',False),('order_disrupted_target','ordered',True)]}
        v['coverage']={}
        for split,part in [('train',train),('validation',test)]:
            fr=[f for f in files if f['placement']==placement and ((f['subject']<=7)==(split=='train'))]
            groups={name:defaultdict(Counter) for name in ['count','order']}
            for r in part:groups['count'][r['proportion']][r['activity']]+=1;groups['order'][tuple(r['ordered'])][r['activity']]+=1
            v['coverage'][split]={'windows':len(part),'varying_windows':sum(r['varying'] for r in part),'files':len(fr),'represented_files':len({r['source'] for r in part}),'samples_total':sum(r['samples'] for r in fr),'retained_samples':500*len(part),'variable_subjects':dict(Counter(r['subject'] for r in part if r['varying'])),'variable_classes':dict(Counter(r['activity'] for r in part if r['varying'])),'pattern_bounds':{name:sum(max(c.values()) for c in gs.values())/len(part) for name,gs in groups.items()}}
        trfiles=[r for r in files if r['placement']==placement and r['subject']<=7];tefiles=[r for r in files if r['placement']==placement and r['subject']>=8]
        v['file_duration_baseline']=score(tefiles,nearest(trfiles,tefiles,'duration'))
        v['file_proportion_baseline']=score(tefiles,nearest(trfiles,tefiles,'proportion'))
        results[placement]=v;window_manifest.extend([r|{'placement':placement} for r in ws])
    dump(OUT/'temporal_baselines.json',results);dump(OUT/'window_manifest.json',window_manifest)
    assert all(sha(ROOT/p)==h for p,h in protected.items())
    print('Reliability:',summary)
    for p,v in results.items():
        print(p,'validation',[(k,v[k]['accuracy'],v[k]['varying_accuracy']) for k in ['count','ordered','order_disrupted_target']], 'LOSO order-count',[(s,round(d['ordered']['accuracy']-d['count']['accuracy'],4)) for s,d in v['train_loso'].items()])
if __name__=='__main__':main()
