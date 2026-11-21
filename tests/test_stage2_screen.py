from project_paths import dataset_path
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import stage2_screen as s


def test_prompt_factor_isolation_and_original_bridge():
    t=s.templates();refs=[{'activity':c,'binary_sequence':[0]*100} for c in s.CLASSES]
    target=[0,1]*50;history=[1]*400
    prompts={c:s.render(c,target,history,refs,t) for c in s.CONDITIONS}
    assert prompts['R0']==s.stage1_messages(target)
    for c in s.CONDITIONS[:-1]:
        system,user=prompts[c]
        assert system==prompts['C000'][0]
        assert json.dumps(target) in user['content']
        assert ('right pocket' in user['content'])==(c in ['C010','C111'])
        assert (json.dumps(history) in user['content'])==(c in ['C100','C111'])
        assert ('"binary_sequence"' in user['content'])==(c in ['C001','C111'])
    with pytest.raises(ValueError):s.render('C011',target,history,refs,t)
    with pytest.raises(ValueError):s.render('C000',target,history,[{'activity':'Sitting','source':'hidden'}],t)


def test_prepared_84_request_manifest_and_source_matching():
    import numpy as np
    data=s.ROOT/'data/stage2-screen'
    if not (data/'requests.jsonl').is_file() or not dataset_path().is_dir():
        pytest.skip('Private historical export and source dataset are not included')
    jobs=s.read_lines(data/'requests.jsonl');truth=s.read_lines(data/'truth.jsonl')
    obs={r['id']:r for r in s.read_lines(data/'selected_observations.jsonl')}
    assert len(jobs)==len({j['id'] for j in jobs})==84
    assert len(truth)==14
    assert {(r['subject'],r['activity']) for r in truth}=={(sub,c) for sub in [8,9] for c in s.CLASSES}
    for row in truth:
        a=np.loadtxt(dataset_path()/row['recording'],delimiter=',',skiprows=1,usecols=7,dtype=int)
        start=row['block_start_sample'];o=obs[row['id']]
        assert o['history']+o['target']==a[start:start+500].tolist()
        for job in [j for j in jobs if j['target_id']==row['id']]:
            text=json.dumps(job['messages'])
            assert row['recording'] not in text
            assert 'User '+str(row['subject']) not in text
    assert all(sum(j['condition']==c for j in jobs)==14 for c in s.CONDITIONS)
