import pytest
from project_paths import dataset_path
import json
from collections import Counter
from pathlib import Path
from e3_experiment import DATA,ROOT,CLASSES,render,read_binary,read_lines,sha

@pytest.mark.skipif(not (DATA/'references.json').is_file() or not dataset_path().is_dir(), reason="Private historical experiment fixtures are not included in the public repository")
def test_nested_disjoint_authentic_references():
    refs=json.loads((DATA/'references.json').read_text());prov=json.loads((DATA/'reference_provenance.json').read_text())
    assert refs['1']==json.loads((ROOT/'data/stage2-screen/references.json').read_text())
    for k in [0,1,5,10,20]:
        assert refs[str(k)]==refs['20'][:7*k]
        assert Counter(r['activity'] for r in refs[str(k)])==Counter({c:k for c in CLASSES})
    for c in CLASSES:
        assert {r['subject'] for r in prov[c]}==set(range(1,8))
        for i,p in enumerate(prov[c]):
            path=dataset_path()/p['source'];a,_=read_binary(path)
            assert sha(path)==p['sha256']
            assert a[p['start_sample']:p['start_sample']+100,1].astype(int).tolist()==refs['20'][7*i+CLASSES.index(c)]['binary_sequence']

@pytest.mark.skipif(not (DATA/'requests.jsonl').is_file() or not (ROOT/'data/stage2-screen/requests.jsonl').is_file(), reason="Private historical experiment fixtures are not included in the public repository")
def test_targets_and_bridge_and_information_boundary():
    obs=read_lines(DATA/'selected_observations.jsonl');assert obs==read_lines(ROOT/'data/stage2-screen/selected_observations.jsonl')
    jobs=read_lines(DATA/'requests.jsonl');assert len(jobs)==86 and len({j['id'] for j in jobs})==86
    prior={j['target_id']:j['messages'] for j in read_lines(ROOT/'data/stage2-screen/requests.jsonl') if j['condition']=='C111'}
    for j in jobs:
        if j['condition']=='E2-bridge':assert j['messages']==prior[j['target_id']]
        content=json.dumps(j['messages'])
        assert 'User 8' not in content and '.csv' not in content and j['target_id'] not in content
    refs=json.loads((DATA/'references.json').read_text())
    for o in obs:
        a=render(o,refs['1']);b=render(o,refs['20'])
        assert a[0]==b[0]
        assert a[1]['content'].replace(json.dumps(refs['1']),'REF')==b[1]['content'].replace(json.dumps(refs['20']),'REF')
