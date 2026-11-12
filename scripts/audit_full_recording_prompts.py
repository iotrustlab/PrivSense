"""Offline saved-request and full-recording audit. Never calls an inference API."""
import sys,json,re,csv,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from tokenizers import Tokenizer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from direct_llm import CLASSES,read_lines,dump,messages
from stage2_screen import read_binary,sha,render,templates
from e3_experiment import render as e3render
OUT=ROOT/'reports/full_recording_audit';DATA=ROOT/'data/full-recording-audit';SOURCE=ROOT.parent/'Datasets/Data_STM-DT'
SYSTEM='''Infer the activity of the unlabeled target recording using only the supplied sensor information, binary observations, and labeled references from other participants.
The references are independent recordings, not consecutive parts of a session. The target label is hidden. Do not infer unavailable measurements or treat an ambiguous pattern as a unique activity signature. A required single prediction may be uncertain.'''
USER='''Sensor information:
The system uses an IMU with accelerometer and gyroscope channels, placed in the right pocket. You see only its shake/no-shake output, not raw sensor channels. A 0 means no shake detected; a 1 means shake detected. The output is not a seven-class activity label. Export samples are spaced 0.02 seconds apart; the detector's internal decision frequency, thresholds and training details are not supplied. No shake does not establish complete physical stillness; a one does not measure amplitude, cadence or a unique activity.

Encoding: {encoding}
Each binary_sequence is ordered from earliest to latest. Each object has its own recording boundary. Observation extent states whether the object covers a complete processed recording or a contiguous excerpt. Do not treat different objects as a continuous session.

Labeled references from other participants:
{references}

Unlabeled target observation:
{target}

Predict the single activity assigned to the target recording, using the supplied portion of that recording. The candidate activities are Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.
Return only a JSON object with exactly:
- predicted_activity: one candidate activity name
- confidence: number in [0,1] for that exact activity
- alternative_activities: distinct other candidate names
- explanation: a brief account of the supplied evidence and its limitations
- sufficient_information: boolean indicating whether the evidence reliably distinguishes the exact activity.
Do not invent differences between identical observations.'''

def serialize(bits,encoding):return list(map(int,bits)) if encoding=='array' else ''.join(map(str,map(int,bits)))
def prompt(target,refs,tf,rf,encoding):
    return [{'role':'system','content':SYSTEM},{'role':'user','content':USER.format(encoding=('JSON integer arrays; each element is one sample.' if encoding=='array' else 'JSON strings of 0 and 1; every character is one sample, with no compression or omitted samples.'),references=json.dumps([{'activity':r['activity'],'observation_extent':'complete recording' if rf else 'contiguous excerpt','binary_sequence':serialize(r['bits'] if rf else r['bits'][:100],encoding)} for r in refs]),target=json.dumps({'observation_extent':'complete recording' if tf else 'contiguous excerpt','binary_sequence':serialize(target['bits'] if tf else target['short'],encoding)}))}]
def tokens(msg,tok):return sum(len(tok.encode(m['content']).ids) for m in msg)
def array_after(text,marker):return json.JSONDecoder().raw_decode(text.split(marker,1)[1].lstrip())[0]
def main():
    OUT.mkdir(exist_ok=True)
    prior={str(p.relative_to(ROOT)):sha(p) for folder in ['runs','data/direct-stage1','data/stage2-screen','data/e3-screen'] for p in (ROOT/folder).rglob('*') if p.is_file()}
    for p in ['direct_llm.py','stage2_screen.py','e3_experiment.py','reports/direct_llm_inference_pilot.md','reports/stage2_screening_results.md','reports/e3_cross_user_auxiliary_inference.md']:prior[p]=sha(ROOT/p)
    dump(OUT/'prior_artifact_hashes.json',prior)
    tok=Tokenizer.from_file(str(DATA/'tokenizer.json'));arrays={};records=[]
    for subject in range(1,10):
        base=SOURCE/f'User {subject}'/'Processed'
        for path in sorted(base.glob('**/right-pocket*.csv')):
            a,segments=read_binary(path);bits=a[:,1].astype(int);rel=str(path.relative_to(SOURCE));arrays[rel]=bits
            with path.open() as f:header=next(csv.reader(f))
            assert header[0]=='time[us]' and header[7]=='dec_tree_out_1'
            edges=np.flatnonzero(np.diff(bits)!=0)+1
            records.append({'source':rel,'subject':subject,'activity':path.relative_to(base).parts[0],'split':'train' if subject<8 else 'validation','sha256':sha(path),'samples':len(bits),'coverage_seconds':len(bits)*.02,'timestamp_span_seconds':float((a[-1,0]-a[0,0])/1e6),'continuous_segments':len(segments),'percent_ones':float(bits.mean()*100),'percent_zeros':float((1-bits.mean())*100),'transitions':len(edges),'transition_indices':edges.tolist(),'transition_seconds':((a[edges,0]-a[0,0])/1e6).tolist(),'transitions_after_first100':int(sum(edges>=100)),'transitions_after_first500':int(sum(edges>=500)),'transition_quartiles':dict(Counter(str(min(3,int(i*4/len(bits)))) for i in edges)),'array_tokens':len(tok.encode(json.dumps(bits.tolist())).ids),'string_tokens':len(tok.encode(''.join(map(str,bits.tolist()))).ids)})
    dump(OUT/'recordings.json',records)
    with (OUT/'recordings.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    # Independently compare parsed saved text with source-derived observations.
    audits={};examples={}
    truth1={r['id']:r for r in read_lines(ROOT/'data/direct-stage1/truth.jsonl')}
    obs1={r['id']:r['bits'] for r in read_lines(ROOT/'data/direct-stage1/observations.jsonl')}
    for ident,r in truth1.items():
        assert r['segment']==0
        assert obs1[ident]==arrays[r['recording']][r['start_sample_in_segment']:r['start_sample_in_segment']+100].tolist()
    allruns={'E1':read_lines(ROOT/'runs/direct-stage1-full/responses.jsonl'),'E2':read_lines(ROOT/'runs/stage2-screen/responses.jsonl'),'E3':read_lines(ROOT/'runs/e3-screen/responses.jsonl')}
    for folder in ['direct-stage1-smoke','direct-stage1-smoke-002']:
        allruns['E1-'+folder]=read_lines(ROOT/'runs'/folder/'responses.jsonl')
    truth2={r['id']:r for r in read_lines(ROOT/'data/stage2-screen/truth.jsonl')};obs2={r['id']:r for r in read_lines(ROOT/'data/stage2-screen/selected_observations.jsonl')}
    for ident,o in obs2.items():
        r=truth2[ident];start=r['target_start_sample'];assert o['target']==arrays[r['recording']][start:start+100].tolist();assert o['history']==arrays[r['recording']][start-400:start].tolist()
    refs2=json.loads((ROOT/'data/stage2-screen/references.json').read_text());prov2=json.loads((ROOT/'data/stage2-screen/reference_provenance.json').read_text())
    for r,p in zip(refs2,prov2):assert r['binary_sequence']==arrays[p['source']][p['start_sample']:p['start_sample']+100].tolist()
    refs3=json.loads((ROOT/'data/e3-screen/references.json').read_text());prov3=json.loads((ROOT/'data/e3-screen/reference_provenance.json').read_text())
    for i,r in enumerate(refs3['20']):
        p=prov3[r['activity']][i//7];assert r['binary_sequence']==arrays[p['source']][p['start_sample']:p['start_sample']+100].tolist();assert p['subject']<8
    for name,rows in allruns.items():
        mismatches=[];latest={};usage=[]
        for row in rows:
            user=row['messages'][1]['content'];latest[row['id']]=row
            assert len(row['messages'])==2 and [m['role'] for m in row['messages']]==['system','user']
            if name.startswith('E1'):
                parsed=array_after(user,'Observed sequence:');expected=messages(obs1[row['id']]);assert parsed==obs1[row['id']]
            else:
                o=obs2[row['target_id']];c=row['condition']
                if name=='E2':expected=render(c,o['target'],o['history'],refs2,templates())
                elif c=='E2-bridge':expected=render('C111',o['target'],o['history'],refs2,templates())
                else:
                    ref=refs3[c.split('K')[1].split('-')[0]]
                    if c.endswith('reversed'):ref=list(reversed(ref))
                    expected=e3render(o,ref)
                if (name=='E2' and c!='R0') or (name=='E3' and c=='E2-bridge'):
                    assert array_after(user,'Target observations:')==o['target']
                elif name=='E3':
                    assert array_after(user,'Target binary observations')==o['target'];assert array_after(user,'The following binary observations immediately precede the target interval within the same uninterrupted recording:')==o['history']
            if expected!=row['messages']:mismatches.append(row['id'])
            if row.get('usage'):
                u=row['usage'];usage.append({'local_content_tokens':tokens(row['messages'],tok),'provider_input_tokens':u.get('prompt_tokens'),'provider_output_tokens':u.get('completion_tokens'),'finish_reason':row.get('finish_reason')})
        assert not mismatches
        audits[name]={'attempt_rows':len(rows),'unique_requests':len(latest),'attempt_status':dict(Counter(r['status'] for r in rows)),'final_status':dict(Counter(r['status'] for r in latest.values())),'message_mismatches':mismatches,'returned_models':dict(Counter(str(r.get('returned_model')) for r in rows)),'returned_providers':dict(Counter(str(r.get('returned_provider','not logged')) for r in rows)),'finish_reasons':dict(Counter(str(r.get('finish_reason')) for r in rows)),'settings':[json.loads(s) for s in sorted({json.dumps(r['settings'],sort_keys=True) for r in rows})],'token_comparisons':usage}
        chosen=next(r for r in rows if r['status']=='valid' and (name.startswith('E1') or r['condition']==('C111' if name=='E2' else 'E3-K20')))
        examples[name]=chosen['messages'];dump(OUT/f'{name}_actual_messages.json',chosen['messages'])
    dump(OUT/'saved_request_audit.json',audits)
    # Freeze proposed full-file references across seven subjects by class order, not values.
    references=[]
    for i,label in enumerate(CLASSES):
        rec=next(r for r in records if r['subject']==i+1 and r['activity']==label and r['continuous_segments']==1)
        references.append({'activity':label,'source':rec['source'],'subject':rec['subject'],'bits':arrays[rec['source']].tolist(),'sha256':rec['sha256']})
    targets=[{'id':ident,'source':r['recording'],'subject':r['subject'],'activity':r['activity'],'bits':arrays[r['recording']].tolist(),'short':obs2[ident]['target'],'short_start':r['target_start_sample']} for ident,r in truth2.items()]
    dump(DATA/'selection_manifest.json',{'reference_rule':'Class index i -> User i+1; lexicographically first continuous processed right-pocket file for that class; full contents; no variation selection','references':[{k:v for k,v in r.items() if k!='bits'} for r in references],'targets':[{k:v for k,v in r.items() if k not in ['bits','short']} for r in targets]})
    dump(DATA/'templates.json',{'system':SYSTEM,'user':USER})
    jobs=[];costs=[]
    for encoding in ['array','string']:
        for c,tf,rf in [('C1',False,False),('C2',False,True),('C3',True,False),('C4',True,True)]:
            for t in targets:
                msg=prompt(t,references,tf,rf,encoding);n=tokens(msg,tok)
                costs.append({'id':t['id'],'condition':c,'encoding':encoding,'content_tokens':n,'budget_tokens':n+600+1024,'target_samples':len(t['bits']) if tf else 100,'reference_samples':sum(len(r['bits']) if rf else 100 for r in references)})
                jobs.append({'id':t['id']+'-'+c+'-'+encoding,'messages':msg})
    with (DATA/'proposed_prompts.jsonl').open('w') as f:
        for j in jobs:f.write(json.dumps(j)+'\n')
    dump(OUT/'token_budgets.json',costs)
    # Duration diagnostic and signatures; descriptive, not a hidden-label attacker.
    summaries={}
    for split in ['train','validation']:
        rs=[r for r in records if r['split']==split];d={}
        for c in CLASSES:
            cr=[r for r in rs if r['activity']==c];ns=[r['samples'] for r in cr]
            d[c]={'files':len(cr),'samples_min':min(ns),'samples_median':float(np.median(ns)),'samples_max':max(ns),'varying':sum(r['transitions']>0 for r in cr),'transitions':sum(r['transitions'] for r in cr)}
        signatures={}
        for mode in ['first100','first500','full','length','bit_and_length']:
            groups=defaultdict(Counter)
            for r in rs:
                b=arrays[r['source']]
                key=tuple(b[:100]) if mode=='first100' else tuple(b[:500]) if mode=='first500' else tuple(b) if mode=='full' else len(b) if mode=='length' else (int(b[0]),len(b))
                groups[key][r['activity']]+=1
            signatures[mode]={'unique':len(groups),'empirical_majority_bound':sum(max(g.values()) for g in groups.values())/len(rs)}
        summaries[split]={'files':len(rs),'samples':sum(r['samples'] for r in rs),'varying':sum(r['transitions']>0 for r in rs),'transitions':sum(r['transitions'] for r in rs),'edges_after100':sum(r['transitions_after_first100'] for r in rs),'edges_after500':sum(r['transitions_after_first500'] for r in rs),'classes':d,'signatures':signatures}
    # Exact-length nearest-neighbor baseline, training only; frozen first path tie-break.
    tr=[r for r in records if r['split']=='train'];vr=[r for r in records if r['split']=='validation']
    pred=[min(tr,key=lambda x:(abs(x['samples']-r['samples']),x['source']))['activity'] for r in vr]
    summaries['length_nearest_training_recording']={'correct':sum(p==r['activity'] for p,r in zip(pred,vr)),'n':len(vr),'note':'exploratory length-only predictor; no Qwen, no fitting on validation'}
    dump(OUT/'summary.json',summaries)
    dump(OUT/'proposed_selections.json',{'references':[{k:v for k,v in r.items() if k!='bits'}|{'samples':len(r['bits']),'transitions':int(np.count_nonzero(np.diff(r['bits'])))} for r in references],'targets':[{k:v for k,v in r.items() if k not in ['bits','short']}|{'samples':len(r['bits'])} for r in targets]})
    assert all(sha(ROOT/p)==h for p,h in prior.items())
    dump(OUT/'verification.json',{'preserved_files':len(prior),'all_prior_hashes_match':True,'source_recordings':len(records),'source_headers_verified':True,'source_reconstruction_passed':True,'tokenizer_sha256':sha(DATA/'tokenizer.json'),'tokenizer_config_sha256':sha(DATA/'tokenizer_config.json'),'tokenizer_library':__import__('tokenizers').__version__,'model_metadata_url':'https://openrouter.ai/api/v1/models/qwen/qwen3.5-35b-a3b/endpoints','tokenizer_url':'https://huggingface.co/Qwen/Qwen3.5-35B-A3B/resolve/main/tokenizer.json','inference_calls':0})
    print(json.dumps(summaries,indent=2))
    print('Selected reference samples:',[len(r['bits']) for r in references])
    for enc in ['array','string']:
        for c in ['C1','C2','C3','C4']:
            ns=[r['content_tokens'] for r in costs if r['condition']==c and r['encoding']==enc];print(enc,c,min(ns),max(ns))
if __name__=='__main__':main()
