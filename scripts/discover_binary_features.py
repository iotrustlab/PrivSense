"""Restructured PrivSense Stage 1: offline binary feature discovery, no LLM."""
import sys,json,csv,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from itertools import combinations
import numpy as np
from sklearn.tree import DecisionTreeClassifier,export_text
from sklearn.dummy import DummyClassifier
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from direct_llm import CLASSES,classification
from stage2_screen import read_binary,sha
OUT=ROOT/'reports/activity_feature_audit';SOURCE=ROOT.parent/'Datasets/Data_STM-DT'
TEMPORAL=['transition_rate_hz','mean_zero_run_fraction','mean_one_run_fraction','max_zero_run_fraction','max_one_run_fraction','segment_duty_std','segment_duty_slope','lag1_correlation','lag50_correlation']
GROUPS={'class_prior':[],'duty_cycle':['fraction_ones'],'duration_only':['duration_seconds'],'temporal_no_explicit_duration':['fraction_ones']+TEMPORAL,'combined_with_duration':['fraction_ones']+TEMPORAL+['duration_seconds']}
CANDIDATES=['fraction_ones','duration_seconds','transition_count','transition_rate_hz','mean_zero_run_seconds','mean_one_run_seconds','max_zero_run_seconds','max_one_run_seconds']+TEMPORAL[1:]+['binary_entropy','segment_duty_range','first_last_duty_difference','candidate_period_available','candidate_period_score']
CANDIDATES=list(dict.fromkeys(CANDIDATES))

def correlation(x,lag):
    if lag>=len(x) or np.std(x[:-lag])==0 or np.std(x[lag:])==0:return 0.
    return float(np.corrcoef(x[:-lag],x[lag:])[0,1])

def features(bits,dt=.02):
    b=np.asarray(bits);n=len(b)
    if n<10 or not np.isin(b,[0,1]).all():raise ValueError('Need at least ten genuine binary samples')
    b=b.astype(int)
    edges=np.flatnonzero(np.diff(b)!=0)+1;bounds=np.r_[0,edges,n];lens=np.diff(bounds);states=b[bounds[:-1]];duty=float(b.mean());segments=np.array([x.mean() for x in np.array_split(b,10)])
    f={'samples':n,'duration_seconds':n*dt,'timestamp_span_seconds':(n-1)*dt,'fraction_ones':duty,'fraction_zeros':1-duty,'transition_count':len(edges),'transition_rate_hz':len(edges)/((n-1)*dt),'binary_entropy':float(-sum(p*np.log2(p) for p in [duty,1-duty] if p>0)),'segment_duty_std':float(segments.std()),'segment_duty_range':float(np.ptp(segments)),'segment_duty_slope':float(np.polyfit(np.linspace(0,1,10),segments,1)[0]),'first_last_duty_difference':float(segments[-1]-segments[0]),'lag1_correlation':correlation(b,1),'lag50_correlation':correlation(b,50)}
    runs={}
    for state,name in [(0,'zero'),(1,'one')]:
        l=lens[states==state];runs[name]={'samples':l.tolist(),'seconds':(l*dt).tolist(),'boundary_censored':[bool(i==0 or i==len(lens)-1) for i in np.flatnonzero(states==state)]}
        for stat,fn in [('mean',np.mean),('median',np.median),('max',np.max),('p90',lambda a:np.quantile(a,.9))]:
            value=float(fn(l)) if len(l) else 0.
            f[stat+'_'+name+'_run_seconds']=value*dt;f[stat+'_'+name+'_run_fraction']=value/n
        f[name+'_bout_count']=len(l)
    # A periodicity candidate needs repeated bouts and an interior positive autocorrelation peak.
    lags=list(range(50,min(1000,n//3)+1,50));ac=[correlation(b,k) for k in lags] if len(edges)>=6 and sum(states==1)>=3 else []
    peaks=[i for i in range(1,len(ac)-1) if ac[i]>.3 and ac[i]>ac[i-1]+1e-8 and ac[i]>=ac[i+1]]
    best=max(peaks,key=lambda i:ac[i]) if peaks else None
    f['candidate_period_available']=int(best is not None);f['candidate_period_score']=ac[best] if best is not None else 0.
    detail={'transition_indices':edges.tolist(),'segment_duty':segments.tolist(),'runs':runs,'candidate_period_seconds':lags[best]*dt if best is not None else None,'candidate_autocorrelation_lags_samples':lags if ac else [],'candidate_autocorrelations':ac,'periodicity_interpretation':'Candidate recurrence only, not verified motion/gait periodicity. Missing means not measurable by this rule.'}
    return f,detail

def disrupt(b,seed):
    n=len(b)//50;blocks=np.array(b[:n*50]).reshape(n,50);tail=np.array(b[n*50:]);rng=np.random.default_rng(seed)
    return np.r_[blocks[rng.permutation(n)].ravel(),tail].astype(int)

def fit_predict(train,test,fields,depth=3):
    x=np.array([[r['features'][f] for f in fields] for r in train]) if fields else np.zeros((len(train),1))
    z=np.array([[r['features'][f] for f in fields] for r in test]) if fields else np.zeros((len(test),1))
    y=[r['activity'] for r in train]
    model=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=3,class_weight='balanced',random_state=42) if fields else DummyClassifier(strategy='most_frequent')
    model.fit(x,y);return model.predict(z).tolist(),model

def score(rs,p):
    return classification([r['activity'] for r in rs],p)

def loso(train,fields,depth=3):
    rows=[];pred=[];by={}
    for s in range(1,8):
        a=[r for r in train if r['subject']!=s];b=[r for r in train if r['subject']==s];p,_=fit_predict(a,b,fields,depth)
        rows+=b;pred+=p;by[str(s)]=score(b,p)
    return {'pooled':score(rows,pred),'subjects':by,'mean_subject_balanced_accuracy':float(np.mean([v['balanced_accuracy'] for v in by.values()]))}

def main():
    OUT.mkdir(exist_ok=True)
    protected={str(p.relative_to(ROOT)):sha(p) for folder in ['data','runs','reports'] for p in (ROOT/folder).rglob('*') if p.is_file() and OUT not in p.parents}
    (OUT/'preservation.json').write_text(json.dumps(protected,indent=2))
    audit=json.loads((ROOT/'reports/stage2_audit/audit.json').read_text());records=[];contexts=defaultdict(list);rawsignatures=defaultdict(list)
    for i,rec in enumerate(audit['processed_records']):
        path=SOURCE/rec['path'];assert sha(path)==rec['sha256'];a,segs=read_binary(path)
        # Full-file features assume continuous sampling; do not bridge gaps.
        assert len(segs)==1
        bits=a[:,1].astype(int);f,d=features(bits)
        row={'source':rec['path'],'sha256':rec['sha256'],'subject':rec['subject'],'activity':rec['activity'],'placement':rec['placement'],'features':f,'details':d};records.append(row)
        rawsignatures[rec['placement']].append({'subject':rec['subject'],'activity':rec['activity'],'full_hash':hashlib.sha256(bits.tobytes()).hexdigest(),'fixed100_hash':hashlib.sha256(bits[:100].tobytes()).hexdigest(),'constant':bool(np.all(bits==bits[0])),'bit':int(bits[0])})
        if len(bits)>=500:
            shuffle=disrupt(bits,10000+i);short=bits[:100];long=bits[:500];longshuffle=disrupt(long,20000+i)
            assert len(shuffle)==len(bits) and shuffle.sum()==bits.sum() and longshuffle.sum()==long.sum()
            for name,bb in [('short_2s',short),('long_10s',long),('full',bits),('full_order_disrupted',shuffle),('long_order_disrupted',longshuffle)]:
                ff,dd=features(bb);contexts[(rec['placement'],name)].append({k:row[k] for k in ['source','subject','activity','placement']}|{'features':ff,'order_changed':bool(not np.array_equal(bb,bits if name.startswith('full') else long)) if 'disrupted' in name else False})
    dump=lambda name,x:(OUT/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
    dump('recording_features.json',records)
    with (OUT/'recording_features.csv').open('w',newline='') as h:
        fields=['source','subject','activity','placement']+list(records[0]['features']);w=csv.DictWriter(h,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in fields[:4]}|r['features'] for r in records)
    distributions={};rankings={};results={};pairs={};collisions={};coherence={}
    for placement in sorted({r['placement'] for r in records}):
        tr=[r for r in records if r['placement']==placement and r['subject']<=7];te=[r for r in records if r['placement']==placement and r['subject']>=8]
        distributions[placement]={}
        for c in CLASSES:
            cr=[r for r in tr if r['activity']==c];distributions[placement][c]={}
            for feat in CANDIDATES:
                vals=np.array([r['features'][feat] for r in cr]);means=[np.mean([r['features'][feat] for r in cr if r['subject']==s]) for s in range(1,8)]
                distributions[placement][c][feat]={'n':len(vals),'min':float(vals.min()),'q25':float(np.quantile(vals,.25)),'median':float(np.median(vals)),'q75':float(np.quantile(vals,.75)),'max':float(vals.max()),'subject_means':means,'sd_of_subject_means':float(np.std(means))}
        rankings[placement]=[]
        for feat in CANDIDATES:
            cv=loso(tr,[feat],depth=2);rankings[placement].append({'feature':feat,'train_loso':cv})
        rankings[placement].sort(key=lambda r:(-r['train_loso']['mean_subject_balanced_accuracy'],r['feature']))
        results[placement]={}
        for group,fields in GROUPS.items():
            cv=loso(tr,fields);p,model=fit_predict(tr,te,fields)
            results[placement][group]={'features':fields,'train_loso':cv,'validation':score(te,p),'validation_subjects':{str(s):score([r for r in te if r['subject']==s],[x for r,x in zip(te,p) if r['subject']==s]) for s in [8,9]},'individual_predictions':[{'source':r['source'],'truth':r['activity'],'prediction':x} for r,x in zip(te,p)],'tree':export_text(model,feature_names=fields) if fields else 'Training majority class, empirical file prior.'}
        # Pair tasks explicitly assume the candidate set is restricted to the named pair.
        pairs[placement]={}
        for a,b in combinations(CLASSES,2):
            pt=[r for r in tr if r['activity'] in [a,b]];pe=[r for r in te if r['activity'] in [a,b]];out={}
            for name,fields in [('duty',['fraction_ones']),('temporal',['fraction_ones']+TEMPORAL),('duration',['duration_seconds'])]:
                cv=loso(pt,fields,depth=2);p,_=fit_predict(pt,pe,fields,depth=2);out[name]={'train_loso_balanced_accuracy':cv['mean_subject_balanced_accuracy'],'validation_balanced_accuracy':score(pe,p)['balanced_accuracy'],'validation_accuracy':score(pe,p)['accuracy'],'validation_n':len(pe)}
            shuffled_pair=[r for r in contexts[(placement,'full_order_disrupted')] if r['subject']>=8 and r['activity'] in [a,b]]
            pp,_=fit_predict(pt,shuffled_pair,['fraction_ones']+TEMPORAL,depth=2)
            out['temporal']['validation_shuffled_balanced_accuracy']=score(shuffled_pair,pp)['balanced_accuracy']
            pairs[placement][a+' vs '+b]=out
        collisions[placement]={}
        for split,pool in [('train',[r for r in rawsignatures[placement] if r['subject']<=7]),('validation',[r for r in rawsignatures[placement] if r['subject']>=8])]:
            groups=defaultdict(Counter)
            for r in pool:groups[r['fixed100_hash']][r['activity']]+=1
            collisions[placement][split]={'fixed100_unique':len(groups),'fixed100_shared_groups':[dict(g) for g in groups.values() if len(g)>1],'constant_file_classes_by_bit':{str(bit):dict(Counter(r['activity'] for r in pool if r['constant'] and r['bit']==bit)) for bit in [0,1]}}
        coherence[placement]={}
        for context in ['short_2s','long_10s','full']:
            rs=contexts[(placement,context)];train=[r for r in rs if r['subject']<=7];test=[r for r in rs if r['subject']>=8];coherence[placement][context]={}
            for group,fields in GROUPS.items():
                p,model=fit_predict(train,test,fields);coherence[placement][context][group]={'train_n':len(train),'test_n':len(test),'validation':score(test,p)}
        for original,altered in [('full','full_order_disrupted'),('long_10s','long_order_disrupted')]:
            tr1=[r for r in contexts[(placement,original)] if r['subject']<=7];te1=[r for r in contexts[(placement,original)] if r['subject']>=8];tr2=[r for r in contexts[(placement,altered)] if r['subject']<=7];te2=[r for r in contexts[(placement,altered)] if r['subject']>=8]
            fields=GROUPS['temporal_no_explicit_duration'];p,_=fit_predict(tr1,te2,fields);p2,_=fit_predict(tr2,te2,fields)
            coherence[placement][altered]={'chronological_train_shuffled_test':score(te2,p),'shuffled_train_shuffled_test':score(te2,p2),'changed_training':sum(r['order_changed'] for r in tr2),'changed_validation':sum(r['order_changed'] for r in te2)}
        # Whole training population fixed-duration feature ranking uses the matched 142 files.
        fixed=[r for r in contexts[(placement,'long_10s')] if r['subject']<=7]
        rankings[placement+'_fixed10s']=[{'feature':feat,'train_loso':loso(fixed,[feat],depth=2)} for feat in ['fraction_ones']+TEMPORAL]
        rankings[placement+'_fixed10s'].sort(key=lambda r:(-r['train_loso']['mean_subject_balanced_accuracy'],r['feature']))
    dump('training_feature_distributions.json',distributions);dump('training_feature_ranking.json',rankings);dump('cross_user_results.json',results);dump('activity_pair_results.json',pairs);dump('observational_collisions.json',collisions);dump('temporal_coherence.json',coherence)
    dump('analysis_manifest.json',{'scope':'Restructured Stage 1, users 1–9 only, five placements, no APIs','features':GROUPS,'candidate_features':CANDIDATES,'training_selection':'Frozen candidate families and depth; single-feature ranking uses mean training-user LOSO balanced accuracy only; no evaluation-driven feature selection or tuning','estimator':'DecisionTreeClassifier(max_depth=3,min_samples_leaf=3,class_weight=balanced,random_state=42); single-feature and pair analysis depth=2; empirical majority DummyClassifier','durations':'N*0.02 sample coverage; time span (N-1)*0.02','order_control':'Permute complete 50-sample blocks, retain partial tail. Fixed row-based seeds 10000+i/20000+i, identical length/count. Artificial order control explicitly labeled. No source modifications.','preserved_files':len(protected),'source_files':len(records),'sklearn_version':__import__('sklearn').__version__,'numpy_version':np.__version__})
    assert all(sha(ROOT/p)==h for p,h in protected.items())
    for placement,v in results.items():print(placement,[(k,round(x['validation']['accuracy'],4),round(x['validation']['macro_f1'],4)) for k,x in v.items()])
    print('Preserved',len(protected),'files; no LLM calls.')
if __name__=='__main__':main()
