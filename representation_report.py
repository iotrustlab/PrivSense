"""Evaluator-only scoring and report; never feeds answers to Qwen."""
import argparse,json
from project_paths import dataset_path
from collections import Counter,defaultdict
import numpy as np
from direct_llm import CLASSES,classification,dump,read_lines
from stage2_screen import ROOT,sha
from representation_experiment import DATA,RUN,FIELDS,represent
REPORT=ROOT/'reports/qwen_representation_comparison.md'

def baselines():
    assert not (DATA/'baseline_predictions.json').exists()
    targets=json.loads((DATA/'truth.json').read_text());refs=json.loads((DATA/'references.json').read_text());result=[]
    for t in targets:
        rr=[r for r in refs if r['placement']==t['placement']];support=Counter(r['activity'] for r in rr)
        for condition in ['original']+(['disrupted'] if t['varying'] else []):
            b=t['bits'] if condition=='original' else t['disrupted_bits'];f=represent(b,'T')
            pr={'fixed_bit':'Walking' if f['fraction_ones']>.5 else 'Sitting','reference_prior':min(CLASSES,key=lambda c:(-support[c],CLASSES.index(c)))}
            pr['duration_only']=pr['reference_prior']
            for name,fields in [('nearest_duty',FIELDS[:1]),('nearest_temporal',FIELDS)]:
                def vector(ff):return [ff[k]/499 if k=='transition_count' else ff[k] for k in fields]
                z=np.array(vector(f));x=np.array([vector(represent(r['bits'],'T')) for r in rr]);d=np.abs(x-z).mean(axis=1);ix=np.flatnonzero(np.isclose(d,d.min(),atol=1e-10,rtol=0))
                votes={c:sum(rr[i]['activity']==c for i in ix)/support[c] if support[c] else 0 for c in CLASSES}
                pr[name]=min(CLASSES,key=lambda c:(-votes[c],CLASSES.index(c)))
            result.append({'target_id':t['id'],'order':condition,'predictions':pr})
    dump(DATA/'baseline_predictions.json',result)
    print('Frozen conventional predictions before research calls')

def evaluate():
    targets=json.loads((DATA/'truth.json').read_text());truth={t['id']:t for t in targets}
    jobs=read_lines(DATA/'requests.jsonl');rows=read_lines(RUN/'research_responses.jsonl') if (RUN/'research_responses.jsonl').exists() else []
    responses={r['id']:r for r in rows};assert len(responses)==len(rows)
    meta=json.loads((DATA/'manifest.json').read_text());assert sha(DATA/'requests.jsonl')==meta['requests_sha256']
    for r in rows:assert r['messages']==next(j['messages'] for j in jobs if j['id']==r['id'])
    items=[]
    for j in jobs:
        t=truth[j['target_id']];r=responses.get(j['id'],{'status':'missing'});p=r.get('prediction',{}) if r['status']=='valid' else {}
        items.append({'id':j['id'],'target_id':t['id'],'condition':j['condition'],'truth':t['activity'],'subject':t['subject'],'placement':t['placement'],'source':t['source'],'stratum':'varying' if t['varying'] else 'constant','predicted_activity':p.get('predicted_activity','INVALID'),'confidence':p.get('confidence'),'sufficient_information':p.get('sufficient_information'),'status':r['status'],'technical_valid':r.get('technical_valid',False)})
    def score(ii):
        if not ii:return None
        valid=[r for r in ii if r['status']=='valid'];correct=[r for r in valid if r['predicted_activity']==r['truth']];wrong=[r for r in valid if r['predicted_activity']!=r['truth']]
        mean=lambda a:float(np.mean(a)) if a else None
        v=classification([r['truth'] for r in ii],[r['predicted_activity'] for r in ii])
        v.update(status_counts=dict(Counter(r['status'] for r in ii)),mean_confidence=mean([r['confidence'] for r in valid]),confidence_correct=mean([r['confidence'] for r in correct]),confidence_wrong=mean([r['confidence'] for r in wrong]),insufficient_count=sum(not r['sufficient_information'] for r in valid),high_confidence_errors=sum(r['confidence']>=.8 for r in wrong),label_support=dict(Counter(r['truth'] for r in ii)),prediction_counts=dict(Counter(r['predicted_activity'] for r in ii)))
        v['reliability_bins']=[{'range':[lo,hi],'n':len(z),'mean_confidence':mean([r['confidence'] for r in z]),'accuracy':mean([r['predicted_activity']==r['truth'] for r in z])} for lo,hi in [(0,.25),(.25,.5),(.5,.75),(.75,1.00001)] for z in [[r for r in valid if lo<=r['confidence']<hi]]]
        return v
    result={'conditions':{},'individual':items,'contrasts':{},'baselines':{}}
    for c in ['R','D','T','T-order']:
        ii=[r for r in items if r['condition']==c]
        result['conditions'][c]={'all':score(ii),'strata':{s:score([r for r in ii if r['stratum']==s]) for s in ['constant','varying']},'subjects':{str(s):score([r for r in ii if r['subject']==s]) for s in [8,9]},'placements':{s:score([r for r in ii if r['placement']==s]) for s in sorted({t['placement'] for t in targets})}}
    for a,b in [('D','R'),('T','R'),('T','D'),('T-order','T')]:
        aa={r['target_id']:r for r in items if r['condition']==a};bb={r['target_id']:r for r in items if r['condition']==b};ids=sorted(set(aa)&set(bb));changes=[]
        for i in ids:
            x,z=aa[i],bb[i];changes.append({'target_id':i,'before':z['predicted_activity'],'after':x['predicted_activity'],'before_correct':z['predicted_activity']==z['truth'],'after_correct':x['predicted_activity']==x['truth'],'confidence_change':x['confidence']-z['confidence'] if x['confidence'] is not None and z['confidence'] is not None else None})
        result['contrasts'][a+'-'+b]={'paired_n':len(ids),'changes':sum(x['before']!=x['after'] for x in changes),'wrong_to_correct':sum(x['after_correct'] and not x['before_correct'] for x in changes),'correct_to_wrong':sum(x['before_correct'] and not x['after_correct'] for x in changes),'accuracy_difference':float(np.mean([int(x['after_correct'])-int(x['before_correct']) for x in changes])),'pairs':changes}
    baseline=json.loads((DATA/'baseline_predictions.json').read_text())
    for order in ['original','disrupted']:
        rr=[r for r in baseline if r['order']==order];result['baselines'][order]={}
        for name in rr[0]['predictions']:
            ii=[{'truth':truth[r['target_id']]['activity'],'predicted_activity':r['predictions'][name],'status':'valid','confidence':0.,'sufficient_information':False,'stratum':'varying' if truth[r['target_id']]['varying'] else 'constant'} for r in rr]
            result['baselines'][order][name]={'all':classification([x['truth'] for x in ii],[x['predicted_activity'] for x in ii]),'strata':{s:classification([x['truth'] for x in ii if x['stratum']==s],[x['predicted_activity'] for x in ii if x['stratum']==s]) for s in {x['stratum'] for x in ii}}}
    # Observable-input ambiguity diagnostics, not hidden-label attacker baselines.
    result['input_groups']={}
    for c in ['R','D','T','T-order']:
        groups=defaultdict(list)
        for j in jobs:
            if j['condition']==c:groups[json.dumps(j['messages'])].append(truth[j['target_id']]['activity'])
        result['input_groups'][c]={'unique_inputs':len(groups),'label_groups':[dict(Counter(g)) for g in groups.values()],'empirical_pattern_bound':sum(max(Counter(g).values()) for g in groups.values())/sum(map(len,groups.values()))}
    result['order_features']=[{'target_id':t['id'],'original':represent(t['bits'],'T'),'disrupted':represent(t['disrupted_bits'],'T'),'changed_features':[k for k in FIELDS if represent(t['bits'],'T')[k]!=represent(t['disrupted_bits'],'T')[k]],'seed':t['shuffle_seed'],'block_permutation':t['block_permutation']} for t in targets if t['varying']]
    result['usage']={}
    for kind in ['gate','research']:
        rr=read_lines(RUN/(kind+'_responses.jsonl')) if (RUN/(kind+'_responses.jsonl')).exists() else []
        result['usage'][kind]={'calls':len(rr),'valid':sum(r['status']=='valid' for r in rr),'technical_valid':sum(r['technical_valid'] for r in rr),'providers':dict(Counter(r.get('returned_provider') for r in rr)),'usage':{k:sum((r.get('usage') or {}).get(k,0) or 0 for r in rr) for k in ['prompt_tokens','completion_tokens','total_tokens','cost']},'cost_fields_present':sum('cost' in (r.get('usage') or {}) for r in rr)}
    preserved=json.loads((DATA/'preservation.json').read_text());assert all(sha(ROOT/p)==h for p,h in preserved.items())
    assert all(sha(dataset_path()/p)==h for p,h in meta['source_hashes'].items())
    result['per_condition_usage']={c:{k:sum((r.get('usage') or {}).get(k,0) or 0 for r in rows if r['condition']==c) for k in ['prompt_tokens','completion_tokens','cost']} for c in ['R','D','T','T-order']}
    result['baseline_predictions_sha256']=sha(DATA/'baseline_predictions.json')
    result['preserved_files']=len(preserved);dump(RUN/'evaluation.json',result)
    return result

def report(e):
    pct=lambda x:f'{100*x:.1f}%'
    lines=['# PrivSense Stage 2: Qwen representation comparison','',
    'This is the restructured 50-request representation screen, separate from historical E1–E3 and full-recording results. No prior score is repaired or overwritten. Qwen directly predicts activities; conventional baselines are evaluator-side only.','',
    '**Result:** all 12 technical-gate and 50 research responses passed the three-field schema. Raw strings and temporal summaries each achieved 4/15 correct activities; duty-only achieved 3/15. Temporal summaries changed uncertainty substantially but did not improve exact-class accuracy over raw observations. Order disruption changed one wrong prediction to another wrong prediction. This does not justify progressing to an autonomous feature-discovery stage.','',
    '## Output reliability and technical gate','',
    'Protocol `privsense-inference-v2.0` requires exactly `predicted_activity` (one of seven candidates), `confidence` (finite number in [0,1]), and `sufficient_information` (boolean). Duplicate keys, extra/missing fields, invalid labels, nonfinite values and wrong types are rejected without repair. Strict JSON Schema is sent to OpenRouter; no response-healing plugin is used.','',
    'OpenRouter documents endpoint-specific schema support and cautions that strict enforcement varies by provider: [structured outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs). A fresh endpoint snapshot advertises both response_format and structured_outputs for deepinfra/fp8. Local schema and payload tests precede API use.','',
    'The separately logged gate uses 12 calls: two actual User 1 constant binary cases × short (100 samples), fixed (500 samples), and complete-recording profiles × two repeats. References come only from users 2–7. Target labels are neither exported nor scored. All requests were frozen before execution. Gate passage requires 12 strict-valid normal-stop responses, correct provider/model, and plausible input usage. Research calls are conditional on that result. Twelve successes are a smoke test, not proof of a low failure probability (an idealized independent-binomial one-sided 95% upper failure bound is 22.1%).','']
    for k,v in e['usage'].items():lines.append(f"- {k}: {v['calls']} calls, {v['valid']} schema-valid, {v['technical_valid']} delivery-valid; provider counts {v['providers']}; input tokens {v['usage']['prompt_tokens']:,}, output tokens {v['usage']['completion_tokens']:,}; API-reported cost **${v['usage']['cost']:.6f}** ({v['cost_fields_present']} cost fields present).")
    lines += ['', '| Research condition | Input tokens | Output tokens | API cost USD |', '|---|---:|---:|---:|']
    for c,v in e['per_condition_usage'].items():lines.append(f"| {c} | {v['prompt_tokens']:,} | {v['completion_tokens']:,} | ${v['cost']:.6f} |")
    lines += ['', 'Model `qwen/qwen3.5-35b-a3b`; only `deepinfra/fp8`, fallback disabled, require_parameters=true; temperature 0.1; reasoning disabled; 128 output tokens; no sampling seed assumed; independent stateless requests; no retries. The provider advertises 262,144 context tokens. Local token counts include message content; an allowance of 2,048 covers framing/schema. All 62 responses ended with stop and API prompt usage exceeded locally counted message-content tokens by exactly 17 tokens. Usage agreement supports complete submission but does not prove internal attention to every sample.','',
    '## Frozen data, prompts and controls','',
    'The 15 targets are unchanged from `next_inference_audit/proposed_pilot_selection.json`: ten constant controls and five varying intervals. Every interval has 500 actual samples (10 seconds). There are nine fixed training references per placement: seven class-covering plus two deliberately varying references. Users 1–7 supply references; users 8–9 supply targets and remain absent from the reference set. These are previously studied development users, not a new final test.','',
    'R supplies full lossless 500-character binary strings for every reference and target. D supplies fraction_ones only. T supplies fraction_ones, transition_count, max_zero_run_fraction and max_one_run_fraction. Fractions are rounded to four decimals in all feature payloads; full values remain in evaluator artifacts. Sensor knowledge, duration, reference labels/order, candidate order, system instruction and output contract are identical. The common definition block explains all representation fields in every condition. Thus D does not get a different knowledge prompt. Neither file paths, target labels, subject identifiers, source offsets nor classifier outputs appear in messages.','',
    'T-order changes only the five varying target representations; references remain chronological. Ten 50-sample blocks are permuted using the pre-existing source/start-derived seed. Preflight found one original seed produced unchanged bits because blocks repeat. Before any API call, the rule was frozen to draw from that same seeded stream until the bits differ. This guarantees changed displayed order while preserving samples, length, bit counts and within-block observations. It is a declared synthetic ordering control, never presented as newly observed transitions. No activity labels or Qwen results enter this choice. T captures run summaries, not full temporal order: changed bit order can still leave all T fields unchanged.','',
    'Request order is counterbalanced across R/D/T and controls are interspersed with seed 20261111. This is one repeat. The exact system/user prompts are stored in `../data/representation-screen/requests.jsonl`; the separate label-blind gate is in `technical_requests.jsonl`. Source samples and hashes were checked before requests.','',
    '## Activity inference results','',
    'All macro-F1 values average over the seven fixed candidate labels, including labels absent from this small panel. Balanced accuracy averages over supported true labels. Unresolved failures count as incorrect. Moving classes are Downstairs, Jogging, Upstairs and Walking.','',
    '| Condition | N | Accuracy | Macro-F1 | Moving/stationary | Mean confidence | Insufficient | Invalid/missing |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for c,v in e['conditions'].items():
        a=v['all'];lines.append(f"| {c} | {a['n']} | {pct(a['accuracy'])} | {a['macro_f1']:.4f} | {pct(a['moving_stationary_accuracy'])} | {a['mean_confidence']:.3f} | {a['insufficient_count']} | {a['n']-a['status_counts'].get('valid',0)} |")
    lines+=['','T-order is evaluated on five varying targets only; compare it to T on those same five, not to the 15-target aggregate.','',
    '| Condition | Stratum | N | Accuracy | Macro-F1 | Moving/stationary |','|---|---|---:|---:|---:|---:|']
    for c,v in e['conditions'].items():
        for s,a in v['strata'].items():
            if a:lines.append(f"| {c} | {s} | {a['n']} | {pct(a['accuracy'])} | {a['macro_f1']:.4f} | {pct(a['moving_stationary_accuracy'])} |")
    lines+=['','## Paired changes','', '| Contrast (after − before) | N | Predictions changed | Wrong → correct | Correct → wrong | Accuracy difference |','|---|---:|---:|---:|---:|---:|']
    for c,v in e['contrasts'].items():lines.append(f"| {c} | {v['paired_n']} | {v['changes']} | {v['wrong_to_correct']} | {v['correct_to_wrong']} | {100*v['accuracy_difference']:+.1f} pp |")
    lines+=['','## Fixed conventional baselines','',
    'Baseline predictions were frozen before research calls. All reference baselines use the same nine labeled observations per placement. Fixed bit predicts Walking for >50% ones, otherwise Sitting. Reference prior uses reference class frequency, class-list tie-breaking. Duration-only reduces to that prior because every observation is ten seconds. Nearest duty/T uses mean absolute distance, transition_count normalized by 499, and tied-neighbor votes divided by each class’s reference support; final ties use the fixed class order. These rules are descriptive comparison algorithms, not claims about optimal classifiers. No baseline supplies a Qwen answer.','',
    '| Baseline | Order/subset | N | Accuracy | Macro-F1 | Moving/stationary |','|---|---|---:|---:|---:|---:|']
    for order,bs in e['baselines'].items():
        for name,v in bs.items():
            for s,a in [('all',v['all'])]+list(v['strata'].items()):lines.append(f"| {name} | {order}/{s} | {a['n']} | {pct(a['accuracy'])} | {a['macro_f1']:.4f} | {pct(a['moving_stationary_accuracy'])} |")
    lines+=['','## Individual predictions','', '| Target | Placement | Subject | True class | Stratum | R | D | T | T-order |','|---|---|---:|---|---|---|---|---|---|']
    ids=list(dict.fromkeys(r['target_id'] for r in e['individual']))
    for id in sorted(ids):
        rr=[r for r in e['individual'] if r['target_id']==id];t=rr[0];cells=[]
        for c in ['R','D','T','T-order']:
            r=next((r for r in rr if r['condition']==c),None);cells.append(f"{r['predicted_activity']} ({r['confidence']})" if r else '—')
        lines.append(f"| {id} | {t['placement']} | {t['subject']} | {t['truth']} | {t['stratum']} | "+' | '.join(cells)+' |')
    lines+=['','## Order control: actual feature changes','', '| Target | Duty | Transitions before → after | Max zero run fraction | Max one run fraction | Changed fields |','|---|---:|---|---|---|---|']
    for r in e['order_features']:
        a,b=r['original'],r['disrupted'];lines.append(f"| {r['target_id']} | {a['fraction_ones']} | {a['transition_count']} → {b['transition_count']} | {a['max_zero_run_fraction']} → {b['max_zero_run_fraction']} | {a['max_one_run_fraction']} → {b['max_one_run_fraction']} | {', '.join(r['changed_features']) or 'None'} |")
    lines+=['','## Subject and placement breakdowns','', '| Condition | Group | N | Accuracy | Macro-F1 | Moving/stationary |','|---|---|---:|---:|---:|---:|']
    for c,v in e['conditions'].items():
        for name,group in [('subject',v['subjects']),('placement',v['placements'])]:
            for s,a in group.items():
                if a:lines.append(f"| {c} | {name} {s} | {a['n']} | {pct(a['accuracy'])} | {a['macro_f1']:.4f} | {pct(a['moving_stationary_accuracy'])} |")
    lines+=['','## Confidence and uncertainty','', '| Condition | Confidence correct | Confidence incorrect | Errors at confidence ≥0.8 | Insufficient / valid |','|---|---:|---:|---:|---:|']
    for c,v in e['conditions'].items():
        a=v['all'];lines.append(f"| {c} | {a['confidence_correct']:.3f} | {a['confidence_wrong']:.3f} | {a['high_confidence_errors']} | {a['insufficient_count']} / {a['status_counts'].get('valid',0)} |")
    lines+=['','Raw-input mean confidence was 0.850 despite 26.7% accuracy; D reduced it to 0.359 and T to 0.423. High-confidence errors fell from 8 under R to 1 under D and T. R declared 9/15 targets sufficient, D 0/15, and T 1/15. This is improved acknowledgment of uncertainty in this sample, not demonstrated probability calibration.','',
    'Confidence is a self-report for the exact class, not a calibrated probability established by this screen. Reliability bins are saved in the evaluation JSON. Sufficiency is not counted as correctness. Explanations were deliberately omitted from the reliable contract, so unsupported-explanation rates and claims about Qwen’s reasoning cannot be measured in this experiment.','',
    '## Interpretation and research decision','',
    'The summary below must be interpreted as a small paired development screen, not a population estimate. Constant controls span Laying, Standing, Jogging, Upstairs, Downstairs and Walking; varying targets cover Standing at the ankles and Downstairs at the right wrist. Sitting is absent from target labels. Support over all 15 targets is Downstairs=3, Jogging=2, Laying=2, Sitting=0, Standing=6, Upstairs=1, Walking=1. Multiple intervals share a person and recording. Do not use independent-window confidence intervals or treat five placements as five independent people.','',
    f"Structured features versus raw: D−R changed accuracy by {100*e['contrasts']['D-R']['accuracy_difference']:+.1f} percentage points; T−R by {100*e['contrasts']['T-R']['accuracy_difference']:+.1f}. Temporal summaries beyond duty: T−D changed accuracy by {100*e['contrasts']['T-D']['accuracy_difference']:+.1f} points. The paired table shows whether these aggregate differences reflect actual corrections or changed guesses.", '',
    f"Order disruption changed {e['contrasts']['T-order-T']['changes']}/5 predictions, with an accuracy difference of {100*e['contrasts']['T-order-T']['accuracy_difference']:+.1f} points on the same five targets. All five T payloads changed, as shown in the feature-change table; the comparison tests sensitivity to run summaries rather than proving understanding of chronology.", '',
    'The single T-over-D correction is p03 (left-ankle Standing), already correct under R. The four T-versus-R class changes are all wrong-to-wrong. The moving/stationary gain is p09: R predicted Upstairs, whereas T predicted Sitting for true Standing. The T-order change is that same p09 from Sitting to Laying, both wrong exact postures. All five control feature objects actually differ; this is not an identical-prompt contrast. However, one sample per condition cannot separate systematic feature sensitivity from sampling variability.','',
    'The fixed nearest-duty baseline equals R/T accuracy (4/15), while nearest-temporal achieves 5/15 with higher macro-F1 than Qwen. Neither establishes robust generalization: selection is tiny and concentrated. Qwen has not demonstrated an advantage over these simple permitted-reference comparisons.','',
    'Features are deterministic computations on already exposed binary observations; improvement is computational assistance, not discovery of new leakage. All durations are matched, so acquisition length cannot explain between-condition differences here. Selection of constant/varying cases and reference enrichment limits representativeness. The model sees reference labels but not evaluation labels; correctness alone does not establish a unique observable activity signature.','',
    'Recommendation: do not progress to autonomous feature-search claims on this panel. First establish cross-user, duration-controlled distinguishability in a better documented legitimate interface or additional independently collected sessions, retaining ambiguous controls. An agent cannot recover activity information that the interface does not distinguish. Even positive feature assistance would justify a narrowly preregistered replication on a richer interface, not automatic expansion or fine-tuning. A stronger follow-up needs varying examples across more activities and independent people, chronology/marginal controls, and a newly held-out split. No further calls are launched by this report.','',
    '## Reproducibility and preservation','',
    f"Preservation checks confirm {e['preserved_files']} existing data/run/report artifacts unchanged; all sources read for this experiment match their frozen hashes. Code: `../representation_experiment.py`, `../representation_report.py`, and existing `../inference_protocol_v2.py`. Inputs/manifests: `../data/representation-screen/`; raw API responses, technical gate results and complete evaluation: `../runs/representation-screen/`. These data/run directories remain ignored by Git, consistent with the repository; credentials are neither exported nor logged.", '',
    'Install `requirements-representation.txt`. Reproduction uses `representation_experiment.py metadata` (read-only endpoint metadata), then `prepare`, `gate`, and `research` only after a passed gate; existing manifests/runs refuse silent overwrites. `representation_report.py baselines` freezes baselines before research; `representation_report.py report` performs offline scoring. Re-running inference incurs fresh costs and is not part of this task.','',
    '## Confusion matrices','',f"Rows: {', '.join(CLASSES)}. Columns: same order plus INVALID_OR_MISSING.",'']
    for c,v in e['conditions'].items():lines.extend([f'### {c}','', '```json',json.dumps(v['all']['confusion_matrix']),'```',''])
    REPORT.write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['baselines','report']);a=p.parse_args()
    if a.command=='baselines':baselines()
    else:report(evaluate())
