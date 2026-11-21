"""Read-only data survey. No Qwen, no source edits, no test-user payload reads."""
import hashlib
import sys
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from project_paths import dataset_path
DATA=dataset_path()


def signature(bits):return ''.join(map(str,bits.astype(int)))


def diagnostics(windows):
    patterns=defaultdict(Counter);counts=defaultdict(Counter);labels=Counter()
    for bits,label,subject,recording in windows:
        patterns[signature(bits)][label]+=1;counts[str(int(bits.sum()))][label]+=1;labels[label]+=1
    n=len(windows)
    return {'windows':n,'class_counts':dict(labels),'nonconstant_windows':sum(bool(np.any(b!=b[0])) for b,_,_,_ in windows),'unique_ordered_patterns':len(patterns),'unique_one_counts':len(counts),'ordered_pattern_bound':sum(max(c.values()) for c in patterns.values())/n if n else None,'one_count_bound':sum(max(c.values()) for c in counts.values())/n if n else None,'pattern_label_counts':{k:dict(v) for k,v in patterns.items()}}


def survey():
    inventory={'dataset':'UTAH-STM-HAR','all_file_extensions':dict(Counter(p.suffix for p in DATA.rglob('*') if p.is_file())),'scope':'Processed users 1–9 across all placements; users 10–11 payloads not read. Raw files have no recorded binary column in prior audit. Other dataset names in research context are not assumed locally installed.'}
    audit=json.loads((ROOT/'reports/stage2_audit/audit.json').read_text())
    file_rows=[];groups=defaultdict(list);hashes={}
    for rec in audit['processed_records']:
        path=DATA/rec['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=rec['sha256']:raise ValueError('Source changed since audit')
        a=np.loadtxt(path,delimiter=',',skiprows=1,usecols=(0,7),ndmin=2)
        ts,bits=a.T;bits=bits.astype(int)
        if not np.isin(bits,[0,1]).all() or np.any(np.diff(ts)<=0):raise ValueError('Invalid source')
        cuts=np.flatnonzero(~np.isclose(np.diff(ts),20000,atol=1,rtol=0))+1
        segment_arrays=np.split(bits,cuts)
        file_rows.append({'path':rec['path'],'subject':rec['subject'],'split':rec['split'],'placement':rec['placement'],'activity':rec['activity'],'samples':len(bits),'transitions':rec['transitions'],'constant':rec['constant'],'sha256':rec['sha256']})
        for seconds,n in [(2,100),(10,500)]:
            for segment in segment_arrays:
                for start in range(0,len(segment)-n+1,n):
                    groups[(rec['split'],rec['placement'],seconds)].append((segment[start:start+n],rec['activity'],rec['subject'],rec['path']))
    results={}
    for (split,placement,seconds),windows in groups.items():
        files=[r for r in file_rows if r['split']==split and r['placement']==placement]
        varying=[r for r in files if not r['constant']]
        d=diagnostics(windows)
        d.update(files=len(files),varying_files=len(varying),varying_subjects=sorted({r['subject'] for r in varying}),varying_classes=sorted({r['activity'] for r in varying}),transitions=sum(r['transitions'] for r in files),variation_by_subject=dict(Counter(r['subject'] for r in varying)),variation_by_class=dict(Counter(r['activity'] for r in varying)))
        # Descriptive recurrence diagnostic; not a trained classifier or selection based on Qwen.
        if split=='validation':
            train=groups[('train',placement,seconds)]
            train_signatures={signature(b) for b,_,_,_ in train}
            train_label_signatures={(signature(b),label) for b,label,_,_ in train}
            varying_windows=[(b,label) for b,label,_,_ in windows if np.any(b!=b[0])]
            d['varying_windows_seen_in_training']=sum(signature(b) in train_signatures for b,_ in varying_windows)
            d['varying_windows_seen_in_training_with_same_label']=sum((signature(b),label) in train_label_signatures for b,label in varying_windows)
        results[f'{split}/{placement}/{seconds}s']=d
    out=ROOT/'reports/stage2_screen_survey.json'
    out.write_text(json.dumps({'inventory':inventory,'source_summary':file_rows,'diagnostics':results},indent=2)+'\n')
    for key,d in sorted(results.items()):
        print(key,{k:d[k] for k in ['windows','nonconstant_windows','unique_ordered_patterns','ordered_pattern_bound','one_count_bound','varying_files','varying_subjects','varying_classes']})


if __name__=='__main__':survey()
