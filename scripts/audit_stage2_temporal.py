"""Offline provenance/temporal audit; reads development users 1–9 only. No APIs."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent/'Datasets/Data_STM-DT'
OUT = ROOT/'reports/stage2_audit/audit.json'


def summarize(records):
    out = {}
    for key in sorted({(r['split'],r['placement']) for r in records}):
        rs = [r for r in records if (r['split'],r['placement'])==key]
        out['/'.join(key)] = {'files':len(rs),'samples':sum(r['samples'] for r in rs),'constant_files':sum(r['constant'] for r in rs),'transitions':sum(r['transitions'] for r in rs),'non_20ms_steps':sum(r['non_20ms_steps'] for r in rs),'nonincreasing_steps':sum(r['nonincreasing_steps'] for r in rs),'classes':dict(Counter(r['activity'] for r in rs))}
    return out


def audit():
    records=[]; raw=[]; stairs={}; notes=[]; matches=[]
    arrays={}
    for subject in range(1,10):
        base=DATA/f'User {subject}'
        for path in sorted((base/'Processed').rglob('*.csv')):
            a=np.loadtxt(path,delimiter=',',skiprows=1,usecols=(0,7),ndmin=2)
            ts,bits=a.T
            if not np.isfinite(a).all() or not np.isin(bits,[0,1]).all():raise ValueError(str(path))
            relative=path.relative_to(base/'Processed')
            placement=path.stem.split('_')[0]
            edges=np.flatnonzero(np.diff(bits)!=0)+1
            rec={'path':str(path.relative_to(DATA)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'subject':subject,'split':'validation' if subject in [8,9] else 'train','activity':relative.parts[0],'placement':placement,'samples':len(ts),'first_us':float(ts[0]),'last_us':float(ts[-1]),'sample_coverage_seconds':len(ts)*.02,'span_seconds':float((ts[-1]-ts[0])/1e6),'ones':int(bits.sum()),'constant':bool(np.all(bits==bits[0])),'transitions':len(edges),'transition_indices':edges.tolist(),'transition_seconds_from_start':((ts[edges]-ts[0])/1e6).tolist(),'non_20ms_steps':int(np.sum(~np.isclose(np.diff(ts),20000,atol=1,rtol=0))),'nonincreasing_steps':int(np.sum(np.diff(ts)<=0))}
            records.append(rec)
            if subject in [8,9] and placement=='right-pocket':arrays[str(path.relative_to(DATA))]=bits.astype(int)
        if subject not in [8,9]:continue
        for path in sorted((base/'Raw').glob('*/times.txt')):
            notes.append({'path':str(path.relative_to(DATA)),'text':path.read_text()})
        for path in sorted((base/'Raw').glob('*/right-pocket.csv')):
            with path.open() as h: header=[h.readline().strip() for _ in range(3)]
            a=np.loadtxt(path,delimiter=',',skiprows=3,ndmin=2)
            ts=a[:,0];delta=np.diff(ts)
            raw.append({'path':str(path.relative_to(DATA)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'subject':subject,'activity':path.parent.name,'header':header,'samples':len(ts),'first_us':float(ts[0]),'last_us':float(ts[-1]),'span_seconds':float((ts[-1]-ts[0])/1e6),'median_step_us':float(np.median(delta)),'min_step_us':float(delta.min()),'max_step_us':float(delta.max()),'nonincreasing_steps':int(np.sum(delta<=0))})
            proc=base/'Processed'/path.parent.name/'right-pocket.csv'
            if proc.exists():
                p=np.loadtxt(proc,delimiter=',',skiprows=1,ndmin=2)
                # Exact unit-scaled first-vector matching is diagnostic, not proof of pipeline.
                err=np.max(abs(a[:,1:7]*1000-p[0,1:7]),axis=1)
                ix=np.flatnonzero(err<=.001)
                interpolation = None
                if len(ix)==1:
                    offset = ts[ix[0]]-p[0,0]
                    predicted = np.column_stack([np.interp(p[:,0]+offset,ts,a[:,j]*1000) for j in range(1,7)])
                    interpolation = {'assumed_offset_us':float(offset),'max_absolute_error_per_channel':np.max(abs(predicted-p[:,1:7]),axis=0).tolist(),'raw_seconds_from_file_start_to_first_match':float((ts[ix[0]]-ts[0])/1e6)}
                matches.append({'processed':str(proc.relative_to(DATA)),'raw':str(path.relative_to(DATA)),'linear_interpolation_check':interpolation,'raw_match_indices':ix.tolist(),'matched_raw_times_us':ts[ix].tolist(),'processed_first_us':float(p[0,0]),'processed_sensor_peak_to_peak':np.ptp(p[:,1:7],axis=0).tolist(),'first_vector_max_error_min':float(err.min())})
        sr=sorted([r for r in records if r['subject']==subject and r['placement']=='right-pocket' and r['activity'] in ['Upstairs','Downstairs']],key=lambda r:r['first_us'])
        stairs[str(subject)]={'segments':[{k:r[k] for k in ['path','activity','first_us','last_us','samples','ones','transitions']} for r in sr],'adjacent_start_minus_previous_end_us':[b['first_us']-a['last_us'] for a,b in zip(sr,sr[1:])]}
    # Independent reconstruction of every Stage 1 exported validation window.
    truth=[json.loads(l) for l in (ROOT/'data/direct-stage1/truth.jsonl').read_text().splitlines()]
    obs={r['id']:r for r in [json.loads(l) for l in (ROOT/'data/direct-stage1/observations.jsonl').read_text().splitlines()]}
    for r in truth:
        assert r['segment']==0
        source=arrays[r['recording']][r['start_sample_in_segment']:r['start_sample_in_segment']+100].tolist()
        assert source==obs[r['id']]['bits']
    # Original ordering is available within a file; never join distinct files here.
    support=[]
    for subject in [8,9]:
        rs=[r for r in records if r['subject']==subject and r['placement']=='right-pocket']
        for seconds in [2,5,10,20]:
            n=int(seconds*50)
            support.append({'subject':subject,'seconds':seconds,'windows':sum(r['samples']//n for r in rs),'eligible_files':sum(r['samples']>=n for r in rs),'included_samples':sum(r['samples']//n*n for r in rs),'total_samples':sum(r['samples'] for r in rs)})
    result={'scope':'Processed all five placements for users 1–9; raw right-pocket and times.txt for users 8–9; no users 10–11 content, no API calls','summary':summarize(records),'processed_records':records,'raw_right_pocket_validation':raw,'notes_validation':notes,'raw_processed_first_vector_matches':matches,'stairs_local_timestamp_order_diagnostic_only':stairs,'stage1_export_reconstruction':{'matched_windows':len(truth),'total_windows':len(obs),'bit_exact':True},'duration_support':support}
    result['edge_index_modulo_50'] = {split:dict(Counter(str(i%50) for f in records if f['split']==split for i in f['transition_indices'])) for split in ['train','validation']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'summary':result['summary'],'stage1_export_reconstruction':result['stage1_export_reconstruction'],'duration_support':support},indent=2))


if __name__=='__main__':audit()
