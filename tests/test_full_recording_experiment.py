import pytest
import json
from full_recording_experiment import DATA,CONDITIONS,read_lines,technical,unpack

@pytest.mark.skipif(not (DATA/'requests.jsonl').is_file() or not (DATA/'manifest.json').is_file(), reason="Private historical experiment fixtures are not included in the public repository")
def test_frozen_grid_and_provider_limits():
    jobs=read_lines(DATA/'requests.jsonl');meta=json.loads((DATA/'manifest.json').read_text())
    assert len(jobs)==70 and len({j['id'] for j in jobs})==70
    assert jobs[0]['condition']=='C4'
    assert meta['settings']['provider']=={'only':['deepinfra/fp8'],'allow_fallbacks':False,'require_parameters':True}
    for c in CONDITIONS:
        js=[j for j in jobs if j['condition']==c];assert len(js)==14
        for j in js:
            refs,target=unpack(j['messages']);assert len(refs)==7
            assert j['local_content_tokens']+1624<meta['provider']['context_length']
            assert 'activity' not in target
            if c in ['C1','C2']:assert len(target['binary_sequence'])==100
            if c=='C5':assert len(target['binary_sequence'])==500
            if c in ['C1','C3']:assert all(len(r['binary_sequence'])==100 for r in refs)

def test_technical_gate_rejects_provider_switch_or_missing_input():
    meta={'settings':{'model':'mock-model'},'provider':{'context_length':262144}}
    r={'http_status':200,'returned_provider':'DeepInfra','returned_model':meta['settings']['model'],'usage':{'prompt_tokens':100017},'local_content_tokens':100000}
    assert technical(r,meta)
    assert not technical(r|{'returned_provider':'Other'},meta)
    assert not technical(r|{'usage':{'prompt_tokens':50000}},meta)
    assert not technical(r|{'usage':None},meta)
